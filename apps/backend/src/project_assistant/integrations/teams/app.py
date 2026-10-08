import logging
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

from .logger import BotExecutionTrace
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
        self,
        activity: MessageActivity,
        bot_mention_text: str | None,
        trace: BotExecutionTrace | None = None,
    ) -> TeamsPresentation | None:
        raw_text = activity.text or ""
        if trace:
            trace.log("🔍 Parsing Command", f"Text={raw_text!r}, Mention={bot_mention_text!r}")
        command = parse_command(raw_text, bot_mention_text)
        if command is None:
            user_message = raw_text
            if bot_mention_text and user_message.startswith(bot_mention_text):
                user_message = user_message[len(bot_mention_text) :].strip()
            if not user_message:
                if trace:
                    trace.log("⚠️ Empty User Message", "No message content after mention strip")
                return None
            if trace:
                trace.log(
                    "💬 Routing to LLM",
                    f"Provider={self.llm_provider.__class__.__name__}, Prompt={user_message!r}",
                )
            try:
                reply = await self.llm_provider.chat(user_message)
                if trace:
                    trace.log("✅ LLM Response Received", f"Length={len(reply)} chars")
                return TeamsPresentation(shared_text=reply, private_card={})
            except Exception as error:
                if trace:
                    trace.log_error("LLM Chat Call Failed", error)
                logger.exception("[BOT_LLM_CHAT_ERROR] LLM chat failed: %s", error)
                raise

        if trace:
            trace.log("⚡ Command Parsed", f"Command=/{command.name}, Args={command.arguments}")
            trace.log("🆔 Resolving Context", f"Action=/{command.name}")
        context = await self.context_resolver.resolve(activity, command.name)
        if trace:
            trace.log(
                "👤 Identity Resolved", f"Actor={context.actor_id}, Tenant={context.tenant_id}"
            )
            trace.log("⚙️ Dispatching Action", f"Command={command.name}")
        result = await self.dispatcher.dispatch(command, context, _payload_from_arguments(command))
        if trace:
            trace.log("✅ Action Completed", f"Kind={result.kind}, Message={result.message}")
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
    teams_app = App(**options)
    processor = TeamsMessageProcessor(dispatcher, context_resolver, llm_provider)

    @teams_app.on_message  # type: ignore[untyped-decorator]
    async def on_message(ctx: ActivityContext[MessageActivity]) -> None:
        from_id = getattr(ctx.activity.from_, "id", "unknown")
        conv_id = getattr(ctx.activity.conversation, "id", "unknown")
        text = getattr(ctx.activity, "text", "")
        trace = BotExecutionTrace(conversation_id=conv_id, from_id=from_id)
        trace.log("📥 Activity Received", f"Text={text!r}")
        try:
            mention_text = _bot_mention_text(ctx.activity)
            presentation = await processor.process(ctx.activity, mention_text, trace=trace)
            if presentation is not None:
                log_suffix = f"\n\n---\n{trace.render_markdown()}"
                if (
                    _is_personal(ctx.activity)
                    and presentation.private_card
                    and "type" in presentation.private_card
                ):
                    trace.log("📤 Sending AdaptiveCard to personal chat")
                    await ctx.send(AdaptiveCard.model_validate(presentation.private_card))
                    await ctx.send(f"✅ Action rendered above.{log_suffix}")
                else:
                    trace.log("📤 Sending shared text reply")
                    await ctx.send(f"{presentation.shared_text}{log_suffix}")
            else:
                trace.log("⚠️ Presentation Empty", "No message sent")
                await ctx.send(f"⚠️ Empty presentation.{log_suffix}")
        except Exception as error:
            trace.log_error("Failed Processing Activity", error)
            logger.exception(
                "[BOT_ERROR] Failed to process message from=%s text=%r: %s", from_id, text, error
            )
            await ctx.send(f"⚠️ **Bot Error:** `{error}`\n\n---\n{trace.render_markdown()}")

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
