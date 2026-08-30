from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

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
        String(20),
        nullable=False,
        default="user"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
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

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="Pending"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
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
    # NEW ASSIGNMENT FIELDS
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