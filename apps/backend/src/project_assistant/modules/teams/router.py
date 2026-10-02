from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.core.auth import require_roles
from project_assistant.core.database import get_session
from project_assistant.core.errors import AppError
from project_assistant.modules.teams.overview import TeamOverview, TeamOverviewService
from project_assistant.modules.teams.repository import SqlAlchemyOverviewRepository
from project_assistant.modules.users.models import User, UserRole

router = APIRouter(prefix="/teams", tags=["monitoring"])
lead_or_pm = require_roles(UserRole.LEAD, UserRole.PM)


async def get_overview_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TeamOverviewService:
    return TeamOverviewService(SqlAlchemyOverviewRepository(session))


@router.get("/{team_id}/overview", response_model=TeamOverview)
async def get_team_overview(
    team_id: str,
    actor: Annotated[User, Depends(lead_or_pm)],
    service: Annotated[TeamOverviewService, Depends(get_overview_service)],
    reporting_date: Annotated[date | None, Query(alias="reportingDate")] = None,
) -> TeamOverview:
    if actor.team_id != team_id:
        raise AppError(404, "TEAM_NOT_FOUND", "Team was not found")
    return await service.get_overview(team_id, reporting_date or date.today())
