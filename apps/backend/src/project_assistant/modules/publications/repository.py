from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.modules.publications.models import ReportPublication
from project_assistant.modules.weekly_reports.models import WeeklyReport, WeeklyReportTeam


class SqlAlchemyPublicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_idempotency_key(self, key: str) -> ReportPublication | None:
        return await self.session.scalar(
            select(ReportPublication).where(ReportPublication.idempotency_key == key)
        )

    async def get_report(self, report_id: str) -> WeeklyReport | None:
        return await self.session.get(WeeklyReport, report_id)

    async def list_report_team_ids(self, report_id: str) -> list[str]:
        team_ids = await self.session.scalars(
            select(WeeklyReportTeam.team_id)
            .where(WeeklyReportTeam.weekly_report_id == report_id)
            .order_by(WeeklyReportTeam.team_id)
        )
        return list(team_ids)

    async def save(self, publication: ReportPublication) -> ReportPublication:
        self.session.add(publication)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.find_by_idempotency_key(publication.idempotency_key)
            if existing is not None:
                return existing
            raise
        await self.session.refresh(publication)
        return publication
