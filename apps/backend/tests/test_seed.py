from datetime import date

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from project_assistant.core.database import Base
from project_assistant.modules.audit.models import (
    ActionInvocation,
    InvocationStatus,
    WorkItemStatusEvent,
)
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.projects.models import Project
from project_assistant.modules.teams.models import Team
from project_assistant.modules.users.models import User
from project_assistant.modules.weekly_reports.models import WeeklyReport, WeeklyReportStatus
from project_assistant.modules.work_items.models import WorkItem
from project_assistant.seed import seed_database


def test_seed_is_idempotent_and_contains_demo_scenarios() -> None:
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        del connection_record
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_database(session, reference_date=date(2026, 10, 1))
        seed_database(session, reference_date=date(2026, 10, 1))

        assert session.scalar(select(func.count()).select_from(Team)) == 2
        assert session.scalar(select(func.count()).select_from(Project)) == 4
        assert session.scalar(select(func.count()).select_from(User)) >= 8
        assert session.scalar(select(func.count()).select_from(WorkItem)) >= 20
        assert session.scalar(select(func.count()).select_from(DailyReport)) >= 30
        assert (
            session.scalar(
                select(func.count())
                .select_from(DailyReport)
                .where(DailyReport.status == WorkStatus.BLOCKED)
            )
            >= 2
        )
        report_count = session.scalar(select(func.count()).select_from(DailyReport))
        assert report_count is not None
        assert (
            session.scalar(select(func.count()).select_from(ActionInvocation))
            == report_count
        )
        assert (
            session.scalar(select(func.count()).select_from(WorkItemStatusEvent))
            == report_count
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ActionInvocation)
                .where(ActionInvocation.status == InvocationStatus.SUCCEEDED)
            )
            == report_count
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(WorkItemStatusEvent)
                .where(WorkItemStatusEvent.status == WorkStatus.BLOCKED)
            )
            >= 2
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(WeeklyReport)
                .where(WeeklyReport.status == WeeklyReportStatus.CONFIRMED)
            )
            >= 1
        )
        membership_rows = session.execute(
            select(
                func.count(),
            ).select_from(Base.metadata.tables["team_memberships"])
        ).scalar_one()
        assert membership_rows >= 10
    engine.dispose()
