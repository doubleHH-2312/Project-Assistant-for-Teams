from collections.abc import Collection
from importlib import import_module

import pytest

from project_assistant.core.errors import AppError
from project_assistant.modules.memberships.models import TeamMembership, TeamRole


class FakeMembershipRepository:
    def __init__(self, memberships: Collection[TeamMembership]) -> None:
        self.memberships = {
            (membership.user_id, membership.team_id): membership for membership in memberships
        }

    async def get_active(self, user_id: str, team_id: str) -> TeamMembership | None:
        membership = self.memberships.get((user_id, team_id))
        return membership if membership is not None and membership.active else None


def _authorization_types():  # type: ignore[no-untyped-def]
    try:
        module = import_module("project_assistant.modules.memberships.service")
    except ModuleNotFoundError:
        pytest.fail("Membership authorization service is not implemented")
    return module.AuthorizationService, module.Permission


def membership(team_id: str, role: TeamRole, *, active: bool = True) -> TeamMembership:
    return TeamMembership(
        id=f"membership-{team_id}-{role.value}",
        user_id="user-1",
        team_id=team_id,
        role=role,
        active=active,
    )


@pytest.mark.asyncio
async def test_roles_inherit_only_their_team_permissions() -> None:
    authorization_service, permission = _authorization_types()
    member_service = authorization_service(
        FakeMembershipRepository([membership("team-a", TeamRole.MEMBER)])
    )
    lead_service = authorization_service(
        FakeMembershipRepository([membership("team-a", TeamRole.TECH_LEAD)])
    )
    pm_service = authorization_service(
        FakeMembershipRepository([membership("team-a", TeamRole.PM)])
    )

    assert (await member_service.require("user-1", ["team-a"], permission.SUBMIT_OWN_DAILY))[
        "team-a"
    ].role == TeamRole.MEMBER
    with pytest.raises(AppError) as member_denied:
        await member_service.require("user-1", ["team-a"], permission.VIEW_TEAM_DAILY_SUMMARY)
    await lead_service.require("user-1", ["team-a"], permission.SUBMIT_OWN_DAILY)
    await lead_service.require("user-1", ["team-a"], permission.GENERATE_TEAM_WEEKLY)
    await pm_service.require("user-1", ["team-a"], permission.GENERATE_TEAM_WEEKLY)
    await pm_service.require("user-1", ["team-a"], permission.MANAGE_TEAMS_BINDING)
    with pytest.raises(AppError):
        await lead_service.require("user-1", ["team-a"], permission.MANAGE_TEAMS_BINDING)

    assert member_denied.value.status_code == 403
    assert member_denied.value.code == "FORBIDDEN"


@pytest.mark.asyncio
async def test_inactive_or_missing_membership_hides_team() -> None:
    authorization_service, permission = _authorization_types()
    service = authorization_service(
        FakeMembershipRepository([membership("team-a", TeamRole.TECH_LEAD, active=False)])
    )

    with pytest.raises(AppError) as hidden:
        await service.require("user-1", ["team-a"], permission.VIEW_TEAM_DAILY_SUMMARY)

    assert hidden.value.status_code == 404
    assert hidden.value.code == "TEAM_NOT_FOUND"


@pytest.mark.asyncio
async def test_multi_team_requires_same_eligible_role_in_every_team() -> None:
    authorization_service, permission = _authorization_types()
    lead_service = authorization_service(
        FakeMembershipRepository(
            [
                membership("team-a", TeamRole.TECH_LEAD),
                membership("team-b", TeamRole.TECH_LEAD),
            ]
        )
    )
    mixed_service = authorization_service(
        FakeMembershipRepository(
            [
                membership("team-a", TeamRole.TECH_LEAD),
                membership("team-b", TeamRole.PM),
            ]
        )
    )
    pm_service = authorization_service(
        FakeMembershipRepository(
            [membership("team-a", TeamRole.PM), membership("team-b", TeamRole.PM)]
        )
    )

    assert set(
        await lead_service.require(
            "user-1", ["team-a", "team-b"], permission.GENERATE_MULTI_TEAM_WEEKLY
        )
    ) == {"team-a", "team-b"}
    with pytest.raises(AppError) as mixed_denied:
        await mixed_service.require(
            "user-1", ["team-a", "team-b"], permission.GENERATE_MULTI_TEAM_WEEKLY
        )
    assert set(
        await pm_service.require(
            "user-1", ["team-a", "team-b"], permission.GENERATE_MULTI_TEAM_WEEKLY
        )
    ) == {"team-a", "team-b"}

    assert mixed_denied.value.status_code == 403
    assert mixed_denied.value.code == "FORBIDDEN"
