#!/usr/bin/env python3
"""Review-only demo data seed script for DevFlow college project demonstration.

This script populates a dedicated SQLite database (devflow_demo.db) with a complete
demonstration scenario featuring two projects, seven role-specific accounts,
and realistic interconnected artifacts suitable for RCIA demonstration.

Usage:
    DATABASE_URL=sqlite:///./devflow_demo.db python -m backend.scripts.seed_review_demo
    or
    DATABASE_URL=sqlite:///./devflow_demo.db python backend/scripts/seed_review_demo.py

SAFETY FEATURES:
- Requires explicit DATABASE_URL environment variable override
- Refuses to run against devflow_local.db (development database)
- Refuses to overwrite an existing database file
- Idempotent: safe to rerun against the same demo database
- Uses only existing ORM models, schema constraints, and service functions
- Never modifies authentication configuration or production secrets

This is a DEVELOPMENT-ONLY utility for review demonstrations. It requires SQLite mode.
"""

import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

# Add the backend directory to the path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.base import Base
from backend.app.db.sqlite_path import get_sqlite_file_path, resolve_sqlite_path
from backend.app.models import auth, core, rcia, traceability  # noqa: F401 - register models
from backend.app.models.auth import Role, User, user_roles
from backend.app.models.core import (
    Bug, Milestone, Project, Requirement, Sprint, Task, TestCase, project_members
)
from backend.app.models.rcia import RequirementChangeRequest
from backend.app.models.traceability import TraceabilityLink
from backend.app.services.auth_service import hash_password, assign_role, ROLE_CATALOG

# =============================================================================
# CONFIGURATION - Demo account credentials and project definitions
# =============================================================================

DEMO_PASSWORD = "demo1234"  # Temporary password for review environment only

# Demo accounts: (email, full_name, global_role)
DEMO_ACCOUNTS = [
    ("admin@demo.local", "Admin User", "admin"),
    ("pm@demo.local", "Project Manager", "project_manager"),
    ("tl@demo.local", "Team Lead", "team_lead"),
    ("dev-a@demo.local", "Developer A", "developer"),
    ("dev-b@demo.local", "Developer B", "developer"),
    ("qa@demo.local", "Tester QA", "tester"),
    ("client@demo.local", "Client User", "client"),
]

# Project A: Identity & Access Platform
PROJECT_A_NAME = "Identity & Access Platform"
PROJECT_A_DESC = (
    "Comprehensive identity and access management platform featuring authentication, "
    "session management, account recovery, access control, multi-factor authentication, "
    "notifications, and audit logging."
)

# Project B: Student Services Portal
PROJECT_B_NAME = "Student Services Portal"
PROJECT_B_DESC = (
    "Student-facing portal for profile management, course registration, timetable "
    "management, notifications, and service requests."
)

# Requirement keys for Project A (Identity & Access Platform)
REQ_KEYS_A = {
    "auth": "IAP-1",
    "session": "IAP-2",
    "recovery": "IAP-3",
    "access": "IAP-4",
    "mfa": "IAP-5",
    "notify": "IAP-6",
    "audit": "IAP-7",
    "password_policy": "IAP-8",
    "oauth": "IAP-9",
    "api_keys": "IAP-10",
    "device_trust": "IAP-11",
    "admin_console": "IAP-12",
}

# Requirement keys for Project B (Student Services Portal)
REQ_KEYS_B = {
    "profile": "SSP-1",
    "registration": "SSP-2",
    "timetable": "SSP-3",
    "notifications": "SSP-4",
    "service_requests": "SSP-5",
    "grades": "SSP-6",
    "payments": "SSP-7",
}

# =============================================================================
# SAFETY CHECKS
# =============================================================================

def validate_demo_database_target() -> str:
    """Validate that we're targeting the correct demo database.

    Returns:
        The resolved SQLite file path for the demo database.

    Raises:
        SystemExit: If safety checks fail.
    """
    db_url = settings.database_url

    if not db_url.startswith("sqlite"):
        print("ERROR: DATABASE_URL must be a SQLite URL for demo seeding.", file=sys.stderr)
        print(f"  Current: {db_url}", file=sys.stderr)
        print("  Set DATABASE_URL=sqlite:///./devflow_demo.db", file=sys.stderr)
        sys.exit(1)

    # Resolve the path
    resolved_url = resolve_sqlite_path(db_url)
    file_path = get_sqlite_file_path(db_url)

    if file_path is None:
        print("ERROR: Invalid SQLite URL or in-memory database.", file=sys.stderr)
        sys.exit(1)

    # Safety check: refuse to run against devflow_local.db
    if "devflow_local.db" in file_path:
        print("ERROR: Refusing to seed into devflow_local.db (development database).", file=sys.stderr)
        print(f"  Target path: {file_path}", file=sys.stderr)
        print("  Use DATABASE_URL=sqlite:///./devflow_demo.db instead.", file=sys.stderr)
        sys.exit(1)

    # Safety check: refuse to overwrite existing database file
    if Path(file_path).exists():
        print("ERROR: Demo database file already exists.", file=sys.stderr)
        print(f"  Path: {file_path}", file=sys.stderr)
        print("  Remove it manually if you want to re-seed: rm " + file_path, file=sys.stderr)
        sys.exit(1)

    # Verify it's the expected demo database
    expected_path = str(Path(backend_dir) / "devflow_demo.db")
    if file_path != expected_path:
        print("WARNING: Database path differs from expected demo location.", file=sys.stderr)
        print(f"  Expected: {expected_path}", file=sys.stderr)
        print(f"  Actual:   {file_path}", file=sys.stderr)
        # Continue anyway - user explicitly set the path

    print(f"✓ Safety checks passed")
    print(f"  Target database: {file_path}")
    print(f"  Resolved URL: {resolved_url}")

    return file_path


def get_database_engine(db_url: str):
    """Create and configure a SQLAlchemy engine for the demo database."""
    resolved_db_url = resolve_sqlite_path(db_url)

    engine = create_engine(
        resolved_db_url,
        echo=settings.database_echo,
        connect_args={"check_same_thread": False},
    )

    # Enable foreign keys and WAL mode
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_or_create_role(db: Session, role_code: str) -> Role:
    """Return a catalog role, creating only a missing reference role."""
    role = db.scalar(select(Role).where(Role.code == role_code))
    if role is not None:
        return role
    if role_code not in ROLE_CATALOG:
        raise ValueError(f"Unsupported role: {role_code}")
    role = Role(code=role_code, name=ROLE_CATALOG[role_code])
    db.add(role)
    db.flush()
    return role


def get_or_create_user(db: Session, email: str, full_name: str, role_code: str) -> User:
    """Get existing user or create with specified role."""
    user = db.scalar(select(User).where(User.email == email))
    if user:
        # Ensure user has the required role
        role = get_or_create_role(db, role_code)
        if role not in user.roles:
            user.roles.append(role)
            db.flush()
        return user

    password_hash = hash_password(DEMO_PASSWORD)
    role = get_or_create_role(db, role_code)
    user = User(
        full_name=full_name,
        email=email,
        password_hash=password_hash,
        account_status="active",
        roles=[role],
    )
    db.add(user)
    db.flush()
    return user


