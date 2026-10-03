import uuid
from dataclasses import replace
from datetime import date
from typing import Protocol

from project_assistant.core.errors import AppError
from project_assistant.modules.audit.models import (
    ActionInvocation,
    RequestAuditContext,
    WorkItemStatusEvent,
)
from project_assistant.modules.audit.service import AuditService
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.daily_reports.schemas import (
    DailyHistoryFilters,
    DailyReportCreate,
    DailyReportUpdate,
)
from project_assistant.modules.memberships.service import AuthorizationService, Permission
from project_assistant.modules.projects.models import Project
from project_assistant.modules.teams.models import Team
from project_assistant.modules.work_items.models import WorkItem


class ActorIdentity(Protocol):
    @property
    def id(self) -> str: ...


class DailyReportRepository(Protocol):
    async def get_team(self, team_id: str) -> Team | None: ...

    async def get_project(self, project_id: str, team_id: str) -> Project | None: ...

    async def get_work_item(self, work_item_id: str, team_id: str) -> WorkItem | None: ...

    async def list_active_projects(self, team_id: str) -> list[Project]: ...

    async def list_work_items(self, team_id: str) -> list[WorkItem]: ...

    async def get_by_key(
        self, user_id: str, work_item_id: str, report_date: date, team_id: str
    ) -> DailyReport | None: ...

    async def get_by_id(
        self, report_id: str, user_id: str, team_id: str
    ) -> DailyReport | None: ...

    async def list_for_user(self, user_id: str, team_id: str) -> list[DailyReport]: ...

    async def list_history(
        self,
        user_id: str,
        team_id: str,
        project_id: str | None,
        date_from: date,
        date_to: date,
        status: WorkStatus | None,
    ) -> list[DailyReport]: ...

    async def get_latest_event(
        self, daily_report_id: str
    ) -> WorkItemStatusEvent | None: ...

    async def save_with_event_and_success(
        self,
        report: DailyReport,
        status_event: WorkItemStatusEvent,
        invocation_id: str,
    ) -> DailyReport: ...


