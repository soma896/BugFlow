from pathlib import Path
import secrets

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash

from .database import get_db
from .models import (
    AdminAction,
    Defect,
    Issue,
    IssueStatus,
    IssueType,
    Priority,
    Severity,
    User,
)


# =========================================================
# APP
# =========================================================

app = FastAPI(title="BugFlow API")


# =========================================================
# PATHS
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "Frontend"


# =========================================================
# AUTHENTICATION
# =========================================================

security = HTTPBearer(auto_error=False)

# Temporary in-memory sessions
# token -> user_id
sessions: dict[str, int] = {}


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

    return user


def get_admin_user(
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    return current_user


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
    user_id: int
    title: str
    description: str
    category: str
    priority: str
    environment: str | None = None
    reproduction_steps: str | None = None
    expected_result: str | None = None
    actual_result: str | None = None

    # Optional assignment fields.
    # These are used when the current Defect model
    # contains assigned_role and assigned_user_id.
    assigned_role: str | None = None
    assigned_user_id: int | None = None


class AdminActionCreate(BaseModel):
    admin_id: int
    defect_id: int
    action: str


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "message": "BugFlow API is running"
    }


# =========================================================
# FRONTEND PAGES
# =========================================================

@app.get("/login-ui")
def login_ui():
    page = FRONTEND_DIR / "index.html"

    if not page.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Login page not found: {page}",
        )

    return FileResponse(page)


@app.get("/admin-ui")
def admin_ui():
    page = FRONTEND_DIR / "admin.html"

    if not page.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Admin dashboard not found: {page}",
        )

    return FileResponse(page)


@app.get("/user-ui")
def user_ui():
    page = FRONTEND_DIR / "user.html"

    if page.exists():
        return FileResponse(page)

    return HTMLResponse(
        """
        <!DOCTYPE html>
        <html>
        <head>
            <title>BugFlow User Dashboard</title>
        </head>
        <body>
            <h1>BugFlow User Dashboard</h1>
            <p>User dashboard page not found.</p>
        </body>
        </html>
        """
    )


@app.get("/analytics-ui")
def analytics_ui():
    page = FRONTEND_DIR / "analytics.html"

    if not page.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Analytics page not found: {page}",
        )

    return FileResponse(page)


@app.get("/all-defects-ui")
def all_defects_ui():
    """
    Separate All Defects page.

    This route uses all-defects.html when that file exists.
    Keeping the route here allows Dashboard and All Defects
    to remain separate pages.
    """

    page = FRONTEND_DIR / "all-defects.html"

    if not page.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "All Defects page not found. "
                "Create app/Frontend/all-defects.html."
            ),
        )

    return FileResponse(page)


# =========================================================
# LOGIN
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

    return {
        "message": "Login successful",
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
    }


# =========================================================
# LOGOUT
# =========================================================

@app.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    if credentials is None:
        return {
            "message": "Already logged out"
        }

    token = credentials.credentials

    sessions.pop(token, None)

    return {
        "message": "Logout successful"
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
        .filter(
            Issue.issue_key == issue_data.issue_key
        )
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # User can only create a defect for their own account
    if defect_data.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only report defects for your own account",
        )

    # -----------------------------------------------------
    # Base defect data
    # -----------------------------------------------------

    defect_values = {
        "user_id": current_user.id,
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

    # -----------------------------------------------------
    # Assignment fields
    #
    # Your PostgreSQL defects table contains:
    # assigned_role
    # assigned_user_id
    #
    # The getattr/setattr checks keep this endpoint
    # compatible with the existing model while allowing
    # the assignment fields when they are present.
    # -----------------------------------------------------

    if hasattr(Defect, "assigned_role"):
        defect_values["assigned_role"] = (
            defect_data.assigned_role
        )

    if hasattr(Defect, "assigned_user_id"):
        defect_values["assigned_user_id"] = (
            defect_data.assigned_user_id
        )

    defect = Defect(
        **defect_values
    )

    db.add(defect)
    db.commit()
    db.refresh(defect)

    return defect


@app.get("/defects")
def get_defects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Defect)
        .filter(
            Defect.user_id == current_user.id
        )
        .order_by(Defect.id)
        .all()
    )


