from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from project_assistant.core.database import Base
from project_assistant.modules import model_registry  # noqa: F401
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.daily_reports.repository import SqlAlchemyDailyReportRepository
from project_assistant.modules.memberships.models import TeamMembership, TeamRole
from project_assistant.modules.notifications.repository import SqlAlchemyNotificationRepository
from project_assistant.modules.projects.models import Project
from project_assistant.modules.teams.models import Team
from project_assistant.modules.teams.repository import SqlAlchemyOverviewRepository
from project_assistant.modules.users.models import User
from project_assistant.modules.weekly_reports.models import (
    ReportScope,
    WeeklyReport,
    WeeklyReportStatus,
)
from project_assistant.modules.weekly_reports.repository import SqlAlchemyWeeklyReportRepository
from project_assistant.modules.work_items.models import WorkItem


class SyncBackedAsyncSession:
    """Run repository statements against real SQLite without an async DB driver."""

    def __init__(self, session: Session) -> None:
        self.session = session

    async def scalar(self, statement):  # type: ignore[no-untyped-def]
        return self.session.scalar(statement)

    async def scalars(self, statement):  # type: ignore[no-untyped-def]
        return self.session.scalars(statement)


def _seed_scoped_records(session: Session) -> None:
    teams = [
        Team(id="team-a", tenant_id="tenant-1", name="Team A"),
        Team(id="team-b", tenant_id="tenant-1", name="Team B"),
    ]
    users = [
        User(
            id="user-1",
            tenant_id="tenant-1",
            external_user_id="entra-1",
            name="Member One",
            email="member1@example.test",
        ),
        User(
            id="user-2",
            tenant_id="tenant-1",
            external_user_id="entra-2",
            name="Member Two",
            email="member2@example.test",
        ),
    ]
    session.add_all(teams)
    session.flush()
    session.add_all(users)
    session.flush()
    session.add_all(
        [
            TeamMembership(
                id="membership-a",
                user_id="user-1",
                team_id="team-a",
                role=TeamRole.MEMBER,
            ),
            TeamMembership(
                id="membership-b",
                user_id="user-2",
                team_id="team-b",
                role=TeamRole.MEMBER,
            ),
        ]
    )
    projects = [
        Project(id="project-a", team_id="team-a", name="Shared Name"),
        Project(id="project-b", team_id="team-b", name="Shared Name"),
    ]
    session.add_all(projects)
    session.flush()
    work_items = [
        WorkItem(id="item-a", project_id="project-a", code="SAME", title="A"),
        WorkItem(id="item-b", project_id="project-b", code="SAME", title="B"),
    ]
    session.add_all(work_items)
    session.flush()
    reports = [
        DailyReport(
            id="daily-a",
            team_id="team-a",
            user_id="user-1",
            project_id="project-a",
            work_item_id="item-a",
            report_date=date(2026, 10, 2),
            status=WorkStatus.IN_PROGRESS,
            work_summary="Team A work",
            next_action="Continue A",
        ),
        DailyReport(
            id="daily-b",
            team_id="team-b",
            user_id="user-1",
            project_id="project-b",
            work_item_id="item-b",
            report_date=date(2026, 10, 2),
            status=WorkStatus.IN_PROGRESS,
            work_summary="Team B work",
            next_action="Continue B",
        ),
    ]
    session.add_all(reports)
    session.flush()
    session.add_all(
        [
            WeeklyReport(
                id="weekly-a",
                scope=ReportScope.MEMBER,
                subject_user_id="user-1",
                team_id="team-a",
                week_start=date(2026, 9, 28),
                week_end=date(2026, 10, 2),
                content_json={},
                missing_contributors=[],
                input_record_ids=["daily-a"],
                generation_source="MOCK",
                generation_metadata={},
                status=WeeklyReportStatus.GENERATED,
                template_id="template-a",
                template_version=1,
                created_by="user-1",
            ),
            WeeklyReport(
                id="weekly-b",
                scope=ReportScope.MEMBER,
                subject_user_id="user-1",
                team_id="team-b",
                week_start=date(2026, 9, 28),
                week_end=date(2026, 10, 2),
                content_json={},
                missing_contributors=[],
                input_record_ids=["daily-b"],
                generation_source="MOCK",
                generation_metadata={},
                status=WeeklyReportStatus.GENERATED,
                template_id="template-b",
                template_version=1,
                created_by="user-1",
            ),
        ]
    )
    session.commit()


@pytest.mark.asyncio
async def test_repositories_never_cross_explicit_team_scope() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_scoped_records(session)
        async_session = SyncBackedAsyncSession(session)
        daily = SqlAlchemyDailyReportRepository(async_session)  # type: ignore[arg-type]
        overview = SqlAlchemyOverviewRepository(async_session)  # type: ignore[arg-type]
        weekly = SqlAlchemyWeeklyReportRepository(async_session)  # type: ignore[arg-type]
        notification = SqlAlchemyNotificationRepository(async_session)  # type: ignore[arg-type]

        assert [report.id for report in await daily.list_for_user("user-1", "team-a")] == [
            "daily-a"
        ]
        assert await daily.get_project("project-b", "team-a") is None
        assert await daily.get_work_item("item-b", "team-a") is None
        assert [user.id for user in await overview.list_expected_reporters("team-a")] == [
            "user-1"
        ]
        assert [
            report.id
            for report in await overview.list_reports_through(
                "team-a", date(2026, 10, 2), 7
            )
        ] == ["daily-a"]
        assert [
            report.id
            for report in await weekly.list_daily_reports(
                "user-1", "team-a", date(2026, 9, 28), date(2026, 10, 2)
            )
        ] == ["daily-a"]
        assert await weekly.get_by_id("weekly-b", "team-a") is None
        assert [user.id for user in await notification.list_expected_reporters("team-a")] == [
            "user-1"
        ]
        assert await notification.has_daily_report(
            "user-1", "team-a", date(2026, 10, 2)
        )
        assert not await notification.has_daily_report(
            "user-1", "team-b", date(2026, 10, 1)
        )
    engine.dispose()
