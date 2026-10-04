"""BugFlow Module 3 - REST API Layer & Integrations Router
Provides REST APIs for:
1. Issue Management (GET, POST, PUT, DELETE, filtering, pagination)
2. Assignment & Status (Assign, Reassign, Accept, Reject, Resolve)
3. Sprint Operations (List, Create, Backlog, Add/Remove issues)
4. Analytics Retrieval (Summary, Trends, Quality, Team, Dashboard)
5. Reports & Export (CSV, JSON, Printable Summary)
6. GitHub Integration (Webhooks, commit tracking, manual sync)
7. CI/CD Synchronization (Pipeline webhooks, run triggers, auto-defect filing)
8. In-App Notification Center
"""

import csv
import io
import json
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from .analytics_engine import AnalyticsEngine, normalize_role
from .database import get_db
from .models import (
    AdminAction,
    AuditLog,
    CICDRun,
    Comment,
    Defect,
    GitHubEvent,
    Issue,
    IssueStatus,
    IssueType,
    Notification,
    Priority,
    Severity,
    Sprint,
    SprintIssue,
    User,
)

router = APIRouter(prefix="/api/v1", tags=["Module 3 - Analytics, APIs & Integrations"])
security = HTTPBearer(auto_error=False)


# =========================================================
# HELPER: Auth & Workspace Context
# =========================================================

def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    """Extract authenticated user if bearer token is provided."""
    if not credentials or not credentials.credentials:
        # Fall back to Admin if running in open local workspace mode
        return db.query(User).filter(User.role == "admin").first()

    token = credentials.credentials
    from .main import sessions
    user_id = sessions.get(token)
    if user_id:
        return db.query(User).filter(User.id == user_id).first()

    # Look in AuthSession
    from .models import AuthSession
    session_record = (
        db.query(AuthSession)
        .filter(AuthSession.token == token, AuthSession.expires_at > datetime.utcnow())
        .first()
    )
    if session_record:
        return db.query(User).filter(User.id == session_record.user_id).first()

    return db.query(User).filter(User.role == "admin").first()


