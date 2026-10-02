from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.core.auth import get_current_user
from project_assistant.core.database import get_session
from project_assistant.modules.daily_reports.repository import SqlAlchemyDailyReportRepository
from project_assistant.modules.daily_reports.schemas import (
    DailyReportCreate,
    DailyReportRead,
    DailyReportUpdate,
)
from project_assistant.modules.daily_reports.service import DailyReportService
from project_assistant.modules.users.models import User

router = APIRouter(prefix="/daily-reports", tags=["daily-reports"])


async def get_daily_report_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DailyReportService:
    return DailyReportService(SqlAlchemyDailyReportRepository(session))


@router.post("", response_model=DailyReportRead, status_code=status.HTTP_201_CREATED)
async def create_daily_report(
    request: DailyReportCreate,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[DailyReportService, Depends(get_daily_report_service)],
) -> DailyReportRead:
    report = await service.create(actor, request)
    return DailyReportRead.model_validate(report)


@router.put("/{report_id}", response_model=DailyReportRead)
async def update_daily_report(
    report_id: str,
    request: DailyReportUpdate,
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[DailyReportService, Depends(get_daily_report_service)],
) -> DailyReportRead:
    report = await service.update(actor, report_id, request)
    return DailyReportRead.model_validate(report)


@router.get("/me", response_model=list[DailyReportRead])
async def list_my_daily_reports(
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[DailyReportService, Depends(get_daily_report_service)],
) -> list[DailyReportRead]:
    reports = await service.list_for_user(actor)
    return [DailyReportRead.model_validate(report) for report in reports]

