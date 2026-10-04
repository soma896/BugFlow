from pathlib import Path
from datetime import date, datetime, timedelta
import secrets

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import or_, text
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash

from .database import get_db
from .models import (
    AdminAction,
    AuditLog,
    Attachment,
    AuthSession,
    Comment,
    Defect,
    Issue,
    IssueStatus,
    IssueType,
    Priority,
    Severity,
    Sprint,
    SprintIssue,
    User,
)

app = FastAPI(title="BugFlow API")


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "Frontend"

# Module 2 uploaded attachment storage
ATTACHMENTS_DIR = BASE_DIR / "uploads" / "attachments"
ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)


def serve_page(filename: str):
    page = FRONTEND_DIR / filename

    if not page.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Page not found: {filename}",
        )

    # Keep the existing Admin pages as separate pages, but make
    # Sprint Management available in the Admin navigation on all
    # three Admin screens without changing their existing layout.
    admin_pages = {
        "admin.html",
        "all-defects.html",
        "analytics.html",
    }

    if filename in admin_pages:
        html = page.read_text(encoding="utf-8")

        if "Sprint Management" not in html:
            nav_item = """
        <a href="/milestone2-ui" class="nav-link">
            <span class="nav-icon">◈</span>
            <span class="nav-text">Sprint Management</span>
        </a>
"""
            marker = """
        <a href="/login-ui" class="nav-link" id="logoutLink">"""

            if marker in html:
                html = html.replace(marker, nav_item + marker, 1)

        # Module 2: expose the EXISTING Admin Team Collaboration page
        # in the Admin navigation. Role-specific dashboards use their
        # own Team Collaboration routes in their dashboard HTML files.
        if "Team Collaboration" not in html:
            nav_item = """
        <a href="/team-collaboration-ui" class="nav-link">
            <span class="nav-icon">◉</span>
            <span class="nav-text">Team Collaboration</span>
        </a>
"""
            marker = """
        <a href="/login-ui" class="nav-link" id="logoutLink">"""

            if marker in html:
                html = html.replace(marker, nav_item + marker, 1)

        # Module 3: expose Integrations & CI/CD in Admin navigation
        if "Integrations &amp; CI/CD" not in html and "Integrations & CI/CD" not in html and "/integrations-ui" not in html:
            nav_item = """
        <a href="/integrations-ui" class="nav-link">
            <span class="nav-icon">⚡</span>
            <span class="nav-text">Integrations & CI/CD</span>
        </a>
"""
            marker = """
        <a href="/login-ui" class="nav-link" id="logoutLink">"""

            if marker in html:
                html = html.replace(marker, nav_item + marker, 1)

        # Module 3: expose API Explorer in Admin navigation
        if "API Explorer" not in html and "/api-explorer-ui" not in html:
            nav_item = """
        <a href="/api-explorer-ui" class="nav-link">
            <span class="nav-icon">⚙</span>
            <span class="nav-text">API Explorer</span>
        </a>
"""
            marker = """
        <a href="/login-ui" class="nav-link" id="logoutLink">"""

            if marker in html:
                html = html.replace(marker, nav_item + marker, 1)

        return HTMLResponse(content=html)

    return FileResponse(page)


# =========================================================
# AUTHENTICATION
# =========================================================

security = HTTPBearer(auto_error=False)

# Temporary in-memory sessions
# token -> user_id
sessions: dict[str, int] = {}

# Active workspace context for authenticated sessions
# token -> active workspace role (e.g. "developer", "tester", "senior_dev", "admin", "user")
workspace_sessions: dict[str, str] = {}


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    token = credentials.credentials
    user_id = sessions.get(token)

    if user_id is None:
        auth_session = (
            db.query(AuthSession)
            .filter(
                AuthSession.token == token,
                AuthSession.expires_at > datetime.utcnow(),
            )
            .first()
        )
        if auth_session:
            user_id = auth_session.user_id
            sessions[token] = user_id

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
        )

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        sessions.pop(token, None)

        raise HTTPException(
            status_code=401,
            detail="User account not found",
        )

    user._token = token
    return user


def get_admin_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
):
    if credentials is not None:
        token = credentials.credentials
        user_id = sessions.get(token)

        if user_id is None:
            auth_session = (
                db.query(AuthSession)
                .filter(
                    AuthSession.token == token,
                    AuthSession.expires_at > datetime.utcnow(),
                )
                .first()
            )
            if auth_session:
                user_id = auth_session.user_id
                sessions[token] = user_id

        if user_id:
            user = db.query(User).filter(User.id == user_id).first()

            if user and user.role == "admin":
                return user

    admin_user = db.query(User).filter(User.role == "admin").first()

    if admin_user:
        return admin_user

    first_user = db.query(User).filter(User.id == 1).first()

    if first_user:
        return first_user

    raise HTTPException(
        status_code=403,
        detail="Admin access required",
    )


# =========================================================
# REQUEST MODELS
# =========================================================

class IssueCreate(BaseModel):
    issue_key: str
    issue_type: IssueType
    title: str
    description: str
    reproduction_steps: str | None = None
    severity: Severity
    priority: Priority
    status: IssueStatus = IssueStatus.REPORTED
    affected_module: str | None = None
    environment: str | None = None
    screenshot_url: str | None = None
    project_key: str
    reporter_id: int
    assignee_id: int | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class DefectCreate(BaseModel):
    id: int | None = None
    defect_id: int | str | None = None
    user_id: int
    title: str
    description: str
    category: str
    priority: str
    environment: str | None = None
    reproduction_steps: str | None = None
    expected_result: str | None = None
    actual_result: str | None = None


class AdminActionCreate(BaseModel):
    admin_id: int
    defect_id: int
    action: str


class DefectAssignRequest(BaseModel):
    defect_id: int
    assigned_role: str


class RoleActionCreate(BaseModel):
    defect_id: int
    role: str
    action: str


class SprintCreate(BaseModel):
    sprint_name: str
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str = "PLANNING"


class SprintAssignRequest(BaseModel):
    assigned_role: str


# =========================================================
# MODULE 2 - PART 3: COLLABORATION COMMENTS
# =========================================================

class CommentCreate(BaseModel):
    comment: str


class WorkflowStatusRequest(BaseModel):
    status: str


# =========================================================
# MODULE 2 - SMART PRIORITY CALCULATOR
# =========================================================

class TriageRecommendationRequest(BaseModel):
    severity: str
    category: str


# Severity weights
SEVERITY_WEIGHTS = {
    "CRITICAL": 4,
    "MAJOR": 3,
    "MINOR": 2,
    "TRIVIAL": 1,

    # Existing Module 1 / Issue model compatibility
    "BLOCKER": 4,
}


# Category urgency weights
CATEGORY_URGENCY_WEIGHTS = {
    "SECURITY": 3,
    "SECURITY VULNERABILITY": 3,
    "DATABASE": 3,

    "API": 2,
    "BACKEND": 2,
    "API/BACKEND": 2,

    "UI": 1,
    "COLORS": 1,
    "TYPOS": 1,
    "UI/COLORS/TYPOS": 1,
}


def calculate_priority_score(
    severity: str,
    category: str,
):
    """
    Module 2 Smart Priority Calculator.

    Priority Score =
        Severity Weight × Category Urgency Weight

    Score:
        >= 10  -> URGENT
        7-9    -> HIGH
        4-6    -> MEDIUM
        < 4    -> LOW
    """

    severity_key = severity.strip().upper()
    category_key = category.strip().upper()

    # -----------------------------------------------------
    # Get severity weight
    # -----------------------------------------------------

    severity_weight = SEVERITY_WEIGHTS.get(severity_key)

    if severity_weight is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid severity: {severity}. "
                f"Allowed values: CRITICAL, MAJOR, MINOR, TRIVIAL"
            ),
        )

    # -----------------------------------------------------
    # Get category urgency weight
    # -----------------------------------------------------

    category_weight = CATEGORY_URGENCY_WEIGHTS.get(category_key)

    # Allow category names containing the required keywords
    if category_weight is None:

        if "SECURITY" in category_key:
            category_weight = 3

        elif "DATABASE" in category_key:
            category_weight = 3

        elif (
            "API" in category_key
            or "BACKEND" in category_key
        ):
            category_weight = 2

        elif (
            "UI" in category_key
            or "COLOR" in category_key
            or "TYPO" in category_key
        ):
            category_weight = 1

    if category_weight is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid category: {category}. "
                f"Allowed categories include Security, Database, "
                f"API/Backend, and UI/Colors/Typos."
            ),
        )

    # -----------------------------------------------------
    # Calculate score
    # -----------------------------------------------------

    score = severity_weight * category_weight

    # -----------------------------------------------------
    # Determine priority
    # -----------------------------------------------------

    if score >= 10:
        priority = "URGENT"

    elif score >= 7:
        priority = "HIGH"

    elif score >= 4:
        priority = "MEDIUM"

    else:
        priority = "LOW"

    return {
        "severity": severity_key,
        "category": category,
        "severity_weight": severity_weight,
        "category_urgency_weight": category_weight,
        "score": score,
        "priority": priority,
    }


@app.post("/api/v1/issues/triage-recommendation")
def triage_recommendation(
    data: TriageRecommendationRequest,
):
    """
    Module 2 Part 1 API.

    Calculates the recommended priority
    based on severity and category.
    """

    return calculate_priority_score(
        data.severity,
        data.category,
    )


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "message": "BugFlow API is running",
    }


# =========================================================
# FRONTEND PAGES
# =========================================================

@app.get("/login-ui")
def login_ui():
    return serve_page("index.html")


@app.get("/admin-ui")
def admin_ui():
    return serve_page("admin.html")


@app.get("/all-defects-ui")
def all_defects_ui():
    return serve_page("all-defects.html")