class DailyReportService:
    def __init__(
        self,
        repository: DailyReportRepository,
        authorization: AuthorizationService,
        audit_service: AuditService,
    ) -> None:
        self.repository = repository
        self.authorization = authorization
        self.audit_service = audit_service

    async def create(
        self,
        actor: ActorIdentity,
        team_id: str,
        request: DailyReportCreate,
        audit: RequestAuditContext,
    ) -> DailyReport:
        invocation = await self._start_invocation(team_id, audit)
        try:
            if request.team_id != team_id:
                raise AppError(422, "TEAM_SCOPE_MISMATCH", "Payload Team does not match scope")
            await self.authorization.require(
                actor.id, [team_id], Permission.SUBMIT_OWN_DAILY
            )
            team = await self.repository.get_team(team_id)
            if team is None:
                raise AppError(404, "TEAM_NOT_FOUND", "Team was not found")
            report_date = resolve_report_date(
                request.report_date,
                invocation.local_date,
                team.backfill_window_days,
            )
            project = await self.repository.get_project(request.project_id, team_id)
            work_item = await self.repository.get_work_item(request.work_item_id, team_id)
            if (
                project is None
                or work_item is None
                or work_item.project_id != project.id
            ):
                raise AppError(
                    404, "WORK_ITEM_NOT_FOUND", "Project or work item was not found"
                )
            existing = await self.repository.get_by_key(
                actor.id, request.work_item_id, report_date, team_id
            )
            if existing is not None:
                raise AppError(
                    409,
                    "DAILY_REPORT_EXISTS",
                    "A daily report already exists for this work item and date",
                    {"reportId": existing.id},
                )
            report = DailyReport(
                id=str(uuid.uuid4()),
                team_id=team_id,
                user_id=actor.id,
                project_id=request.project_id,
                work_item_id=request.work_item_id,
                report_date=report_date,
                status=request.status,
                work_summary=request.work_summary,
                blocker=request.blocker,
                next_action=request.next_action,
                source=audit.source,
                submitted_at=invocation.triggered_at,
            )
            status_event = self._status_event(report, invocation, audit.source)
            return await self.repository.save_with_event_and_success(
                report, status_event, invocation.id
            )
        except AppError as error:
            await self._record_failure(invocation, error)
            raise
        except Exception:
            await self.audit_service.fail(invocation.id, "INTERNAL_ERROR")
            raise

    async def update(
        self,
        actor: ActorIdentity,
        team_id: str,
        report_id: str,
        request: DailyReportUpdate,
        audit: RequestAuditContext,
    ) -> DailyReport:
        invocation = await self._start_invocation(team_id, audit)
        try:
            await self.authorization.require(
                actor.id, [team_id], Permission.SUBMIT_OWN_DAILY
            )
            report = await self.repository.get_by_id(report_id, actor.id, team_id)
            if report is None:
                raise AppError(404, "DAILY_REPORT_NOT_FOUND", "Daily report was not found")
            previous_event = await self.repository.get_latest_event(report.id)
            changes = request.model_dump(exclude_unset=True)
            for field, value in changes.items():
                setattr(report, field, value)
            report.last_edited_at = invocation.triggered_at
            status_event = self._status_event(
                report,
                invocation,
                audit.source,
                supersedes_event_id=previous_event.id if previous_event else None,
            )
            return await self.repository.save_with_event_and_success(
                report, status_event, invocation.id
            )
        except AppError as error:
            await self._record_failure(invocation, error)
            raise
        except Exception:
            await self.audit_service.fail(invocation.id, "INTERNAL_ERROR")
            raise

    async def list_for_user(
        self, actor: ActorIdentity, team_id: str
    ) -> list[DailyReport]:
        await self.authorization.require(actor.id, [team_id], Permission.VIEW_OWN_HISTORY)
        return await self.repository.list_for_user(actor.id, team_id)

    async def get_form_options(
        self, actor: ActorIdentity, team_id: str
    ) -> dict[str, list[dict[str, str]]]:
        await self.authorization.require(
            actor.id, [team_id], Permission.SUBMIT_OWN_DAILY
        )
        projects = await self.repository.list_active_projects(team_id)
        work_items = await self.repository.list_work_items(team_id)
        return {
            "projects": [
                {"id": project.id, "name": project.name} for project in projects
            ],
            "workItems": [
                {
                    "id": item.id,
                    "projectId": item.project_id,
                    "code": item.code,
                    "title": item.title,
                }
                for item in work_items
            ],
        }

    async def list_history(
        self, actor: ActorIdentity, filters: DailyHistoryFilters
    ) -> list[DailyReport]:
        await self.authorization.require(
            actor.id, [filters.team_id], Permission.VIEW_OWN_HISTORY
        )
        if filters.date_from > filters.date_to:
            raise AppError(422, "HISTORY_DATE_RANGE_INVALID", "Date range is invalid")
        return await self.repository.list_history(
            actor.id,
            filters.team_id,
            filters.project_id,
            filters.date_from,
            filters.date_to,
            filters.status,
        )

    async def _start_invocation(
        self, team_id: str, context: RequestAuditContext
    ) -> ActionInvocation:
        team = await self.repository.get_team(team_id)
        timezone = team.timezone if team is not None else context.timezone
        invocation = await self.audit_service.start(
            replace(context, team_id=team_id, timezone=timezone)
        )
        return await self.audit_service.enrich_scope(
            invocation.id,
            team_id=team_id,
            project_id=context.project_id,
            timezone=timezone,
        )

    async def _record_failure(
        self, invocation: ActionInvocation, error: AppError
    ) -> None:
        if error.status_code == 403:
            await self.audit_service.deny(invocation.id, error.code)
        else:
            await self.audit_service.fail(invocation.id, error.code)

    @staticmethod
    def _status_event(
        report: DailyReport,
        invocation: ActionInvocation,
        source: str,
        *,
        supersedes_event_id: str | None = None,
    ) -> WorkItemStatusEvent:
        return WorkItemStatusEvent(
            id=str(uuid.uuid4()),
            daily_report_id=report.id,
            action_invocation_id=invocation.id,
            team_id=report.team_id,
            project_id=report.project_id,
            work_item_id=report.work_item_id,
            user_id=report.user_id,
            status=report.status,
            effective_blocker=report.effective_blocker,
            business_date=report.report_date,
            recorded_at=invocation.triggered_at,
            local_datetime=invocation.local_datetime,
            local_date=invocation.local_date,
            timezone=invocation.timezone,
            source=source,
            supersedes_event_id=supersedes_event_id,
        )


def resolve_report_date(
    requested_date: date | None,
    local_today: date,
    backfill_window_days: int,
) -> date:
    report_date = requested_date or local_today
    if report_date > local_today:
        raise AppError(422, "REPORT_DATE_IN_FUTURE", "Report date cannot be in the future")
    if (local_today - report_date).days > backfill_window_days:
        raise AppError(
            422,
            "REPORT_DATE_OUTSIDE_BACKFILL_WINDOW",
            "Report date is outside the Team backfill window",
            {"backfillWindowDays": backfill_window_days},
        )
    return report_date
