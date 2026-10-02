from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.core.errors import AppError
from project_assistant.modules.daily_reports.models import DailyReport
from project_assistant.modules.projects.models import Project
from project_assistant.modules.work_items.models import WorkItem


class SqlAlchemyDailyReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_project(self, project_id: str) -> Project | None:
        return await self.session.get(Project, project_id)

    async def get_work_item(self, work_item_id: str) -> WorkItem | None:
        return await self.session.get(WorkItem, work_item_id)

    async def get_by_key(
        self, user_id: str, work_item_id: str, report_date: date
    ) -> DailyReport | None:
        return await self.session.scalar(
            select(DailyReport).where(
                DailyReport.user_id == user_id,
                DailyReport.work_item_id == work_item_id,
                DailyReport.report_date == report_date,
            )
        )

    async def get_by_id(self, report_id: str) -> DailyReport | None:
        return await self.session.get(DailyReport, report_id)

    async def list_for_user(self, user_id: str) -> list[DailyReport]:
        result = await self.session.scalars(
            select(DailyReport)
            .where(DailyReport.user_id == user_id)
            .order_by(DailyReport.report_date.desc(), DailyReport.updated_at.desc())
        )
        return list(result)

    async def save(self, report: DailyReport) -> DailyReport:
        self.session.add(report)
        try:
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise AppError(
                409,
                "DAILY_REPORT_EXISTS",
                "A daily report already exists for this work item and date",
            ) from error
        await self.session.refresh(report)
        return report

