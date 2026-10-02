from collections.abc import Collection
from enum import StrEnum
from typing import Protocol

from project_assistant.core.errors import AppError
from project_assistant.modules.memberships.models import TeamMembership, TeamRole


class Permission(StrEnum):
    SUBMIT_OWN_DAILY = "SUBMIT_OWN_DAILY"
    VIEW_OWN_HISTORY = "VIEW_OWN_HISTORY"
    GENERATE_OWN_WEEKLY = "GENERATE_OWN_WEEKLY"
    VIEW_TEAM_DAILY_SUMMARY = "VIEW_TEAM_DAILY_SUMMARY"
    GENERATE_TEAM_WEEKLY = "GENERATE_TEAM_WEEKLY"
    GENERATE_MULTI_TEAM_WEEKLY = "GENERATE_MULTI_TEAM_WEEKLY"


MEMBER_PERMISSIONS = frozenset(
    {
        Permission.SUBMIT_OWN_DAILY,
        Permission.VIEW_OWN_HISTORY,
        Permission.GENERATE_OWN_WEEKLY,
    }
)
TECH_LEAD_PERMISSIONS = MEMBER_PERMISSIONS | {
    Permission.VIEW_TEAM_DAILY_SUMMARY,
    Permission.GENERATE_TEAM_WEEKLY,
    Permission.GENERATE_MULTI_TEAM_WEEKLY,
}
ROLE_PERMISSIONS: dict[TeamRole, frozenset[Permission]] = {
    TeamRole.MEMBER: MEMBER_PERMISSIONS,
    TeamRole.TECH_LEAD: TECH_LEAD_PERMISSIONS,
    TeamRole.PM: frozenset(Permission),
}


class MembershipRepository(Protocol):
    async def get_active(self, user_id: str, team_id: str) -> TeamMembership | None: ...


class AuthorizationService:
    def __init__(self, repository: MembershipRepository) -> None:
        self.repository = repository

    async def require(
        self,
        actor_id: str,
        team_ids: Collection[str],
        permission: Permission,
    ) -> dict[str, TeamMembership]:
        selected_team_ids = sorted(set(team_ids))
        if not selected_team_ids:
            raise AppError(422, "TEAM_SCOPE_REQUIRED", "At least one Team is required")

        memberships: dict[str, TeamMembership] = {}
        for team_id in selected_team_ids:
            membership = await self.repository.get_active(actor_id, team_id)
            if membership is None:
                raise AppError(404, "TEAM_NOT_FOUND", "Team was not found")
            if permission not in ROLE_PERMISSIONS[membership.role]:
                raise AppError(403, "FORBIDDEN", "This action is not permitted for the Team")
            memberships[team_id] = membership

        if permission == Permission.GENERATE_MULTI_TEAM_WEEKLY:
            roles = {membership.role for membership in memberships.values()}
            if roles not in ({TeamRole.TECH_LEAD}, {TeamRole.PM}):
                raise AppError(
                    403,
                    "FORBIDDEN",
                    "The same eligible role is required for every selected Team",
                )
        return memberships