@app.get("/analytics-ui")
@app.get("/admin-analytics-ui")
def analytics_ui():
    return serve_page("analytics.html")


@app.get("/tester-ui")
def tester_ui():
    return serve_page("tester-dashboard.html")


@app.get("/tester-defects-ui")
def tester_defects_ui():
    return serve_page("tester-defects.html")


@app.get("/tester-analytics-ui")
def tester_analytics_ui():
    return serve_page("tester-analytics.html")


@app.get("/developer-ui")
def developer_ui():
    return serve_page("developer-dashboard.html")


@app.get("/developer-defects-ui")
def developer_defects_ui():
    return serve_page("developer-defects.html")


@app.get("/developer-analytics-ui")
def developer_analytics_ui():
    return serve_page("developer-analytics.html")


@app.get("/senior-dev-ui")
@app.get("/senior-developer-ui")
def senior_developer_ui():
    return serve_page("senior-dev-dashboard.html")


@app.get("/senior-developer-defects-ui")
@app.get("/senior-defects-ui")
def senior_developer_defects_ui():
    return serve_page("senior-developer-defects.html")


@app.get("/senior-analytics-ui")
@app.get("/senior-developer-analytics-ui")
def senior_analytics_ui():
    return serve_page("senior-analytics.html")


@app.get("/user-ui")
def user_ui():
    return serve_page("user.html")


@app.get("/milestone2-ui")
def milestone2_ui():
    return serve_page("milestone2.html")


@app.get("/team-collaboration-ui")
def team_collaboration_ui():
    return serve_page("team-collaboration.html")


@app.get("/team-collaboration-developer-ui")
def team_collaboration_developer_ui():
    return serve_page("developer-team-collaboration.html")


@app.get("/team-collaboration-tester-ui")
def team_collaboration_tester_ui():
    return serve_page("tester-team-collaboration.html")


@app.get("/team-collaboration-senior-developer-ui")
def team_collaboration_senior_developer_ui():
    return serve_page("senior-dev-team-collaboration.html")


# Compatibility aliases for role dashboards that may use the shorter
# Team Collaboration route names. Existing routes above are preserved.
@app.get("/developer-team-collaboration-ui")
def developer_team_collaboration_ui():
    return serve_page("developer-team-collaboration.html")


@app.get("/tester-team-collaboration-ui")
def tester_team_collaboration_ui():
    return serve_page("tester-team-collaboration.html")


@app.get("/senior-dev-team-collaboration-ui")
def senior_dev_team_collaboration_ui():
    return serve_page("senior-dev-team-collaboration.html")


# =========================================================
# ROLE SPRINT PAGES
# =========================================================

@app.get("/tester-sprints-ui")
def tester_sprints_ui():
    return serve_page("tester-sprints.html")


@app.get("/developer-sprints-ui")
def developer_sprints_ui():
    return serve_page("developer-sprints.html")


@app.get("/senior-developer-sprints-ui")
def senior_developer_sprints_ui():
    return serve_page("senior-developer-sprints.html")


# =========================================================
# MODULE 3 PAGES
# =========================================================

@app.get("/integrations-ui")
def integrations_ui():
    return serve_page("integrations.html")


@app.get("/api-explorer-ui")
def api_explorer_ui():
    return serve_page("api-explorer.html")


# =========================================================
# LOGIN & LOGOUT
# =========================================================

@app.post("/login")
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.email == data.email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    if not check_password_hash(
        user.password_hash,
        data.password,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    token = secrets.token_urlsafe(32)

    sessions[token] = user.id
    workspace_sessions[token] = "admin" if user.role == "admin" else user.role
    try:
        new_session = AuthSession(
            token=token,
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        db.add(new_session)
        db.commit()
    except Exception:
        db.rollback()

    return {
        "message": "Login successful",
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }


@app.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
):
    if credentials is None:
        return {
            "message": "Already logged out",
        }

    token = credentials.credentials

    sessions.pop(token, None)
    workspace_sessions.pop(token, None)
    try:
        db.query(AuthSession).filter(AuthSession.token == token).delete()
        db.commit()
    except Exception:
        db.rollback()

    return {
        "message": "Logout successful",
    }


# =========================================================
# ISSUES
# =========================================================

@app.get("/issues")
def get_issues(
    db: Session = Depends(get_db),
):
    return db.query(Issue).all()


@app.get("/issues/{issue_id}")
def get_issue(
    issue_id: int,
    db: Session = Depends(get_db),
):
    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found",
        )

    return issue


@app.post("/issues")
def create_issue(
    issue_data: IssueCreate,
    db: Session = Depends(get_db),
):
    existing = (
        db.query(Issue)
        .filter(Issue.issue_key == issue_data.issue_key)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Issue key already exists",
        )

    issue = Issue(
        **issue_data.model_dump()
    )

    db.add(issue)
    db.commit()
    db.refresh(issue)

    return issue


# =========================================================
# USER DEFECTS
# =========================================================

@app.post("/defects")
def create_defect(
    defect_data: DefectCreate,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
):
    user_id = defect_data.user_id

    if credentials is not None:
        token = credentials.credentials
        sess_user_id = sessions.get(token)

        if sess_user_id:
            user_id = sess_user_id

    custom_id = None
    raw_id = defect_data.id if defect_data.id is not None else defect_data.defect_id
    if raw_id is not None:
        try:
            clean_str = str(raw_id).lstrip("#").strip()
            if clean_str.isdigit():
                candidate_id = int(clean_str)
                exists = db.query(Defect.id).filter(Defect.id == candidate_id).first()
                if exists:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Defect ID #{candidate_id} already exists",
                    )
                custom_id = candidate_id
        except HTTPException:
            raise
        except Exception:
            pass

    defect_kwargs = {
        "user_id": user_id,
        "title": defect_data.title,
        "description": defect_data.description,
        "category": defect_data.category,
        "priority": defect_data.priority,
        "status": "Pending",
        "environment": defect_data.environment,
        "reproduction_steps": defect_data.reproduction_steps,
        "expected_result": defect_data.expected_result,
        "actual_result": defect_data.actual_result,
    }
    if custom_id is not None:
        defect_kwargs["id"] = custom_id

    defect = Defect(**defect_kwargs)

    db.add(defect)
    db.commit()
    db.refresh(defect)

    if custom_id is not None:
        try:
            db.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence('defects', 'id'), "
                    "(SELECT COALESCE(MAX(id), 1) FROM defects))"
                )
            )
            db.commit()
            db.refresh(defect)
        except Exception:
            pass

    return defect


@app.get("/defects")
def get_defects(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
):
    if credentials is not None:
        token = credentials.credentials
        user_id = sessions.get(token)

        if user_id:
            return (
                db.query(Defect)
                .filter(Defect.user_id == user_id)
                .order_by(Defect.id)
                .all()
            )

    return (
        db.query(Defect)
        .order_by(Defect.id)
        .all()
    )


@app.get("/users/{user_id}/defects")
def get_user_defects(
    user_id: int,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    return (
        db.query(Defect)
        .filter(Defect.user_id == user_id)
        .order_by(Defect.id)
        .all()
    )


# =========================================================
# ROLE DEFECTS ENDPOINTS
# =========================================================

@app.get("/tester/defects")
def get_tester_defects(
    db: Session = Depends(get_db),
):
    return (
        db.query(Defect)
        .filter(Defect.assigned_role.ilike("tester"))
        .order_by(Defect.id)
        .all()
    )


@app.get("/developer/defects")
def get_developer_defects(
    db: Session = Depends(get_db),
):
    return (
        db.query(Defect)
        .filter(Defect.assigned_role.ilike("developer"))
        .order_by(Defect.id)
        .all()
    )


@app.get("/senior-developer/defects")
def get_senior_developer_defects(
    db: Session = Depends(get_db),
):
    return (
        db.query(Defect)
        .filter(
            or_(
                Defect.assigned_role.ilike("senior_dev"),
                Defect.assigned_role.ilike("senior_developer"),
                Defect.assigned_role.ilike("senior developer"),
                Defect.assigned_role.ilike("senior dev"),
            )
        )
        .order_by(Defect.id)
        .all()
    )


@app.get("/role-defects")
def get_role_defects(
    view_role: str = "user",
    db: Session = Depends(get_db),
):
    role = view_role.strip().lower()

    if role == "tester":
        return get_tester_defects(db)

    elif role == "developer":
        return get_developer_defects(db)

    elif role in [
        "senior_dev",
        "senior_developer",
    ]:
        return get_senior_developer_defects(db)

    else:
        return (
            db.query(Defect)
            .order_by(Defect.id)
            .all()
        )


@app.post("/role/actions")
def update_role_defect_status(
    action_data: RoleActionCreate,
    db: Session = Depends(get_db),
):
    defect = (
        db.query(Defect)
        .filter(Defect.id == action_data.defect_id)
        .first()
    )

    if not defect:
        raise HTTPException(
            status_code=404,
            detail=f"Defect #{action_data.defect_id} not found",
        )

    action = action_data.action.strip()
    act_lower = action.lower()

    if act_lower in ["accept", "accepted"]:
        target_status = "ACCEPTED"
    elif act_lower in ["reject", "rejected"]:
        target_status = "REJECTED"
    elif act_lower in ["resolve", "resolved"]:
        target_status = "RESOLVED"
    elif act_lower in ["assign", "assigned"]:
        target_status = "ASSIGNED"
    else:
        raise HTTPException(
            status_code=400,
            detail="Action must be ACCEPT, REJECT, or RESOLVE",
        )

    user_role = action_data.role.strip().lower()
    defect_role = (
        defect.assigned_role or ""
    ).strip().lower()

    if not defect_role:
        raise HTTPException(
            status_code=403,
            detail="Cannot update unassigned defects",
        )

    def normalize(r: str) -> str:
        if r in [
            "senior_dev",
            "senior_developer",
            "senior developer",
            "senior dev",
        ]:
            return "senior_dev"

        return r

    if normalize(user_role) != normalize(defect_role):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Role '{user_role}' is not authorized "
                f"to update defects assigned to "
                f"'{defect.assigned_role}'"
            ),
        )

    curr_status = (defect.status or "").strip().upper()

    # Permission & State Flow Rules:
    # 1. ASSIGNED -> ACCEPT -> ACCEPTED
    # 2. ASSIGNED -> REJECT -> REJECTED
    # 3. ACCEPTED -> RESOLVE -> RESOLVED
    if target_status == "RESOLVED":
        if curr_status != "ACCEPTED":
            raise HTTPException(
                status_code=400,
                detail="Defect must be ACCEPTED before it can be RESOLVED",
            )
    elif target_status in ["ACCEPTED", "REJECTED"]:
        if curr_status not in ["ASSIGNED", "PENDING", ""]:
            raise HTTPException(
                status_code=400,
                detail=f"Defect cannot be {target_status} from current status '{defect.status}'",
            )

    defect.status = target_status

    db.commit()
    db.refresh(defect)

    return {
        "message": (
            f"Defect #{defect.id} marked as {defect.status}"
        ),
        "defect_id": defect.id,
        "new_status": defect.status,
        "status": defect.status,
    }


