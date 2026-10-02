from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.modules.memberships.models import TeamMembership, TeamRole


class SqlAlchemyMembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active(self, user_id: str, team_id: str) -> TeamMembership | None:
        return await self.session.scalar(
            select(TeamMembership).where(
                TeamMembership.user_id == user_id,
                TeamMembership.team_id == team_id,
                TeamMembership.active.is_(True),
            )
        )

    async def list_active_for_user(self, user_id: str) -> list[TeamMembership]:
        memberships = await self.session.scalars(
            select(TeamMembership)
            .where(
                TeamMembership.user_id == user_id,
                TeamMembership.active.is_(True),
            )
            .order_by(TeamMembership.team_id)
        )
        return list(memberships)

    async def list_expected_members(self, team_id: str) -> list[TeamMembership]:
        memberships = await self.session.scalars(
            select(TeamMembership)
            .where(
                TeamMembership.team_id == team_id,
                TeamMembership.role == TeamRole.MEMBER,
                TeamMembership.active.is_(True),
            )
            .order_by(TeamMembership.user_id)
        )
        return list(memberships)