@app.get("/users/{user_id}/defects")
def get_user_defects(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Normal user can only see own defects
    # Admin can inspect any user's defects
    if (
        current_user.role != "admin"
        and user_id != current_user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="You can only view your own defects",
        )

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
# ASSIGNMENT OPTIONS
# =========================================================

@app.get("/assignment-options")
def get_assignment_options(
    current_user: User = Depends(get_current_user),
):
    """
    These are project assignment choices shown to users.
    They are NOT login roles.

    Login remains email + password only.
    """

    return [
        {
            "value": "admin",
            "name": "System Administrator",
            "role": "Admin",
            "display": "System Administrator (Admin)",
        },
        {
            "value": "senior_dev",
            "name": "John Doe",
            "role": "Senior Developer",
            "display": "John Doe (Senior Developer)",
        },
        {
            "value": "developer",
            "name": "Alex Rivera",
            "role": "Developer",
            "display": "Alex Rivera (Developer)",
        },
        {
            "value": "tester",
            "name": "Bruce Wayne",
            "role": "Tester",
            "display": "Bruce Wayne (Tester)",
        },
    ]


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.get("/admin/dashboard")
def admin_dashboard(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    total_defects = (
        db.query(Defect)
        .count()
    )

    pending = (
        db.query(Defect)
        .filter(
            Defect.status == "Pending"
        )
        .count()
    )

    resolved = (
        db.query(Defect)
        .filter(
            Defect.status == "Resolved"
        )
        .count()
    )

    rejected = (
        db.query(Defect)
        .filter(
            Defect.status == "Rejected"
        )
        .count()
    )

    # Number of defects with an assignment, when
    # the model contains the assignment field.
    assigned = 0

    if hasattr(Defect, "assigned_role"):
        assigned = (
            db.query(Defect)
            .filter(
                Defect.assigned_role.isnot(None),
                Defect.assigned_role != "",
            )
            .count()
        )

    return {
        "total_defects": total_defects,
        "pending": pending,
        "resolved": resolved,
        "rejected": rejected,
        "assigned": assigned,
    }


# =========================================================
# ADMIN DEFECTS
# =========================================================

@app.get("/admin/defects")
def get_admin_defects(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Defect)
        .order_by(Defect.id)
        .all()
    )


# =========================================================
# ADMIN ACTIONS
# =========================================================

@app.post("/admin/actions")
def create_admin_action(
    action_data: AdminActionCreate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    # Prevent admin ID spoofing
    if action_data.admin_id != admin.id:
        raise HTTPException(
            status_code=403,
            detail="Admin ID does not match logged-in admin",
        )

    defect = (
        db.query(Defect)
        .filter(
            Defect.id == action_data.defect_id
        )
        .first()
    )

    if not defect:
        raise HTTPException(
            status_code=404,
            detail="Defect not found",
        )

    action = action_data.action.strip()

    allowed_actions = {
        "Resolved",
        "Rejected",
    }

    if action not in allowed_actions:
        raise HTTPException(
            status_code=400,
            detail="Action must be Resolved or Rejected",
        )

    defect.status = action

    admin_action = AdminAction(
        admin_id=admin.id,
        defect_id=defect.id,
        action=action,
    )

    db.add(admin_action)

    db.commit()

    db.refresh(admin_action)

    return {
        "message":
            "Admin action recorded successfully",

        "defect_id":
            defect.id,

        "new_status":
            defect.status,

        "admin_action_id":
            admin_action.id,
    }


@app.get("/admin/actions")
def get_admin_actions(
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(AdminAction)
        .order_by(AdminAction.id)
        .all()
    )


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "BugFlow API",
    }