# =========================================================
# ADMIN DASHBOARD & DEFECTS
# =========================================================

@app.get("/admin/dashboard")
def admin_dashboard(
    db: Session = Depends(get_db),
):
    total_defects = db.query(Defect).count()

    pending = (
        db.query(Defect)
        .filter(
            or_(
                Defect.status.ilike("Pending"),
                Defect.status.ilike("ASSIGNED"),
                Defect.status.ilike("ACCEPTED"),
            )
        )
        .count()
    )

    resolved = (
        db.query(Defect)
        .filter(Defect.status.ilike("Resolved"))
        .count()
    )

    rejected = (
        db.query(Defect)
        .filter(Defect.status.ilike("Rejected"))
        .count()
    )

    return {
        "total_defects": total_defects,
        "pending": pending,
        "resolved": resolved,
        "rejected": rejected,
    }


@app.get("/admin/defects")
def get_admin_defects(
    db: Session = Depends(get_db),
):
    return (
        db.query(Defect)
        .order_by(Defect.id)
        .all()
    )


# =========================================================
# ADMIN ACTIONS & ASSIGNMENT
# =========================================================

@app.post("/admin/assign")
def assign_defect(
    data: DefectAssignRequest,
    db: Session = Depends(get_db),
):
    defect = (
        db.query(Defect)
        .filter(Defect.id == data.defect_id)
        .first()
    )

    if not defect:
        raise HTTPException(
            status_code=404,
            detail=f"Defect #{data.defect_id} not found",
        )

    role = data.assigned_role.strip()

    defect.assigned_role = role
    defect.status = "ASSIGNED"

    role_user_map = {
        "tester": "Hinata",
        "developer": "Sasuke",
        "senior_dev": "Itachi",
        "senior_developer": "Itachi",
        "senior developer": "Itachi",
        "senior dev": "Itachi",
        "admin": "Naruto",
    }
    user_name = role_user_map.get(role.lower())
    if user_name:
        u = db.query(User).filter(User.name.ilike(user_name)).first()
        if u:
            defect.assigned_user_id = u.id

    db.commit()
    db.refresh(defect)

    role_display_map = {
        "tester": "Hinata (Tester)",
        "developer": "Sasuke (Developer)",
        "senior_dev": "Itachi (Senior Developer)",
        "senior_developer": "Itachi (Senior Developer)",
        "admin": "Naruto (Admin)",
    }

    return {
        "message": (
            f"Defect #{defect.id} assigned "
            f"successfully to {role}"
        ),
        "defect_id": defect.id,
        "assigned_role": defect.assigned_role,
        "assigned_user_id": defect.assigned_user_id,
        "status": defect.status,
        "assigned_display": role_display_map.get(
            role.lower(),
            role,
        ),
    }


@app.post("/admin/actions")
def create_admin_action(
    action_data: AdminActionCreate,
    db: Session = Depends(get_db),
):
    defect = (
        db.query(Defect)
        .filter(Defect.id == action_data.defect_id)
        .first()
    )

    if not defect:
        raise HTTPException(
            status_code=404,
            detail="Defect not found",
        )

    action = action_data.action.strip()
    act_lower = action.lower()

    if act_lower in ["accept", "accepted"]:
        target_status = "ACCEPTED"
    elif act_lower in ["reject", "rejected"]:
        target_status = "REJECTED"
    elif act_lower in ["resolve", "resolved"]:
        target_status = "RESOLVED"
    elif act_lower in ["assign", "assigned"]:
        target_status = "ASSIGNED"
    else:
        target_status = action

    defect.status = target_status

    admin_action = AdminAction(
        admin_id=action_data.admin_id,
        defect_id=defect.id,
        action=action,
    )

    db.add(admin_action)
    db.commit()
    db.refresh(admin_action)

    return {
        "message": (
            "Admin action recorded successfully"
        ),
        "defect_id": defect.id,
        "new_status": defect.status,
        "status": defect.status,
        "admin_action_id": admin_action.id,
    }


@app.get("/admin/actions")
def get_admin_actions(
    db: Session = Depends(get_db),
):
    return (
        db.query(AdminAction)
        .order_by(AdminAction.id)
        .all()
    )


# =========================================================
# MODULE 2 - PART 3: COLLABORATION COMMENTS
# =========================================================

@app.post("/api/v1/collaboration/issues/{issue_id}/comments")
def add_issue_comment(
    issue_id: int,
    data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add and permanently save a comment on an issue."""

    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found",
        )

    comment_text = data.comment.strip()

    if not comment_text:
        raise HTTPException(
            status_code=400,
            detail="Comment cannot be empty",
        )

    new_comment = Comment(
        issue_id=issue_id,
        user_id=current_user.id,
        comment=comment_text,
    )

    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    return {
        "message": "Comment added successfully",
        "comment_id": new_comment.id,
        "issue_id": issue_id,
        "user_id": current_user.id,
        "user_name": current_user.name,
        "comment": new_comment.comment,
        "created_at": new_comment.created_at,
    }


@app.get("/api/v1/collaboration/issues/{issue_id}/comments")
def get_issue_comments(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all saved comments for an issue."""

    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found",
        )

    comments = (
        db.query(Comment)
        .filter(Comment.issue_id == issue_id)
        .order_by(Comment.created_at.asc(), Comment.id.asc())
        .all()
    )

    return {
        "issue_id": issue_id,
        "comments": [
            {
                "comment_id": item.id,
                "user_id": item.user_id,
                "user_name": item.user.name if item.user else "Unknown User",
                "comment": item.comment,
                "created_at": item.created_at,
            }
            for item in comments
        ],
    }


# =========================================================
# MODULE 2 - PART 3: ATTACHMENTS
# =========================================================

ALLOWED_ATTACHMENT_EXTENSIONS = {".png", ".jpg", ".log"}


@app.post("/api/v1/collaboration/issues/{issue_id}/attachments")
def upload_issue_attachment(
    issue_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload and permanently save an allowed attachment for an issue."""

    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found",
        )

    original_filename = Path(file.filename or "").name

    if not original_filename:
        raise HTTPException(
            status_code=400,
            detail="A file must be selected",
        )

    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only .png, .jpg, and .log files are allowed",
        )

    # Create a unique stored filename so uploads cannot overwrite each other.
    stored_filename = (
        f"issue_{issue_id}_"
        f"{secrets.token_hex(8)}"
        f"{extension}"
    )

    stored_path = ATTACHMENTS_DIR / stored_filename

    try:
        with stored_path.open("wb") as output_file:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                output_file.write(chunk)

        attachment = Attachment(
            issue_id=issue_id,
            user_id=current_user.id,
            filename=original_filename,
            file_path=str(stored_path),
        )

        db.add(attachment)
        db.commit()
        db.refresh(attachment)

    except Exception as exc:
        if stored_path.exists():
            stored_path.unlink()

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to save attachment: {exc}",
        )

    finally:
        file.file.close()

    return {
        "message": "Attachment uploaded successfully",
        "attachment_id": attachment.id,
        "issue_id": issue_id,
        "user_id": current_user.id,
        "user_name": current_user.name,
        "filename": attachment.filename,
        "uploaded_at": attachment.uploaded_at,
    }


@app.get("/api/v1/collaboration/issues/{issue_id}/attachments")
def get_issue_attachments(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all saved attachments for an issue."""

    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found",
        )

    attachments = (
        db.query(Attachment)
        .filter(Attachment.issue_id == issue_id)
        .order_by(Attachment.uploaded_at.asc(), Attachment.id.asc())
        .all()
    )

    return {
        "issue_id": issue_id,
        "attachments": [
            {
                "attachment_id": item.id,
                "user_id": item.user_id,
                "user_name": item.user.name if item.user else "Unknown User",
                "filename": item.filename,
                "uploaded_at": item.uploaded_at,
            }
            for item in attachments
        ],
    }



# =========================================================
# MODULE 2 - TEAM COLLABORATION SUPPORT
# =========================================================

class CollaborationAssignmentRequest(BaseModel):
    assignee_id: int | None = None


class CollaborationActionRequest(BaseModel):
    action: str
    note: str | None = None
    role: str | None = None


class CollaborationTeamRequest(BaseModel):
    roles: list[str]


