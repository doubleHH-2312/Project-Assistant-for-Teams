from datetime import UTC, date, datetime

import pytest

from project_assistant.modules.audit.models import (
    ActionInvocation,
    InvocationStatus,
    RequestAuditContext,
    WorkItemStatusEvent,
)
from project_assistant.modules.audit.service import AuditService
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.daily_reports.schemas import DailyReportCreate, DailyReportUpdate
from project_assistant.modules.daily_reports.service import DailyReportService
from project_assistant.modules.projects.models import Project
from project_assistant.modules.teams.models import Team
from project_assistant.modules.users.models import User
from project_assistant.modules.work_items.models import WorkItem


class TimelineRepository:
    def __init__(self, invocations: dict[str, ActionInvocation]) -> None:
        self.invocations = invocations
        self.team = Team(
            id="team-1",
            tenant_id="tenant-1",
            name="Team One",
            timezone="Asia/Ho_Chi_Minh",
        )
        self.project = Project(id="project-1", team_id="team-1", name="Project One")
        self.work_item = WorkItem(
            id="item-1", project_id="project-1", code="ITEM-1", title="Ship MVP"
        )
        self.report: DailyReport | None = None
        self.events: list[WorkItemStatusEvent] = []

    async def get_team(self, team_id: str) -> Team | None:
        return self.team if team_id == self.team.id else None

    async def get_project(self, project_id: str, team_id: str) -> Project | None:
        if project_id == self.project.id and team_id == self.project.team_id:
            return self.project
        return None

    async def get_work_item(self, work_item_id: str, team_id: str) -> WorkItem | None:
        if work_item_id == self.work_item.id and team_id == self.project.team_id:
            return self.work_item
        return None

    async def get_by_key(
        self, user_id: str, work_item_id: str, report_date: date, team_id: str
    ) -> DailyReport | None:
        report = self.report
        if (
            report is not None
            and report.user_id == user_id
            and report.work_item_id == work_item_id
            and report.report_date == report_date
            and report.team_id == team_id
        ):
            return report
        return None

    async def get_by_id(
        self, report_id: str, user_id: str, team_id: str
    ) -> DailyReport | None:
        report = self.report
        if (
            report is not None
            and report.id == report_id
            and report.user_id == user_id
            and report.team_id == team_id
        ):
            return report
        return None

    async def get_latest_event(self, daily_report_id: str) -> WorkItemStatusEvent | None:
        events = [event for event in self.events if event.daily_report_id == daily_report_id]
        return events[-1] if events else None

    async def list_for_user(self, user_id: str, team_id: str) -> list[DailyReport]:
        report = self.report
        return (
            [report]
            if report is not None and report.user_id == user_id and report.team_id == team_id
            else []
        )

    async def save_with_event_and_success(
        self,
        report: DailyReport,
        status_event: WorkItemStatusEvent,
        invocation_id: str,
    ) -> DailyReport:
        self.report = report
        self.events.append(status_event)
        invocation = self.invocations[invocation_id]
        invocation.status = InvocationStatus.SUCCEEDED
        invocation.result_ref = report.id
        invocation.completed_at = status_event.recorded_at
        return report


class TimelineAuditRepository:
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


class AllowAuthorization:
    async def require(self, actor_id, team_ids, permission):  # type: ignore[no-untyped-def]
        del actor_id, team_ids, permission
        return {}


def member() -> User:
    return User(
        id="user-1",
        tenant_id="tenant-1",
        external_user_id="entra-1",
        name="Member",
        email="member@example.test",
    )


def context(idempotency_key: str) -> RequestAuditContext:
    return RequestAuditContext(
        action="daily.submit",
        actor_id="user-1",
        tenant_id="tenant-1",
        team_id="team-1",
        project_id="project-1",
        conversation_id="web:user-1",
        conversation_type="WEB",
        timezone="UTC",
        correlation_id=f"correlation:{idempotency_key}",
        idempotency_key=idempotency_key,
        source="WEB",
    )


@pytest.mark.asyncio
async def test_blocker_date_survives_later_daily_report_update() -> None:
    times = iter(
        [
            datetime(2026, 10, 3, 18, 0, tzinfo=UTC),
            datetime(2026, 10, 6, 2, 0, tzinfo=UTC),
        ]
    )
    audit_repository = TimelineAuditRepository()
    audit_service = AuditService(audit_repository, clock=lambda: next(times))  # type: ignore[arg-type]
    repository = TimelineRepository(audit_repository.invocations)
    service = DailyReportService(
        repository,
        AllowAuthorization(),  # type: ignore[arg-type]
        audit_service,
    )

    report = await service.create(
        member(),
        "team-1",
        DailyReportCreate(
            teamId="team-1",
            projectId="project-1",
            workItemId="item-1",
            reportDate=date(2026, 10, 4),
            status=WorkStatus.BLOCKED,
            workSummary="Blocked by missing environment access",
            blocker=None,
            nextAction="Ask the platform team",
        ),
        context("activity-1:daily.submit"),
    )
    first_event = repository.events[0]

    await service.update(
        member(),
        "team-1",
        report.id,
        DailyReportUpdate(
            status=WorkStatus.IN_PROGRESS,
            workSummary="Access granted; implementation resumed",
            blocker=None,
            nextAction="Finish integration",
        ),
        context("activity-2:daily.submit"),
    )

    assert len(repository.events) == 2
    assert first_event.status == WorkStatus.BLOCKED
    assert first_event.local_date == date(2026, 10, 4)
    assert first_event.business_date == date(2026, 10, 4)
    assert first_event.effective_blocker == "Blocked by missing environment access"
    assert repository.events[1].status == WorkStatus.IN_PROGRESS
    assert repository.events[1].local_date == date(2026, 10, 6)
    assert repository.events[1].supersedes_event_id == first_event.id
