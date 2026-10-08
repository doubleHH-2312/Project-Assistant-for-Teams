from importlib import import_module

import pytest
from fastapi import FastAPI
from microsoft_teams.api import Account, ConversationAccount, MessageActivity
from microsoft_teams.apps import App
from pydantic import ValidationError

from project_assistant.core.config import Settings
from project_assistant.integrations.llm.provider import MockLLMProvider
from project_assistant.modules.actions.contracts import (
    ActionContext,
    ActionResult,
    ConversationType,
)


def _teams_app_module():  # type: ignore[no-untyped-def]
    try:
        return import_module("project_assistant.integrations.teams.app")
    except ModuleNotFoundError:
        pytest.fail("Teams SDK adapter is not implemented")


def _activity(text: str) -> MessageActivity:
    return MessageActivity(
        id="activity-1",
        channelId="msteams",
        serviceUrl="https://smba.trafficmanager.net/teams",
        from_=Account(id="teams-user-1", aadObjectId="entra-user-1"),
        recipient=Account(id="bot-1", name="Project Assistant"),
        conversation=ConversationAccount(
            id="conversation-1",
            tenantId="tenant-1",
            conversationType="personal",
            isGroup=False,
        ),
        text=text,
    )


class Resolver:
    def __init__(self) -> None:
        self.calls = 0

    async def resolve(self, activity, action):  # type: ignore[no-untyped-def]
        self.calls += 1
        return ActionContext(
            actor_id="user-1",
            tenant_id="tenant-1",
            conversation_id=activity.conversation.id,
            conversation_type=ConversationType.PERSONAL,
            current_team_id=None,
            correlation_id=activity.id,
            idempotency_key=f"teams:{activity.id}:{action}",
            timezone="UTC",
        )


class Dispatcher:
    def __init__(self) -> None:
        self.commands = []

    async def dispatch(self, command, context, payload):  # type: ignore[no-untyped-def]
        self.commands.append((command, context, payload))
        return ActionResult(kind="form", message="Complete the form", data={})


@pytest.mark.asyncio
async def test_sdk_app_registers_messages_endpoint_once() -> None:
    module = _teams_app_module()
    fastapi_app = FastAPI()
    settings = Settings(
        app_env="test",
        dev_auth_enabled=True,
        teams_transport="sdk",
        teams_skip_auth=True,
    )
    teams_app = module.create_teams_app(
        fastapi_app,
        settings,
        Dispatcher(),  # type: ignore[arg-type]
        MockLLMProvider(),
        context_resolver=Resolver(),
    )

    await teams_app.initialize()
    await teams_app.initialize()

    assert isinstance(teams_app, App)
    matching = [
        route for route in fastapi_app.routes if getattr(route, "path", None) == "/api/messages"
    ]
    assert len(matching) == 1
    assert teams_app.options.dangerously_allow_unauthenticated_requests is True


def test_sdk_app_uses_configured_tenant_for_single_tenant_auth() -> None:
    module = _teams_app_module()
    settings = Settings(
        app_env="test",
        dev_auth_enabled=True,
        entra_tenant_id="tenant-1",
        teams_transport="sdk",
        teams_skip_auth=True,
    )

    teams_app = module.create_teams_app(
        FastAPI(),
        settings,
        Dispatcher(),  # type: ignore[arg-type]
        MockLLMProvider(),
        context_resolver=Resolver(),
    )

    assert teams_app.options.tenant_id == "tenant-1"


@pytest.mark.asyncio
async def test_message_processor_dispatches_commands_and_ignores_ordinary_text() -> None:
    module = _teams_app_module()
    resolver = Resolver()
    dispatcher = Dispatcher()
    processor = module.TeamsMessageProcessor(dispatcher, resolver, MockLLMProvider())

    ordinary = await processor.process(_activity("hello team"), None)
    command = await processor.process(
        _activity("<at>Project Assistant</at> /daily"),
        "<at>Project Assistant</at>",
    )

    assert ordinary is not None
    assert "hello team" in ordinary.shared_text
    assert resolver.calls == 1
    assert [item[0].name for item in dispatcher.commands] == ["daily"]
    assert command is not None
    assert command.shared_text == "Complete the form"


def test_skip_auth_is_rejected_outside_local_and_test() -> None:
    with pytest.raises(ValidationError, match="Teams unauthenticated mode"):
        Settings(
            app_env="production",
            auth_mode="entra",
            dev_auth_enabled=False,
            entra_tenant_id="tenant-1",
            entra_client_id="client-1",
            entra_jwks_url="https://login.example.test/keys",
            teams_transport="sdk",
            teams_app_id="app-1",
            teams_app_password="secret",
            teams_skip_auth=True,
        )