class CollaborationWorkRequest(BaseModel):
    status: str
    note: str | None = None
    role: str | None = None
    work_type: str | None = None


class CollaborationAssignmentResponseRequest(BaseModel):
    action: str  # ACCEPT or REJECT
    role: str | None = None
    note: str | None = None


def normalize_collaboration_role(role) -> str:
    value = str(role or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "admin": "admin",
        "tester": "tester",
        "developer": "developer",
        "senior_dev": "senior_dev",
        "senior_developer": "senior_dev",
    }
    return aliases.get(value, value)


def get_effective_workspace_role(
    credentials: HTTPAuthorizationCredentials | None,
    current_user: User,
) -> str:
    """Return the active workspace role if Admin has switched workspace.

    If the authenticated user is Admin, use the active workspace role
    associated with their session token if one has been set.
    Otherwise, fall back to the normalized database role.
    """
    if current_user.role == "admin":
        token = credentials.credentials if credentials else getattr(current_user, "_token", None)
        if token and token in workspace_sessions:
            return workspace_sessions[token]
    return normalize_collaboration_role(current_user.role)


class WorkspaceSwitchRequest(BaseModel):
    role: str


@app.post("/api/v1/workspace/switch")
def switch_workspace(
    data: WorkspaceSwitchRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    current_user: User = Depends(get_current_user),
):
    """Switch the server-side active workspace context for the current Admin session."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only Admin can switch workspaces",
        )

    target_role = normalize_collaboration_role(data.role)
    if target_role not in {"admin", "developer", "tester", "senior_dev", "user"}:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid workspace role: {data.role}",
        )

    token = credentials.credentials if credentials else getattr(current_user, "_token", None)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication token required",
        )

    workspace_sessions[token] = target_role

    return {
        "message": f"Workspace switched to {target_role}",
        "workspace_role": target_role,
        "user_id": current_user.id,
        "name": current_user.name,
    }


@app.get("/api/v1/workspace/current")
def get_current_workspace(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    current_user: User = Depends(get_current_user),
):
    """Return the current active workspace role for the authenticated user session."""
    role = get_effective_workspace_role(credentials, current_user)
    return {
        "workspace_role": role,
        "authenticated_role": current_user.role,
        "user_id": current_user.id,
        "name": current_user.name,
    }


ALLOWED_COLLABORATION_ROLES = {
    "admin",
    "developer",
    "tester",
    "senior_dev",
}

WORKING_COLLABORATION_ROLES = {
    "developer",
    "tester",
    "senior_dev",
}

COLLABORATION_WORK_CONFIG = {
    "developer": {
        "work_type": "Development & Issue Resolution",
        "statuses": {
            "NOT_STARTED": 0,
            "IN_PROGRESS": 50,
            "COMPLETED": 100,
            "BLOCKED": None,
        },
    },
    "tester": {
        "work_type": "Testing & Verification",
        "statuses": {
            "NOT_STARTED": 0,
            "IN_TESTING": 50,
            "PASSED": 100,
            "FAILED": 50,
            "BLOCKED": None,
        },
    },
    "senior_dev": {
        "work_type": "Technical Review & Support",
        "statuses": {
            "NOT_STARTED": 0,
            "IN_REVIEW": 50,
            "CHANGES_REQUESTED": 50,
            "APPROVED": 100,
            "BLOCKED": None,
        },
    },
}

ASSIGNMENT_REQUIRED_ROLES = [
    "developer",
    "tester",
    "senior_dev",
]

COLLABORATION_ROLE_USERS = {
    "admin": {"name": "Naruto", "role_title": "Admin"},
    "developer": {"name": "Sasuke", "role_title": "Developer"},
    "tester": {"name": "Hinata", "role_title": "Tester"},
    "senior_dev": {"name": "Itachi", "role_title": "Senior Developer"},
}


def get_saved_assignment_states(issue_id: int, roles: list[str], db: Session) -> dict[str, str]:
    """Read the latest assignment acceptance/rejection state for each collaboration role.

    States:
    - PENDING: Assigned but has not accepted or rejected yet.
    - ACCEPTED: Role has explicitly accepted the assignment.
    - REJECTED: Role has explicitly rejected the assignment.
    """
    latest_team_log = (
        db.query(AuditLog)
        .filter(
            AuditLog.issue_id == issue_id,
            AuditLog.action.like("TEAM_UPDATED:%"),
        )
        .order_by(AuditLog.id.desc())
        .first()
    )

    query = db.query(AuditLog).filter(
        AuditLog.issue_id == issue_id,
        AuditLog.action.like("ASSIGNMENT_RESPONSE:%"),
    )
    if latest_team_log:
        query = query.filter(AuditLog.id >= latest_team_log.id)

    logs = query.order_by(AuditLog.id.desc()).all()

    states = {role: "PENDING" for role in ASSIGNMENT_REQUIRED_ROLES}
    found = set()

    for log in logs:
        parts = log.action.split(":")
        if len(parts) >= 3:
            r = normalize_collaboration_role(parts[1])
            st = parts[2].strip().upper()
            if r in states and r not in found:
                if st in {"ACCEPTED", "REJECTED"}:
                    states[r] = st
                    found.add(r)

    return states


def can_resolve_issue(issue_id: int, roles: list[str], db: Session) -> bool:
    """Return True only if ALL THREE required roles (developer, tester, senior_dev) have accepted."""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        return False
    if issue_status_value(issue.status).upper() in {"RESOLVED", "CLOSED"}:
        return False
    norm_roles = [normalize_collaboration_role(r) for r in roles]
    for req in ASSIGNMENT_REQUIRED_ROLES:
        if req not in norm_roles:
            return False
    states = get_saved_assignment_states(issue.id, roles, db)
    return all(states.get(req) == "ACCEPTED" for req in ASSIGNMENT_REQUIRED_ROLES)


def get_saved_collaboration_roles(issue_id: int, db: Session) -> list[str]:
    """Read the latest saved collaboration team from existing AuditLog data.

    No new table or schema is required. Team changes are stored as audit
    events using the existing audit_logs table.
    """
    logs = (
        db.query(AuditLog)
        .filter(
            AuditLog.issue_id == issue_id,
            AuditLog.action.like("TEAM_UPDATED:%"),
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .all()
    )

    if not logs:
        return []

    latest = logs[0].action
    _, _, raw_roles = latest.partition(":")

    roles = []
    for raw_role in raw_roles.split(","):
        role = normalize_collaboration_role(raw_role)
        if role in ALLOWED_COLLABORATION_ROLES and role not in roles:
            roles.append(role)

    return roles


def get_saved_work_states(issue_id: int, db: Session) -> dict[str, dict]:
    """Read the latest persisted work state for each collaboration role."""
    logs = (
        db.query(AuditLog)
        .filter(
            AuditLog.issue_id == issue_id,
            AuditLog.action.like("WORK_UPDATED:%"),
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .all()
    )

    states = {}
    for log in logs:
        parts = log.action.split(":", 3)
        if len(parts) < 4:
            continue

        _, role, status, progress = parts
        role = normalize_collaboration_role(role)
        if role not in WORKING_COLLABORATION_ROLES or role in states:
            continue

        try:
            progress_value = max(0, min(100, int(progress)))
        except ValueError:
            continue

        states[role] = {
            "status": status,
            "progress": progress_value,
            "updated_at": log.created_at,
            "updated_by": log.user.name if log.user else None,
        }

    return states


def collaboration_work_snapshot(issue_id: int, roles: list[str], db: Session):
    states = get_saved_work_states(issue_id, db)
    required_roles = [role for role in roles if role in WORKING_COLLABORATION_ROLES]
    workstreams = []

    for role in required_roles:
        config = COLLABORATION_WORK_CONFIG[role]
        state = states.get(role, {
            "status": "NOT_STARTED",
            "progress": 0,
            "updated_at": None,
            "updated_by": None,
        })
        workstreams.append({
            "role": role,
            "work_type": config["work_type"],
            **state,
        })

    overall = (
        round(sum(item["progress"] for item in workstreams) / len(workstreams))
        if workstreams
        else 0
    )
    incomplete_roles = [
        item["role"] for item in workstreams
        if item["progress"] < 100
    ]

    return {
        "required_roles": required_roles,
        "workstreams": workstreams,
        "overall_progress": overall,
        "can_final_approve": not incomplete_roles,
        "incomplete_roles": incomplete_roles,
    }


@app.get("/api/v1/collaboration/issues")
def get_collaboration_issues(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return issues visible to the current collaboration role."""
    issues = (
        db.query(Issue)
        .order_by(Issue.id.asc())
        .all()
    )

    current_role = get_effective_workspace_role(credentials, current_user)
    result = []

    for issue in issues:
        roles = get_saved_collaboration_roles(issue.id, db)

        # Admin can see every collaboration issue. Other roles only see
        # issues where that role was selected by Admin.
        if current_role != "admin" and current_role not in roles:
            continue

        assignment_states = get_saved_assignment_states(issue.id, roles, db)
        can_res = can_resolve_issue(issue.id, roles, db)

        result.append({
            "id": issue.id,
            "issue_key": issue.issue_key,
            "title": issue.title,
            "description": issue.description,
            "priority": issue.priority,
            "severity": issue.severity,
            "status": issue.status,
            "reporter_id": issue.reporter_id,
            "assignee_id": issue.assignee_id,
            "project_key": issue.project_key,
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
            "collaboration_roles": roles,
            "assignment_states": assignment_states,
            "can_resolve": can_res,
            "work_states": get_saved_work_states(issue.id, db),
        })

    return {"issues": result}


