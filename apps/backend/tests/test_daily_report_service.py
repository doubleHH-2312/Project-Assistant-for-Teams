from datetime import date

import pytest

from project_assistant.core.errors import AppError
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.daily_reports.schemas import DailyReportCreate, DailyReportUpdate
from project_assistant.modules.daily_reports.service import DailyReportService
from project_assistant.modules.projects.models import Project
from project_assistant.modules.users.models import User
from project_assistant.modules.work_items.models import WorkItem


class FakeDailyReportRepository:
    def __init__(self) -> None:
        self.projects = {"project-1": Project(id="project-1", team_id="team-1", name="MVP")}
        self.work_items = {
            "item-1": WorkItem(
                id="item-1", project_id="project-1", code="OPS-001", title="Build"
            )
        }
        self.reports: dict[str, DailyReport] = {}

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

    async def save(self, report: DailyReport) -> DailyReport:
        if report.id is None:
            report.id = f"daily-{len(self.reports) + 1}"
        self.reports[report.id] = report
        return report


class AllowAuthorization:
    async def require(self, actor_id, team_ids, permission):  # type: ignore[no-untyped-def]
        del actor_id, team_ids, permission
        return {}


def member(user_id: str = "user-1") -> User:
    return User(
        id=user_id,
        external_user_id=f"entra-{user_id}",
        name="Member",
        email=f"{user_id}@example.test",
    )


@pytest.mark.asyncio
async def test_create_rejects_duplicate_and_exposes_effective_blocker() -> None:
    repository = FakeDailyReportRepository()
    service = DailyReportService(repository, AllowAuthorization())  # type: ignore[arg-type]
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

    created = await service.create(member(), request)

    assert created.effective_blocker == "Waiting for approved sample data"
    with pytest.raises(AppError) as duplicate:
        await service.create(member(), request)
    assert duplicate.value.status_code == 409
    assert duplicate.value.code == "DAILY_REPORT_EXISTS"


@pytest.mark.asyncio
async def test_update_hides_another_members_report() -> None:
    repository = FakeDailyReportRepository()
    report = DailyReport(
        id="daily-1",
        user_id="user-1",
        project_id="project-1",
        work_item_id="item-1",
        report_date=date(2026, 10, 1),
        status=WorkStatus.IN_PROGRESS,
        work_summary="Working",
        next_action="Continue",
    )
    repository.reports[report.id] = report
    service = DailyReportService(repository, AllowAuthorization())  # type: ignore[arg-type]

    with pytest.raises(AppError) as hidden:
        await service.update(
            member(user_id="user-2"),
            "team-1",
            report.id,
            DailyReportUpdate(workSummary="Unauthorized edit"),
        )

    assert hidden.value.status_code == 404
    assert report.work_summary == "Working"