def get_or_create_project(db: Session, name: str, description: str, owner: User) -> Project:
    """Get existing project or create it with owner as creator and project_manager member."""
    project = db.scalar(select(Project).where(Project.name == name))
    if project:
        # Ensure owner is a member with project_manager role
        member = db.execute(
            select(project_members.c.user_id).where(
                project_members.c.project_id == project.id,
                project_members.c.user_id == owner.id,
            )
        ).first()
        if not member:
            db.execute(
                project_members.insert().values(
                    project_id=project.id,
                    user_id=owner.id,
                    project_role="project_manager",
                )
            )
            db.flush()
        return project

    project = Project(
        name=name,
        description=description,
        status="active",
        created_by_user_id=owner.id,
    )
    db.add(project)
    db.flush()

    # Add creator as project member with project_manager role
    db.execute(
        project_members.insert().values(
            project_id=project.id,
            user_id=owner.id,
            project_role="project_manager",
        )
    )
    db.flush()
    return project


def add_project_member(db: Session, project: Project, user: User, project_role: str) -> None:
    """Add user as project member with specified project role if not already a member."""
    member = db.execute(
        select(project_members.c.user_id).where(
            project_members.c.project_id == project.id,
            project_members.c.user_id == user.id,
        )
    ).first()
    if not member:
        db.execute(
            project_members.insert().values(
                project_id=project.id,
                user_id=user.id,
                project_role=project_role,
            )
        )
        db.flush()


def get_or_create_requirement(db: Session, project: Project, key: str, title: str,
                               description: str, req_type: str, priority: str,
                               status: str, creator: User) -> Requirement:
    """Get existing requirement or create it."""
    req = db.scalar(
        select(Requirement).where(
            Requirement.project_id == project.id,
            Requirement.requirement_key == key,
        )
    )
    if req:
        return req

    req = Requirement(
        project_id=project.id,
        requirement_key=key,
        title=title,
        description=description,
        requirement_type=req_type,
        priority=priority,
        status=status,
        version=1,
        created_by_user_id=creator.id,
        updated_by_user_id=creator.id,
    )
    db.add(req)
    db.flush()
    return req


def get_or_create_task(db: Session, project: Project, requirement: Requirement,
                       title: str, description: str, priority: str, status: str,
                       assignee: User | None, creator: User, sprint: Sprint | None = None) -> Task:
    """Get existing task or create it."""
    task = db.scalar(
        select(Task).where(
            Task.project_id == project.id,
            Task.requirement_id == requirement.id,
            Task.title == title,
        )
    )
    if task:
        return task

    task = Task(
        project_id=project.id,
        requirement_id=requirement.id,
        sprint_id=sprint.id if sprint else None,
        title=title,
        description=description,
        priority=priority,
        status=status,
        assigned_to_user_id=assignee.id if assignee else None,
        created_by_user_id=creator.id,
    )
    db.add(task)
    db.flush()
    return task


def get_or_create_bug(db: Session, project: Project, title: str, description: str,
                      severity: str, status: str, assignee: User | None,
                      reporter: User, requirement: Requirement | None = None,
                      task: Task | None = None) -> Bug:
    """Get existing bug or create it."""
    bug = db.scalar(
        select(Bug).where(
            Bug.project_id == project.id,
            Bug.title == title,
        )
    )
    if bug:
        return bug

    bug = Bug(
        project_id=project.id,
        requirement_id=requirement.id if requirement else None,
        task_id=task.id if task else None,
        title=title,
        description=description,
        severity=severity,
        status=status,
        assigned_to_user_id=assignee.id if assignee else None,
        reported_by_user_id=reporter.id,
    )
    db.add(bug)
    db.flush()
    return bug


def get_or_create_test_case(db: Session, project: Project, requirement: Requirement,
                            title: str, preconditions: str, test_steps: str,
                            expected_result: str, status: str, creator: User) -> TestCase:
    """Get existing test case or create it."""
    tc = db.scalar(
        select(TestCase).where(
            TestCase.project_id == project.id,
            TestCase.requirement_id == requirement.id,
            TestCase.title == title,
        )
    )
    if tc:
        return tc

    tc = TestCase(
        project_id=project.id,
        requirement_id=requirement.id,
        title=title,
        preconditions=preconditions,
        test_steps=test_steps,
        expected_result=expected_result,
        status=status,
        created_by_user_id=creator.id,
    )
    db.add(tc)
    db.flush()
    return tc


def get_or_create_sprint(db: Session, project: Project, name: str, goal: str,
                         start_date, end_date, status: str) -> Sprint:
    """Get existing sprint or create it."""
    sprint = db.scalar(
        select(Sprint).where(
            Sprint.project_id == project.id,
            Sprint.name == name,
        )
    )
    if sprint:
        return sprint

    sprint = Sprint(
        project_id=project.id,
        name=name,
        goal=goal,
        start_date=start_date,
        end_date=end_date,
        status=status,
    )
    db.add(sprint)
    db.flush()
    return sprint


def get_or_create_milestone(db: Session, project: Project, name: str, description: str,
                            target_date, status: str) -> Milestone:
    """Get existing milestone or create it."""
    ms = db.scalar(
        select(Milestone).where(
            Milestone.project_id == project.id,
            Milestone.name == name,
        )
    )
    if ms:
        return ms

    ms = Milestone(
        project_id=project.id,
        name=name,
        description=description,
        target_date=target_date,
        status=status,
    )
    db.add(ms)
    db.flush()
    return ms


def ensure_traceability_link(
    db: Session,
    project: Project,
    creator: User,
    source_type: str,
    source_id: UUID,
    target_type: str,
    target_id: UUID,
    relationship_type: str,
) -> TraceabilityLink | None:
    """Create traceability link if it doesn't exist. Returns the link or None if already exists."""
    existing = db.scalar(
        select(TraceabilityLink).where(
            TraceabilityLink.project_id == project.id,
            TraceabilityLink.source_artifact_type == source_type,
            TraceabilityLink.source_artifact_id == source_id,
            TraceabilityLink.target_artifact_type == target_type,
            TraceabilityLink.target_artifact_id == target_id,
            TraceabilityLink.relationship_type == relationship_type,
        )
    )
    if existing:
        return None

    link = TraceabilityLink(
        project_id=project.id,
        source_artifact_type=source_type,
        source_artifact_id=source_id,
        target_artifact_type=target_type,
        target_artifact_id=target_id,
        relationship_type=relationship_type,
        created_by_user_id=creator.id,
    )
    db.add(link)
    db.flush()
    return link


def get_or_create_change_request(db: Session, project: Project, requirement: Requirement,
                                  creator: User, change_summary: str,
                                  proposed_description: str, proposed_priority: str,
                                  proposed_status: str) -> RequirementChangeRequest:
    """Get existing change request or create it."""
    cr = db.scalar(
        select(RequirementChangeRequest).where(
            RequirementChangeRequest.requirement_id == requirement.id,
            RequirementChangeRequest.change_summary == change_summary,
        )
    )
    if cr:
        return cr

    cr = RequirementChangeRequest(
        requirement_id=requirement.id,
        requested_by_user_id=creator.id,
        change_summary=change_summary,
        proposed_description=proposed_description,
        proposed_priority=proposed_priority,
        proposed_status=proposed_status,
        status="submitted",
    )
    db.add(cr)
    db.flush()
    return cr


# =============================================================================
# PROJECT A: IDENTITY & ACCESS PLATFORM
# =============================================================================