@app.get("/api/v1/collaboration/issues/{issue_id}/team")
def get_collaboration_team(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the saved collaboration roles for an issue."""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    roles = get_saved_collaboration_roles(issue_id, db)
    assignment_states = get_saved_assignment_states(issue_id, roles, db)
    can_res = can_resolve_issue(issue_id, roles, db)

    return {
        "issue_id": issue_id,
        "roles": roles,
        "assignment_states": assignment_states,
        "can_resolve": can_res,
    }


@app.put("/api/v1/collaboration/issues/{issue_id}/team")
def save_collaboration_team(
    issue_id: int,
    data: CollaborationTeamRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save an issue's collaboration team using the existing audit log."""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    # Team membership is an Admin-controlled operation.
    current_role = normalize_collaboration_role(current_user.role)
    if current_role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only Admin can update the collaboration team",
        )

    normalized_roles = []
    for raw_role in data.roles:
        role = normalize_collaboration_role(raw_role)

        if role not in ALLOWED_COLLABORATION_ROLES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported collaboration role: {raw_role}",
            )

        if role not in normalized_roles:
            normalized_roles.append(role)

    if len(normalized_roles) < 2:
        raise HTTPException(
            status_code=400,
            detail="Select at least 2 roles for collaboration",
        )

    if len(normalized_roles) > 4:
        raise HTTPException(
            status_code=400,
            detail="A maximum of 4 roles can be selected for collaboration",
        )

    # Preserve the selected order while storing the team in the existing
    # audit_logs table. No database schema changes are required.
    current_status = issue_status_value(issue.status)
    action_text = "TEAM_UPDATED: " + ",".join(normalized_roles)

    audit = AuditLog(
        issue_id=issue.id,
        user_id=current_user.id,
        action=action_text,
        old_status=current_status,
        new_status=current_status,
    )

    db.add(audit)
    db.commit()
    db.refresh(audit)

    states = get_saved_assignment_states(issue_id, normalized_roles, db)
    can_res = can_resolve_issue(issue_id, normalized_roles, db)

    return {
        "message": "Collaboration team saved",
        "issue_id": issue_id,
        "roles": normalized_roles,
        "assignment_states": states,
        "can_resolve": can_res,
        "activity_id": audit.id,
    }


@app.get("/api/v1/collaboration/issues/{issue_id}/work")
def get_collaboration_work(
    issue_id: int,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return persisted role work and progress for one shared issue."""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    roles = get_saved_collaboration_roles(issue_id, db)
    current_role = get_effective_workspace_role(credentials, current_user)
    if current_user.role != "admin" and current_role != "admin" and current_role not in roles:
        raise HTTPException(
            status_code=403,
            detail="You are not a member of this collaboration team",
        )

    states = get_saved_assignment_states(issue_id, roles, db)
    can_res = can_resolve_issue(issue_id, roles, db)

    return {
        "issue_id": issue_id,
        "assignment_states": states,
        "can_resolve": can_res,
        **collaboration_work_snapshot(issue_id, roles, db),
    }


@app.put("/api/v1/collaboration/issues/{issue_id}/work")
def update_collaboration_work(
    issue_id: int,
    data: CollaborationWorkRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist one selected role's work state in the existing audit log."""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    roles = get_saved_collaboration_roles(issue_id, db)

    # 1. Normalize submitted status (handle "Changes Requested", "CHANGES_REQUESTED", etc.)
    status_raw = data.status.strip().upper()
    status = status_raw.replace(" ", "_").replace("-", "_")

    # 2. Determine target role
    target_role = None
    if data.role:
        candidate = normalize_collaboration_role(data.role)
        if candidate in WORKING_COLLABORATION_ROLES:
            target_role = candidate

    if not target_role and data.work_type:
        for r, cfg in COLLABORATION_WORK_CONFIG.items():
            if cfg["work_type"].lower() == data.work_type.strip().lower():
                target_role = r
                break

    if not target_role:
        hdr = request.headers.get("X-Workspace-Role") or request.headers.get("x-role")
        if hdr:
            candidate = normalize_collaboration_role(hdr)
            if candidate in WORKING_COLLABORATION_ROLES:
                target_role = candidate

    if not target_role:
        referer = (request.headers.get("referer") or "").lower()
        if "senior-developer" in referer or "senior-dev" in referer:
            target_role = "senior_dev"
        elif "tester" in referer:
            target_role = "tester"
        elif "developer" in referer:
            target_role = "developer"

    if not target_role:
        # Match statuses uniquely defined for a specific role
        sr_statuses = (
            set(COLLABORATION_WORK_CONFIG["senior_dev"]["statuses"])
            - set(COLLABORATION_WORK_CONFIG["developer"]["statuses"])
            - set(COLLABORATION_WORK_CONFIG["tester"]["statuses"])
        )
        tester_statuses = (
            set(COLLABORATION_WORK_CONFIG["tester"]["statuses"])
            - set(COLLABORATION_WORK_CONFIG["developer"]["statuses"])
            - set(COLLABORATION_WORK_CONFIG["senior_dev"]["statuses"])
        )
        dev_statuses = (
            set(COLLABORATION_WORK_CONFIG["developer"]["statuses"])
            - set(COLLABORATION_WORK_CONFIG["tester"]["statuses"])
            - set(COLLABORATION_WORK_CONFIG["senior_dev"]["statuses"])
        )

        if status in sr_statuses:
            target_role = "senior_dev"
        elif status in tester_statuses:
            target_role = "tester"
        elif status in dev_statuses:
            target_role = "developer"

    if not target_role:
        target_role = get_effective_workspace_role(credentials, current_user)

    # 3. Authorization check
    if current_user.role == "admin":
        if target_role not in WORKING_COLLABORATION_ROLES:
            raise HTTPException(
                status_code=403,
                detail="Only Developer, Tester, or Senior Developer can update work",
            )
        # Keep admin workspace session in sync
        token = credentials.credentials if credentials else getattr(current_user, "_token", None)
        if token:
            workspace_sessions[token] = target_role
    else:
        user_role = normalize_collaboration_role(current_user.role)
        if user_role not in WORKING_COLLABORATION_ROLES:
            raise HTTPException(
                status_code=403,
                detail="Only Developer, Tester, or Senior Developer can update work",
            )
        if user_role != target_role:
            raise HTTPException(
                status_code=403,
                detail=f"You do not have permission to update work for {target_role}",
            )

    # 4. Check if role is in collaboration team for this issue
    if target_role not in roles:
        raise HTTPException(
            status_code=403,
            detail="Your role is not selected for this collaboration issue",
        )

    # 5. Role-specific status validation
    status_progress = COLLABORATION_WORK_CONFIG[target_role]["statuses"]
    if status not in status_progress:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid {target_role} work status. Allowed values: "
                + ", ".join(status_progress)
            ),
        )

    # 6. Progress mapping
    previous = get_saved_work_states(issue_id, db).get(target_role)
    progress = status_progress[status]
    if progress is None:
        progress = previous["progress"] if previous else 0

    # 7. Audit log persistence
    current_status = issue_status_value(issue.status)
    audit = AuditLog(
        issue_id=issue.id,
        user_id=current_user.id,
        action=f"WORK_UPDATED:{target_role}:{status}:{progress}",
        old_status=current_status,
        new_status=current_status,
    )
    db.add(audit)

    if data.note and data.note.strip():
        db.add(AuditLog(
            issue_id=issue.id,
            user_id=current_user.id,
            action=f"WORK_NOTE:{target_role}:{data.note.strip()[:70]}",
            old_status=current_status,
            new_status=current_status,
        ))

    db.commit()
    db.refresh(audit)

    snapshot = collaboration_work_snapshot(issue_id, roles, db)
    return {
        "message": "Work progress saved",
        "issue_id": issue_id,
        "role": target_role,
        "status": status,
        "progress": progress,
        **snapshot,
    }


@app.get("/api/v1/collaboration/users")
def get_collaboration_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return project users who can participate in issue collaboration."""
    users = (
        db.query(User)
        .filter(
            User.role.in_(
                ["admin", "tester", "developer", "senior_dev",
                 "senior_developer"]
            )
        )
        .order_by(User.id.asc())
        .all()
    )

    return {
        "users": [
            {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
            }
            for user in users
        ]
    }


@app.post("/api/v1/collaboration/issues/{issue_id}/assignment")
def assign_collaboration_issue(
    issue_id: int,
    data: CollaborationAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Assign or reassign an existing issue and record the activity."""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    new_user = None
    if data.assignee_id is not None:
        new_user = db.query(User).filter(User.id == data.assignee_id).first()
        if not new_user:
            raise HTTPException(status_code=404, detail="Assignee not found")

    old_user_id = issue.assignee_id
    issue.assignee_id = data.assignee_id

    if old_user_id == data.assignee_id:
        db.commit()
        return {
            "message": "Issue assignment unchanged",
            "issue_id": issue.id,
            "assignee_id": issue.assignee_id,
        }

    action = "ISSUE_REASSIGNED" if old_user_id else "ISSUE_ASSIGNED"
    current_status = issue_status_value(issue.status)

    audit = AuditLog(
        issue_id=issue.id,
        user_id=current_user.id,
        action=action,
        old_status=current_status,
        new_status=current_status,
    )
    db.add(audit)
    db.commit()
    db.refresh(issue)
    db.refresh(audit)

    return {
        "message": (
            f"Issue reassigned to {new_user.name}"
            if new_user and old_user_id
            else f"Issue assigned to {new_user.name}"
            if new_user
            else "Issue assignment cleared"
        ),
        "issue_id": issue.id,
        "assignee_id": issue.assignee_id,
        "assignee_name": new_user.name if new_user else None,
        "activity_id": audit.id,
    }


