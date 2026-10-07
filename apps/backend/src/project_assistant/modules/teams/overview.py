from collections import Counter
from datetime import date
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from project_assistant.modules.audit.models import WorkItemStatusEvent
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
    project_id: str = Field(alias="projectId")
    work_item_id: str = Field(alias="workItemId")
    effective_blocker: str = Field(alias="effectiveBlocker")
    blocked_since: date = Field(alias="blockedSince")
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

    async def list_status_events_through(
        self, team_id: str, reporting_date: date, history_days: int
    ) -> list[WorkItemStatusEvent]: ...


class TeamOverviewService:
    def __init__(self, repository: OverviewRepository) -> None:
        self.repository = repository

    async def get_overview(self, team_id: str, reporting_date: date) -> TeamOverview:
        users = [
            user for user in await self.repository.list_expected_reporters(team_id) if user.active
        ]
        reports = await self.repository.list_reports_through(team_id, reporting_date, 90)
        events = await self.repository.list_status_events_through(team_id, reporting_date, 90)
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
        blockers: list[ActiveBlocker] = []
        event_pairs = {(event.user_id, event.work_item_id) for event in events}
        reports_by_id = {report.id: report for report in reports}
        for user_id, work_item_id in event_pairs:
            history = sorted(
                (
                    event
                    for event in events
                    if event.user_id == user_id and event.work_item_id == work_item_id
                ),
                key=lambda event: (event.recorded_at, event.id),
            )
            latest_event = history[-1]
            if latest_event.status != WorkStatus.BLOCKED or not latest_event.effective_blocker:
                continue
            matching_dates = [
                event.local_date
                for event in history
                if event.status == WorkStatus.BLOCKED
                and event.effective_blocker == latest_event.effective_blocker
            ]
            first_date = min(matching_dates)
            latest_report = reports_by_id.get(latest_event.daily_report_id)
            blockers.append(
                ActiveBlocker(
                    report_id=latest_event.daily_report_id,
                    user_id=user_id,
                    project_id=latest_event.project_id,
                    work_item_id=work_item_id,
                    effective_blocker=latest_event.effective_blocker,
                    blocked_since=first_date,
                    age_days=(reporting_date - first_date).days + 1,
                    next_action=latest_report.next_action if latest_report else "",
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