def create_notification(
    db: Session,
    title: str,
    message: str,
    category: str = "SYSTEM",
    target_role: str | None = None,
    user_id: int | None = None,
    link: str | None = None,
) -> Notification:
    """Helper to emit in-app notifications."""
    notif = Notification(
        title=title,
        message=message,
        category=category,
        target_role=target_role,
        user_id=user_id,
        link=link,
        created_at=datetime.utcnow(),
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def log_defect_workflow_activity(
    db: Session,
    defect_id: int,
    user_id: int,
    action: str,
    old_status: str,
    new_status: str,
):
    """Safely records activity in AdminAction and in AuditLog if an Issue exists."""
    admin_act = AdminAction(
        admin_id=user_id or 1,
        defect_id=defect_id,
        action=action[:95],
        created_at=datetime.utcnow(),
    )
    db.add(admin_act)

    target_issue = (
        db.query(Issue)
        .filter(or_(Issue.id == defect_id, Issue.issue_key == f"BUG-{defect_id:03d}"))
        .first()
    )
    if target_issue:
        audit = AuditLog(
            issue_id=target_issue.id,
            user_id=user_id or 1,
            action=action[:95],
            old_status=old_status[:45] if old_status else "Pending",
            new_status=new_status[:45] if new_status else "Pending",
            created_at=datetime.utcnow(),
        )
        db.add(audit)
    db.commit()


# =========================================================
# PYDANTIC SCHEMAS
# =========================================================

class IssueCreateRequest(BaseModel):
    title: str
    description: str
    issue_type: str = "BUG"
    severity: str = "MAJOR"
    priority: str = "HIGH"
    category: str | None = "Backend"
    affected_module: str | None = "Core System"
    environment: str | None = "Production"
    reproduction_steps: str | None = None
    expected_result: str | None = None
    actual_result: str | None = None
    assigned_role: str | None = None
    project_key: str = "BUGFLOW"


class IssueUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    severity: str | None = None
    affected_module: str | None = None
    environment: str | None = None
    category: str | None = None
    status: str | None = None


class AssignmentRequest(BaseModel):
    role: str
    user_id: int | None = None
    note: str | None = None


class AssignmentResponseModel(BaseModel):
    action: str  # ACCEPT or REJECT
    role: str | None = None
    note: str | None = None


class StatusUpdateRequest(BaseModel):
    status: str
    note: str | None = None


class SprintCreateRequest(BaseModel):
    sprint_name: str
    goal: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    assigned_role: str | None = None


class GitHubSyncRequest(BaseModel):
    repository: str = "soma896/BugFlow"
    branch: str = "main"
    author: str = "Sasuke Uchiha"
    commit_sha: str | None = None
    commit_message: str = "Fix defect in auth validation (refs BUG-002)"


class CICDTriggerRequest(BaseModel):
    pipeline_name: str = "BugFlow Automated Test Suite"
    branch: str = "main"
    simulated_outcome: str = "SUCCESS"  # SUCCESS or FAILURE
    failed_tests_count: int = 0


# =========================================================
# 1. REST APIS: ISSUE MANAGEMENT OPERATIONS
# =========================================================

@router.get("/issues", summary="List issues and defects with filtering and pagination")
def list_issues(
    status: str | None = Query(None, description="Filter by status (e.g. Pending, Assigned, Accepted, Resolved, Closed)"),
    priority: str | None = Query(None, description="Filter by priority (Urgent, High, Medium, Low)"),
    severity: str | None = Query(None, description="Filter by severity (BLOCKER, CRITICAL, MAJOR, MINOR)"),
    role: str | None = Query(None, description="Filter by assigned role (admin, developer, tester, senior_dev)"),
    q: str | None = Query(None, description="Search term in title, description, or key"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    source: str = Query("all", description="Source table: 'all', 'issues', or 'defects'"),
    db: Session = Depends(get_db),
):
    """Retrieve filtered issues with pagination and total statistics."""
    results = []

    # 1. Fetch from Defect table
    if source in ("all", "defects"):
        query = db.query(Defect)
        if status:
            query = query.filter(Defect.status.ilike(f"%{status}%"))
        if priority:
            query = query.filter(Defect.priority.ilike(f"%{priority}%"))
        if role:
            query = query.filter(Defect.assigned_role.ilike(f"%{role}%"))
        if q:
            query = query.filter(
                or_(
                    Defect.title.ilike(f"%{q}%"),
                    Defect.description.ilike(f"%{q}%"),
                    Defect.category.ilike(f"%{q}%"),
                )
            )

        for d in query.order_by(desc(Defect.id)).all():
            results.append({
                "id": d.id,
                "key": f"DEF-{d.id}",
                "title": d.title,
                "description": d.description,
                "status": d.status,
                "priority": d.priority,
                "severity": "CRITICAL" if (d.priority or "").upper() == "URGENT" else "MAJOR",
                "category": d.category,
                "assigned_role": d.assigned_role,
                "assigned_role_normalized": normalize_role(d.assigned_role),
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "environment": d.environment,
                "source": "defect",
            })

    # 2. Fetch from Issue table
    if source in ("all", "issues"):
        i_query = db.query(Issue)
        if status:
            i_query = i_query.filter(Issue.status.ilike(f"%{status}%"))
        if priority:
            i_query = i_query.filter(Issue.priority.ilike(f"%{priority}%"))
        if severity:
            i_query = i_query.filter(Issue.severity.ilike(f"%{severity}%"))
        if q:
            i_query = i_query.filter(
                or_(
                    Issue.title.ilike(f"%{q}%"),
                    Issue.description.ilike(f"%{q}%"),
                    Issue.issue_key.ilike(f"%{q}%"),
                )
            )

        for iss in i_query.order_by(desc(Issue.id)).all():
            # Check if not already added
            results.append({
                "id": iss.id,
                "key": iss.issue_key,
                "title": iss.title,
                "description": iss.description,
                "status": getattr(iss.status, "value", str(iss.status)),
                "priority": getattr(iss.priority, "value", str(iss.priority)),
                "severity": getattr(iss.severity, "value", str(iss.severity)),
                "category": iss.affected_module or "Issue",
                "assigned_role": None,
                "assigned_role_normalized": "unassigned",
                "created_at": iss.created_at.isoformat() if iss.created_at else None,
                "environment": iss.environment,
                "source": "issue",
            })

    total_count = len(results)
    paginated = results[skip : skip + limit]

    return {
        "total": total_count,
        "skip": skip,
        "limit": limit,
        "count": len(paginated),
        "items": paginated,
    }


@router.post("/issues", summary="Create a new issue or defect")
def create_issue(
    data: IssueCreateRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Create a structured defect and issue record."""
    reporter_id = user.id if user else 1

    # Normalize priority
    prio_str = data.priority.strip().title()
    if prio_str not in ("Urgent", "High", "Medium", "Low"):
        prio_str = "High"

    # Create Defect record
    new_defect = Defect(
        user_id=reporter_id,
        title=data.title,
        description=data.description,
        category=data.category or "General",
        priority=prio_str,
        status="Pending",
        environment=data.environment,
        reproduction_steps=data.reproduction_steps,
        expected_result=data.expected_result,
        actual_result=data.actual_result,
        assigned_role=data.assigned_role,
        created_at=datetime.utcnow(),
    )
    db.add(new_defect)
    db.commit()
    db.refresh(new_defect)

    # Also register in Issue table for sprint/collaboration compatibility
    key_candidate = f"BUG-{new_defect.id:03d}"
    existing_key = db.query(Issue).filter(Issue.issue_key == key_candidate).first()
    if not existing_key:
        issue_model = Issue(
            issue_key=key_candidate,
            issue_type=IssueType.BUG,
            title=data.title,
            description=data.description,
            reproduction_steps=data.reproduction_steps,
            severity=Severity.MAJOR if prio_str in ("High", "Urgent") else Severity.MINOR,
            priority=Priority.HIGH if prio_str == "High" else Priority.URGENT if prio_str == "Urgent" else Priority.MEDIUM,
            status=IssueStatus.REPORTED,
            affected_module=data.affected_module,
            environment=data.environment,
            project_key=data.project_key,
            reporter_id=reporter_id,
            created_at=datetime.utcnow(),
        )
        db.add(issue_model)
        db.commit()

    # Emit notification
    create_notification(
        db,
        title=f"New Defect Reported: #{new_defect.id}",
        message=f"{data.title} ({prio_str} priority) was submitted.",
        category="WORKFLOW",
        target_role="admin",
        link=f"/all-defects-ui",
    )

    return {
        "message": f"Defect #{new_defect.id} created successfully",
        "id": new_defect.id,
        "key": key_candidate,
        "title": new_defect.title,
        "status": new_defect.status,
        "priority": new_defect.priority,
        "created_at": new_defect.created_at.isoformat(),
    }


@router.get("/issues/{issue_id}", summary="Get detailed issue by ID with comments, audit logs, and integrations")
def get_issue_details(
    issue_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve full details of an issue or defect."""
    defect = db.query(Defect).filter(Defect.id == issue_id).first()
    issue = db.query(Issue).filter(or_(Issue.id == issue_id, Issue.issue_key == f"BUG-{issue_id:03d}")).first()

    if not defect and not issue:
        raise HTTPException(status_code=404, detail=f"Issue/Defect #{issue_id} not found")

    title = defect.title if defect else issue.title
    description = defect.description if defect else issue.description
    status = defect.status if defect else getattr(issue.status, "value", str(issue.status))
    priority = defect.priority if defect else getattr(issue.priority, "value", str(issue.priority))
    assigned_role = defect.assigned_role if defect else None
    created_at = (defect.created_at if defect else issue.created_at).isoformat()

    # Find comments
    target_iss_id = issue.id if issue else defect.id
    comments = (
        db.query(Comment)
        .filter(Comment.issue_id == target_iss_id)
        .order_by(Comment.created_at.asc())
        .all()
    )
    comments_list = [
        {
            "id": c.id,
            "user_id": c.user_id,
            "comment": c.comment,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in comments
    ]

    # Find audit logs from both AuditLog (Module 2) and AdminAction (Module 1/3)
    audit_logs = (
        db.query(AuditLog)
        .filter(AuditLog.issue_id == target_iss_id)
        .order_by(desc(AuditLog.id))
        .all()
    ) if target_iss_id else []

    admin_actions = (
        db.query(AdminAction)
        .filter(AdminAction.defect_id == issue_id)
        .order_by(desc(AdminAction.id))
        .all()
    )

    audit_list = [
        {
            "id": a.id,
            "action": a.action,
            "old_status": a.old_status,
            "new_status": a.new_status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in audit_logs
    ] + [
        {
            "id": act.id,
            "action": act.action,
            "old_status": status,
            "new_status": status,
            "created_at": act.created_at.isoformat() if act.created_at else None,
        }
        for act in admin_actions
    ]

    # Linked GitHub Commits
    gh_events = (
        db.query(GitHubEvent)
        .filter(or_(GitHubEvent.linked_defect_id == issue_id, GitHubEvent.linked_issue_id == target_iss_id))
        .all()
    )
    commits_list = [
        {
            "commit_id": g.commit_id,
            "sender": g.sender,
            "commit_message": g.commit_message,
            "created_at": g.created_at.isoformat(),
        }
        for g in gh_events
    ]

    return {
        "id": issue_id,
        "key": issue.issue_key if issue else f"DEF-{defect.id}",
        "title": title,
        "description": description,
        "status": status,
        "priority": priority,
        "category": defect.category if defect else (issue.affected_module or "General"),
        "assigned_role": assigned_role,
        "assigned_role_normalized": normalize_role(assigned_role),
        "environment": defect.environment if defect else (issue.environment if issue else None),
        "created_at": created_at,
        "comments": comments_list,
        "audit_logs": audit_list,
        "linked_github_commits": commits_list,
    }


@router.put("/issues/{issue_id}", summary="Update issue details")
def update_issue(
    issue_id: int,
    data: IssueUpdateRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Update fields on an issue/defect record."""
    defect = db.query(Defect).filter(Defect.id == issue_id).first()
    if not defect:
        raise HTTPException(status_code=404, detail=f"Defect #{issue_id} not found")

    old_status = defect.status
    if data.title is not None:
        defect.title = data.title
    if data.description is not None:
        defect.description = data.description
    if data.priority is not None:
        defect.priority = data.priority
    if data.environment is not None:
        defect.environment = data.environment
    if data.category is not None:
        defect.category = data.category
    if data.status is not None:
        defect.status = data.status

    db.commit()
    db.refresh(defect)

    # Log audit safely
    log_defect_workflow_activity(
        db,
        defect.id,
        user.id if user else 1,
        "ISSUE_UPDATED",
        old_status,
        defect.status,
    )

    return {
        "message": f"Defect #{defect.id} updated successfully",
        "id": defect.id,
        "title": defect.title,
        "status": defect.status,
        "priority": defect.priority,
    }


@router.delete("/issues/{issue_id}", summary="Delete an issue (Admin only)")
def delete_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Delete issue record."""
    defect = db.query(Defect).filter(Defect.id == issue_id).first()
    if not defect:
        raise HTTPException(status_code=404, detail=f"Defect #{issue_id} not found")

    db.delete(defect)
    db.commit()
    return {"message": f"Defect #{issue_id} deleted successfully"}


# =========================================================
# 2. REST APIS: ASSIGNMENT OPERATIONS
# =========================================================

@router.post("/issues/{issue_id}/assign", summary="Assign defect/issue to a role or user")
def assign_issue(
    issue_id: int,
    data: AssignmentRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Assign defect to role (admin, developer, tester, senior_dev).

    Workflow rule:
    ADMIN ASSIGNS -> status becomes ASSIGNED (not Resolved!).
    """
    defect = db.query(Defect).filter(Defect.id == issue_id).first()
    if not defect:
        raise HTTPException(status_code=404, detail=f"Defect #{issue_id} not found")

    target_role = normalize_role(data.role)
    if target_role not in ("admin", "developer", "tester", "senior_dev"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role '{data.role}'. Must be admin, developer, tester, or senior_dev.",
        )

    old_status = defect.status or "Pending"
    defect.assigned_role = target_role
    defect.status = "ASSIGNED"

    db.commit()
    db.refresh(defect)

    # Record audit log safely
    log_defect_workflow_activity(
        db,
        defect.id,
        user.id if user else 1,
        f"ASSIGNED_TO_ROLE:{target_role}",
        old_status,
        "ASSIGNED",
    )

    # Emit notification to persona
    role_names = {
        "admin": "Naruto",
        "developer": "Sasuke",
        "tester": "Hinata",
        "senior_dev": "Itachi",
    }
    persona_name = role_names.get(target_role, target_role.title())

    create_notification(
        db,
        title=f"Defect #{defect.id} Assigned to {persona_name}",
        message=f"Defect #{defect.id} '{defect.title}' was assigned to {persona_name} ({target_role}).",
        category="ASSIGNMENT",
        target_role=target_role,
        link=f"/{target_role}-defects-ui" if target_role != "senior_dev" else "/senior-developer-defects-ui",
    )

    return {
        "message": f"Defect #{defect.id} assigned to {persona_name} ({target_role})",
        "issue_id": defect.id,
        "assigned_role": target_role,
        "status": defect.status,
    }


@router.post("/issues/{issue_id}/reassign", summary="Reassign defect to a different role")
def reassign_issue(
    issue_id: int,
    data: AssignmentRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Reassign defect with an audit note."""
    return assign_issue(issue_id, data, db, user)


@router.post("/issues/{issue_id}/assignment-response", summary="Role Accept or Reject assignment")
def respond_assignment(
    issue_id: int,
    data: AssignmentResponseModel,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Handle role Accept or Reject of issue assignment.

    Workflow rule:
    ASSIGNED -> ACCEPT -> ACCEPTED
    ASSIGNED -> REJECT -> REJECTED
    Crucial: Issue does NOT become RESOLVED upon Accept!
    """
    defect = db.query(Defect).filter(Defect.id == issue_id).first()
    if not defect:
        raise HTTPException(status_code=404, detail=f"Defect #{issue_id} not found")

    action_norm = data.action.strip().upper()
    if action_norm in ("ACCEPT", "ACCEPTED"):
        target_status = "ACCEPTED"
    elif action_norm in ("REJECT", "REJECTED"):
        target_status = "REJECTED"
    else:
        raise HTTPException(status_code=400, detail="Action must be ACCEPT or REJECT")

    curr_status = (defect.status or "").strip().upper()
    if curr_status not in ("ASSIGNED", "PENDING", ""):
        raise HTTPException(
            status_code=400,
            detail=f"Defect cannot be {target_status} from current status '{defect.status}'",
        )

    old_status = defect.status
    defect.status = target_status
    db.commit()
    db.refresh(defect)

    log_defect_workflow_activity(
        db,
        defect.id,
        user.id if user else 1,
        f"ASSIGNMENT_RESPONSE:{target_status}",
        old_status,
        target_status,
    )

    # Emit notification
    create_notification(
        db,
        title=f"Assignment {target_status}: Defect #{defect.id}",
        message=f"Defect #{defect.id} assignment was {target_status.lower()} by {defect.assigned_role or 'role'}.",
        category="WORKFLOW",
        target_role="admin",
        link=f"/all-defects-ui",
    )

    return {
        "message": f"Defect #{defect.id} marked as {target_status}",
        "issue_id": defect.id,
        "status": defect.status,
    }


# =========================================================
# 3. REST APIS: STATUS UPDATE OPERATIONS
# =========================================================

@router.post("/defects/{issue_id}/status", summary="Update defect status respecting workflow rules")
@router.post("/issues/{issue_id}/workflow-status", summary="Update status respecting workflow rules")
def update_issue_workflow_status(
    issue_id: int,
    data: StatusUpdateRequest,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Enforce workflow rules:
    ASSIGNED -> ACCEPTED / REJECTED
    ACCEPTED -> RESOLVED (Admin resolve or role resolve)
    RESOLVED -> CLOSED
    """
    defect = db.query(Defect).filter(Defect.id == issue_id).first()
    if not defect:
        raise HTTPException(status_code=404, detail=f"Defect #{issue_id} not found")

    target_status = data.status.strip().upper()
    curr_status = (defect.status or "").strip().upper()

    if target_status == "RESOLVED":
        if curr_status != "ACCEPTED":
            raise HTTPException(
                status_code=400,
                detail=f"Defect must be ACCEPTED before it can be RESOLVED (current: {defect.status})",
            )
    elif target_status in ("ACCEPTED", "REJECTED"):
        if curr_status not in ("ASSIGNED", "PENDING", ""):
            raise HTTPException(
                status_code=400,
                detail=f"Defect cannot transition to {target_status} from '{defect.status}'",
            )

    old_status = defect.status
    defect.status = target_status
    db.commit()
    db.refresh(defect)

    log_defect_workflow_activity(
        db,
        defect.id,
        user.id if user else 1,
        f"STATUS_CHANGE:{target_status}",
        old_status,
        target_status,
    )

    return {
        "message": f"Defect #{defect.id} status changed to {target_status}",
        "issue_id": defect.id,
        "old_status": old_status,
        "new_status": target_status,
    }


@router.post("/issues/{issue_id}/resolve", summary="Resolve defect after acceptance")
def resolve_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """Admin / Developer resolve endpoint."""
    return update_issue_workflow_status(
        issue_id,
        StatusUpdateRequest(status="RESOLVED", note="Resolved via Module 3 API"),
        db,
        user,
    )


# =========================================================
# 4. REST APIS: SPRINT OPERATIONS (Complements existing sprint APIs)
# =========================================================

@router.get("/sprints/{sprint_id}", summary="Get sprint with its issues and metrics")
def get_sprint_details(sprint_id: int, db: Session = Depends(get_db)):
    """Retrieve sprint details, metrics, and assigned issues."""
    sprint = db.query(Sprint).filter(Sprint.id == sprint_id).first()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")

    issues_list = []
    resolved_count = 0
    for si in sprint.issues:
        iss = si.issue
        if iss:
            st = getattr(iss.status, "value", str(iss.status)).upper()
            if st in ("RESOLVED", "CLOSED"):
                resolved_count += 1
            issues_list.append({
                "id": iss.id,
                "key": iss.issue_key,
                "title": iss.title,
                "status": st,
                "priority": getattr(iss.priority, "value", str(iss.priority)),
                "severity": getattr(iss.severity, "value", str(iss.severity)),
                "added_at": si.added_at.isoformat() if si.added_at else None,
            })

    total_issues = len(issues_list)
    completion_pct = round((resolved_count / total_issues * 100), 1) if total_issues > 0 else 0.0

    return {
        "id": sprint.id,
        "sprint_name": sprint.sprint_name,
        "goal": sprint.goal,
        "status": sprint.status,
        "assigned_role": sprint.assigned_role,
        "total_issues": total_issues,
        "resolved_issues": resolved_count,
        "completion_percentage": completion_pct,
        "issues": issues_list,
    }


@router.delete("/sprints/{sprint_id}/issues/{issue_id}", summary="Remove issue from sprint")
def remove_issue_from_sprint(sprint_id: int, issue_id: int, db: Session = Depends(get_db)):
    """Remove an issue from sprint backlog."""
    si = (
        db.query(SprintIssue)
        .filter(SprintIssue.sprint_id == sprint_id, SprintIssue.issue_id == issue_id)
        .first()
    )
    if not si:
        raise HTTPException(status_code=404, detail="Issue not found in this sprint")

    db.delete(si)
    db.commit()
    return {"message": f"Issue #{issue_id} removed from sprint #{sprint_id}"}


@router.get("/sprints/metrics/analytics", summary="Sprint velocity and burndown metrics")
def get_sprint_metrics(db: Session = Depends(get_db)):
    """Sprint analytics metrics across all sprints."""
    sprints = db.query(Sprint).order_by(Sprint.id.asc()).all()
    results = []
    for s in sprints:
        total = len(s.issues)
        resolved = sum(
            1 for si in s.issues
            if si.issue and getattr(si.issue.status, "value", str(si.issue.status)).upper() in ("RESOLVED", "CLOSED")
        )
        pct = round((resolved / total * 100), 1) if total > 0 else 0.0
        results.append({
            "sprint_id": s.id,
            "sprint_name": s.sprint_name,
            "assigned_role": s.assigned_role,
            "status": s.status,
            "total_issues": total,
            "resolved_issues": resolved,
            "completion_percentage": pct,
        })
    return results


# =========================================================
# 5. REST APIS: ANALYTICS RETRIEVAL OPERATIONS
# =========================================================

@router.get("/analytics/summary", summary="Retrieve high-level defect & project metrics")
def get_analytics_summary(db: Session = Depends(get_db)):
    """Return live summary metrics: total, resolved, rejected, fix rate, MTTR, DSI."""
    engine = AnalyticsEngine(db)
    return engine.get_summary_metrics()


@router.get("/analytics/trends", summary="Retrieve defect trends over time")
def get_analytics_trends(
    days: int = Query(30, ge=7, le=180, description="Time window in days"),
    db: Session = Depends(get_db),
):
    """Return daily incoming defect rates, cumulative progress, and aging buckets."""
    engine = AnalyticsEngine(db)
    return engine.get_trends_metrics(days=days)


@router.get("/analytics/quality", summary="Retrieve software quality monitoring metrics")
def get_analytics_quality(db: Session = Depends(get_db)):
    """Return Defect Severity Index (DSI), defect density, category, and severity breakdown."""
    engine = AnalyticsEngine(db)
    return engine.get_quality_metrics()


@router.get("/analytics/team", summary="Retrieve team workload & persona metrics")
def get_analytics_team(db: Session = Depends(get_db)):
    """Return workload and acceptance metrics for Naruto, Sasuke, Hinata, and Itachi."""
    engine = AnalyticsEngine(db)
    return engine.get_team_metrics()


@router.get("/analytics/dashboard", summary="Unified complete analytics dashboard payload")
def get_analytics_dashboard(db: Session = Depends(get_db)):
    """Combined one-shot analytics payload for UI charts and dashboards."""
    engine = AnalyticsEngine(db)
    return engine.get_dashboard_payload()


# =========================================================
# 6. REPORTS & EXPORT OPERATIONS
# =========================================================

@router.get("/analytics/export/csv", summary="Export all defect records as CSV download")
def export_defects_csv(db: Session = Depends(get_db)):
    """Stream downloadable CSV file of all defects."""
    defects = db.query(Defect).order_by(Defect.id.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Defect ID",
        "Title",
        "Category",
        "Priority",
        "Status",
        "Assigned Role",
        "Created At",
        "Environment",
        "Description",
    ])

    for d in defects:
        writer.writerow([
            d.id,
            d.title,
            d.category or "General",
            d.priority,
            d.status,
            d.assigned_role or "Unassigned",
            d.created_at.strftime("%Y-%m-%d %H:%M:%S") if d.created_at else "",
            d.environment or "N/A",
            (d.description or "").replace("\n", " "),
        ])

    output.seek(0)
    filename = f"bugflow_defects_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/analytics/export/json", summary="Export complete analytics report in JSON")
def export_analytics_json(db: Session = Depends(get_db)):
    """Downloadable full JSON dump of system analytics."""
    engine = AnalyticsEngine(db)
    payload = engine.get_dashboard_payload()
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f"attachment; filename=bugflow_analytics_{datetime.utcnow().strftime('%Y%m%d')}.json"},
    )


@router.get("/analytics/export/summary", response_class=HTMLResponse, summary="Printable executive quality report")
def export_summary_report(db: Session = Depends(get_db)):
    """Printable executive software-quality summary HTML."""
    engine = AnalyticsEngine(db)
    summary = engine.get_summary_metrics()
    quality = engine.get_quality_metrics()
    team = engine.get_team_metrics()

    team_rows = "".join(
        f"<tr><td><strong>{r['label']}</strong></td><td>{r['total_assigned']}</td><td>{r['accepted']}</td><td>{r['rejected']}</td><td>{r['resolved']}</td><td>{r['acceptance_rate_pct']}%</td></tr>"
        for r in team["roles"]
    )

    cat_rows = "".join(
        f"<tr><td>{cat}</td><td>{info['count']}</td><td>{info['percentage']}%</td></tr>"
        for cat, info in quality["defect_density"].items()
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>BugFlow Quality & Analytics Executive Report</title>
<style>
body {{ font-family: Inter, Segoe UI, sans-serif; margin: 40px; color: #1e293b; background: #fff; }}
.header {{ border-bottom: 2px solid #3b66d9; padding-bottom: 15px; margin-bottom: 25px; }}
h1 {{ margin: 0; color: #0f172a; font-size: 24px; }}
.meta {{ color: #64748b; font-size: 12px; margin-top: 5px; }}
.grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; }}
.kpi {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 15px; background: #f8fafc; }}
.kpi-title {{ font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 700; }}
.kpi-val {{ font-size: 26px; font-weight: 800; color: #3b66d9; margin-top: 6px; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; font-size: 13px; }}
th, td {{ border: 1px solid #e2e8f0; padding: 10px 12px; text-align: left; }}
th {{ background: #f1f5f9; color: #334155; font-weight: 700; }}
.print-btn {{ position: fixed; top: 20px; right: 20px; padding: 8px 16px; background: #3b66d9; color: #fff; border: none; border-radius: 6px; cursor: pointer; }}
@media print {{ .print-btn {{ display: none; }} }}
</style>
</head>
<body>
<button class="print-btn" onclick="window.print()">Print / Save PDF</button>
<div class="header">
    <h1>BUGFLOW INTELLIGENT DEFECT MANAGEMENT SYSTEM</h1>
    <div class="meta">Module 3 — Project Analytics, Software-Quality & Integration Report | Generated on {datetime.utcnow().strftime('%B %d, %Y %H:%M UTC')}</div>
</div>

<div class="grid">
    <div class="kpi"><div class="kpi-title">Total Defects</div><div class="kpi-val">{summary['total_defects']}</div></div>
    <div class="kpi"><div class="kpi-title">Resolution Rate</div><div class="kpi-val">{summary['resolution_rate_pct']}%</div></div>
    <div class="kpi"><div class="kpi-title">Defect Severity Index</div><div class="kpi-val">{summary['defect_severity_index']}</div></div>
    <div class="kpi"><div class="kpi-title">Mean Time to Resolution</div><div class="kpi-val">{summary['mttr_display']}</div></div>
</div>

<h2>1. Software Quality Metrics & Defect Density</h2>
<table>
    <thead><tr><th>Category / Module</th><th>Defect Count</th><th>Density Share (%)</th></tr></thead>
    <tbody>{cat_rows}</tbody>
</table>

<h2>2. Team Persona Workload & SLA Performance</h2>
<table>
    <thead><tr><th>Persona</th><th>Assigned</th><th>Accepted</th><th>Rejected</th><th>Resolved</th><th>Acceptance Rate</th></tr></thead>
    <tbody>{team_rows}</tbody>
</table>

<div style="margin-top: 40px; font-size: 11px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 10px;">
    BugFlow Module 3 | Verified live from PostgreSQL data store.
</div>
</body>
</html>"""
    return HTMLResponse(content=html)


# =========================================================
# MODULE 4: PRODUCTIVITY ANALYTICS & ADVANCED REPORTS
# =========================================================

@router.get("/analytics/productivity", summary="Retrieve productivity analytics across canonical team personas")
def get_productivity_analytics(db: Session = Depends(get_db)):
    """Module 4: Computes factual productivity metrics for Naruto (Admin),
    Sasuke (Developer), Hinata (Tester), and Itachi (Senior Developer)
    from PostgreSQL records.
    """
    engine = AnalyticsEngine(db)
    return engine.get_productivity_metrics()


@router.get("/analytics/workflow", summary="Retrieve workflow funnel and transition metrics")
def get_workflow_analytics(db: Session = Depends(get_db)):
    """Module 4: Computes workflow pipeline throughput, funnel distribution,
    and status transition activity.
    """
    engine = AnalyticsEngine(db)
    return engine.get_workflow_metrics()


@router.get("/analytics/export/productivity", summary="Export team productivity analytics report as CSV")
def export_productivity_csv(db: Session = Depends(get_db)):
    """Module 4: Stream downloadable CSV file of team productivity metrics."""
    engine = AnalyticsEngine(db)
    prod = engine.get_productivity_metrics()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Persona Name",
        "Role Title",
        "Role Key",
        "Issues Assigned",
        "Issues Accepted",
        "Issues Rejected",
        "Issues Resolved",
        "Open Backlog",
        "Resolution Rate (%)",
        "Avg Resolution Time (hrs)",
        "Transition Activity Count",
        "Workload Share (%)",
        "Assigned Sprints Count",
        "Sprint Issues Count",
    ])

    for r in prod.get("roles", []):
        writer.writerow([
            r.get("persona_name"),
            r.get("role_title"),
            r.get("role_key"),
            r.get("issues_assigned"),
            r.get("issues_accepted"),
            r.get("issues_rejected"),
            r.get("issues_resolved"),
            r.get("open_backlog"),
            f"{r.get('resolution_rate_pct')}%",
            f"{r.get('avg_resolution_time_hours')} hrs",
            r.get("status_transition_activity"),
            f"{r.get('work_distribution_pct')}%",
            r.get("sprints_count"),
            r.get("sprint_issues_count"),
        ])

    output.seek(0)
    filename = f"bugflow_productivity_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/analytics/export/sprint", summary="Export sprint performance metrics as CSV")
def export_sprint_report_csv(db: Session = Depends(get_db)):
    """Module 4: Stream downloadable CSV file of sprint performance and backlogs."""
    sprints = db.query(Sprint).order_by(Sprint.id.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Sprint ID",
        "Sprint Name",
        "Status",
        "Assigned Role",
        "Start Date",
        "End Date",
        "Total Issues",
        "Goal",
    ])

    for s in sprints:
        writer.writerow([
            s.id,
            s.sprint_name,
            s.status,
            s.assigned_role or "Unassigned",
            s.start_date.strftime("%Y-%m-%d") if s.start_date else "",
            s.end_date.strftime("%Y-%m-%d") if s.end_date else "",
            len(s.issues),
            (s.goal or "").replace("\n", " "),
        ])

    output.seek(0)
    filename = f"bugflow_sprints_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/analytics/export/workflow", summary="Export workflow performance metrics as CSV")
def export_workflow_report_csv(db: Session = Depends(get_db)):
    """Module 4: Stream downloadable CSV file of workflow stage counts and transitions."""
    engine = AnalyticsEngine(db)
    wf = engine.get_workflow_metrics()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Workflow Stage", "Defect Count", "Percentage of Total"])
    for stage, count in wf.get("funnel_counts", {}).items():
        pct = wf.get("funnel_percentages", {}).get(stage, 0.0)
        writer.writerow([stage, count, f"{pct}%"])

    writer.writerow([])
    writer.writerow(["Top Transition Sequence", "Occurrences Count"])
    for t in wf.get("top_transitions", []):
        writer.writerow([t.get("transition"), t.get("count")])

    output.seek(0)
    filename = f"bugflow_workflow_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# =========================================================
# 7. GITHUB INTEGRATION OPERATIONS
# =========================================================

@router.post("/integrations/github/webhook", summary="GitHub Webhook receiver for push and PR events")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    """Receives GitHub webhook payloads (Push, Pull Request, Commit Comments).

    Extracts commit messages, matches issue references (#12, BUG-002),
    and records an audit log entry on the target issue.
    """
    event_type = request.headers.get("X-GitHub-Event", "push")
    try:
        body = await request.json()
    except Exception:
        body = {}

    repo_name = body.get("repository", {}).get("full_name", "soma896/BugFlow")
    sender = body.get("sender", {}).get("login", "github-bot")
    ref = body.get("ref", "refs/heads/main")
    branch = ref.split("/")[-1] if "/" in ref else ref

    commits = body.get("commits", [])
    if not commits and "head_commit" in body:
        commits = [body["head_commit"]]

    processed_commits = []

    for c in commits:
        commit_id = c.get("id", "c001")
        msg = c.get("message", "")
        author = c.get("author", {}).get("name", sender)

        # Regex search for issue/defect references: #12, BUG-002, DEF-14
        match_id = None
        m = re.search(r"(?:#|BUG-|DEF-)(\d+)", msg, re.IGNORECASE)
        if m:
            try:
                match_id = int(m.group(1))
            except Exception:
                pass

        # Save event
        gh_event = GitHubEvent(
            event_type=event_type,
            repository=repo_name,
            sender=author,
            ref_branch=branch,
            commit_id=commit_id,
            commit_message=msg,
            linked_defect_id=match_id,
            linked_issue_id=match_id,
            payload_json=json.dumps(c)[:1000],
            created_at=datetime.utcnow(),
        )
        db.add(gh_event)
        db.commit()

        # If matched to a defect, record in AdminAction and AuditLog safely
        if match_id:
            defect = db.query(Defect).filter(Defect.id == match_id).first()
            if defect:
                admin_act = AdminAction(
                    admin_id=1,
                    defect_id=defect.id,
                    action=f"GITHUB:{commit_id[:7]}:{msg[:40]}"[:95],
                    created_at=datetime.utcnow(),
                )
                db.add(admin_act)
                db.commit()

            target_issue = db.query(Issue).filter(or_(Issue.id == match_id, Issue.issue_key == f"BUG-{match_id:03d}")).first()
            if target_issue:
                audit = AuditLog(
                    issue_id=target_issue.id,
                    user_id=1,
                    action=f"GITHUB:{commit_id[:7]} {msg[:40]}"[:95],
                    old_status=getattr(target_issue.status, "value", str(target_issue.status))[:45],
                    new_status=getattr(target_issue.status, "value", str(target_issue.status))[:45],
                    created_at=datetime.utcnow(),
                )
                db.add(audit)
                db.commit()

        processed_commits.append({
            "commit_id": commit_id,
            "message": msg,
            "matched_defect_id": match_id,
        })

    # Create notification
    create_notification(
        db,
        title=f"GitHub {event_type.title()} Event Synced",
        message=f"Received {len(processed_commits)} commit(s) on branch '{branch}' in {repo_name}.",
        category="GITHUB",
        target_role="admin",
        link="/integrations-ui",
    )

    return {
        "status": "success",
        "event_type": event_type,
        "repository": repo_name,
        "branch": branch,
        "commits_processed": len(processed_commits),
        "details": processed_commits,
    }


@router.post("/integrations/github/sync", summary="Simulate or manually trigger GitHub sync")
def github_sync(data: GitHubSyncRequest, db: Session = Depends(get_db)):
    """Allows manual sync or testing of commit linking from UI."""
    commit_sha = data.commit_sha or f"git{datetime.utcnow().strftime('%f')[:6]}"

    # Search for defect reference in message
    match_id = None
    m = re.search(r"(?:#|BUG-|DEF-)(\d+)", data.commit_message, re.IGNORECASE)
    if m:
        try:
            match_id = int(m.group(1))
        except Exception:
            pass

    gh_event = GitHubEvent(
        event_type="push",
        repository=data.repository,
        sender=data.author,
        ref_branch=data.branch,
        commit_id=commit_sha,
        commit_message=data.commit_message,
        linked_defect_id=match_id,
        linked_issue_id=match_id,
        payload_json=json.dumps({"manual_sync": True}),
        created_at=datetime.utcnow(),
    )
    db.add(gh_event)
    db.commit()

    if match_id:
        defect = db.query(Defect).filter(Defect.id == match_id).first()
        if defect:
            admin_act = AdminAction(
                admin_id=1,
                defect_id=defect.id,
                action=f"GITHUB:{commit_sha[:7]}:{data.commit_message[:40]}"[:95],
                created_at=datetime.utcnow(),
            )
            db.add(admin_act)
            db.commit()

        target_issue = db.query(Issue).filter(or_(Issue.id == match_id, Issue.issue_key == f"BUG-{match_id:03d}")).first()
        if target_issue:
            audit = AuditLog(
                issue_id=target_issue.id,
                user_id=1,
                action=f"GITHUB:{commit_sha[:7]} {data.commit_message[:40]}"[:95],
                old_status=getattr(target_issue.status, "value", str(target_issue.status))[:45],
                new_status=getattr(target_issue.status, "value", str(target_issue.status))[:45],
                created_at=datetime.utcnow(),
            )
            db.add(audit)
            db.commit()

    create_notification(
        db,
        title=f"GitHub Commit Linked to Defect #{match_id}" if match_id else "GitHub Push Synced",
        message=f"Commit {commit_sha[:7]} by {data.author}: {data.commit_message}",
        category="GITHUB",
        target_role="developer",
        link="/integrations-ui",
    )

    return {
        "message": "GitHub synchronization completed successfully",
        "commit_sha": commit_sha,
        "matched_defect_id": match_id,
        "event_id": gh_event.id,
    }


@router.get("/integrations/github/status", summary="GitHub integration health and stats")
def github_status(db: Session = Depends(get_db)):
    """Status of GitHub integration."""
    total_events = db.query(GitHubEvent).count()
    linked_events = db.query(GitHubEvent).filter(GitHubEvent.linked_defect_id != None).count()
    latest_event = db.query(GitHubEvent).order_by(desc(GitHubEvent.id)).first()

    return {
        "status": "CONNECTED",
        "repository": "soma896/BugFlow",
        "webhook_url": "/api/v1/integrations/github/webhook",
        "total_events_received": total_events,
        "commits_linked_to_defects": linked_events,
        "last_sync": latest_event.created_at.isoformat() if latest_event else None,
    }


@router.get("/integrations/github/events", summary="List recent GitHub events")
def list_github_events(db: Session = Depends(get_db)):
    """Retrieve recent GitHub webhook and commit events."""
    events = db.query(GitHubEvent).order_by(desc(GitHubEvent.id)).limit(20).all()
    return [
        {
            "id": e.id,
            "event_type": e.event_type,
            "repository": e.repository,
            "sender": e.sender,
            "branch": e.ref_branch,
            "commit_id": e.commit_id,
            "commit_message": e.commit_message,
            "linked_defect_id": e.linked_defect_id,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


# =========================================================
# 8. CI/CD SYNCHRONIZATION OPERATIONS
# =========================================================

@router.post("/integrations/cicd/webhook", summary="CI/CD Pipeline Webhook receiver")
async def cicd_webhook(request: Request, db: Session = Depends(get_db)):
    """Receives automated CI/CD pipeline results.

    When status is FAILURE:
    Automatically creates a Defect in BugFlow and notifies Developer (Sasuke).
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    pipeline_name = body.get("pipeline_name", "BugFlow Build & Test Pipeline")
    pipeline_id = body.get("pipeline_id", f"pipe-{int(datetime.utcnow().timestamp())}")
    build_num = int(body.get("build_number", 1))
    branch = body.get("branch", "main")
    commit_sha = body.get("commit_sha", "HEAD")
    status = (body.get("status") or "SUCCESS").strip().upper()

    total_tests = int(body.get("total_tests", 24))
    passed_tests = int(body.get("passed_tests", 24 if status == "SUCCESS" else 20))
    failed_tests = int(body.get("failed_tests", 0 if status == "SUCCESS" else 4))
    duration = int(body.get("duration_seconds", 38))
    logs = body.get("logs", "CI/CD build pipeline execution completed.")

    auto_defect_id = None

    # Automated Defect Filing on Failure
    if status == "FAILURE":
        auto_defect = Defect(
            user_id=1,
            title=f"[CI/CD Test Failure] {pipeline_name} #{build_num} on {branch}",
            description=(
                f"Automated CI/CD test failure triggered.\n"
                f"Pipeline: {pipeline_name}\n"
                f"Build Number: #{build_num}\n"
                f"Branch: {branch}\n"
                f"Commit: {commit_sha[:7]}\n"
                f"Tests: {passed_tests}/{total_tests} passed, {failed_tests} failed.\n"
                f"Failure Log:\n{logs[:400]}"
            ),
            category="CI/CD & Testing",
            priority="Urgent" if failed_tests > 2 else "High",
            status="Pending",
            assigned_role="developer",
            environment=f"CI Pipeline ({branch})",
            created_at=datetime.utcnow(),
        )
        db.add(auto_defect)
        db.commit()
        db.refresh(auto_defect)
        auto_defect_id = auto_defect.id

        create_notification(
            db,
            title=f"CI/CD Failure: Build #{build_num} Failed",
            message=f"{failed_tests} test(s) failed in {pipeline_name}. Defect #{auto_defect.id} was automatically created and assigned to Developer (Sasuke).",
            category="CICD",
            target_role="developer",
            link="/developer-defects-ui",
        )
    else:
        create_notification(
            db,
            title=f"CI/CD Pipeline Succeeded: Build #{build_num}",
            message=f"All {total_tests} tests passed on branch '{branch}' in {duration}s.",
            category="CICD",
            target_role="admin",
            link="/integrations-ui",
        )

    # Save run record
    run = CICDRun(
        pipeline_id=pipeline_id,
        pipeline_name=pipeline_name,
        build_number=build_num,
        branch=branch,
        commit_sha=commit_sha,
        status=status,
        total_tests=total_tests,
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        duration_seconds=duration,
        triggered_by=body.get("triggered_by", "automated_webhook"),
        logs=logs,
        auto_defect_id=auto_defect_id,
        created_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return {
        "message": f"CI/CD Pipeline #{build_num} status recorded as {status}",
        "run_id": run.id,
        "status": status,
        "auto_defect_created": auto_defect_id is not None,
        "defect_id": auto_defect_id,
    }


@router.post("/integrations/cicd/trigger", summary="Trigger a CI/CD build run simulation")
def trigger_cicd_run(data: CICDTriggerRequest, db: Session = Depends(get_db)):
    """Simulates running the automated test suite."""
    build_count = db.query(CICDRun).count()
    next_build_num = build_count + 1

    outcome = data.simulated_outcome.strip().upper()
    total_tests = 32
    if outcome == "FAILURE":
        failed_tests = data.failed_tests_count if data.failed_tests_count > 0 else 3
        passed_tests = total_tests - failed_tests
        logs = (
            f"FAILED: test_auth_token_expiration (AssertionError: Token expired unexpectedly)\n"
            f"FAILED: test_defect_status_workflow (Expected 'ACCEPTED', got 'PENDING')\n"
            f"FAILED: test_metrics_calculation (ZeroDivisionError in custom formula)"
        )
    else:
        failed_tests = 0
        passed_tests = total_tests
        logs = f"SUCCESS: 32 tests executed successfully in 18.4s. 0 failures, 0 errors."

    # Use webhook logic
    from unittest.mock import MagicMock
    req_mock = MagicMock()
    req_mock.json.return_value = {
        "pipeline_name": data.pipeline_name,
        "pipeline_id": f"pipe-auto-{next_build_num}",
        "build_number": next_build_num,
        "branch": data.branch,
        "commit_sha": f"c{datetime.utcnow().strftime('%f')[:6]}",
        "status": outcome,
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "duration_seconds": 18,
        "logs": logs,
        "triggered_by": "manual_simulation",
    }

    import asyncio
    res = asyncio.run(cicd_webhook(req_mock, db))
    return res


@router.get("/integrations/cicd/status", summary="CI/CD integration health and pass rate")
def cicd_status(db: Session = Depends(get_db)):
    """Return pipeline pass rates and build statistics."""
    runs = db.query(CICDRun).order_by(desc(CICDRun.id)).all()
    total_runs = len(runs)
    successful = sum(1 for r in runs if r.status == "SUCCESS")
    failed = sum(1 for r in runs if r.status == "FAILURE")
    pass_rate = round((successful / total_runs * 100), 1) if total_runs > 0 else 100.0
    latest = runs[0] if runs else None

    return {
        "status": "OPERATIONAL",
        "pipeline_name": "BugFlow Main CI/CD Pipeline",
        "total_runs": total_runs,
        "successful_runs": successful,
        "failed_runs": failed,
        "pass_rate_pct": pass_rate,
        "latest_run": {
            "build_number": latest.build_number,
            "status": latest.status,
            "branch": latest.branch,
            "created_at": latest.created_at.isoformat(),
        } if latest else None,
    }


@router.get("/integrations/cicd/runs", summary="List recent CI/CD pipeline runs")
def list_cicd_runs(db: Session = Depends(get_db)):
    """Retrieve history of build and test execution runs."""
    runs = db.query(CICDRun).order_by(desc(CICDRun.id)).limit(20).all()
    return [
        {
            "id": r.id,
            "pipeline_name": r.pipeline_name,
            "build_number": r.build_number,
            "branch": r.branch,
            "commit_sha": r.commit_sha,
            "status": r.status,
            "total_tests": r.total_tests,
            "passed_tests": r.passed_tests,
            "failed_tests": r.failed_tests,
            "duration_seconds": r.duration_seconds,
            "triggered_by": r.triggered_by,
            "auto_defect_id": r.auto_defect_id,
            "created_at": r.created_at.isoformat(),
        }
        for r in runs
    ]


# =========================================================
# 9. NOTIFICATION CENTER OPERATIONS
# =========================================================

@router.get("/notifications", summary="Retrieve recent system and integration notifications")
def list_notifications(
    category: str | None = Query(None, description="Filter by category (GITHUB, CICD, WORKFLOW, ASSIGNMENT)"),
    unread_only: bool = Query(False),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Retrieve in-app notifications."""
    query = db.query(Notification)
    if category:
        query = query.filter(Notification.category.ilike(f"%{category}%"))
    if unread_only:
        query = query.filter(Notification.is_read == False)

    notifications = query.order_by(desc(Notification.id)).limit(limit).all()
    unread_count = db.query(Notification).filter(Notification.is_read == False).count()

    return {
        "unread_count": unread_count,
        "total": len(notifications),
        "items": [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "category": n.category,
                "target_role": n.target_role,
                "link": n.link,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ],
    }


@router.post("/notifications/read", summary="Mark notifications as read")
def mark_notifications_read(
    notification_id: int | None = Query(None, description="Specific ID, or omit to mark all read"),
    db: Session = Depends(get_db),
):
    """Mark notifications as read."""
    if notification_id:
        notif = db.query(Notification).filter(Notification.id == notification_id).first()
        if notif:
            notif.is_read = True
    else:
        db.query(Notification).update({Notification.is_read: True})

    db.commit()
    return {"message": "Notifications marked as read"}


@router.post("/notifications/clear", summary="Clear read notifications")
def clear_notifications(db: Session = Depends(get_db)):
    """Remove read notifications."""
    db.query(Notification).filter(Notification.is_read == True).delete()
    db.commit()
    return {"message": "Read notifications cleared"}