@app.post("/api/v1/collaboration/issues/{issue_id}/action")
def collaboration_issue_action(
    issue_id: int,
    data: CollaborationActionRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record collaboration actions such as escalation, approval, acceptance, rejection, and resolution."""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()

    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    action = data.action.strip().upper()

    allowed_actions = {
        "ESCALATE",
        "REQUEST_APPROVAL",
        "APPROVE",
        "REJECT_APPROVAL",
        "RESOLVE",
        "ACCEPT",
        "REJECT",
        "ACCEPT_ASSIGNMENT",
        "REJECT_ASSIGNMENT",
    }

    if action not in allowed_actions:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid collaboration action. Allowed actions: "
                + ", ".join(sorted(allowed_actions))
            ),
        )

    if action in {"ACCEPT", "REJECT", "ACCEPT_ASSIGNMENT", "REJECT_ASSIGNMENT"}:
        resp_data = CollaborationAssignmentResponseRequest(
            action="ACCEPT" if "ACCEPT" in action else "REJECT",
            role=data.role,
            note=data.note,
        )
        return respond_collaboration_assignment(
            issue_id=issue_id,
            data=resp_data,
            request=request,
            credentials=credentials,
            db=db,
            current_user=current_user,
        )

    if action == "RESOLVE":
        return resolve_collaboration_issue(
            issue_id=issue_id,
            credentials=credentials,
            db=db,
            current_user=current_user,
        )

    if action == "APPROVE":
        current_role = normalize_collaboration_role(current_user.role)
        if current_role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Only Admin can approve a collaboration issue",
            )

        roles = get_saved_collaboration_roles(issue_id, db)
        progress = collaboration_work_snapshot(issue_id, roles, db)
        if not progress["can_final_approve"]:
            incomplete = ", ".join(
                role.replace("_", " ").title()
                for role in progress["incomplete_roles"]
            )
            raise HTTPException(
                status_code=400,
                detail=f"Required team work is not complete: {incomplete}",
            )

    # Keep the action and optional note together in the existing audit log.
    action_text = action
    if data.note and data.note.strip():
        action_text = f"{action}: {data.note.strip()}"

    current_status = issue_status_value(issue.status)

    audit = AuditLog(
        issue_id=issue.id,
        user_id=current_user.id,
        action=action_text,
        old_status=current_status,
        new_status=current_status,
    )

    db.add(audit)
    db.commit()
    db.refresh(audit)

    return {
        "message": f"{action.replace('_', ' ').title()} recorded successfully",
        "issue_id": issue.id,
        "action": action,
        "activity_id": audit.id,
        "created_at": audit.created_at,
    }


@app.post("/api/v1/collaboration/issues/{issue_id}/assignment-response")
@app.post("/api/v1/collaboration/issues/{issue_id}/assignment/response")
def respond_collaboration_assignment(
    issue_id: int,
    data: CollaborationAssignmentResponseRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Handle role Accept or Reject of issue assignment.
    
    CRITICAL: Accept or Reject changes only that role's assignment state
    (ACCEPTED or REJECTED). The issue itself must NOT become Resolved.
    """
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    roles = get_saved_collaboration_roles(issue_id, db)

    # 1. Determine target role
    target_role = None
    if data.role:
        candidate = normalize_collaboration_role(data.role)
        if candidate in WORKING_COLLABORATION_ROLES:
            target_role = candidate

    if not target_role:
        hdr = request.headers.get("X-Workspace-Role") or request.headers.get("x-role")
        if hdr:
            candidate = normalize_collaboration_role(hdr)
            if candidate in WORKING_COLLABORATION_ROLES:
                target_role = candidate

    if not target_role:
        referer = (request.headers.get("referer") or "").lower()
        if "senior-developer" in referer or "senior-dev" in referer:
            target_role = "senior_dev"
        elif "tester" in referer:
            target_role = "tester"
        elif "developer" in referer:
            target_role = "developer"

    if not target_role:
        target_role = get_effective_workspace_role(credentials, current_user)

    if target_role not in WORKING_COLLABORATION_ROLES:
        raise HTTPException(
            status_code=400,
            detail="Role must be developer, tester, or senior_dev",
        )

    # 2. Authorization check: Non-admin users can only respond for their own role
    if current_user.role != "admin":
        user_role = normalize_collaboration_role(current_user.role)
        if user_role != target_role:
            raise HTTPException(
                status_code=403,
                detail=f"You do not have permission to respond for {target_role}",
            )

    # 3. Check role is assigned to this issue
    if target_role not in roles:
        if current_user.role == "admin":
            new_roles = list(roles) + [target_role]
            save_audit = AuditLog(
                issue_id=issue.id,
                user_id=current_user.id,
                action="TEAM_UPDATED: " + ",".join(new_roles),
                old_status=issue_status_value(issue.status),
                new_status=issue_status_value(issue.status),
            )
            db.add(save_audit)
            db.commit()
            roles = new_roles
        else:
            raise HTTPException(
                status_code=400,
                detail=f"{target_role.replace('_', ' ').title()} is not assigned to this issue",
            )

    # 4. Normalize action
    raw_action = data.action.strip().upper()
    if raw_action in {"ACCEPT", "ACCEPTED", "ACCEPT_ASSIGNMENT"}:
        state = "ACCEPTED"
    elif raw_action in {"REJECT", "REJECTED", "REJECT_ASSIGNMENT"}:
        state = "REJECTED"
    else:
        raise HTTPException(
            status_code=400,
            detail="Action must be ACCEPT or REJECT",
        )

    # 5. Persist assignment response in audit log
    current_status = issue_status_value(issue.status)
    action_text = f"ASSIGNMENT_RESPONSE:{target_role}:{state}"
    if data.note and data.note.strip():
        action_text += f": {data.note.strip()[:60]}"

    audit = AuditLog(
        issue_id=issue.id,
        user_id=current_user.id,
        action=action_text,
        old_status=current_status,
        new_status=current_status,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)

    # CRITICAL: Issue itself must NOT become Resolved!
    states = get_saved_assignment_states(issue_id, roles, db)
    can_res = can_resolve_issue(issue_id, roles, db)

    role_user_info = COLLABORATION_ROLE_USERS.get(target_role, {})
    user_display = role_user_info.get("name", target_role.title())

    return {
        "message": f"{target_role.replace('_', ' ').title()} ({user_display}) assignment {state.lower()}",
        "issue_id": issue.id,
        "role": target_role,
        "assigned_user": user_display,
        "assignment_state": state,
        "assignment_states": states,
        "can_resolve": can_res,
        "issue_status": current_status,
        "activity_id": audit.id,
    }


@app.post("/api/v1/collaboration/issues/{issue_id}/resolve")
def resolve_collaboration_issue(
    issue_id: int,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin clicks Resolve: issue becomes RESOLVED only after all 3 roles have ACCEPTED."""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    eff_role = get_effective_workspace_role(credentials, current_user)
    if current_user.role != "admin" and eff_role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only Admin can resolve the issue",
        )

    roles = get_saved_collaboration_roles(issue_id, db)
    states = get_saved_assignment_states(issue_id, roles, db)

    for req in ASSIGNMENT_REQUIRED_ROLES:
        if req not in roles:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot resolve issue: {req.replace('_', ' ').title()} is not assigned to this issue.",
            )
        if states.get(req) != "ACCEPTED":
            rejected_or_pending = states.get(req, "PENDING")
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot resolve issue: Developer, Tester, and Senior Developer must all accept the assignment first. "
                    f"({req.replace('_', ' ').title()} is {rejected_or_pending})"
                ),
            )

    old_status = issue_status_value(issue.status)
    if old_status.upper() in {"RESOLVED", "CLOSED"}:
        return {
            "message": "Issue is already resolved",
            "issue_id": issue.id,
            "status": old_status,
        }

    issue.status = IssueStatus.RESOLVED

    audit = AuditLog(
        issue_id=issue.id,
        user_id=current_user.id,
        action="RESOLVED",
        old_status=old_status,
        new_status="RESOLVED",
    )
    db.add(audit)
    db.commit()
    db.refresh(issue)
    db.refresh(audit)

    return {
        "message": "Issue resolved successfully",
        "issue_id": issue.id,
        "old_status": old_status,
        "new_status": "RESOLVED",
        "status": "RESOLVED",
        "audit_log_id": audit.id,
    }


@app.get("/api/v1/collaboration/attachments/{attachment_id}/download")
def download_collaboration_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Open/download an existing issue attachment."""
    attachment = (
        db.query(Attachment)
        .filter(Attachment.id == attachment_id)
        .first()
    )

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    path = Path(attachment.file_path)

    if not path.exists() or not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Attachment file is no longer available",
        )

    return FileResponse(
        path=str(path),
        filename=attachment.filename,
        media_type="application/octet-stream",
    )


# =========================================================
# MODULE 2 - SMART DEVELOPER MATCHER
# =========================================================

class DeveloperMatcherRequest(BaseModel):
    title: str
    description: str


# Developer skill profiles.
# Kept separate from the existing database so Module 1
# database structure is not changed.
DEVELOPER_PROFILES = [
    {
        "name": "John",
        "skills": [
            "python",
            "postgresql",
            "database",
            "backend",
            "sql",
            "api",
        ],
    },
    {
        "name": "Alice",
        "skills": [
            "react",
            "javascript",
            "css",
            "html",
            "ui",
            "frontend",
        ],
    },
    {
        "name": "Bob",
        "skills": [
            "python",
            "fastapi",
            "api",
            "backend",
            "javascript",
        ],
    },
    {
        "name": "Charlie",
        "skills": [
            "testing",
            "qa",
            "automation",
            "selenium",
            "bug",
        ],
    },
]


# Keywords that indicate a particular technical skill.
SKILL_KEYWORDS = {
    "database": [
        "database",
        "db",
        "sql",
        "postgresql",
        "postgres",
        "mysql",
        "oracle",
        "query",
        "connection",
        "timeout",
    ],
    "python": [
        "python",
        "django",
        "flask",
        "fastapi",
    ],
    "backend": [
        "backend",
        "server",
        "api",
        "endpoint",
        "authentication",
        "login",
    ],
    "api": [
        "api",
        "endpoint",
        "rest",
        "request",
        "response",
    ],
    "frontend": [
        "frontend",
        "react",
        "javascript",
        "html",
        "css",
        "page",
        "browser",
    ],
    "react": [
        "react",
        "component",
        "jsx",
    ],
    "css": [
        "css",
        "style",
        "styling",
        "color",
        "layout",
        "alignment",
    ],
    "testing": [
        "test",
        "testing",
        "qa",
        "automation",
        "selenium",
    ],
}


def detect_required_skills(text: str) -> list[str]:
    """Analyze issue title and description and identify relevant skills."""
    text_lower = text.lower()
    detected_skills = []

    for skill, keywords in SKILL_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                detected_skills.append(skill)
                break

    return detected_skills


def calculate_developer_match(
    developer: dict,
    required_skills: list[str],
    active_task_count: int,
):
    """Calculate developer match percentage with workload adjustment."""
    developer_skills = {
        skill.lower()
        for skill in developer["skills"]
    }

    matching_skills = [
        skill
        for skill in required_skills
        if skill in developer_skills
    ]

    if required_skills:
        skill_match_percentage = (
            len(matching_skills)
            / len(required_skills)
        ) * 100
    else:
        skill_match_percentage = 0

    # More active tasks slightly reduce the recommendation score.
    workload_penalty = min(active_task_count * 5, 25)

    final_match = max(
        0,
        round(skill_match_percentage - workload_penalty),
    )

    if matching_skills:
        explanation = (
            f"Matches skills: {', '.join(matching_skills)}. "
            f"Currently has {active_task_count} active task(s)."
        )
    else:
        explanation = (
            f"No direct skill match found. "
            f"Currently has {active_task_count} active task(s)."
        )

    return {
        "name": developer["name"],
        "match_percentage": final_match,
        "matching_skills": matching_skills,
        "active_task_count": active_task_count,
        "explanation": explanation,
    }


@app.post("/api/v1/issues/developer-matcher")
def developer_matcher(
    data: DeveloperMatcherRequest,
    db: Session = Depends(get_db),
):
    """Module 2 Part 2: Smart Developer Matcher."""
    combined_text = f"{data.title} {data.description}"

    required_skills = detect_required_skills(combined_text)
    recommendations = []

    for developer in DEVELOPER_PROFILES:
        # If the profile exists in the database, use the actual
        # active defect count. Otherwise use zero for the demo profile.
        user = (
            db.query(User)
            .filter(User.name.ilike(developer["name"]))
            .first()
        )

        active_task_count = 0

        if user:
            active_task_count = (
                db.query(Defect)
                .filter(
                    Defect.assigned_user_id == user.id,
                    Defect.status.notin_(["Resolved", "Rejected"]),
                )
                .count()
            )

        result = calculate_developer_match(
            developer,
            required_skills,
            active_task_count,
        )
        recommendations.append(result)

    # Highest match first; lower workload wins ties.
    recommendations.sort(
        key=lambda item: (
            -item["match_percentage"],
            item["active_task_count"],
        )
    )

    return {
        "issue_title": data.title,
        "detected_skills": required_skills,
        "recommendations": recommendations[:3],
    }


# =========================================================
# MODULE 2 - PART 4: SPRINT PLANNING & BACKLOG
# =========================================================

ALLOWED_SPRINT_STATUSES = {"PLANNING", "ACTIVE", "COMPLETED"}


def sprint_response(sprint: Sprint, db: Session):
    """Return sprint details, progress, velocity, and its issues."""

    links = (
        db.query(SprintIssue)
        .filter(SprintIssue.sprint_id == sprint.id)
        .all()
    )

    issue_ids = [link.issue_id for link in links]

    issues = []
    if issue_ids:
        issues = (
            db.query(Issue)
            .filter(Issue.id.in_(issue_ids))
            .order_by(Issue.id)
            .all()
        )

    total_issues = len(issues)

    completed_issues = sum(
        1
        for issue in issues
        if issue.status in {IssueStatus.RESOLVED, IssueStatus.CLOSED}
    )

    progress_percentage = (
        round((completed_issues / total_issues) * 100)
        if total_issues
        else 0
    )

    velocity = (
        completed_issues
        if sprint.status.upper() == "COMPLETED"
        else None
    )

    return {
        "id": sprint.id,
        "sprint_name": sprint.sprint_name,
        "goal": sprint.goal,
        "start_date": sprint.start_date,
        "end_date": sprint.end_date,
        "status": sprint.status,
        "assigned_role": sprint.assigned_role,
        "total_issues": total_issues,
        "completed_issues": completed_issues,
        "progress_percentage": progress_percentage,
        "velocity": velocity,
        "issues": [
            {
                "id": issue.id,
                "issue_key": issue.issue_key,
                "title": issue.title,
                "status": issue.status,
                "priority": issue.priority,
                "assignee_id": issue.assignee_id,
            }
            for issue in issues
        ],
    }


@app.post("/api/v1/sprints/")
def create_sprint(
    data: SprintCreate,
    db: Session = Depends(get_db),
):
    """Create a new Agile sprint."""

    sprint_name = data.sprint_name.strip()

    if not sprint_name:
        raise HTTPException(
            status_code=400,
            detail="Sprint name cannot be empty",
        )

    status = data.status.strip().upper()

    if status not in ALLOWED_SPRINT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail="Status must be PLANNING, ACTIVE, or COMPLETED",
        )

    if data.start_date and data.end_date and data.end_date < data.start_date:
        raise HTTPException(
            status_code=400,
            detail="End date cannot be before start date",
        )

    existing = (
        db.query(Sprint)
        .filter(Sprint.sprint_name.ilike(sprint_name))
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Sprint name already exists",
        )

    sprint = Sprint(
        sprint_name=sprint_name,
        goal=data.goal.strip() if data.goal else None,
        start_date=data.start_date,
        end_date=data.end_date,
        status=status,
        assigned_role=None,
    )

    db.add(sprint)
    db.commit()
    db.refresh(sprint)

    return sprint_response(sprint, db)


