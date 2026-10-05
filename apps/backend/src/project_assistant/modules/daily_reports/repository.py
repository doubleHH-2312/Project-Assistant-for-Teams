from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.core.errors import AppError
from project_assistant.modules.audit.models import (
    ActionInvocation,
    InvocationStatus,
    WorkItemStatusEvent,
)
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.projects.models import Project
from project_assistant.modules.teams.models import Team
from project_assistant.modules.work_items.models import WorkItem


class SqlAlchemyDailyReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_team(self, team_id: str) -> Team | None:
        return await self.session.get(Team, team_id)

    async def get_project(self, project_id: str, team_id: str) -> Project | None:
        return await self.session.scalar(
            select(Project).where(Project.id == project_id, Project.team_id == team_id)
        )

    async def get_work_item(self, work_item_id: str, team_id: str) -> WorkItem | None:
        return await self.session.scalar(
            select(WorkItem)
            .join(Project, Project.id == WorkItem.project_id)
            .where(WorkItem.id == work_item_id, Project.team_id == team_id)
        )

    async def list_active_projects(self, team_id: str) -> list[Project]:
        projects = await self.session.scalars(
            select(Project)
            .where(Project.team_id == team_id, Project.status == "ACTIVE")
            .order_by(Project.name, Project.id)
        )
        return list(projects)

    async def list_work_items(self, team_id: str) -> list[WorkItem]:
        work_items = await self.session.scalars(
            select(WorkItem)
            .join(Project, Project.id == WorkItem.project_id)
            .where(Project.team_id == team_id, Project.status == "ACTIVE")
            .order_by(WorkItem.code, WorkItem.id)
        )
        return list(work_items)

    async def get_by_key(
        self, user_id: str, work_item_id: str, report_date: date, team_id: str
    ) -> DailyReport | None:
        return await self.session.scalar(
            select(DailyReport)
            .where(
                DailyReport.user_id == user_id,
                DailyReport.work_item_id == work_item_id,
                DailyReport.report_date == report_date,
                DailyReport.team_id == team_id,
            )
        )

    async def get_by_id(
        self, report_id: str, user_id: str, team_id: str
    ) -> DailyReport | None:
        return await self.session.scalar(
            select(DailyReport)
            .where(
                DailyReport.id == report_id,
                DailyReport.user_id == user_id,
                DailyReport.team_id == team_id,
            )
        )

    async def list_for_user(self, user_id: str, team_id: str) -> list[DailyReport]:
        result = await self.session.scalars(
            select(DailyReport)
            .where(DailyReport.user_id == user_id, DailyReport.team_id == team_id)
            .order_by(DailyReport.report_date.desc(), DailyReport.updated_at.desc())
        )
        return list(result)

    async def list_history(
        self,
        user_id: str,
        team_id: str,
        project_id: str | None,
        date_from: date,
        date_to: date,
        status: WorkStatus | None,
    ) -> list[DailyReport]:
        statement = select(DailyReport).where(
            DailyReport.user_id == user_id,
            DailyReport.team_id == team_id,
            DailyReport.report_date >= date_from,
            DailyReport.report_date <= date_to,
        )
        if project_id is not None:
            statement = statement.where(DailyReport.project_id == project_id)
        if status is not None:
            statement = statement.where(DailyReport.status == status)
        reports = await self.session.scalars(
            statement.order_by(
                DailyReport.report_date.desc(),
                DailyReport.project_id,
                DailyReport.work_item_id,
            )
        )
        return list(reports)

    async def get_latest_event(
        self, daily_report_id: str
    ) -> WorkItemStatusEvent | None:
        return await self.session.scalar(
            select(WorkItemStatusEvent)
            .where(WorkItemStatusEvent.daily_report_id == daily_report_id)
            .order_by(
                WorkItemStatusEvent.recorded_at.desc(),
                WorkItemStatusEvent.id.desc(),
            )
            .limit(1)
        )

    async def save_with_event_and_success(
        self,
        report: DailyReport,
        status_event: WorkItemStatusEvent,
        invocation_id: str,
    ) -> DailyReport:
        try:
            self.session.add(report)
            # The status event references the report, but the models intentionally do
            # not expose an ORM relationship. Flush the aggregate root explicitly so
            # SQLAlchemy cannot order the event insert ahead of its parent row.
            await self.session.flush()
            self.session.add(status_event)
            invocation = await self.session.get(ActionInvocation, invocation_id)
            if invocation is None:
                await self.session.rollback()
                raise AppError(
                    404, "INVOCATION_NOT_FOUND", "Action invocation was not found"
                )
            invocation.status = InvocationStatus.SUCCEEDED
            invocation.result_ref = report.id
            invocation.error_code = None
            invocation.completed_at = status_event.recorded_at
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise AppError(
                409,
                "DAILY_REPORT_EXISTS",
                "A daily report or status event already exists for this request",
            ) from error
        await self.session.refresh(report)
        return report
