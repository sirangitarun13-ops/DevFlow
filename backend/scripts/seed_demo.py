#!/usr/bin/env python3
"""Development-only demo data seed script for RCIA demonstration.

This script populates the local SQLite database with a complete RCIA
demonstration scenario in a project named "Demo Project".

Usage:
    python -m backend.scripts.seed_demo
    or
    python backend/scripts/seed_demo.py

The script is idempotent: running it multiple times will not create
duplicate records. It reuses existing demo data where possible.

This is a DEVELOPMENT-ONLY utility. It requires SQLite mode.
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
from backend.app.models.core import Bug, Project, Requirement, Task, TestCase, project_members
from backend.app.models.rcia import RequirementChangeRequest
from backend.app.models.traceability import TraceabilityLink
from backend.app.services.auth_service import hash_password


DEMO_PASSWORD = "password123"
DEMO_PROJECT_NAME = "Demo Project"
DEMO_REQUIREMENT_KEY = "RCIA-1"
DEMO_REQUIREMENT_2_KEY = "RCIA-2"
DEMO_MANAGER_EMAIL = "pm@example.com"
DEMO_MANAGER_NAME = "Demo Project Manager"


def get_database_path() -> str:
    """Get the SQLite database file path from settings using shared resolver."""
    db_url = settings.database_url
    if not db_url.startswith("sqlite"):
        raise ValueError(f"Expected SQLite URL, got: {db_url}")

    path = get_sqlite_file_path(db_url)
    if path is None:
        raise ValueError(f"Invalid SQLite URL or in-memory database: {db_url}")
    return path


def get_or_create_role(db: Session, role_code: str) -> Role:
    """Return a catalog role, creating only a missing reference role."""
    from backend.app.services.auth_service import ROLE_CATALOG, get_or_create_role as svc_get_or_create_role
    return svc_get_or_create_role(db, role_code)


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


def get_or_create_demo_manager(db: Session) -> User:
    """Ensure the demo project manager user exists with project_manager role."""
    return get_or_create_user(db, DEMO_MANAGER_EMAIL, DEMO_MANAGER_NAME, "project_manager")


def get_or_create_demo_project(db: Session, manager: User) -> Project:
    """Get existing demo project or create it with manager as owner."""
    project = db.scalar(select(Project).where(Project.name == DEMO_PROJECT_NAME))
    if project:
        # Ensure manager is a member with project_manager role
        member = db.execute(
            select(project_members.c.user_id).where(
                project_members.c.project_id == project.id,
                project_members.c.user_id == manager.id,
            )
        ).first()
        if not member:
            db.execute(
                project_members.insert().values(
                    project_id=project.id,
                    user_id=manager.id,
                    project_role="project_manager",
                )
            )
            db.flush()
        return project

    project = Project(
        name=DEMO_PROJECT_NAME,
        description="RCIA demonstration project with requirement, task, bugs, test case, and traceability links.",
        status="active",
        created_by_user_id=manager.id,
    )
    db.add(project)
    db.flush()

    # Add creator as project member with project_manager role
    db.execute(
        project_members.insert().values(
            project_id=project.id,
            user_id=manager.id,
            project_role="project_manager",
        )
    )
    db.flush()
    return project


def get_or_create_requirement(db: Session, project: Project, manager: User) -> Requirement:
    """Get existing requirement RCIA-1 or create it."""
    req = db.scalar(
        select(Requirement).where(
            Requirement.project_id == project.id,
            Requirement.requirement_key == DEMO_REQUIREMENT_KEY,
        )
    )
    if req:
        return req

    req = Requirement(
        project_id=project.id,
        requirement_key=DEMO_REQUIREMENT_KEY,
        title="User Authentication Flow",
        description="Implement secure user authentication with JWT tokens, password hashing, and session management.",
        requirement_type="functional",
        priority="high",
        status="approved",
        version=1,
        created_by_user_id=manager.id,
        updated_by_user_id=manager.id,
    )
    db.add(req)
    db.flush()
    return req


def get_or_create_requirement_2(db: Session, project: Project, manager: User) -> Requirement:
    """Get existing requirement RCIA-2 or create it."""
    req = db.scalar(
        select(Requirement).where(
            Requirement.project_id == project.id,
            Requirement.requirement_key == DEMO_REQUIREMENT_2_KEY,
        )
    )
    if req:
        return req

    req = Requirement(
        project_id=project.id,
        requirement_key=DEMO_REQUIREMENT_2_KEY,
        title="Account Recovery Flow",
        description="Allow users to recover their accounts via email verification and security questions.",
        requirement_type="functional",
        priority="medium",
        status="approved",
        version=1,
        created_by_user_id=manager.id,
        updated_by_user_id=manager.id,
    )
    db.add(req)
    db.flush()
    return req


def get_or_create_task(db: Session, project: Project, requirement: Requirement, manager: User) -> Task:
    """Get existing task linked to requirement or create it."""
    task = db.scalar(
        select(Task).where(
            Task.project_id == project.id,
            Task.requirement_id == requirement.id,
            Task.title == "Implement JWT Authentication Service",
        )
    )
    if task:
        return task

    task = Task(
        project_id=project.id,
        requirement_id=requirement.id,
        title="Implement JWT Authentication Service",
        description="Create auth service with token generation, validation, and refresh logic.",
        priority="high",
        status="in_progress",
        assigned_to_user_id=manager.id,
        created_by_user_id=manager.id,
    )
    db.add(task)
    db.flush()
    return task


def get_or_create_direct_bug(db: Session, project: Project, requirement: Requirement, manager: User) -> Bug:
    """Get existing direct bug linked to requirement or create it."""
    bug = db.scalar(
        select(Bug).where(
            Bug.project_id == project.id,
            Bug.requirement_id == requirement.id,
            Bug.title == "Token Refresh Fails Under Load",
        )
    )
    if bug:
        return bug

    bug = Bug(
        project_id=project.id,
        requirement_id=requirement.id,
        title="Token Refresh Fails Under Load",
        description="When multiple concurrent requests attempt to refresh tokens, race conditions cause 401 errors.",
        severity="high",
        status="open",
        assigned_to_user_id=manager.id,
        reported_by_user_id=manager.id,
    )
    db.add(bug)
    db.flush()
    return bug


def get_or_create_indirect_bug(db: Session, project: Project, task: Task, manager: User) -> Bug:
    """Get existing indirect bug linked to task or create it."""
    bug = db.scalar(
        select(Bug).where(
            Bug.project_id == project.id,
            Bug.task_id == task.id,
            Bug.title == "Session Expiry Not Handled on Mobile",
        )
    )
    if bug:
        return bug

    bug = Bug(
        project_id=project.id,
        task_id=task.id,
        title="Session Expiry Not Handled on Mobile",
        description="Mobile clients do not redirect to login when JWT expires; app crashes instead.",
        severity="medium",
        status="open",
        assigned_to_user_id=manager.id,
        reported_by_user_id=manager.id,
    )
    db.add(bug)
    db.flush()
    return bug


def get_or_create_test_case(db: Session, project: Project, requirement: Requirement, manager: User) -> TestCase:
    """Get existing test case linked to requirement or create it."""
    tc = db.scalar(
        select(TestCase).where(
            TestCase.project_id == project.id,
            TestCase.requirement_id == requirement.id,
            TestCase.title == "Verify Token Refresh Flow",
        )
    )
    if tc:
        return tc

    tc = TestCase(
        project_id=project.id,
        requirement_id=requirement.id,
        title="Verify Token Refresh Flow",
        preconditions="User has valid access and refresh tokens",
        test_steps="1. Wait for access token to expire\n2. Make API request with expired token\n3. Verify refresh token is used automatically\n4. Verify new access token is issued",
        expected_result="Request succeeds with new access token; no user interaction required",
        status="not_run",
        created_by_user_id=manager.id,
    )
    db.add(tc)
    db.flush()
    return tc


def ensure_traceability_link(
    db: Session,
    project: Project,
    manager: User,
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
        created_by_user_id=manager.id,
    )
    db.add(link)
    db.flush()
    return link


def create_traceability_links(db: Session, project: Project, manager: User, requirement: Requirement, requirement_2: Requirement, task: Task, direct_bug: Bug, indirect_bug: Bug, test_case: TestCase) -> int:
    """Create all required traceability links. Returns count of newly created links."""
    created = 0

    # 1. Requirement RCIA-1 → Task (implements)
    if ensure_traceability_link(db, project, manager, "requirement", requirement.id, "task", task.id, "implements"):
        created += 1

    # 2. Requirement RCIA-1 → Direct Bug (affects)
    if ensure_traceability_link(db, project, manager, "requirement", requirement.id, "bug", direct_bug.id, "affects"):
        created += 1

    # 3. Requirement RCIA-1 → Test Case (validates)
    if ensure_traceability_link(db, project, manager, "requirement", requirement.id, "test_case", test_case.id, "validates"):
        created += 1

    # 4. Task → Indirect Bug (implements)
    if ensure_traceability_link(db, project, manager, "task", task.id, "bug", indirect_bug.id, "implements"):
        created += 1

    # 5. Indirect Bug → Task (affects) - cycle for cycle detection test
    if ensure_traceability_link(db, project, manager, "bug", indirect_bug.id, "task", task.id, "affects"):
        created += 1

    # 6. Requirement RCIA-2 depends_on Requirement RCIA-1
    # RCIA-2 (Account Recovery Flow) depends on RCIA-1 (User Authentication Flow)
    if ensure_traceability_link(db, project, manager, "requirement", requirement_2.id, "requirement", requirement.id, "depends_on"):
        created += 1

    return created


def get_or_create_change_request(db: Session, project: Project, requirement: Requirement, manager: User) -> RequirementChangeRequest:
    """Get existing change request or create it."""
    cr = db.scalar(
        select(RequirementChangeRequest).where(
            RequirementChangeRequest.requirement_id == requirement.id,
            RequirementChangeRequest.change_summary == "Analyze this change",
        )
    )
    if cr:
        return cr

    cr = RequirementChangeRequest(
        requirement_id=requirement.id,
        requested_by_user_id=manager.id,
        change_summary="Analyze this change",
        proposed_description="Update authentication flow to support refresh token rotation",
        proposed_priority="high",
        proposed_status="in_progress",
        status="submitted",
    )
    db.add(cr)
    db.flush()
    return cr


def seed_demo_data() -> dict:
    """Seed all demo data. Returns summary counts."""
    db_path = get_database_path()
    resolved_db_url = resolve_sqlite_path(settings.database_url)

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

    try:
        # Ensure tables exist
        Base.metadata.create_all(engine)

        with Session(engine) as db:
            # Ensure roles exist
            for role_code in ("admin", "project_manager", "team_lead", "developer", "tester", "client"):
                get_or_create_role(db, role_code)

            # Create/reuse demo manager
            manager = get_or_create_demo_manager(db)

            # Create/reuse demo project
            project = get_or_create_demo_project(db, manager)

            # Create/reuse requirement RCIA-1
            requirement = get_or_create_requirement(db, project, manager)

            # Create/reuse requirement RCIA-2 (depends on RCIA-1)
            requirement_2 = get_or_create_requirement_2(db, project, manager)

            # Create/reuse artifacts for RCIA-1
            task = get_or_create_task(db, project, requirement, manager)
            direct_bug = get_or_create_direct_bug(db, project, requirement, manager)
            indirect_bug = get_or_create_indirect_bug(db, project, task, manager)
            test_case = get_or_create_test_case(db, project, requirement, manager)

            # Create traceability links (including requirement-to-requirement dependency)
            links_created = create_traceability_links(
                db, project, manager, requirement, requirement_2, task, direct_bug, indirect_bug, test_case
            )

            # Create change request for RCIA-1
            change_request = get_or_create_change_request(db, project, requirement, manager)

            db.commit()

            # Verify the scenario produces expected RCIA results
            from backend.app.services.rcia_service import traverse_impacts

            impacts = traverse_impacts(db, project.id, requirement.id)
            impact_summary = [(i["artifact_type"], str(i["artifact_id"]), i["impact_category"]) for i in impacts]

            return {
                "project_name": project.name,
                "project_id": str(project.id),
                "manager_email": manager.email,
                "manager_name": manager.full_name,
                "requirement_key": requirement.requirement_key,
                "requirement_id": str(requirement.id),
                "requirement_2_key": requirement_2.requirement_key,
                "requirement_2_id": str(requirement_2.id),
                "task_id": str(task.id),
                "direct_bug_id": str(direct_bug.id),
                "indirect_bug_id": str(indirect_bug.id),
                "test_case_id": str(test_case.id),
                "change_request_id": str(change_request.id),
                "links_created": links_created,
                "impacts_found": impact_summary,
            }

    except Exception as e:
        print(f"\n✗ Seeding failed: {e}", file=sys.stderr)
        raise
    finally:
        engine.dispose()


def main() -> int:
    """Main entry point."""
    print("DevFlow RCIA Demonstration Data Seeder")
    print("=" * 50)
    print(f"Environment: {settings.app_environment}")
    print(f"Database URL: {settings.database_url}")
    print()

    if not settings.is_sqlite():
        print("ERROR: DATABASE_URL is not configured for SQLite.", file=sys.stderr)
        print("Set DATABASE_URL=sqlite:///./devflow_local.db in backend/.env", file=sys.stderr)
        return 1

    try:
        summary = seed_demo_data()
        print("\n✓ Demo data seeded successfully!")
        print(f"  Project: {summary['project_name']} (ID: {summary['project_id']})")
        print(f"  Manager: {summary['manager_name']} ({summary['manager_email']})")
        print(f"  Requirement 1: {summary['requirement_key']} (ID: {summary['requirement_id']})")
        print(f"  Requirement 2: {summary['requirement_2_key']} (ID: {summary['requirement_2_id']})")
        print(f"  Artifacts: 1 task, 2 bugs (1 direct, 1 indirect), 1 test case")
        print(f"  Traceability links created: {summary['links_created']}")
        print(f"  Change request: {summary['change_request_id']}")
        print(f"  RCIA impacts: {summary['impacts_found']}")
        print()
        print("Next steps:")
        print("  1. Start backend:  uvicorn backend.app.main:app --reload")
        print("  2. Start frontend: cd frontend && npm run dev")
        print("  3. Login as: pm@example.com / password123")
        print("  4. Select 'Demo Project' in project picker")
        print("  5. Go to Change Requests → click 'Run impact analysis'")
        print("  6. View results at /impact-analysis/<analysis-id>")
        print("  7. Download PDF report from Reports page")
        return 0
    except Exception as e:
        print(f"\n✗ Seeding failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())