@app.post("/api/v1/sprints/{sprint_id}/assign")
def assign_sprint(
    sprint_id: int,
    data: SprintAssignRequest,
    db: Session = Depends(get_db),
):
    """Assign a sprint to the Tester, Developer, or Senior Developer role."""

    allowed_roles = {"tester", "developer", "senior_dev"}
    role = data.assigned_role.strip().lower()

    if role not in allowed_roles:
        raise HTTPException(
            status_code=400,
            detail="Sprint can be assigned only to tester, developer, or senior_dev",
        )

    sprint = db.query(Sprint).filter(Sprint.id == sprint_id).first()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")

    if sprint.status.upper() == "COMPLETED":
        raise HTTPException(status_code=400, detail="Cannot assign a completed sprint")

    sprint.assigned_role = role
    db.commit()
    db.refresh(sprint)

    return {
        "message": "Sprint assigned successfully",
        "sprint_id": sprint.id,
        "sprint_name": sprint.sprint_name,
        "assigned_role": sprint.assigned_role,
    }


@app.get("/api/v1/sprints/assigned/{role}")
def get_assigned_sprints(
    role: str,
    db: Session = Depends(get_db),
):
    """
    Return sprints assigned by Admin to one project role.

    Canonical role values:
      - tester
      - developer
      - senior_dev
    """

    role_key = role.strip().lower()

    role_aliases = {
        "tester": "tester",
        "developer": "developer",
        "senior_dev": "senior_dev",
        "senior-developer": "senior_dev",
        "senior_developer": "senior_dev",
        "senior developer": "senior_dev",
        "senior dev": "senior_dev",
    }

    canonical_role = role_aliases.get(role_key)

    if canonical_role is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid role. Allowed roles: "
                "tester, developer, senior_dev"
            ),
        )

    sprints = (
        db.query(Sprint)
        .filter(Sprint.assigned_role == canonical_role)
        .order_by(Sprint.id.asc())
        .all()
    )

    return {
        "role": canonical_role,
        "count": len(sprints),
        "sprints": [
            sprint_response(sprint, db)
            for sprint in sprints
        ],
    }


@app.get("/api/v1/sprints/")
def get_sprints(db: Session = Depends(get_db)):
    """Return all sprints with progress and velocity."""

    sprints = db.query(Sprint).order_by(Sprint.id).all()

    return {
        "sprints": [sprint_response(sprint, db) for sprint in sprints]
    }


@app.get("/api/v1/sprints/backlog")
def get_sprint_backlog(
    sprint_id: int | None = None,
    db: Session = Depends(get_db),
):
    """
    Return issues available to add to a sprint.

    When sprint_id is supplied, only issues already linked to THAT sprint
    are excluded. An issue that belongs to another sprint can therefore be
    added to the selected sprint as well.
    """

    assigned_issue_ids = set()

    if sprint_id is not None:
        sprint = db.query(Sprint).filter(Sprint.id == sprint_id).first()
        if not sprint:
            raise HTTPException(status_code=404, detail="Sprint not found")

        assigned_issue_ids = {
            row[0]
            for row in (
                db.query(SprintIssue.issue_id)
                .filter(SprintIssue.sprint_id == sprint_id)
                .distinct()
                .all()
            )
        }

    backlog_query = db.query(Issue)

    if assigned_issue_ids:
        backlog_query = backlog_query.filter(
            ~Issue.id.in_(assigned_issue_ids)
        )

    backlog = (
        backlog_query
        .order_by(Issue.created_at.asc(), Issue.id.asc())
        .all()
    )

    return {
        "count": len(backlog),
        "backlog": [
            {
                "id": issue.id,
                "issue_key": issue.issue_key,
                "title": issue.title,
                "description": issue.description,
                "severity": issue.severity,
                "priority": issue.priority,
                "status": issue.status,
                "created_at": issue.created_at,
            }
            for issue in backlog
        ],
    }


