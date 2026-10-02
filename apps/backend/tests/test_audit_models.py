from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from project_assistant.core.database import Base
from project_assistant.modules import model_registry  # noqa: F401
from project_assistant.modules.audit.models import (
    ActionInvocation,
    InvocationStatus,
    RequestAuditContext,
    WorkItemStatusEvent,
)
from project_assistant.modules.audit.service import AuditService
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.projects.models import Project
from project_assistant.modules.teams.models import Team
from project_assistant.modules.users.models import User
from project_assistant.modules.work_items.models import WorkItem


class FakeAuditRepository:
    def __init__(self) -> None:
        self.invocations: dict[str, ActionInvocation] = {}

    async def find_by_idempotency_key(self, key: str) -> ActionInvocation | None:
        return next(
            (
                invocation
                for invocation in self.invocations.values()
                if invocation.idempotency_key == key
            ),
            None,
        )

    async def get(self, invocation_id: str) -> ActionInvocation | None:
        return self.invocations.get(invocation_id)

    async def save(self, invocation: ActionInvocation) -> ActionInvocation:
        self.invocations[invocation.id] = invocation
        return invocation


def audit_context(**metadata: object) -> RequestAuditContext:
    return RequestAuditContext(
        action="daily.create",
        actor_id="user-1",
        tenant_id="tenant-1",
        team_id="team-1",
        project_id="project-1",
        conversation_id="conversation-1",
        conversation_type="WEB",
        timezone="Asia/Ho_Chi_Minh",
        correlation_id="correlation-1",
        idempotency_key="activity-1:daily.create",
        source="WEB",
        metadata=metadata,
    )


@pytest.mark.asyncio
async def test_audit_lifecycle_uses_server_time_and_sanitizes_metadata() -> None:
    repository = FakeAuditRepository()
    triggered_at = datetime(2026, 10, 3, 18, 30, tzinfo=UTC)
    service = AuditService(repository, clock=lambda: triggered_at)  # type: ignore[arg-type]

    invocation = await service.start(
        audit_context(
            activityId="activity-1",
            authorization="Bearer must-not-be-stored",
            reportContent="complete report text must-not-be-stored",
            retryCount=1,
        )
    )
    replay = await service.start(audit_context(activityId="ignored-on-replay"))

    assert replay is invocation
    assert invocation.status == InvocationStatus.PENDING
    assert invocation.triggered_at == triggered_at
    assert invocation.local_date == date(2026, 10, 4)
    assert invocation.metadata_json == {"activityId": "activity-1", "retryCount": 1}

    denied = await service.deny(invocation.id, "FORBIDDEN")
    assert denied.status == InvocationStatus.DENIED
    assert denied.error_code == "FORBIDDEN"
    assert denied.completed_at == triggered_at


def test_audit_constraints_and_status_event_linkage_are_persisted() -> None:
    engine = create_engine("sqlite:///:memory:")
    event.listen(
        engine,
        "connect",
        lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"),
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Team(id="team-1", tenant_id="tenant-1", name="Team One"))
        session.add(
            User(
                id="user-1",
                tenant_id="tenant-1",
                external_user_id="entra-1",
                name="Member",
                email="member@example.test",
            )
        )
        session.flush()
        session.add(Project(id="project-1", team_id="team-1", name="Project One"))
        session.flush()
        session.add(
            WorkItem(
                id="item-1",
                project_id="project-1",
                code="ITEM-1",
                title="Implement audit",
            )
        )
        session.flush()
        invocation = ActionInvocation(
            id="invocation-1",
            action="daily.create",
            actor_id="user-1",
            tenant_id="tenant-1",
            team_id="team-1",
            project_id="project-1",
            conversation_id="conversation-1",
            conversation_type="WEB",
            triggered_at=datetime(2026, 10, 4, 8, tzinfo=UTC),
            local_datetime=datetime(2026, 10, 4, 15, tzinfo=UTC),
            local_date=date(2026, 10, 4),
            timezone="Asia/Ho_Chi_Minh",
            correlation_id="correlation-1",
            idempotency_key="activity-1:daily.create",
            status=InvocationStatus.PENDING,
            metadata_json={},
        )
        report = DailyReport(
            id="daily-1",
            team_id="team-1",
            user_id="user-1",
            project_id="project-1",
            work_item_id="item-1",
            report_date=date(2026, 10, 4),
            status=WorkStatus.BLOCKED,
            work_summary="Blocked by access",
            next_action="Request access",
            source="WEB",
        )
        session.add_all([invocation, report])
        session.flush()
        status_event = WorkItemStatusEvent(
            id="event-1",
            daily_report_id="daily-1",
            action_invocation_id="invocation-1",
            team_id="team-1",
            project_id="project-1",
            work_item_id="item-1",
            user_id="user-1",
            status=WorkStatus.BLOCKED,
            effective_blocker="Blocked by access",
            business_date=date(2026, 10, 4),
            recorded_at=datetime(2026, 10, 4, 8, tzinfo=UTC),
            local_datetime=datetime(2026, 10, 4, 15, tzinfo=UTC),
            local_date=date(2026, 10, 4),
            timezone="Asia/Ho_Chi_Minh",
            source="WEB",
        )
        session.add(status_event)
        session.commit()

        assert status_event.daily_report_id == report.id
        assert status_event.action_invocation_id == invocation.id

        session.add(
            ActionInvocation(
                id="invocation-2",
                action="daily.create",
                actor_id="user-1",
                tenant_id="tenant-1",
                team_id="team-1",
                project_id="project-1",
                conversation_id="conversation-1",
                conversation_type="WEB",
                triggered_at=datetime(2026, 10, 4, 8, tzinfo=UTC),
                local_datetime=datetime(2026, 10, 4, 15, tzinfo=UTC),
                local_date=date(2026, 10, 4),
                timezone="Asia/Ho_Chi_Minh",
                correlation_id="correlation-2",
                idempotency_key="activity-1:daily.create",
                status=InvocationStatus.PENDING,
                metadata_json={},
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
    engine.dispose()
