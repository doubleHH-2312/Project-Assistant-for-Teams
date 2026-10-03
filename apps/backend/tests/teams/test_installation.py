from importlib import import_module

import pytest

from project_assistant.modules.memberships.service import Permission
from project_assistant.modules.notifications.models import TeamsConversation
from project_assistant.modules.users.models import User


def _context_module():  # type: ignore[no-untyped-def]
    try:
        return import_module("project_assistant.integrations.teams.context")
    except ModuleNotFoundError:
        pytest.fail("Teams installation service is not implemented")


class BindingRepository:
    def __init__(self) -> None:
        self.saved = []

    async def save_binding(self, binding):  # type: ignore[no-untyped-def]
        self.saved.append(binding)
        return binding

    async def bind_team(self, binding_id: str, team_id: str):
        binding = next(item for item in self.saved if item.id == binding_id)
        binding.team_id = team_id
        return binding


class Authorization:
    def __init__(self) -> None:
        self.calls = []

    async def require(self, actor_id, team_ids, permission):  # type: ignore[no-untyped-def]
        self.calls.append((actor_id, list(team_ids), permission))
        return {}


def _actor() -> User:
    return User(
        id="pm-1",
        tenant_id="tenant-1",
        external_user_id="entra-pm-1",
        name="PM",
        email="pm@example.test",
    )


@pytest.mark.asyncio
async def test_personal_install_has_no_fixed_team_and_group_binding_is_pm_only() -> None:
    module = _context_module()
    repository = BindingRepository()
    authorization = Authorization()
    service = module.TeamsInstallationService(repository, authorization)

    personal = await service.record_installation(
        actor=_actor(),
        tenant_id="tenant-1",
        conversation_id="personal-1",
        conversation_type="PERSONAL",
        service_url="https://smba.trafficmanager.net/teams",
    )
    group = await service.record_installation(
        actor=_actor(),
        tenant_id="tenant-1",
        conversation_id="group-1",
        conversation_type="GROUP_CHAT",
        service_url="https://smba.trafficmanager.net/teams",
    )
    bound = await service.bind_group(_actor(), group.id, "team-1")

    assert personal.user_id == "pm-1"
    assert personal.team_id is None
    assert group.user_id is None
    assert bound.team_id == "team-1"
    assert authorization.calls == [
        ("pm-1", ["team-1"], Permission.MANAGE_TEAMS_BINDING)
    ]


@pytest.mark.asyncio
async def test_missing_personal_conversation_is_delivery_failure() -> None:
    from project_assistant.integrations.teams.transport import MockTeamsTransport

    conversation = TeamsConversation(
        user_id="user-1",
        conversation_id="",
        tenant_id="tenant-1",
        service_url="",
    )

    result = await MockTeamsTransport().send_proactive(conversation, {"type": "reminder"})

    assert result.success is False
    assert result.error_code == "MISSING_CONVERSATION_ID"