def seed_project_a(db: Session, pm_user: User, dev_a: User, dev_b: User,
                   tl_user: User, qa_user: User, client_user: User) -> dict:
    """Seed Project A: Identity & Access Platform."""
    print("\n📦 Seeding Project A: Identity & Access Platform")

    project = get_or_create_project(db, PROJECT_A_NAME, PROJECT_A_DESC, pm_user)

    # Add project members
    add_project_member(db, project, pm_user, "project_manager")
    add_project_member(db, project, tl_user, "team_lead")
    add_project_member(db, project, dev_a, "developer")
    add_project_member(db, project, dev_b, "developer")
    add_project_member(db, project, qa_user, "tester")
    add_project_member(db, project, client_user, "client")

    # Create sprints
    from datetime import date, timedelta
    today = date.today()
    sprint1 = get_or_create_sprint(db, project, "Sprint 1: Core Auth",
        "Implement core authentication and session management",
        today - timedelta(days=30), today - timedelta(days=16), "completed")
    sprint2 = get_or_create_sprint(db, project, "Sprint 2: Access & Recovery",
        "Implement access control, account recovery, and MFA",
        today - timedelta(days=15), today - timedelta(days=1), "active")
    sprint3 = get_or_create_sprint(db, project, "Sprint 3: Hardening & Observability",
        "Add audit logging, notifications, password policy, and admin console",
        today + timedelta(days=1), today + timedelta(days=15), "planned")

    # Create milestones
    ms1 = get_or_create_milestone(db, project, "M1: Core Auth Complete",
        "Authentication, sessions, and basic login flow", today - timedelta(days=16), "completed")
    ms2 = get_or_create_milestone(db, project, "M2: Access & Recovery Complete",
        "RBAC, account recovery, and MFA", today - timedelta(days=1), "in_progress")
    ms3 = get_or_create_milestone(db, project, "M3: Platform Hardening",
        "Audit logging, notifications, password policy, admin console", today + timedelta(days=15), "planned")

    # Create requirements
    req_auth = get_or_create_requirement(db, project, REQ_KEYS_A["auth"],
        "User Authentication Flow",
        "Implement secure user authentication with JWT tokens, password hashing (Argon2id), and login rate limiting.",
        "functional", "critical", "approved", pm_user)
    req_session = get_or_create_requirement(db, project, REQ_KEYS_A["session"],
        "Session Management",
        "Implement secure session handling with JWT access/refresh tokens, token rotation, and concurrent session limits.",
        "functional", "critical", "approved", pm_user)
    req_recovery = get_or_create_requirement(db, project, REQ_KEYS_A["recovery"],
        "Account Recovery Flow",
        "Allow users to recover accounts via email verification, security questions, and backup codes.",
        "functional", "high", "approved", pm_user)
    req_access = get_or_create_requirement(db, project, REQ_KEYS_A["access"],
        "Role-Based Access Control",
        "Implement RBAC with six roles (admin, project_manager, team_lead, developer, tester, client) and project-scoped permissions.",
        "functional", "critical", "approved", pm_user)
    req_mfa = get_or_create_requirement(db, project, REQ_KEYS_A["mfa"],
        "Multi-Factor Authentication",
        "Support TOTP-based MFA with backup codes and recovery flows.",
        "functional", "high", "in_progress", pm_user)
    req_notify = get_or_create_requirement(db, project, REQ_KEYS_A["notify"],
        "Security Notifications",
        "Send email notifications for login from new device, password change, MFA enrollment, and suspicious activity.",
        "functional", "medium", "in_progress", pm_user)
    req_audit = get_or_create_requirement(db, project, REQ_KEYS_A["audit"],
        "Audit Logging",
        "Implement immutable audit log for all authentication and authorization events with search and export.",
        "functional", "high", "in_progress", pm_user)
    req_password = get_or_create_requirement(db, project, REQ_KEYS_A["password_policy"],
        "Password Policy Enforcement",
        "Enforce configurable password complexity, rotation, history, and breach detection via HaveIBeenPwned.",
        "functional", "medium", "draft", pm_user)
    req_oauth = get_or_create_requirement(db, project, REQ_KEYS_A["oauth"],
        "OAuth 2.0 / OIDC Provider",
        "Implement OAuth 2.0 authorization server and OpenID Connect provider for third-party integrations.",
        "functional", "medium", "draft", pm_user)
    req_api_keys = get_or_create_requirement(db, project, REQ_KEYS_A["api_keys"],
        "API Key Management",
        "Allow users and services to create, rotate, and revoke scoped API keys with expiration and audit trail.",
        "functional", "medium", "draft", pm_user)
    req_device = get_or_create_requirement(db, project, REQ_KEYS_A["device_trust"],
        "Device Trust & Fingerprinting",
        "Track and manage trusted devices with fingerprinting, risk scoring, and step-up authentication.",
        "functional", "low", "draft", pm_user)
    req_admin = get_or_create_requirement(db, project, REQ_KEYS_A["admin_console"],
        "Admin Console",
        "Build administrative dashboard for user management, role assignment, audit log review, and system health.",
        "functional", "high", "proposed", pm_user)

    # Create tasks
    # Auth tasks
    task_auth_1 = get_or_create_task(db, project, req_auth,
        "Implement JWT Token Service", "Create token generation, validation, and refresh logic with RS256 signing.",
        "critical", "completed", dev_a, pm_user, sprint1)
    task_auth_2 = get_or_create_task(db, project, req_auth,
        "Implement Login Endpoint", "Build /auth/login with rate limiting, credential validation, and token issuance.",
        "critical", "completed", dev_a, pm_user, sprint1)
    task_auth_3 = get_or_create_task(db, project, req_auth,
        "Implement Password Hashing", "Integrate Argon2id via argon2-cffi with configurable parameters.",
        "critical", "completed", dev_b, pm_user, sprint1)

    # Session tasks
    task_session_1 = get_or_create_task(db, project, req_session,
        "Implement Refresh Token Rotation", "Issue new refresh token on each use; revoke old token; detect reuse.",
        "critical", "completed", dev_a, pm_user, sprint1)
    task_session_2 = get_or_create_task(db, project, req_session,
        "Concurrent Session Limits", "Enforce max concurrent sessions per user with oldest-session eviction.",
        "high", "completed", dev_b, pm_user, sprint1)
    task_session_3 = get_or_create_task(db, project, req_session,
        "Token Revocation on Logout", "Implement /auth/logout to revoke refresh token and optionally all user sessions.",
        "high", "completed", dev_a, pm_user, sprint1)

    # Recovery tasks
    task_recovery_1 = get_or_create_task(db, project, req_recovery,
        "Email Verification Flow", "Send verification email with time-limited token; validate on click.",
        "high", "in_progress", dev_b, pm_user, sprint2)
    task_recovery_2 = get_or_create_task(db, project, req_recovery,
        "Security Questions", "Store hashed security answers; challenge on recovery; rate limit attempts.",
        "high", "in_progress", dev_a, pm_user, sprint2)
    task_recovery_3 = get_or_create_task(db, project, req_recovery,
        "Backup Codes Generation", "Generate 10 single-use backup codes; store hashed; invalidate on use.",
        "medium", "todo", dev_b, pm_user, sprint2)

    # Access control tasks
    task_access_1 = get_or_create_task(db, project, req_access,
        "Role Catalog & Assignment", "Create six built-in roles; implement user_roles many-to-many; API for assignment.",
        "critical", "completed", dev_a, pm_user, sprint1)
    task_access_2 = get_or_create_task(db, project, req_access,
        "Project-Scoped Permissions", "Implement project_members with project_role; enforce in core_service.py.",
        "critical", "completed", dev_b, pm_user, sprint1)
    task_access_3 = get_or_create_task(db, project, req_access,
        "Permission Dependency Checker", "Build require_project_access / require_project_management / require_team_management helpers.",
        "high", "completed", dev_a, pm_user, sprint1)

    # MFA tasks
    task_mfa_1 = get_or_create_task(db, project, req_mfa,
        "TOTP Enrollment & Verification", "Generate QR code; verify TOTP codes; store encrypted secret.",
        "high", "in_progress", dev_a, pm_user, sprint2)
    task_mfa_2 = get_or_create_task(db, project, req_mfa,
        "Backup Codes for MFA", "Generate and manage backup codes as second factor alternative.",
        "high", "todo", dev_b, pm_user, sprint2)

    # Notification tasks
    task_notify_1 = get_or_create_task(db, project, req_notify,
        "Email Notification Service", "Build templated email sender with queue; integrate with auth events.",
        "medium", "in_progress", dev_b, pm_user, sprint2)
    task_notify_2 = get_or_create_task(db, project, req_notify,
        "Security Event Notifications", "Trigger emails for new device login, password change, MFA enrollment.",
        "medium", "todo", dev_a, pm_user, sprint2)

    # Audit tasks
    task_audit_1 = get_or_create_task(db, project, req_audit,
        "Audit Log Data Model", "Implement immutable append-only log table with tamper-evident chaining.",
        "high", "in_progress", dev_a, pm_user, sprint3)
    task_audit_2 = get_or_create_task(db, project, req_audit,
        "Audit Log Search & Export", "Build filtered search, pagination, and CSV/JSON export for audit events.",
        "medium", "todo", dev_b, pm_user, sprint3)

    # Password policy tasks
    task_pwd_1 = get_or_create_task(db, project, req_password,
        "Password Complexity Rules", "Configurable min length, character classes, max age, history count.",
        "medium", "todo", dev_a, pm_user, sprint3)
    task_pwd_2 = get_or_create_task(db, project, req_password,
        "Breach Detection Integration", "Check new passwords against HaveIBeenPwned API (k-anonymity).",
        "medium", "todo", dev_b, pm_user, sprint3)

    # OAuth tasks
    task_oauth_1 = get_or_create_task(db, project, req_oauth,
        "Authorization Code Flow", "Implement RFC 6749 authorization code grant with PKCE support.",
        "medium", "todo", dev_a, pm_user, sprint3)
    task_oauth_2 = get_or_create_task(db, project, req_oauth,
        "OIDC Discovery & UserInfo", "Expose /.well-known/openid-configuration and /userinfo endpoint.",
        "medium", "todo", dev_b, pm_user, sprint3)

    # API keys tasks
    task_apikey_1 = get_or_create_task(db, project, req_api_keys,
        "API Key CRUD", "Create, list, rotate, revoke scoped keys with prefix identification.",
        "medium", "todo", dev_a, pm_user, sprint3)
    task_apikey_2 = get_or_create_task(db, project, req_api_keys,
        "API Key Expiration & Audit", "Enforce expiration; log all key usage in audit trail.",
        "medium", "todo", dev_b, pm_user, sprint3)

    # Device trust tasks
    task_device_1 = get_or_create_task(db, project, req_device,
        "Device Fingerprinting", "Collect client signals; generate stable device ID; risk scoring.",
        "low", "todo", dev_a, pm_user, sprint3)
    task_device_2 = get_or_create_task(db, project, req_device,
        "Step-Up Authentication", "Trigger MFA challenge for high-risk devices or impossible travel.",
        "low", "todo", dev_b, pm_user, sprint3)

    # Admin console tasks
    task_admin_1 = get_or_create_task(db, project, req_admin,
        "User Management UI", "List, search, filter users; assign/remove roles; suspend/activate accounts.",
        "high", "todo", dev_a, pm_user, sprint3)
    task_admin_2 = get_or_create_task(db, project, req_admin,
        "Audit Log Viewer", "Filterable audit log table with event details and export.",
        "high", "todo", dev_b, pm_user, sprint3)

    # Create bugs
    bug_1 = get_or_create_bug(db, project,
        "Token Refresh Race Condition",
        "Concurrent refresh requests with same token cause 401; need atomic compare-and-swap.",
        "critical", "resolved", dev_a, qa_user, req_session, task_session_1)
    bug_2 = get_or_create_bug(db, project,
        "Session Not Invalidated on Password Change",
        "Changing password does not revoke existing sessions; security gap.",
        "high", "open", dev_b, qa_user, req_session, task_session_3)
    bug_3 = get_or_create_bug(db, project,
        "MFA Backup Codes Not Invalidated After Use",
        "Used backup codes remain valid; should be single-use.",
        "high", "in_progress", dev_a, qa_user, req_mfa, task_mfa_2)
    bug_4 = get_or_create_bug(db, project,
        "Audit Log Missing Correlation ID",
        "Cross-request tracing difficult without correlation IDs in audit events.",
        "medium", "open", dev_a, qa_user, req_audit, task_audit_1)
    bug_5 = get_or_create_bug(db, project,
        "OAuth PKCE Verification Bypass",
        "Missing code_verifier check allows authorization code interception.",
        "critical", "open", dev_b, qa_user, req_oauth, task_oauth_1)
    bug_6 = get_or_create_bug(db, project,
        "API Key Prefix Collision",
        "Different key types share same prefix causing identification ambiguity.",
        "medium", "open", dev_a, qa_user, req_api_keys, task_apikey_1)

    # Create test cases
    tc_1 = get_or_create_test_case(db, project, req_auth,
        "Valid Login Returns Tokens",
        "User exists with valid credentials",
        "1. POST /auth/login with correct email/password\n2. Observe response",
        "200 OK with access_token and refresh_token; tokens are valid JWTs",
        "passed", pm_user)
    tc_2 = get_or_create_test_case(db, project, req_auth,
        "Invalid Login Rejected",
        "User exists",
        "1. POST /auth/login with wrong password\n2. Observe response",
        "401 Unauthorized; no tokens issued; rate limit counter increments",
        "passed", pm_user)
    tc_3 = get_or_create_test_case(db, project, req_session,
        "Refresh Token Rotation Works",
        "Valid refresh token exists",
        "1. POST /auth/refresh with valid token\n2. Observe new token pair\n3. Attempt reuse of old refresh token",
        "New access+refresh issued; old refresh token rejected on reuse",
        "passed", pm_user)
    tc_4 = get_or_create_test_case(db, project, req_session,
        "Concurrent Session Limit Enforced",
        "User has max_sessions=3 configured",
        "1. Login from 4th device\n2. Observe session eviction",
        "Oldest session revoked; new session created; total active = 3",
        "passed", pm_user)
    tc_5 = get_or_create_test_case(db, project, req_recovery,
        "Email Recovery Flow",
        "User has registered email",
        "1. Request recovery\n2. Click email link\n3. Set new password\n4. Login with new password",
        "Recovery completes; old sessions revoked; new login works",
        "not_run", pm_user)
    tc_6 = get_or_create_test_case(db, project, req_access,
        "Project Manager Can Manage Members",
        "User has project_manager role in project",
        "1. POST /projects/{id}/members\n2. Add developer\n3. Verify membership",
        "Member added with developer project_role; appears in member list",
        "passed", pm_user)
    tc_7 = get_or_create_test_case(db, project, req_access,
        "Developer Cannot Manage Members",
        "User has developer role in project",
        "1. POST /projects/{id}/members as developer\n2. Observe response",
        "403 Forbidden; member not added",
        "passed", pm_user)
    tc_8 = get_or_create_test_case(db, project, req_mfa,
        "TOTP Enrollment and Verification",
        "User has no MFA enrolled",
        "1. Enroll TOTP via QR code\n2. Verify with valid code\n3. Verify with invalid code",
        "Enrollment succeeds; valid code accepted; invalid code rejected",
        "not_run", pm_user)
    tc_9 = get_or_create_test_case(db, project, req_notify,
        "New Device Login Notification",
        "User has email notifications enabled",
        "1. Login from new device fingerprint\n2. Check email",
        "Email received within 1 minute with device details and 'not you?' link",
        "not_run", pm_user)
    tc_10 = get_or_create_test_case(db, project, req_audit,
        "Audit Log Captures Login Events",
        "Audit logging enabled",
        "1. Perform login\n2. Query audit log for user\n3. Verify event present",
        "Login event recorded with timestamp, IP, user agent, success=true",
        "not_run", pm_user)
    tc_11 = get_or_create_test_case(db, project, req_password,
        "Weak Password Rejected",
        "Password policy: min 12 chars, upper, lower, digit, symbol",
        "1. Attempt to set password 'weak'\n2. Attempt to set valid password",
        "Weak password rejected with specific reason; valid password accepted",
        "not_run", pm_user)
    tc_12 = get_or_create_test_case(db, project, req_admin,
        "Admin Console Shows User List",
        "Admin user logged in",
        "1. Navigate to Admin Console > Users\n2. Verify list loads",
        "Paginated user list with roles, status, last login; search works",
        "not_run", pm_user)

    # Create traceability links
    links_created = 0

    def add_link(source_type, source_id, target_type, target_id, rel_type):
        nonlocal links_created
        if ensure_traceability_link(db, project, pm_user, source_type, source_id, target_type, target_id, rel_type):
            links_created += 1

    # Auth requirement links
    add_link("requirement", req_auth.id, "task", task_auth_1.id, "implements")
    add_link("requirement", req_auth.id, "task", task_auth_2.id, "implements")
    add_link("requirement", req_auth.id, "task", task_auth_3.id, "implements")
    add_link("requirement", req_auth.id, "test_case", tc_1.id, "validates")
    add_link("requirement", req_auth.id, "test_case", tc_2.id, "validates")
    add_link("requirement", req_auth.id, "bug", bug_1.id, "affects")  # indirectly via session

    # Session requirement links
    add_link("requirement", req_session.id, "task", task_session_1.id, "implements")
    add_link("requirement", req_session.id, "task", task_session_2.id, "implements")
    add_link("requirement", req_session.id, "task", task_session_3.id, "implements")
    add_link("requirement", req_session.id, "bug", bug_1.id, "affects")
    add_link("requirement", req_session.id, "bug", bug_2.id, "affects")
    add_link("requirement", req_session.id, "test_case", tc_3.id, "validates")
    add_link("requirement", req_session.id, "test_case", tc_4.id, "validates")

    # Recovery requirement links
    add_link("requirement", req_recovery.id, "task", task_recovery_1.id, "implements")
    add_link("requirement", req_recovery.id, "task", task_recovery_2.id, "implements")
    add_link("requirement", req_recovery.id, "task", task_recovery_3.id, "implements")
    add_link("requirement", req_recovery.id, "test_case", tc_5.id, "validates")
    add_link("requirement", req_recovery.id, "requirement", req_auth.id, "depends_on")  # recovery depends on auth
    add_link("requirement", req_recovery.id, "requirement", req_session.id, "depends_on")  # recovery depends on session

    # Access control requirement links
    add_link("requirement", req_access.id, "task", task_access_1.id, "implements")
    add_link("requirement", req_access.id, "task", task_access_2.id, "implements")
    add_link("requirement", req_access.id, "task", task_access_3.id, "implements")
    add_link("requirement", req_access.id, "test_case", tc_6.id, "validates")
    add_link("requirement", req_access.id, "test_case", tc_7.id, "validates")
    add_link("requirement", req_access.id, "requirement", req_auth.id, "depends_on")  # access depends on auth

    # MFA requirement links
    add_link("requirement", req_mfa.id, "task", task_mfa_1.id, "implements")
    add_link("requirement", req_mfa.id, "task", task_mfa_2.id, "implements")
    add_link("requirement", req_mfa.id, "bug", bug_3.id, "affects")
    add_link("requirement", req_mfa.id, "test_case", tc_8.id, "validates")
    add_link("requirement", req_mfa.id, "requirement", req_auth.id, "depends_on")  # MFA depends on auth
    add_link("requirement", req_mfa.id, "requirement", req_session.id, "depends_on")  # MFA depends on session

    # Notification requirement links
    add_link("requirement", req_notify.id, "task", task_notify_1.id, "implements")
    add_link("requirement", req_notify.id, "task", task_notify_2.id, "implements")
    add_link("requirement", req_notify.id, "test_case", tc_9.id, "validates")
    add_link("requirement", req_notify.id, "requirement", req_auth.id, "depends_on")  # notify depends on auth (login events)

    # Audit requirement links
    add_link("requirement", req_audit.id, "task", task_audit_1.id, "implements")
    add_link("requirement", req_audit.id, "task", task_audit_2.id, "implements")
    add_link("requirement", req_audit.id, "bug", bug_4.id, "affects")
    add_link("requirement", req_audit.id, "test_case", tc_10.id, "validates")
    add_link("requirement", req_audit.id, "requirement", req_auth.id, "depends_on")  # audit depends on auth events
    add_link("requirement", req_audit.id, "requirement", req_session.id, "depends_on")  # audit depends on session events
    add_link("requirement", req_audit.id, "requirement", req_access.id, "depends_on")  # audit depends on access events

    # Password policy requirement links
    add_link("requirement", req_password.id, "task", task_pwd_1.id, "implements")
    add_link("requirement", req_password.id, "task", task_pwd_2.id, "implements")
    add_link("requirement", req_password.id, "test_case", tc_11.id, "validates")
    add_link("requirement", req_password.id, "requirement", req_auth.id, "depends_on")  # password policy depends on auth

    # OAuth requirement links
    add_link("requirement", req_oauth.id, "task", task_oauth_1.id, "implements")
    add_link("requirement", req_oauth.id, "task", task_oauth_2.id, "implements")
    add_link("requirement", req_oauth.id, "bug", bug_5.id, "affects")
    add_link("requirement", req_oauth.id, "requirement", req_auth.id, "depends_on")  # OAuth depends on auth
    add_link("requirement", req_oauth.id, "requirement", req_session.id, "blocks")  # OAuth blocks legacy session handling

    # API keys requirement links
    add_link("requirement", req_api_keys.id, "task", task_apikey_1.id, "implements")
    add_link("requirement", req_api_keys.id, "task", task_apikey_2.id, "implements")
    add_link("requirement", req_api_keys.id, "bug", bug_6.id, "affects")
    add_link("requirement", req_api_keys.id, "requirement", req_auth.id, "depends_on")  # API keys depend on auth

    # Device trust requirement links
    add_link("requirement", req_device.id, "task", task_device_1.id, "implements")
    add_link("requirement", req_device.id, "task", task_device_2.id, "implements")
    add_link("requirement", req_device.id, "requirement", req_mfa.id, "depends_on")  # device trust depends on MFA
    add_link("requirement", req_device.id, "requirement", req_audit.id, "depends_on")  # device trust depends on audit

    # Admin console requirement links
    add_link("requirement", req_admin.id, "task", task_admin_1.id, "implements")
    add_link("requirement", req_admin.id, "task", task_admin_2.id, "implements")
    add_link("requirement", req_admin.id, "test_case", tc_12.id, "validates")
    add_link("requirement", req_admin.id, "requirement", req_access.id, "depends_on")  # admin console depends on access
    add_link("requirement", req_admin.id, "requirement", req_audit.id, "depends_on")  # admin console depends on audit

    # Task-to-task dependencies are not supported by traceability validation
    # Dependencies are modeled through requirement-to-requirement (depends_on, blocks)
    # and requirement-to-task (implements) relationships instead

    # Create change request for RCIA demonstration
    # Changing the foundational auth requirement (IAP-1) should impact many downstream artifacts
    change_request = get_or_create_change_request(db, project, req_auth, pm_user,
        "Migrate from HS256 to RS256 for JWT signing",
        "Replace symmetric HS256 signing with asymmetric RS256 to support key rotation and third-party verification. "
        "This affects token validation, refresh rotation, session management, and all downstream consumers.",
        "critical", "in_progress")

    print(f"  ✓ Project A seeded: 12 requirements, 24 tasks, 6 bugs, 12 test cases, 3 sprints, 3 milestones, {links_created} traceability links, 1 change request")

    return {
        "project": project,
        "requirements": {
            "auth": req_auth, "session": req_session, "recovery": req_recovery,
            "access": req_access, "mfa": req_mfa, "notify": req_notify,
            "audit": req_audit, "password": req_password, "oauth": req_oauth,
            "api_keys": req_api_keys, "device": req_device, "admin": req_admin,
        },
        "change_request": change_request,
        "links_created": links_created,
        "auth_req_key": req_auth.requirement_key,
        "auth_req_title": req_auth.title,
        "change_request_summary": change_request.change_summary,
    }


