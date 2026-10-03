from datetime import UTC, date, datetime

import pytest

from project_assistant.modules.audit.models import WorkItemStatusEvent
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.teams.overview import TeamOverviewService
from project_assistant.modules.users.models import User


class FakeOverviewRepository:
    def __init__(self, users: list[User], reports: list[DailyReport]) -> None:
        self.users = users
        self.reports = reports

    async def list_expected_reporters(self, team_id: str) -> list[User]:
        del team_id
        return [user for user in self.users if user.active]

    async def list_reports_through(
        self, team_id: str, reporting_date: date, history_days: int
    ) -> list[DailyReport]:
        del team_id, history_days
        user_ids = {user.id for user in self.users}
        return [
            report
            for report in self.reports
            if report.user_id in user_ids and report.report_date <= reporting_date
        ]

    async def list_status_events_through(
        self, team_id: str, reporting_date: date, history_days: int
    ) -> list[WorkItemStatusEvent]:
        del team_id, history_days
        return [
            WorkItemStatusEvent(
                id=f"event-{report.id}",
                daily_report_id=report.id,
                action_invocation_id=f"invocation-{report.id}",
                team_id=report.team_id,
                project_id=report.project_id,
                work_item_id=report.work_item_id,
                user_id=report.user_id,
                status=report.status,
                effective_blocker=report.effective_blocker,
                business_date=report.report_date,
                recorded_at=datetime.combine(
                    report.report_date, datetime.min.time(), tzinfo=UTC
                ),
                local_datetime=datetime.combine(
                    report.report_date, datetime.min.time(), tzinfo=UTC
                ),
                local_date=report.report_date,
                timezone="UTC",
                source="TEST",
            )
            for report in self.reports
            if report.report_date <= reporting_date
        ]


def make_member(index: int) -> User:
    return User(
        id=f"user-{index}",
        external_user_id=f"entra-{index}",
        name=f"Member {index}",
        email=f"member{index}@example.test",
        active=True,
    )


@pytest.mark.asyncio
async def test_overview_computes_coverage_missing_and_blocker_age() -> None:
    users = [make_member(index) for index in range(1, 6)]
    reports = [
        DailyReport(
            id="blocked-old",
            team_id="team-1",
            user_id="user-1",
            project_id="project-1",
            work_item_id="item-1",
            report_date=date(2026, 9, 29),
            status=WorkStatus.BLOCKED,
            work_summary="Waiting for data",
            next_action="Wait",
        ),
        DailyReport(
            id="blocked-current",
            team_id="team-1",
            user_id="user-1",
            project_id="project-1",
            work_item_id="item-1",
            report_date=date(2026, 10, 1),
            status=WorkStatus.BLOCKED,
            work_summary="Waiting for data",
            next_action="Escalate",
        ),
        DailyReport(
            id="current-2",
            team_id="team-1",
            user_id="user-2",
            project_id="project-1",
            work_item_id="item-2",
            report_date=date(2026, 10, 1),
            status=WorkStatus.IN_PROGRESS,
            work_summary="Working",
            next_action="Continue",
        ),
        DailyReport(
            id="current-3",
            team_id="team-1",
            user_id="user-3",
            project_id="project-1",
            work_item_id="item-3",
            report_date=date(2026, 10, 1),
            status=WorkStatus.DONE,
            work_summary="Done",
            next_action="Review",
        ),
    ]
    service = TeamOverviewService(FakeOverviewRepository(users, reports))

    overview = await service.get_overview("team-1", date(2026, 10, 1))

    assert overview.coverage.submitted == 3
    assert overview.coverage.expected == 5
    assert overview.coverage.percentage == 60
    assert [user.id for user in overview.missing_reporters] == ["user-4", "user-5"]
    assert overview.status_counts == {"BLOCKED": 1, "IN_PROGRESS": 1, "DONE": 1}
    assert overview.blockers[0].effective_blocker == "Waiting for data"
    assert overview.blockers[0].blocked_since == date(2026, 9, 29)
    assert overview.blockers[0].age_days == 3
