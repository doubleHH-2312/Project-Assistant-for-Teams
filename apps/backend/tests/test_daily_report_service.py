from datetime import UTC, date, datetime

import pytest

from project_assistant.core.errors import AppError
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


class FakeDailyReportRepository:
    def __init__(self, invocations: dict[str, ActionInvocation]) -> None:
        self.invocations = invocations
        self.team = Team(
            id="team-1",
            tenant_id="tenant-1",
            name="Team One",
            timezone="Asia/Ho_Chi_Minh",
            backfill_window_days=7,
        )
        self.projects = {"project-1": Project(id="project-1", team_id="team-1", name="MVP")}
        self.work_items = {
            "item-1": WorkItem(
                id="item-1", project_id="project-1", code="OPS-001", title="Build"
            )
        }
        self.reports: dict[str, DailyReport] = {}
        self.events: list[WorkItemStatusEvent] = []

    async def get_team(self, team_id: str) -> Team | None:
        return self.team if team_id == self.team.id else None

    async def get_project(self, project_id: str, team_id: str) -> Project | None:
        project = self.projects.get(project_id)
        return project if project is not None and project.team_id == team_id else None

    async def get_work_item(self, work_item_id: str, team_id: str) -> WorkItem | None:
        item = self.work_items.get(work_item_id)
        project = self.projects.get(item.project_id) if item is not None else None
        return item if project is not None and project.team_id == team_id else None

    async def get_by_key(
        self, user_id: str, work_item_id: str, report_date: date, team_id: str
    ) -> DailyReport | None:
        del team_id
        return next(
            (
                report
                for report in self.reports.values()
                if report.user_id == user_id
                and report.work_item_id == work_item_id
                and report.report_date == report_date
            ),
            None,
        )

    async def get_by_id(
        self, report_id: str, user_id: str, team_id: str
    ) -> DailyReport | None:
        report = self.reports.get(report_id)
        project = self.projects.get(report.project_id) if report is not None else None
        if (
            report is None
            or report.user_id != user_id
            or project is None
            or project.team_id != team_id
        ):
            return None
        return report

    async def list_for_user(self, user_id: str, team_id: str) -> list[DailyReport]:
        return [
            report
            for report in self.reports.values()
            if report.user_id == user_id
            and self.projects[report.project_id].team_id == team_id
        ]

    async def get_latest_event(
        self, daily_report_id: str
    ) -> WorkItemStatusEvent | None:
        events = [event for event in self.events if event.daily_report_id == daily_report_id]
        return events[-1] if events else None

    async def save_with_event_and_success(
        self,
        report: DailyReport,
        status_event: WorkItemStatusEvent,
        invocation_id: str,
    ) -> DailyReport:
        self.reports[report.id] = report
        self.events.append(status_event)
        invocation = self.invocations[invocation_id]
        invocation.status = InvocationStatus.SUCCEEDED
        invocation.result_ref = report.id
        return report


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


class AllowAuthorization:
    async def require(self, actor_id, team_ids, permission):  # type: ignore[no-untyped-def]
        del actor_id, team_ids, permission
        return {}


def member(user_id: str = "user-1") -> User:
    return User(
        id=user_id,
        tenant_id="tenant-1",
        external_user_id=f"entra-{user_id}",
        name="Member",
        email=f"{user_id}@example.test",
    )


def audit_context(key: str) -> RequestAuditContext:
    return RequestAuditContext(
        action="daily.submit",
        actor_id="user-1",
        tenant_id="tenant-1",
        team_id="team-1",
        project_id="project-1",
        conversation_id="web:user-1",
        conversation_type="WEB",
        timezone="UTC",
        correlation_id=f"correlation:{key}",
        idempotency_key=key,
        source="WEB",
    )


def make_service() -> tuple[FakeDailyReportRepository, DailyReportService]:
    audit_repository = FakeAuditRepository()
    repository = FakeDailyReportRepository(audit_repository.invocations)
    audit_service = AuditService(
        audit_repository,
        clock=lambda: datetime(2026, 10, 1, 8, tzinfo=UTC),
    )
    service = DailyReportService(
        repository,
        AllowAuthorization(),  # type: ignore[arg-type]
        audit_service,
    )
    return repository, service


@pytest.mark.asyncio
async def test_create_rejects_duplicate_and_exposes_effective_blocker() -> None:
    repository, service = make_service()
    request = DailyReportCreate(
        teamId="team-1",
        projectId="project-1",
        workItemId="item-1",
        reportDate=date(2026, 10, 1),
        status=WorkStatus.BLOCKED,
        workSummary="Waiting for approved sample data",
        blocker=None,
        nextAction="Resume integration",
    )

    created = await service.create(
        member(), "team-1", request, audit_context("daily:create:1")
    )

    assert created.effective_blocker == "Waiting for approved sample data"
    with pytest.raises(AppError) as duplicate:
        await service.create(
            member(), "team-1", request, audit_context("daily:create:2")
        )
    assert duplicate.value.status_code == 409
    assert duplicate.value.code == "DAILY_REPORT_EXISTS"


@pytest.mark.asyncio
async def test_update_hides_another_members_report() -> None:
    repository, service = make_service()
    report = DailyReport(
        id="daily-1",
        team_id="team-1",
        user_id="user-1",
        project_id="project-1",
        work_item_id="item-1",
        report_date=date(2026, 10, 1),
        status=WorkStatus.IN_PROGRESS,
        work_summary="Working",
        next_action="Continue",
    )
    repository.reports[report.id] = report

    with pytest.raises(AppError) as hidden:
        await service.update(
            member(user_id="user-2"),
            "team-1",
            report.id,
            DailyReportUpdate(workSummary="Unauthorized edit"),
            audit_context("daily:update:1"),
        )

    assert hidden.value.status_code == 404
    assert report.work_summary == "Working"