# =============================================================================
# PROJECT B: STUDENT SERVICES PORTAL
# =============================================================================

def seed_project_b(db: Session, pm_user: User, dev_a: User, dev_b: User,
                   tl_user: User, qa_user: User, client_user: User) -> dict:
    """Seed Project B: Student Services Portal."""
    print("\n📦 Seeding Project B: Student Services Portal")

    project = get_or_create_project(db, PROJECT_B_NAME, PROJECT_B_DESC, pm_user)

    # Add project members (different team composition)
    add_project_member(db, project, pm_user, "project_manager")
    add_project_member(db, project, tl_user, "team_lead")
    add_project_member(db, project, dev_a, "developer")
    add_project_member(db, project, dev_b, "developer")
    add_project_member(db, project, qa_user, "tester")
    add_project_member(db, project, client_user, "client")

    # Create sprints
    from datetime import date, timedelta
    today = date.today()
    sprint1 = get_or_create_sprint(db, project, "Sprint 1: Core Portal",
        "Student profiles, authentication integration, and course registration",
        today - timedelta(days=20), today - timedelta(days=6), "completed")
    sprint2 = get_or_create_sprint(db, project, "Sprint 2: Timetable & Notifications",
        "Timetable management, notification preferences, and service requests",
        today - timedelta(days=5), today + timedelta(days=9), "active")
    sprint3 = get_or_create_sprint(db, project, "Sprint 3: Grades & Payments",
        "Grade viewing, payment processing, and portal polish",
        today + timedelta(days=10), today + timedelta(days=24), "planned")

    # Create milestones
    ms1 = get_or_create_milestone(db, project, "M1: Core Portal Live",
        "Profiles, auth, and course registration", today - timedelta(days=6), "completed")
    ms2 = get_or_create_milestone(db, project, "M2: Timetable & Services",
        "Timetable, notifications, service requests", today + timedelta(days=9), "in_progress")
    ms3 = get_or_create_milestone(db, project, "M3: Full Portal",
        "Grades, payments, and production readiness", today + timedelta(days=24), "planned")

    # Create requirements
    req_profile = get_or_create_requirement(db, project, REQ_KEYS_B["profile"],
        "Student Profile Management",
        "Allow students to view and update personal information, contact details, emergency contacts, and privacy settings.",
        "functional", "high", "approved", pm_user)
    req_registration = get_or_create_requirement(db, project, REQ_KEYS_B["registration"],
        "Course Registration",
        "Enable course search, add/drop, waitlist management, prerequisite checking, and registration confirmation.",
        "functional", "critical", "approved", pm_user)
    req_timetable = get_or_create_requirement(db, project, REQ_KEYS_B["timetable"],
        "Timetable Management",
        "Display weekly schedule with conflict detection, calendar export (ICS), and real-time updates for room/time changes.",
        "functional", "high", "in_progress", pm_user)
    req_notifications = get_or_create_requirement(db, project, REQ_KEYS_B["notifications"],
        "Notification Preferences",
        "Configure email/push/SMS preferences for grades, registration, deadlines, announcements, and emergencies.",
        "functional", "medium", "in_progress", pm_user)
    req_services = get_or_create_requirement(db, project, REQ_KEYS_B["service_requests"],
        "Service Requests",
        "Submit, track, and manage service requests (transcripts, verification letters, accommodations, IT support).",
        "functional", "medium", "in_progress", pm_user)
    req_grades = get_or_create_requirement(db, project, REQ_KEYS_B["grades"],
        "Grade Viewing & History",
        "View current and historical grades, GPA calculation, unofficial transcript, and grade change notifications.",
        "functional", "high", "proposed", pm_user)
    req_payments = get_or_create_requirement(db, project, REQ_KEYS_B["payments"],
        "Payment Processing",
        "View tuition balance, make payments via multiple methods, payment plans, and receipt generation.",
        "functional", "high", "proposed", pm_user)

    # Create tasks
    task_profile_1 = get_or_create_task(db, project, req_profile,
        "Profile Data Model & API", "Create student profile schema, CRUD endpoints, and validation.",
        "high", "completed", dev_a, pm_user, sprint1)
    task_profile_2 = get_or_create_task(db, project, req_profile,
        "Privacy Controls", "Implement field-level visibility settings and FERPA compliance flags.",
        "medium", "completed", dev_b, pm_user, sprint1)

    task_reg_1 = get_or_create_task(db, project, req_registration,
        "Course Catalog Search", "Build searchable catalog with filters (department, level, credits, schedule).",
        "critical", "completed", dev_a, pm_user, sprint1)
    task_reg_2 = get_or_create_task(db, project, req_registration,
        "Add/Drop & Waitlist Logic", "Implement registration transactions, waitlist queue, and capacity enforcement.",
        "critical", "completed", dev_b, pm_user, sprint1)
    task_reg_3 = get_or_create_task(db, project, req_registration,
        "Prerequisite Checking", "Validate prerequisites, co-requisites, and anti-requisites at registration time.",
        "high", "completed", dev_a, pm_user, sprint1)

    task_tt_1 = get_or_create_task(db, project, req_timetable,
        "Weekly Schedule View", "Render Monday-Sunday grid with color-coded courses, locations, instructors.",
        "high", "in_progress", dev_a, pm_user, sprint2)
    task_tt_2 = get_or_create_task(db, project, req_timetable,
        "Conflict Detection", "Detect and highlight scheduling conflicts (time overlap, room double-booking).",
        "high", "in_progress", dev_b, pm_user, sprint2)
    task_tt_3 = get_or_create_task(db, project, req_timetable,
        "ICS Calendar Export", "Generate standards-compliant .ics file with recurring events and timezone support.",
        "medium", "todo", dev_a, pm_user, sprint2)

    task_notify_1 = get_or_create_task(db, project, req_notifications,
        "Preference Center UI", "Build granular notification settings per category and channel.",
        "medium", "in_progress", dev_b, pm_user, sprint2)
    task_notify_2 = get_or_create_task(db, project, req_notifications,
        "Event-Driven Notification Dispatch", "Integrate with message queue; trigger on grade posted, registration confirmed, etc.",
        "high", "in_progress", dev_a, pm_user, sprint2)

    task_svc_1 = get_or_create_task(db, project, req_services,
        "Service Request Forms", "Dynamic form builder for different request types with file uploads.",
        "medium", "in_progress", dev_a, pm_user, sprint2)
    task_svc_2 = get_or_create_task(db, project, req_services,
        "Request Tracking & SLA", "Status workflow (submitted/in_progress/completed); SLA timers; advisor assignment.",
        "medium", "todo", dev_b, pm_user, sprint2)

    task_grades_1 = get_or_create_task(db, project, req_grades,
        "Grade Book Integration", "Consume grades from LMS via API; normalize and store.",
        "high", "todo", dev_a, pm_user, sprint3)
    task_grades_2 = get_or_create_task(db, project, req_grades,
        "GPA & Transcript", "Calculate term/cumulative GPA; generate unofficial transcript PDF.",
        "high", "todo", dev_b, pm_user, sprint3)

    task_pay_1 = get_or_create_task(db, project, req_payments,
        "Balance & Payment Methods", "Display itemized balance; integrate Stripe for cards, ACH, and 529 plans.",
        "high", "todo", dev_a, pm_user, sprint3)
    task_pay_2 = get_or_create_task(db, project, req_payments,
        "Payment Plans & Receipts", "Installment plans with auto-pay; generate PDF receipts for all transactions.",
        "medium", "todo", dev_b, pm_user, sprint3)

    # Create bugs
    bug_1 = get_or_create_bug(db, project,
        "Waitlist Position Not Updating in Real Time",
        "Students see stale waitlist position; requires manual refresh.",
        "high", "in_progress", dev_a, qa_user, req_registration, task_reg_2)
    bug_2 = get_or_create_bug(db, project,
        "Prerequisite Check False Positive for Transfer Credits",
        "Transfer credits not recognized; blocks valid registrations.",
        "high", "open", dev_b, qa_user, req_registration, task_reg_3)
    bug_3 = get_or_create_bug(db, project,
        "Timetable Conflict Detection Misses Cross-Day Events",
        "Events spanning midnight not detected as conflicts.",
        "medium", "open", dev_a, qa_user, req_timetable, task_tt_2)
    bug_4 = get_or_create_bug(db, project,
        "Notification Preferences Not Respected for SMS",
        "SMS sent even when disabled; email preference works correctly.",
        "medium", "in_progress", dev_b, qa_user, req_notifications, task_notify_1)
    bug_5 = get_or_create_bug(db, project,
        "Service Request File Upload Size Limit Too Low",
        "5MB limit prevents transcript PDF uploads; need 25MB.",
        "low", "open", dev_a, qa_user, req_services, task_svc_1)

    # Create test cases
    tc_1 = get_or_create_test_case(db, project, req_profile,
        "Profile Update Persists",
        "Student logged in",
        "1. Update phone number\n2. Save\n3. Reload page",
        "New phone number displayed; audit log shows change",
        "passed", pm_user)
    tc_2 = get_or_create_test_case(db, project, req_registration,
        "Successful Course Registration",
        "Course has available seats; prerequisites met",
        "1. Search course\n2. Click Register\n3. Confirm",
        "Registration confirmed; seat count decremented; waitlist unchanged",
        "passed", pm_user)
    tc_3 = get_or_create_test_case(db, project, req_registration,
        "Waitlist Auto-Enrollment",
        "Student on waitlist; seat opens",
        "1. Drop registered student\n2. Wait 1 minute\n3. Check waitlisted student",
        "Waitlisted student auto-enrolled; notification sent; position = 0",
        "not_run", pm_user)
    tc_4 = get_or_create_test_case(db, project, req_timetable,
        "Conflict Detection Identifies Overlap",
        "Two courses same time slot",
        "1. Register for Course A\n2. Attempt Course B (same time)\n3. Observe warning",
        "Clear conflict warning displayed; registration blocked until resolved",
        "not_run", pm_user)
    tc_5 = get_or_create_test_case(db, project, req_notifications,
        "Email Notification Delivered",
        "Student has email enabled for grades",
        "1. Instructor posts grade\n2. Check email inbox",
        "Email received within 2 minutes with course, assignment, grade",
        "not_run", pm_user)
    tc_6 = get_or_create_test_case(db, project, req_services,
        "Service Request Submission",
        "Student needs transcript",
        "1. Select 'Transcript Request'\n2. Fill form\n3. Submit",
        "Request created with 'submitted' status; confirmation email sent; tracking ID provided",
        "not_run", pm_user)
    tc_7 = get_or_create_test_case(db, project, req_grades,
        "GPA Calculation Accuracy",
        "Student has grades for 3 courses",
        "1. View transcript\n2. Verify GPA",
        "GPA matches manual calculation (quality points / credits); 2 decimal places",
        "not_run", pm_user)
    tc_8 = get_or_create_test_case(db, project, req_payments,
        "Credit Card Payment Success",
        "Student has balance due",
        "1. Select 'Pay Balance'\n2. Enter test card 4242 4242 4242 4242\n3. Confirm",
        "Payment processed; balance updated; receipt generated; email confirmation sent",
        "not_run", pm_user)

    # Create traceability links
    links_created = 0

    def add_link(source_type, source_id, target_type, target_id, rel_type):
        nonlocal links_created
        if ensure_traceability_link(db, project, pm_user, source_type, source_id, target_type, target_id, rel_type):
            links_created += 1

    # Profile links
    add_link("requirement", req_profile.id, "task", task_profile_1.id, "implements")
    add_link("requirement", req_profile.id, "task", task_profile_2.id, "implements")
    add_link("requirement", req_profile.id, "test_case", tc_1.id, "validates")

    # Registration links
    add_link("requirement", req_registration.id, "task", task_reg_1.id, "implements")
    add_link("requirement", req_registration.id, "task", task_reg_2.id, "implements")
    add_link("requirement", req_registration.id, "task", task_reg_3.id, "implements")
    add_link("requirement", req_registration.id, "bug", bug_1.id, "affects")
    add_link("requirement", req_registration.id, "bug", bug_2.id, "affects")
    add_link("requirement", req_registration.id, "test_case", tc_2.id, "validates")
    add_link("requirement", req_registration.id, "test_case", tc_3.id, "validates")
    add_link("requirement", req_registration.id, "requirement", req_profile.id, "depends_on")  # registration needs profile

    # Timetable links
    add_link("requirement", req_timetable.id, "task", task_tt_1.id, "implements")
    add_link("requirement", req_timetable.id, "task", task_tt_2.id, "implements")
    add_link("requirement", req_timetable.id, "task", task_tt_3.id, "implements")
    add_link("requirement", req_timetable.id, "bug", bug_3.id, "affects")
    add_link("requirement", req_timetable.id, "test_case", tc_4.id, "validates")
    add_link("requirement", req_timetable.id, "requirement", req_registration.id, "depends_on")  # timetable needs registration

    # Notification links
    add_link("requirement", req_notifications.id, "task", task_notify_1.id, "implements")
    add_link("requirement", req_notifications.id, "task", task_notify_2.id, "implements")
    add_link("requirement", req_notifications.id, "bug", bug_4.id, "affects")
    add_link("requirement", req_notifications.id, "test_case", tc_5.id, "validates")
    add_link("requirement", req_notifications.id, "requirement", req_profile.id, "depends_on")  # notifications need profile/contact

    # Service requests links
    add_link("requirement", req_services.id, "task", task_svc_1.id, "implements")
    add_link("requirement", req_services.id, "task", task_svc_2.id, "implements")
    add_link("requirement", req_services.id, "bug", bug_5.id, "affects")
    add_link("requirement", req_services.id, "test_case", tc_6.id, "validates")
    add_link("requirement", req_services.id, "requirement", req_profile.id, "depends_on")

    # Grades links
    add_link("requirement", req_grades.id, "task", task_grades_1.id, "implements")
    add_link("requirement", req_grades.id, "task", task_grades_2.id, "implements")
    add_link("requirement", req_grades.id, "test_case", tc_7.id, "validates")
    add_link("requirement", req_grades.id, "requirement", req_registration.id, "depends_on")  # grades need enrollment
    add_link("requirement", req_grades.id, "requirement", req_notifications.id, "blocks")  # grade notifications block notification prefs

    # Payments links
    add_link("requirement", req_payments.id, "task", task_pay_1.id, "implements")
    add_link("requirement", req_payments.id, "task", task_pay_2.id, "implements")
    add_link("requirement", req_payments.id, "test_case", tc_8.id, "validates")
    add_link("requirement", req_payments.id, "requirement", req_profile.id, "depends_on")  # payments need profile/billing

    # Task-to-task dependencies are not supported by traceability validation
    # Dependencies are modeled through requirement-to-requirement (depends_on, blocks)
    # and requirement-to-task (implements) relationships instead

    print(f"  ✓ Project B seeded: 7 requirements, 14 tasks, 5 bugs, 8 test cases, 3 sprints, 3 milestones, {links_created} traceability links")

    return {
        "project": project,
        "requirements": {
            "profile": req_profile, "registration": req_registration,
            "timetable": req_timetable, "notifications": req_notifications,
            "services": req_services, "grades": req_grades, "payments": req_payments,
        },
        "links_created": links_created,
    }


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main() -> int:
    print("DevFlow College Review Demo Data Seeder")
    print("=" * 60)

    # Safety checks
    file_path = validate_demo_database_target()

    # Verify we can create the engine
    try:
        engine = get_database_engine(settings.database_url)
    except Exception as e:
        print(f"\n✗ Failed to create database engine: {e}", file=sys.stderr)
        return 1

    try:
        # Ensure tables exist
        Base.metadata.create_all(engine)

        with Session(engine) as db:
            # Ensure all roles exist
            print("\n🔐 Ensuring roles exist...")
            for role_code in ROLE_CATALOG.keys():
                get_or_create_role(db, role_code)
            print("  ✓ All 6 roles present")

            # Create demo accounts
            print("\n👥 Creating demo accounts...")
            accounts = {}
            for email, full_name, role_code in DEMO_ACCOUNTS:
                user = get_or_create_user(db, email, full_name, role_code)
                accounts[email] = user
                print(f"  ✓ {full_name} ({email}) → {role_code}")

            # Extract users by email for clarity
            admin_user = accounts["admin@demo.local"]
            pm_user = accounts["pm@demo.local"]
            tl_user = accounts["tl@demo.local"]
            dev_a_user = accounts["dev-a@demo.local"]
            dev_b_user = accounts["dev-b@demo.local"]
            qa_user = accounts["qa@demo.local"]
            client_user = accounts["client@demo.local"]

            # Seed Project A
            project_a_data = seed_project_a(db,
                pm_user=pm_user,
                dev_a=dev_a_user,
                dev_b=dev_b_user,
                tl_user=tl_user,
                qa_user=qa_user,
                client_user=client_user)

            # Seed Project B
            project_b_data = seed_project_b(db,
                pm_user=pm_user,
                dev_a=dev_a_user,
                dev_b=dev_b_user,
                tl_user=tl_user,
                qa_user=qa_user,
                client_user=client_user)

            db.commit()

            # Verify RCIA works for Project A
            print("\n🔍 Verifying RCIA impact analysis for Project A...")
            from backend.app.services.rcia_service import traverse_impacts

            req_auth = project_a_data["requirements"]["auth"]
            impacts = traverse_impacts(db, project_a_data["project"].id, req_auth.id)
            print(f"  ✓ RCIA on {req_auth.requirement_key} ({req_auth.title})")
            print(f"    Found {len(impacts)} impacted artifacts:")
            for impact in impacts:
                print(f"      - {impact['impact_category'].upper()}: {impact['artifact_type']} {str(impact['artifact_id'])[:8]}... via {len(impact['relationship_path'])} hops")

            # Verify Project B RCIA
            print("\n🔍 Verifying RCIA impact analysis for Project B...")
            req_reg = project_b_data["requirements"]["registration"]
            impacts_b = traverse_impacts(db, project_b_data["project"].id, req_reg.id)
            print(f"  ✓ RCIA on {req_reg.requirement_key} ({req_reg.title})")
            print(f"    Found {len(impacts_b)} impacted artifacts:")
            for impact in impacts_b:
                print(f"      - {impact['impact_category'].upper()}: {impact['artifact_type']} {str(impact['artifact_id'])[:8]}...")

        print("\n" + "=" * 60)
        print("✓ Review demo data seeded successfully!")
        print(f"  Database: {file_path}")
        print(f"  Project A: {PROJECT_A_NAME} ({project_a_data['project'].id})")
        print(f"  Project B: {PROJECT_B_NAME} ({project_b_data['project'].id})")
        print()
        print("Demo Accounts (password: demo1234):")
        for email, full_name, role_code in DEMO_ACCOUNTS:
            print(f"  {email} — {full_name} [{role_code}]")
        print()
        print("Project A Membership:")
        print(f"  pm@demo.local → project_manager")
        print(f"  tl@demo.local → team_lead")
        print(f"  dev-a@demo.local → developer")
        print(f"  dev-b@demo.local → developer")
        print(f"  qa@demo.local → tester")
        print(f"  client@demo.local → client")
        print()
        print("Project B Membership: (same users, same roles)")
        print()
        print("RCIA Demo Scenario (Project A):")
        print(f"  Change Request: {project_a_data['change_request_summary']}")
        print(f"  Target Requirement: {project_a_data['auth_req_key']} - {project_a_data['auth_req_title']}")
        print(f"  Run analysis: POST /api/v1/projects/{project_a_data['project'].id}/requirements/{{req_id}}/change-requests")
        print(f"  Then: POST /api/v1/projects/{project_a_data['project'].id}/change-requests/{{cr_id}}/analyses")
        print(f"  Report: GET /api/v1/projects/{project_a_data['project'].id}/reports/change-impact/{{cr_id}}")
        print()
        print("Next steps:")
        print("  1. Start backend: DATABASE_URL=sqlite:///./devflow_demo.db uvicorn backend.app.main:app --reload --port 8001")
        print("  2. Start frontend: cd frontend && npm run dev")
        print("  3. Login as any demo account (password: demo1234)")
        print("  4. Select a project in the project picker")
        print("  5. Navigate to Change Requests → Run Impact Analysis → View Report")
        return 0

    except Exception as e:
        print(f"\n✗ Seeding failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())