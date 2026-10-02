from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.core.auth import get_current_user
from project_assistant.core.config import get_settings
from project_assistant.core.database import get_session
from project_assistant.integrations.llm.provider import (
    InternalLLMProvider,
    LLMProvider,
    MockLLMProvider,
)
from project_assistant.modules.templates.models import ReportTemplate
from project_assistant.modules.users.models import User
from project_assistant.modules.weekly_reports.models import ReportScope
from project_assistant.modules.weekly_reports.repository import SqlAlchemyWeeklyReportRepository
from project_assistant.modules.weekly_reports.schemas import (
    WeeklyGenerateRequest,
    WeeklyReportRead,
    WeeklyUpdateRequest,
)
from project_assistant.modules.weekly_reports.service import WeeklyReportService

router = APIRouter(tags=["weekly-reports"])


async def get_weekly_report_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WeeklyReportService:
    settings = get_settings()
    repository = SqlAlchemyWeeklyReportRepository(session)
    provider: LLMProvider
    if settings.llm_provider == "internal":
        assert settings.internal_llm_base_url
        assert settings.internal_llm_api_key
        assert settings.internal_llm_model
        provider = InternalLLMProvider(
            settings.internal_llm_base_url,
            settings.internal_llm_api_key,
            settings.internal_llm_model,
        )
    else:
        provider = MockLLMProvider()
    return WeeklyReportService(repository, provider)


@router.post(
    "/weekly-reports/generate",
    response_model=WeeklyReportRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_weekly_report(
    request: WeeklyGenerateRequest,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[WeeklyReportService, Depends(get_weekly_report_service)],
) -> WeeklyReportRead:
    return WeeklyReportRead.model_validate(await service.generate(actor, request))


@router.get("/weekly-reports/{report_id}", response_model=WeeklyReportRead)
async def get_weekly_report(
    report_id: str,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[WeeklyReportService, Depends(get_weekly_report_service)],
) -> WeeklyReportRead:
    return WeeklyReportRead.model_validate(await service.get(actor, report_id))


@router.put("/weekly-reports/{report_id}", response_model=WeeklyReportRead)
async def update_weekly_report(
    report_id: str,
    request: WeeklyUpdateRequest,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[WeeklyReportService, Depends(get_weekly_report_service)],
) -> WeeklyReportRead:
    return WeeklyReportRead.model_validate(await service.update(actor, report_id, request))


@router.post("/weekly-reports/{report_id}/confirm", response_model=WeeklyReportRead)
async def confirm_weekly_report(
    report_id: str,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[WeeklyReportService, Depends(get_weekly_report_service)],
) -> WeeklyReportRead:
    return WeeklyReportRead.model_validate(await service.confirm_by_id(actor, report_id))


@router.post(
    "/weekly-reports/{report_id}/revisions",
    response_model=WeeklyReportRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_weekly_revision(
    report_id: str,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[WeeklyReportService, Depends(get_weekly_report_service)],
) -> WeeklyReportRead:
    return WeeklyReportRead.model_validate(await service.create_revision(actor, report_id))


@router.get("/teams/{team_id}/templates/active")
async def get_active_template(
    team_id: str,
    scope: Annotated[ReportScope, Query()],
    actor: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    if actor.team_id != team_id:
        from project_assistant.core.errors import AppError

        raise AppError(404, "TEAM_NOT_FOUND", "Team was not found")
    template: ReportTemplate | None = await SqlAlchemyWeeklyReportRepository(
        session
    ).get_active_template(team_id, scope)
    if template is None:
        from project_assistant.core.errors import AppError

        raise AppError(404, "TEMPLATE_NOT_FOUND", "Active template was not found")
    return {
        "id": template.id,
        "name": template.name,
        "scope": template.scope,
        "version": template.version,
        "schema": template.schema_json,
    }