@app.post("/api/v1/sprints/{sprint_id}/add-issue/{issue_id}")
def add_issue_to_sprint(
    sprint_id: int,
    issue_id: int,
    db: Session = Depends(get_db),
):
    """Add an issue to a sprint."""

    sprint = (
        db.query(Sprint)
        .filter(Sprint.id == sprint_id)
        .first()
    )

    if not sprint:
        raise HTTPException(
            status_code=404,
            detail="Sprint not found",
        )

    if sprint.status.upper() == "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail="Cannot add issues to a completed sprint",
        )

    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found",
        )

    # An issue may be planned in more than one sprint when the
    # project needs to carry the same work item across sprint planning.
    # Prevent only a duplicate link to the SAME sprint.
    existing_link = (
        db.query(SprintIssue)
        .filter(
            SprintIssue.sprint_id == sprint_id,
            SprintIssue.issue_id == issue_id,
        )
        .first()
    )

    if existing_link:
        raise HTTPException(
            status_code=400,
            detail="Issue is already in this sprint",
        )

    sprint_issue = SprintIssue(
        sprint_id=sprint_id,
        issue_id=issue_id,
        added_at=datetime.utcnow(),
    )

    db.add(sprint_issue)
    db.commit()
    db.refresh(sprint_issue)

    return {
        "message": "Issue added to sprint successfully",
        "sprint_id": sprint_id,
        "sprint_name": sprint.sprint_name,
        "issue_id": issue.id,
        "issue_key": issue.issue_key,
        "issue_title": issue.title,
        "sprint_issue_id": sprint_issue.id,
    }


class SprintIssueCreate(BaseModel):
    issue_key: str
    issue_type: IssueType = IssueType.BUG
    title: str
    description: str
    reproduction_steps: str | None = None
    severity: Severity = Severity.MAJOR
    priority: Priority = Priority.MEDIUM
    status: IssueStatus = IssueStatus.REPORTED
    affected_module: str | None = None
    environment: str | None = None
    project_key: str = "BUGFLOW"
    sprint_id: int


@app.post("/api/v1/sprints/{sprint_id}/create-issue")
def create_issue_in_sprint(
    sprint_id: int,
    data: SprintIssueCreate,
    db: Session = Depends(get_db),
):
    """Create a new issue and immediately add it to the selected sprint."""

    sprint = db.query(Sprint).filter(Sprint.id == sprint_id).first()
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")

    if str(sprint.status).upper() == "COMPLETED":
        raise HTTPException(status_code=400, detail="Cannot add issues to a completed sprint")

    if data.sprint_id != sprint_id:
        raise HTTPException(status_code=400, detail="Sprint mismatch")

    issue_key = data.issue_key.strip()
    title = data.title.strip()
    description = data.description.strip()
    project_key = data.project_key.strip()

    if not issue_key:
        raise HTTPException(status_code=400, detail="Issue key is required")
    if not title:
        raise HTTPException(status_code=400, detail="Issue title is required")
    if not description:
        raise HTTPException(status_code=400, detail="Issue description is required")
    if not project_key:
        raise HTTPException(status_code=400, detail="Project key is required")

    existing = db.query(Issue).filter(Issue.issue_key == issue_key).first()
    if existing:
        raise HTTPException(status_code=400, detail="Issue key already exists")

    admin_user = db.query(User).filter(User.role == "admin").first()
    if not admin_user:
        admin_user = db.query(User).order_by(User.id.asc()).first()
    if not admin_user:
        raise HTTPException(status_code=403, detail="No user available to report the issue")

    issue = Issue(
        issue_key=issue_key,
        issue_type=data.issue_type,
        title=title,
        description=description,
        reproduction_steps=data.reproduction_steps,
        severity=data.severity,
        priority=data.priority,
        status=data.status,
        affected_module=data.affected_module,
        environment=data.environment,
        project_key=project_key,
        reporter_id=admin_user.id,
        assignee_id=None,
    )

    db.add(issue)
    db.flush()

    sprint_issue = SprintIssue(
        sprint_id=sprint_id,
        issue_id=issue.id,
        added_at=datetime.utcnow(),
    )
    db.add(sprint_issue)

    try:
        db.commit()
        db.refresh(issue)
        db.refresh(sprint_issue)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Could not create issue in sprint: {exc}",
        ) from exc

    return {
        "message": "Issue created and added to sprint successfully",
        "issue_id": issue.id,
        "issue_key": issue.issue_key,
        "issue_title": issue.title,
        "sprint_id": sprint.id,
        "sprint_name": sprint.sprint_name,
    }


# =========================================================
# MODULE 2 - WORKFLOW TRANSITIONS & AUDIT LOG
# =========================================================

WORKFLOW_STATUSES = [
    "REPORTED",
    "TRIAGED",
    "IN_PROGRESS",
    "QA_VERIFICATION",
    "RESOLVED",
    "CLOSED",
]

ALLOWED_WORKFLOW_TRANSITIONS = {
    "REPORTED": "TRIAGED",
    "TRIAGED": "IN_PROGRESS",
    "IN_PROGRESS": "QA_VERIFICATION",
    "QA_VERIFICATION": "RESOLVED",
    "RESOLVED": "CLOSED",
}


def issue_status_value(status) -> str:
    """Return an IssueStatus enum or string as a plain status value."""
    return getattr(status, "value", status)


@app.post("/api/v1/issues/{issue_id}/status")
def update_issue_status(
    issue_id: int,
    data: WorkflowStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move an issue through the Module 2 workflow and create an audit log."""

    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found",
        )

    new_status = data.status.strip().upper()

    if new_status not in WORKFLOW_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid workflow status. Allowed values: "
                + ", ".join(WORKFLOW_STATUSES)
            ),
        )

    old_status = issue_status_value(issue.status).upper()

    if old_status == new_status:
        raise HTTPException(
            status_code=400,
            detail="Issue is already in this status",
        )

    expected_next = ALLOWED_WORKFLOW_TRANSITIONS.get(old_status)

    if new_status == "RESOLVED":
        current_role = normalize_collaboration_role(current_user.role)
        if current_role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Only Admin can resolve the issue",
            )

        roles = get_saved_collaboration_roles(issue_id, db)
        states = get_saved_assignment_states(issue_id, roles, db)

        for req in ASSIGNMENT_REQUIRED_ROLES:
            if req not in roles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot resolve issue: {req.replace('_', ' ').title()} is not assigned to this issue.",
                )
            if states.get(req) != "ACCEPTED":
                rejected_or_pending = states.get(req, "PENDING")
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Cannot resolve issue: Developer, Tester, and Senior Developer must all accept the assignment first. "
                        f"({req.replace('_', ' ').title()} is {rejected_or_pending})"
                    ),
                )
    else:
        if expected_next != new_status:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid workflow transition: {old_status} -> {new_status}. "
                    f"Expected next status: {expected_next or 'none'}"
                ),
            )

        if new_status == "CLOSED":
            roles = get_saved_collaboration_roles(issue_id, db)
            progress = collaboration_work_snapshot(issue_id, roles, db)
            if not progress["can_final_approve"]:
                incomplete = ", ".join(
                    role.replace("_", " ").title()
                    for role in progress["incomplete_roles"]
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Required team work is not complete: {incomplete}",
                )

    try:
        # Assign through the SQLAlchemy enum so the database receives
        # the exact workflow value.
        issue.status = IssueStatus(new_status)

        action_name = "RESOLVED" if new_status == "RESOLVED" else "STATUS_CHANGED"
        audit = AuditLog(
            issue_id=issue.id,
            user_id=current_user.id,
            action=action_name,
            old_status=old_status,
            new_status=new_status,
        )

        db.add(audit)
        db.commit()
        db.refresh(issue)
        db.refresh(audit)

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=(
                "Status change could not be saved. "
                "Make sure the new workflow values exist in the PostgreSQL "
                f"IssueStatus enum. Details: {exc}"
            ),
        )

    return {
        "message": "Issue status updated successfully",
        "issue_id": issue.id,
        "issue_key": issue.issue_key,
        "changed_by": current_user.name,
        "changed_by_user_id": current_user.id,
        "old_status": old_status,
        "new_status": new_status,
        "audit_log_id": audit.id,
        "changed_at": audit.created_at,
    }


@app.get("/api/v1/issues/{issue_id}/audit-log")
def get_issue_audit_log(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the complete status-change history for an issue."""

    issue = (
        db.query(Issue)
        .filter(Issue.id == issue_id)
        .first()
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found",
        )

    logs = (
        db.query(AuditLog)
        .filter(AuditLog.issue_id == issue_id)
        .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
        .all()
    )

    return {
        "issue_id": issue.id,
        "issue_key": issue.issue_key,
        "current_status": issue_status_value(issue.status),
        "audit_history": [
            {
                "audit_log_id": item.id,
                "who": item.user.name if item.user else "Unknown User",
                "user_id": item.user_id,
                "action": item.action,
                "old_status": item.old_status,
                "new_status": item.new_status,
                "when": item.created_at,
            }
            for item in logs
        ],
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "BugFlow API",
    }

# =========================================================
# MODULE 3: REST API LAYER & INTEGRATIONS ROUTER
# =========================================================
from .module3_api import router as module3_router
app.include_router(module3_router)
