from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.core.auth import get_authorization_service, get_current_user
from project_assistant.core.database import get_session
from project_assistant.modules.memberships.service import AuthorizationService, Permission
from project_assistant.modules.teams.overview import TeamOverview, TeamOverviewService
from project_assistant.modules.teams.repository import SqlAlchemyOverviewRepository
from project_assistant.modules.users.models import User

router = APIRouter(prefix="/teams", tags=["monitoring"])


async def get_overview_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TeamOverviewService:
    return TeamOverviewService(SqlAlchemyOverviewRepository(session))


@router.get("/{team_id}/overview", response_model=TeamOverview)
async def get_team_overview(
    team_id: str,
    actor: Annotated[User, Depends(get_current_user)],
    authorization: Annotated[AuthorizationService, Depends(get_authorization_service)],
    service: Annotated[TeamOverviewService, Depends(get_overview_service)],
    reporting_date: Annotated[date | None, Query(alias="reportingDate")] = None,
) -> TeamOverview:
    await authorization.require(actor.id, [team_id], Permission.VIEW_TEAM_DAILY_SUMMARY)
    return await service.get_overview(team_id, reporting_date or date.today())
