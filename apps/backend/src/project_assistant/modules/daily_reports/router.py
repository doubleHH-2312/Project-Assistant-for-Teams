from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.core.auth import get_authorization_service, get_current_user
from project_assistant.core.database import get_session
from project_assistant.modules.audit.models import RequestAuditContext
from project_assistant.modules.audit.repository import SqlAlchemyAuditRepository
from project_assistant.modules.audit.service import AuditService
from project_assistant.modules.daily_reports.models import WorkStatus
from project_assistant.modules.daily_reports.repository import SqlAlchemyDailyReportRepository
from project_assistant.modules.daily_reports.schemas import (
    DailyHistoryFilters,
    DailyReportCreate,
    DailyReportRead,
    DailyReportUpdate,
)
from project_assistant.modules.daily_reports.service import DailyReportService
from project_assistant.modules.memberships.service import AuthorizationService
from project_assistant.modules.users.models import User

router = APIRouter(prefix="/daily-reports", tags=["daily-reports"])


async def get_daily_report_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[AuthorizationService, Depends(get_authorization_service)],
) -> DailyReportService:
    return DailyReportService(
        SqlAlchemyDailyReportRepository(session),
        authorization,
        AuditService(SqlAlchemyAuditRepository(session)),
    )


@router.post("", response_model=DailyReportRead, status_code=status.HTTP_201_CREATED)
async def create_daily_report(
    request: DailyReportCreate,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[DailyReportService, Depends(get_daily_report_service)],
    http_request: Request,
) -> DailyReportRead:
    report = await service.create(
        actor,
        request.team_id,
        request,
        _audit_context(
            http_request,
            actor,
            action="daily.create",
            team_id=request.team_id,
            project_id=request.project_id,
        ),
    )
    return DailyReportRead.model_validate(report)


@router.put("/{report_id}", response_model=DailyReportRead)
async def update_daily_report(
    report_id: str,
    request: DailyReportUpdate,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[DailyReportService, Depends(get_daily_report_service)],
    team_id: Annotated[str, Query(alias="teamId")],
    http_request: Request,
) -> DailyReportRead:
    report = await service.update(
        actor,
        team_id,
        report_id,
        request,
        _audit_context(
            http_request,
            actor,
            action="daily.update",
            team_id=team_id,
            project_id=None,
        ),
    )
    return DailyReportRead.model_validate(report)


@router.get("/me", response_model=list[DailyReportRead])
async def list_my_daily_reports(
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[DailyReportService, Depends(get_daily_report_service)],
    team_id: Annotated[str, Query(alias="teamId")],
) -> list[DailyReportRead]:
    reports = await service.list_for_user(actor, team_id)
    return [DailyReportRead.model_validate(report) for report in reports]


@router.get("/history", response_model=list[DailyReportRead])
async def list_daily_history(
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[DailyReportService, Depends(get_daily_report_service)],
    team_id: Annotated[str, Query(alias="teamId")],
    date_from: Annotated[date | None, Query(alias="dateFrom")] = None,
    date_to: Annotated[date | None, Query(alias="dateTo")] = None,
    project_id: Annotated[str | None, Query(alias="projectId")] = None,
    status_filter: Annotated[WorkStatus | None, Query(alias="status")] = None,
) -> list[DailyReportRead]:
    resolved_to = date_to or date.today()
    resolved_from = date_from or resolved_to - timedelta(days=30)
    reports = await service.list_history(
        actor,
        DailyHistoryFilters(
            team_id=team_id,
            project_id=project_id,
            date_from=resolved_from,
            date_to=resolved_to,
            status=status_filter,
        ),
    )
    return [DailyReportRead.model_validate(report) for report in reports]


@router.get("/options")
async def get_daily_options(
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[DailyReportService, Depends(get_daily_report_service)],
    team_id: Annotated[str, Query(alias="teamId")],
) -> dict[str, list[dict[str, str]]]:
    return await service.get_form_options(actor, team_id)


def _audit_context(
    request: Request,
    actor: User,
    *,
    action: str,
    team_id: str,
    project_id: str | None,
) -> RequestAuditContext:
    correlation_id = str(request.state.correlation_id)
    return RequestAuditContext(
        action=action,
        actor_id=actor.id,
        tenant_id=actor.tenant_id,
        team_id=team_id,
        project_id=project_id,
        conversation_id=f"web:{actor.id}",
        conversation_type="WEB",
        timezone="UTC",
        correlation_id=correlation_id,
        idempotency_key=request.headers.get(
            "Idempotency-Key", f"{correlation_id}:{action}"
        ),
        source="WEB",
        metadata={"method": request.method, "path": request.url.path},
    )
