from datetime import date
from typing import Protocol

from project_assistant.core.errors import AppError
from project_assistant.modules.daily_reports.models import DailyReport
from project_assistant.modules.daily_reports.schemas import DailyReportCreate, DailyReportUpdate
from project_assistant.modules.memberships.service import AuthorizationService, Permission
from project_assistant.modules.projects.models import Project
from project_assistant.modules.users.models import User
from project_assistant.modules.work_items.models import WorkItem


class DailyReportRepository(Protocol):
    async def get_project(self, project_id: str, team_id: str) -> Project | None: ...

    async def get_work_item(self, work_item_id: str, team_id: str) -> WorkItem | None: ...

    async def get_by_key(
        self, user_id: str, work_item_id: str, report_date: date, team_id: str
    ) -> DailyReport | None: ...

    async def get_by_id(
        self, report_id: str, user_id: str, team_id: str
    ) -> DailyReport | None: ...

    async def list_for_user(self, user_id: str, team_id: str) -> list[DailyReport]: ...

    async def save(self, report: DailyReport) -> DailyReport: ...


class DailyReportService:
    def __init__(
        self,
        repository: DailyReportRepository,
        authorization: AuthorizationService,
    ) -> None:
        self.repository = repository
        self.authorization = authorization

    async def create(self, actor: User, request: DailyReportCreate) -> DailyReport:
        await self.authorization.require(
            actor.id, [request.team_id], Permission.SUBMIT_OWN_DAILY
        )
        project = await self.repository.get_project(request.project_id, request.team_id)
        work_item = await self.repository.get_work_item(
            request.work_item_id, request.team_id
        )
        if (
            project is None
            or work_item is None
            or work_item.project_id != project.id
        ):
            raise AppError(404, "WORK_ITEM_NOT_FOUND", "Project or work item was not found")
        existing = await self.repository.get_by_key(
            actor.id, request.work_item_id, request.report_date, request.team_id
        )
        if existing is not None:
            raise AppError(
                409,
                "DAILY_REPORT_EXISTS",
                "A daily report already exists for this work item and date",
                {"reportId": existing.id},
            )
        report = DailyReport(
            user_id=actor.id,
            project_id=request.project_id,
            work_item_id=request.work_item_id,
            report_date=request.report_date,
            status=request.status,
            work_summary=request.work_summary,
            blocker=request.blocker,
            next_action=request.next_action,
        )
        return await self.repository.save(report)

    async def update(
        self, actor: User, team_id: str, report_id: str, request: DailyReportUpdate
    ) -> DailyReport:
        await self.authorization.require(actor.id, [team_id], Permission.SUBMIT_OWN_DAILY)
        report = await self.repository.get_by_id(report_id, actor.id, team_id)
        if report is None:
            raise AppError(404, "DAILY_REPORT_NOT_FOUND", "Daily report was not found")
        changes = request.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(report, field, value)
        return await self.repository.save(report)

    async def list_for_user(self, actor: User, team_id: str) -> list[DailyReport]:
        await self.authorization.require(actor.id, [team_id], Permission.VIEW_OWN_HISTORY)
        return await self.repository.list_for_user(actor.id, team_id)
