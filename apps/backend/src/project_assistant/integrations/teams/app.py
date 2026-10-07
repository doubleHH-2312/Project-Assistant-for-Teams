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
from project_assistant.integrations.llm.provider import LLMProvider
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
    async def resolve(self, activity: MessageActivity, action: str) -> ActionContext: ...


class InstallationRecorderProtocol(Protocol):
    async def record(self, activity: InstalledActivity) -> None: ...


import logging

logger = logging.getLogger(__name__)


class TeamsMessageProcessor:
    def __init__(
        self,
        dispatcher: ActionDispatcherProtocol,
        context_resolver: ContextResolverProtocol,
        llm_provider: LLMProvider,
    ) -> None:
        self.dispatcher = dispatcher
        self.context_resolver = context_resolver
        self.llm_provider = llm_provider

    async def process(
        self, activity: MessageActivity, bot_mention_text: str | None
    ) -> TeamsPresentation | None:
        raw_text = activity.text or ""
        logger.info("[BOT_PROCESS] Processing activity text: %r, mention: %r", raw_text, bot_mention_text)
        command = parse_command(raw_text, bot_mention_text)
        if command is None:
            user_message = raw_text
            if bot_mention_text and user_message.startswith(bot_mention_text):
                user_message = user_message[len(bot_mention_text) :].strip()
            if not user_message:
                logger.info("[BOT_PROCESS] Empty user message after mention strip, skipping.")
                return None
            logger.info("[BOT_LLM_CHAT_START] Sending message to LLM provider (%r): %r", self.llm_provider, user_message)
            try:
                reply = await self.llm_provider.chat(user_message)
                logger.info("[BOT_LLM_CHAT_SUCCESS] LLM returned response length: %d, snippet: %r", len(reply), reply[:100])
                return TeamsPresentation(shared_text=reply, private_card={})
            except Exception as error:
                logger.exception("[BOT_LLM_CHAT_ERROR] LLM chat failed: %s", error)
                raise

        logger.info("[BOT_COMMAND] Command parsed: %s, resolving context...", command.name)
        context = await self.context_resolver.resolve(activity, command.name)
        logger.info("[BOT_DISPATCH] Dispatching action: %s, actor: %s", command.name, context.actor_id)
        result = await self.dispatcher.dispatch(command, context, _payload_from_arguments(command))
        logger.info("[BOT_RESULT] Action result kind: %s, success: %s", result.kind, result.message)
        return present_action_result(result, context.conversation_type)

    async def process_card(self, activity: AdaptiveCardInvokeActivity) -> TeamsPresentation:
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
    llm_provider: "LLMProvider",
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
    processor = TeamsMessageProcessor(dispatcher, context_resolver, llm_provider)

    @teams_app.on_message  # type: ignore[untyped-decorator]
    async def on_message(ctx: ActivityContext[MessageActivity]) -> None:
        from_id = getattr(ctx.activity.from_, "id", "unknown")
        conv_id = getattr(ctx.activity.conversation, "id", "unknown")
        text = getattr(ctx.activity, "text", "")
        logger.info("[BOT_ON_MESSAGE] Incoming message from=%s conv=%s text=%r", from_id, conv_id, text)
        try:
            mention_text = _bot_mention_text(ctx.activity)
            presentation = await processor.process(ctx.activity, mention_text)
            if presentation is not None:
                if (
                    _is_personal(ctx.activity)
                    and presentation.private_card
                    and "type" in presentation.private_card
                ):
                    logger.info("[BOT_SEND_REPLY] Sending AdaptiveCard to personal chat")
                    await ctx.send(AdaptiveCard.model_validate(presentation.private_card))
                else:
                    logger.info("[BOT_SEND_REPLY] Sending shared text to chat: %r", presentation.shared_text[:100])
                    await ctx.send(presentation.shared_text)
            else:
                logger.info("[BOT_ON_MESSAGE] Presentation is None, no message sent.")
        except Exception as error:
            logger.exception("[BOT_ERROR] Failed to process message from=%s text=%r: %s", from_id, text, error)
            await ctx.send(f"⚠️ Error: {error}")

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
