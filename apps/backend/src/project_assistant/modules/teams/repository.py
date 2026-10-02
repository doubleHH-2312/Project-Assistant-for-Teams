from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.modules.daily_reports.models import DailyReport
from project_assistant.modules.users.models import User, UserRole


class SqlAlchemyOverviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_expected_reporters(self, team_id: str) -> list[User]:
        users = await self.session.scalars(
            select(User)
            .where(User.team_id == team_id, User.active.is_(True), User.role == UserRole.MEMBER)
            .order_by(User.name, User.id)
        )
        return list(users)

    async def list_reports_through(
        self, team_id: str, reporting_date: date, history_days: int
    ) -> list[DailyReport]:
        reports = await self.session.scalars(
            select(DailyReport)
            .join(User, User.id == DailyReport.user_id)
            .where(
                User.team_id == team_id,
                DailyReport.report_date <= reporting_date,
                DailyReport.report_date >= reporting_date - timedelta(days=history_days),
            )
            .order_by(DailyReport.report_date, DailyReport.created_at)
        )
        return list(reports)

