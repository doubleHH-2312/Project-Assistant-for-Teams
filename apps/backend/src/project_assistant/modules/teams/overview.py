from collections import Counter
from datetime import date
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.users.models import User


class OverviewModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class Coverage(OverviewModel):
    submitted: int
    expected: int
    percentage: int


class ReporterSummary(OverviewModel):
    id: str
    name: str


class ActiveBlocker(OverviewModel):
    report_id: str = Field(alias="reportId")
    user_id: str = Field(alias="userId")
    work_item_id: str = Field(alias="workItemId")
    effective_blocker: str = Field(alias="effectiveBlocker")
    age_days: int = Field(alias="ageDays")
    next_action: str = Field(alias="nextAction")


class TeamOverview(OverviewModel):
    reporting_date: date = Field(alias="reportingDate")
    coverage: Coverage
    missing_reporters: list[ReporterSummary] = Field(alias="missingReporters")
    status_counts: dict[str, int] = Field(alias="statusCounts")
    blockers: list[ActiveBlocker]


class OverviewRepository(Protocol):
    async def list_expected_reporters(self, team_id: str) -> list[User]: ...

    async def list_reports_through(
        self, team_id: str, reporting_date: date, history_days: int
    ) -> list[DailyReport]: ...


class TeamOverviewService:
    def __init__(self, repository: OverviewRepository) -> None:
        self.repository = repository

    async def get_overview(self, team_id: str, reporting_date: date) -> TeamOverview:
        users = [
            user for user in await self.repository.list_expected_reporters(team_id) if user.active
        ]
        reports = await self.repository.list_reports_through(team_id, reporting_date, 90)
        current = [report for report in reports if report.report_date == reporting_date]
        submitted_ids = {report.user_id for report in current}
        missing = sorted(
            (
                ReporterSummary(id=user.id, name=user.name)
                for user in users
                if user.id not in submitted_ids
            ),
            key=lambda user: (user.name, user.id),
        )
        expected = len(users)
        submitted = len(submitted_ids)
        percentage = round((submitted / expected) * 100) if expected else 100
        counts = Counter(report.status.value for report in current)
        user_work_item_pairs = {(report.user_id, report.work_item_id) for report in reports}
        blockers: list[ActiveBlocker] = []
        for user_id, work_item_id in user_work_item_pairs:
            history = sorted(
                (
                    report
                    for report in reports
                    if report.user_id == user_id and report.work_item_id == work_item_id
                ),
                key=lambda report: (report.report_date, report.updated_at or report.created_at),
            )
            latest = history[-1]
            if latest.status != WorkStatus.BLOCKED or not latest.effective_blocker:
                continue
            matching_dates = [
                report.report_date
                for report in history
                if report.status == WorkStatus.BLOCKED
                and report.effective_blocker == latest.effective_blocker
            ]
            first_date = min(matching_dates)
            blockers.append(
                ActiveBlocker(
                    report_id=latest.id,
                    user_id=user_id,
                    work_item_id=work_item_id,
                    effective_blocker=latest.effective_blocker,
                    age_days=(reporting_date - first_date).days + 1,
                    next_action=latest.next_action,
                )
            )
        blockers.sort(key=lambda blocker: (-blocker.age_days, blocker.user_id))
        return TeamOverview(
            reporting_date=reporting_date,
            coverage=Coverage(submitted=submitted, expected=expected, percentage=percentage),
            missing_reporters=missing,
            status_counts=dict(counts),
            blockers=blockers,
        )
