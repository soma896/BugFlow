from datetime import date, datetime
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


# =========================================================
# ISSUE ENUMS
# =========================================================

class IssueType(str, Enum):
    BUG = "BUG"
    FEATURE_REQUEST = "FEATURE_REQUEST"
    ENHANCEMENT = "ENHANCEMENT"
    TECHNICAL_DEBT = "TECHNICAL_DEBT"
    SUPPORT_TICKET = "SUPPORT_TICKET"


class Severity(str, Enum):
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"
    BLOCKER = "BLOCKER"


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class IssueStatus(str, Enum):
    REPORTED = "REPORTED"
    TRIAGED = "TRIAGED"
    IN_PROGRESS = "IN_PROGRESS"
    QA_VERIFICATION = "QA_VERIFICATION"
    ASSIGNED = "ASSIGNED"
    IN_DEVELOPMENT = "IN_DEVELOPMENT"
    IN_REVIEW = "IN_REVIEW"
    IN_TESTING = "IN_TESTING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


# =========================================================
# ISSUES TABLE
# =========================================================

class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    issue_key: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True
    )

    issue_type: Mapped[IssueType] = mapped_column(
        SAEnum(IssueType),
        nullable=False
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    reproduction_steps: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    severity: Mapped[Severity] = mapped_column(
        SAEnum(Severity),
        nullable=False
    )

    priority: Mapped[Priority] = mapped_column(
        SAEnum(Priority),
        nullable=False
    )

    status: Mapped[IssueStatus] = mapped_column(
        SAEnum(IssueStatus),
        nullable=False,
        default=IssueStatus.REPORTED
    )

    affected_module: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    environment: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    screenshot_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )

    project_key: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True
    )

    reporter_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    assignee_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="issue",
        cascade="all, delete-orphan"
    )

    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        back_populates="issue",
        cascade="all, delete-orphan"
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="issue",
        cascade="all, delete-orphan"
    )

    collaboration_roles: Mapped[list["IssueCollaborationRole"]] = relationship(
        "IssueCollaborationRole",
        back_populates="issue",
        cascade="all, delete-orphan"
    )


# =========================================================
# USERS TABLE
# =========================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    role: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="user",
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="user"
    )

    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        back_populates="user"
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user"
    )

    auth_sessions: Mapped[list["AuthSession"]] = relationship(
        "AuthSession",
        back_populates="user",
        cascade="all, delete-orphan"
    )


# =========================================================
# PERSISTENT AUTHENTICATION SESSIONS
# =========================================================

class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="auth_sessions"
    )


# =========================================================
# DEFECTS TABLE
# =========================================================

class Defect(Base):
    __tablename__ = "defects"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )

    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Pending",
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    environment: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True
    )

    reproduction_steps: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    expected_result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    actual_result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # =====================================================
    # AUTOMATIC ASSIGNMENT
    # =====================================================

    assigned_role: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True
    )

    assigned_user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True
    )


# =========================================================
# ADMIN ACTIONS TABLE
# =========================================================

class AdminAction(Base):
    __tablename__ = "admin_actions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    admin_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    defect_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )


# =========================================================
# MODULE 2 - PART 3: COMMENTS TABLE
# =========================================================

class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    comment: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    issue: Mapped["Issue"] = relationship(
        "Issue",
        back_populates="comments"
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="comments"
    )


# =========================================================
# MODULE 2 - PART 3: ATTACHMENTS TABLE
# =========================================================

class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    issue: Mapped["Issue"] = relationship(
        "Issue",
        back_populates="attachments"
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="attachments"
    )


# =========================================================
# MODULE 2 - WORKFLOW AUDIT LOG
# =========================================================

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    old_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    new_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    issue: Mapped["Issue"] = relationship(
        "Issue",
        back_populates="audit_logs"
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="audit_logs"
    )


# =========================================================
# ISSUE-SPECIFIC COLLABORATION ROLES
# =========================================================

class IssueCollaborationRole(Base):
    __tablename__ = "issue_collaboration_roles"
    __table_args__ = (
        UniqueConstraint("issue_id", "role", name="uq_issue_collaboration_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    issue: Mapped["Issue"] = relationship(
        "Issue",
        back_populates="collaboration_roles",
    )


# =========================================================
# MODULE 2 - PART 4: SPRINT PLANNING & BACKLOG
# =========================================================

class Sprint(Base):
    __tablename__ = "sprints"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    sprint_name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True
    )

    goal: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    end_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PLANNING",
        index=True
    )

    assigned_role: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    issues: Mapped[list["SprintIssue"]] = relationship(
        "SprintIssue",
        back_populates="sprint",
        cascade="all, delete-orphan"
    )


class SprintIssue(Base):
    __tablename__ = "sprint_issues"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    sprint_id: Mapped[int] = mapped_column(
        ForeignKey("sprints.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    added_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )

    sprint: Mapped["Sprint"] = relationship(
        "Sprint",
        back_populates="issues"
    )

    issue: Mapped["Issue"] = relationship(
        "Issue"
    )


# =========================================================
# MODULE 3: GITHUB INTEGRATION EVENTS
# =========================================================

class GitHubEvent(Base):
    __tablename__ = "github_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )

    repository: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    sender: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    ref_branch: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    commit_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    commit_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    linked_issue_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True
    )

    linked_defect_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True
    )

    payload_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )


# =========================================================
# MODULE 3: CI/CD SYNCHRONIZATION RUNS
# =========================================================

class CICDRun(Base):
    __tablename__ = "cicd_runs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    pipeline_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )

    pipeline_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    build_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    branch: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    commit_sha: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True
    )

    total_tests: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    passed_tests: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    failed_tests: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    duration_seconds: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    triggered_by: Mapped[str] = mapped_column(
        String(100),
        default="automated",
        nullable=False
    )

    logs: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    auto_defect_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )


# =========================================================
# MODULE 3: INTEGRATION & WORKFLOW NOTIFICATIONS
# =========================================================

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True
    )

    target_role: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    category: Mapped[str] = mapped_column(
        String(50),
        default="SYSTEM",
        nullable=False,
        index=True
    )

    link: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
