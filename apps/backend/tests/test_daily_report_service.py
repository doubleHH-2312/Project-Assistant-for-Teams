from datetime import date

import pytest

from project_assistant.core.errors import AppError
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.daily_reports.schemas import DailyReportCreate, DailyReportUpdate
from project_assistant.modules.daily_reports.service import DailyReportService
from project_assistant.modules.projects.models import Project
from project_assistant.modules.users.models import User, UserRole
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

    async def get_project(self, project_id: str) -> Project | None:
        return self.projects.get(project_id)

    async def get_work_item(self, work_item_id: str) -> WorkItem | None:
        return self.work_items.get(work_item_id)

    async def get_by_key(
        self, user_id: str, work_item_id: str, report_date: date
    ) -> DailyReport | None:
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

    async def get_by_id(self, report_id: str) -> DailyReport | None:
        return self.reports.get(report_id)

    async def list_for_user(self, user_id: str) -> list[DailyReport]:
        return [report for report in self.reports.values() if report.user_id == user_id]

    async def save(self, report: DailyReport) -> DailyReport:
        if report.id is None:
            report.id = f"daily-{len(self.reports) + 1}"
        self.reports[report.id] = report
        return report


def member(user_id: str = "user-1", team_id: str = "team-1") -> User:
    return User(
        id=user_id,
        external_user_id=f"entra-{user_id}",
        name="Member",
        email=f"{user_id}@example.test",
        role=UserRole.MEMBER,
        team_id=team_id,
    )


@pytest.mark.asyncio
async def test_create_rejects_duplicate_and_exposes_effective_blocker() -> None:
    repository = FakeDailyReportRepository()
    service = DailyReportService(repository)
    request = DailyReportCreate(
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
    service = DailyReportService(repository)

    with pytest.raises(AppError) as hidden:
        await service.update(
            member(user_id="user-2"),
            report.id,
            DailyReportUpdate(workSummary="Unauthorized edit"),
        )

    assert hidden.value.status_code == 404
    assert report.work_summary == "Working"
