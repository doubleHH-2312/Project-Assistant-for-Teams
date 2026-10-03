from importlib import import_module

import pytest
from microsoft_teams.api import Account, ConversationAccount, MessageActivity

from project_assistant.modules.actions.contracts import ConversationType
from project_assistant.modules.users.models import User


def _context_module():  # type: ignore[no-untyped-def]
    try:
        return import_module("project_assistant.integrations.teams.context")
    except ModuleNotFoundError:
        pytest.fail("Teams context resolver is not implemented")


def _activity(conversation_type: str, conversation_id: str) -> MessageActivity:
    return MessageActivity(
        id="activity-1",
        channelId="msteams",
        serviceUrl="https://smba.trafficmanager.net/teams",
        from_=Account(id="teams-user-1", aadObjectId="entra-user-1"),
        recipient=Account(id="bot-1", name="Project Assistant"),
        conversation=ConversationAccount(
            id=conversation_id,
            tenantId="tenant-1",
            conversationType=conversation_type,
            isGroup=conversation_type != "personal",
        ),
        text="/daily",
    )


class ContextRepository:
    def __init__(self, binding):  # type: ignore[no-untyped-def]
        self.binding = binding
        self.calls: list[tuple[str, ...]] = []

    async def get_user(self, tenant_id: str, external_user_id: str):
        self.calls.append(("user", tenant_id, external_user_id))
        return User(
            id="user-1",
            tenant_id=tenant_id,
            external_user_id=external_user_id,
            name="Member",
            email="member@example.test",
        )

    async def get_binding(self, tenant_id: str, conversation_id: str):
        self.calls.append(("binding", tenant_id, conversation_id))
        return self.binding


@pytest.mark.asyncio
async def test_personal_activity_maps_identity_without_fixed_team() -> None:
    module = _context_module()
    repository = ContextRepository(None)

    context = await module.TeamsContextResolver(repository).resolve(
        _activity("personal", "conversation-personal"), "daily"
    )

    assert context.actor_id == "user-1"
    assert context.tenant_id == "tenant-1"
    assert context.conversation_type == ConversationType.PERSONAL
    assert context.current_team_id is None
    assert context.idempotency_key == "teams:activity-1:daily"
    assert context.source == "TEAMS"


@pytest.mark.asyncio
async def test_channel_activity_uses_bound_team_and_team_timezone() -> None:
    module = _context_module()
    binding = module.ResolvedConversationBinding(
        id="binding-1",
        team_id="team-1",
        timezone="Asia/Ho_Chi_Minh",
    )
    repository = ContextRepository(binding)

    context = await module.TeamsContextResolver(repository).resolve(
        _activity("channel", "conversation-channel"), "daily-summary"
    )

    assert context.conversation_type == ConversationType.TEAM_CHANNEL
    assert context.current_team_id == "team-1"
    assert context.timezone == "Asia/Ho_Chi_Minh"
