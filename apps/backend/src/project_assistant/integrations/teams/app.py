from collections.abc import Mapping
from typing import Any, Protocol

from fastapi import FastAPI
from microsoft_teams.api import (  # type: ignore[attr-defined]
    AdaptiveCardActionMessageResponse,
    AdaptiveCardInvokeActivity,
    InstalledActivity,
    MessageActivity,
)
from microsoft_teams.apps import (  # type: ignore[import-untyped]
    ActivityContext,
    App,
    FastAPIAdapter,
)
from microsoft_teams.cards import AdaptiveCard

from project_assistant.core.config import Settings
from project_assistant.modules.actions.contracts import ActionContext, ActionResult
from project_assistant.modules.actions.parser import ParsedCommand, parse_command

from .presenters import TeamsPresentation, present_action_result


class ActionDispatcherProtocol(Protocol):
    async def dispatch(
        self,
        command: ParsedCommand,
        context: ActionContext,
        payload: Mapping[str, Any],
    ) -> ActionResult: ...


class ContextResolverProtocol(Protocol):
    async def resolve(
        self, activity: MessageActivity, action: str
    ) -> ActionContext: ...


class InstallationRecorderProtocol(Protocol):
    async def record(self, activity: InstalledActivity) -> None: ...


class TeamsMessageProcessor:
    def __init__(
        self,
        dispatcher: ActionDispatcherProtocol,
        context_resolver: ContextResolverProtocol,
    ) -> None:
        self.dispatcher = dispatcher
        self.context_resolver = context_resolver

    async def process(
        self, activity: MessageActivity, bot_mention_text: str | None
    ) -> TeamsPresentation | None:
        command = parse_command(activity.text or "", bot_mention_text)
        if command is None:
            return None
        context = await self.context_resolver.resolve(activity, command.name)
        result = await self.dispatcher.dispatch(
            command, context, _payload_from_arguments(command)
        )
        return present_action_result(result, context.conversation_type)

    async def process_card(
        self, activity: AdaptiveCardInvokeActivity
    ) -> TeamsPresentation:
        action = activity.value.action
        data = dict(action.data)
        command_name = str(data.pop("action", action.verb or "")).removeprefix("/")
        command_name = {
            "dailyReport.submit": "daily",
            "weeklyReport.generate": "weekly",
        }.get(command_name, command_name)
        command = ParsedCommand(name=command_name, arguments=())
        context = await self.context_resolver.resolve(activity, command.name)
        result = await self.dispatcher.dispatch(command, context, data)
        return present_action_result(result, context.conversation_type)


def create_teams_app(
    fastapi_app: FastAPI,
    settings: Settings,
    dispatcher: ActionDispatcherProtocol,
    *,
    context_resolver: ContextResolverProtocol,
    installation_recorder: InstallationRecorderProtocol | None = None,
) -> App:
    options: dict[str, Any] = {
        "http_server_adapter": FastAPIAdapter(fastapi_app),
        "messaging_endpoint": "/api/messages",
        "dangerously_allow_unauthenticated_requests": settings.teams_skip_auth,
    }
    if settings.teams_app_id:
        options["client_id"] = settings.teams_app_id
    if settings.teams_app_password:
        options["client_secret"] = settings.teams_app_password.get_secret_value()
    if settings.entra_tenant_id and settings.entra_tenant_id != "common":
        options["tenant_id"] = settings.entra_tenant_id
    teams_app = App(**options)
    processor = TeamsMessageProcessor(dispatcher, context_resolver)

    @teams_app.on_message  # type: ignore[untyped-decorator]
    async def on_message(ctx: ActivityContext[MessageActivity]) -> None:
        mention_text = _bot_mention_text(ctx.activity)
        presentation = await processor.process(ctx.activity, mention_text)
        if presentation is not None:
            if _is_personal(ctx.activity):
                await ctx.send(AdaptiveCard.model_validate(presentation.private_card))
            else:
                await ctx.send(presentation.shared_text)

    @teams_app.on_card_action_execute  # type: ignore[untyped-decorator]
    async def on_card_action(
        ctx: ActivityContext[AdaptiveCardInvokeActivity],
    ) -> AdaptiveCardActionMessageResponse:
        presentation = await processor.process_card(ctx.activity)
        return AdaptiveCardActionMessageResponse(value=presentation.shared_text)

    @teams_app.on_install_add  # type: ignore[untyped-decorator]
    async def on_install(ctx: ActivityContext[InstalledActivity]) -> None:
        if installation_recorder is not None:
            await installation_recorder.record(ctx.activity)
        await ctx.send(
            "Project Assistant is ready. Mention me with /help to see available actions."
        )

    return teams_app


def _bot_mention_text(activity: MessageActivity) -> str | None:
    for entity in activity.entities or []:
        if getattr(entity, "type", None) == "mention":
            mentioned = getattr(entity, "mentioned", None)
            if mentioned is not None and mentioned.id == activity.recipient.id:
                return str(getattr(entity, "text", "")) or None
    return None


def _payload_from_arguments(command: ParsedCommand) -> dict[str, Any]:
    if not command.arguments:
        return {}
    if command.name in {"weekly-multi-team", "multi-team-weekly"}:
        return {"teamIds": list(command.arguments)}
    return {"teamId": command.arguments[0]}


def _is_personal(activity: MessageActivity) -> bool:
    return (activity.conversation.conversation_type or "personal").casefold() == "personal"
