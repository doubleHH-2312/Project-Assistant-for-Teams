from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.modules.audit.models import WorkItemStatusEvent
from project_assistant.modules.daily_reports.models import DailyReport
from project_assistant.modules.memberships.models import TeamMembership, TeamRole
from project_assistant.modules.projects.models import Project
from project_assistant.modules.users.models import User


class SqlAlchemyOverviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_expected_reporters(self, team_id: str) -> list[User]:
        users = await self.session.scalars(
            select(User)
            .join(TeamMembership, TeamMembership.user_id == User.id)
            .where(
                TeamMembership.team_id == team_id,
                TeamMembership.role == TeamRole.MEMBER,
                TeamMembership.active.is_(True),
                User.active.is_(True),
            )
            .order_by(User.name, User.id)
        )
        return list(users)

    async def list_reports_through(
        self, team_id: str, reporting_date: date, history_days: int
    ) -> list[DailyReport]:
        reports = await self.session.scalars(
            select(DailyReport)
            .join(Project, Project.id == DailyReport.project_id)
            .where(
                Project.team_id == team_id,
                DailyReport.report_date <= reporting_date,
                DailyReport.report_date >= reporting_date - timedelta(days=history_days),
            )
            .order_by(DailyReport.report_date, DailyReport.created_at)
        )
        return list(reports)

    async def list_status_events_through(
        self, team_id: str, reporting_date: date, history_days: int
    ) -> list[WorkItemStatusEvent]:
        events = await self.session.scalars(
            select(WorkItemStatusEvent)
            .where(
                WorkItemStatusEvent.team_id == team_id,
                WorkItemStatusEvent.local_date <= reporting_date,
                WorkItemStatusEvent.local_date
                >= reporting_date - timedelta(days=history_days),
            )
            .order_by(WorkItemStatusEvent.recorded_at, WorkItemStatusEvent.id)
        )
        return list(events)
