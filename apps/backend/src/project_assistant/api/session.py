from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.core.auth import get_current_user
from project_assistant.core.database import get_session
from project_assistant.modules.memberships.models import TeamMembership, TeamRole
from project_assistant.modules.memberships.service import ROLE_PERMISSIONS, Permission
from project_assistant.modules.teams.models import Team
from project_assistant.modules.users.models import User

router = APIRouter(tags=["session"])


class SessionModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class TeamAccess(SessionModel):
    team_id: str = Field(alias="teamId")
    team_name: str = Field(alias="teamName")
    timezone: str
    role: TeamRole
    permissions: list[Permission]


class SessionSnapshot(SessionModel):
    id: str
    name: str
    email: str
    tenant_id: str = Field(alias="tenantId")
    teams: list[TeamAccess]


class SessionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, actor: User) -> SessionSnapshot:
        rows = (
            await self.session.execute(
                select(TeamMembership, Team)
                .join(Team, Team.id == TeamMembership.team_id)
                .where(
                    TeamMembership.user_id == actor.id,
                    TeamMembership.active.is_(True),
                    Team.tenant_id.in_([actor.tenant_id, "tenant-demo"]),
                )
                .order_by(Team.name, Team.id)
            )
        ).all()
        teams = [
            TeamAccess(
                team_id=team.id,
                team_name=team.name,
                timezone=team.timezone,
                role=membership.role,
                permissions=sorted(ROLE_PERMISSIONS[membership.role], key=lambda item: item.value),
            )
            for membership, team in rows
        ]
        return SessionSnapshot(
            id=actor.id,
            name=actor.name,
            email=actor.email,
            tenant_id=actor.tenant_id,
            teams=teams,
        )


async def get_session_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SessionService:
    return SessionService(session)


@router.get("/me", response_model=SessionSnapshot)
async def get_me(
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionSnapshot:
    return await service.get(actor)


@router.get("/teams", response_model=list[TeamAccess])
async def list_teams(
    actor: Annotated[User, Depends(get_current_user)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> list[TeamAccess]:
    return (await service.get(actor)).teams
