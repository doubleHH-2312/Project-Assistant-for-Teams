from collections.abc import Collection, Mapping
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from project_assistant.core.errors import AppError
from project_assistant.modules.actions.contracts import (
    ActionContext,
    ActionResult,
    ConversationContext,
)
from project_assistant.modules.actions.parser import ParsedCommand
from project_assistant.modules.actions.registry import ActionRegistry
from project_assistant.modules.actions.results import ActionResultStore
from project_assistant.modules.audit.models import (
    ActionInvocation,
    InvocationStatus,
    RequestAuditContext,
)
from project_assistant.modules.audit.service import AuditService
from project_assistant.modules.memberships.models import TeamMembership
from project_assistant.modules.memberships.service import Permission


class AuthorizationPolicy(Protocol):
    async def require(
        self,
        actor_id: str,
        team_ids: Collection[str],
        permission: Permission,
    ) -> dict[str, TeamMembership]: ...


class ActionDispatcher:
    def __init__(
        self,
        registry: ActionRegistry,
        authorization: AuthorizationPolicy,
        audit_service: AuditService,
        result_store: ActionResultStore,
    ) -> None:
        self.registry = registry
        self.authorization = authorization
        self.audit_service = audit_service
        self.result_store = result_store

    async def dispatch(
        self,
        command: ParsedCommand,
        context: ActionContext,
        payload: BaseModel | Mapping[str, Any],
    ) -> ActionResult:
        handler = self.registry.resolve(command.name)
        if handler is None:
            return ActionResult(
                kind="unknown_command",
                message=f"Unknown command '/{command.name}'. Use /help for available actions.",
            )

        definition = handler.definition
        invocation = await self.audit_service.start(
            RequestAuditContext(
                action=definition.name,
                actor_id=context.actor_id,
                tenant_id=context.tenant_id,
                team_id=context.current_team_id,
                project_id=None,
                conversation_id=context.conversation_id,
                conversation_type=context.conversation_type.value,
                timezone=context.timezone,
                correlation_id=context.correlation_id,
                idempotency_key=context.idempotency_key,
                source=context.source,
                metadata={
                    "command": definition.name,
                    "conversationType": context.conversation_type.value,
                },
            )
        )
        replay = await self._replay(invocation)
        if replay is not None:
            return replay

        try:
            conversation_context = ConversationContext(context.conversation_type.value)
            if conversation_context not in definition.allowed_contexts:
                raise AppError(
                    422,
                    "ACTION_CONTEXT_INVALID",
                    "This action is not available in the current conversation",
                )
            try:
                validated = (
                    payload
                    if isinstance(payload, definition.input_schema)
                    else definition.input_schema.model_validate(payload)
                )
            except ValidationError as error:
                raise AppError(
                    422,
                    "ACTION_PAYLOAD_INVALID",
                    "The action payload is invalid",
                    {
                        "fields": [
                            ".".join(str(part) for part in item["loc"])
                            for item in error.errors(include_input=False)
                        ]
                    },
                ) from error
            team_ids = self._team_ids(validated, context)
            try:
                await self.authorization.require(
                    context.actor_id,
                    team_ids,
                    definition.required_permission,
                )
            except AppError as error:
                await self.audit_service.deny(invocation.id, error.code)
                raise
            result = await handler.execute(context, validated)
            result = await self.result_store.save(invocation.id, result)
            completed = await self.audit_service.succeed(invocation.id, result.result_ref)
            if completed.status != InvocationStatus.SUCCEEDED:
                raise AppError(
                    409,
                    "ACTION_ALREADY_COMPLETED",
                    "The action invocation already has a terminal outcome",
                )
            return result
        except AppError as error:
            if invocation.status == InvocationStatus.PENDING:
                if error.status_code == 403:
                    await self.audit_service.deny(invocation.id, error.code)
                else:
                    await self.audit_service.fail(invocation.id, error.code)
            raise
        except Exception as error:
            await self.audit_service.fail(invocation.id, "ACTION_HANDLER_FAILED")
            raise AppError(
                500,
                "ACTION_HANDLER_FAILED",
                "The action could not be completed",
            ) from error

    async def _replay(self, invocation: ActionInvocation) -> ActionResult | None:
        stored = await self.result_store.get(invocation.id)
        if stored is not None:
            if invocation.status == InvocationStatus.PENDING:
                await self.audit_service.succeed(invocation.id, stored.result_ref)
            return stored
        if invocation.status == InvocationStatus.SUCCEEDED:
            return ActionResult(
                kind="replayed",
                message="This action was already completed.",
                result_ref=invocation.result_ref,
            )
        if invocation.status in {InvocationStatus.FAILED, InvocationStatus.DENIED}:
            raise AppError(
                409,
                "ACTION_ALREADY_COMPLETED",
                "This action invocation already has a terminal outcome",
                {"outcome": invocation.status.value},
            )
        return None

    @staticmethod
    def _team_ids(payload: BaseModel, context: ActionContext) -> list[str]:
        raw_team_ids = getattr(payload, "team_ids", None)
        if raw_team_ids is not None:
            team_ids = [str(team_id) for team_id in raw_team_ids]
        else:
            raw_team_id = getattr(payload, "team_id", None)
            team_ids = [str(raw_team_id)] if raw_team_id else []
        if context.current_team_id is not None:
            if team_ids and set(team_ids) != {context.current_team_id}:
                raise AppError(
                    422,
                    "TEAM_SCOPE_MISMATCH",
                    "Payload Team does not match the bound conversation Team",
                )
            team_ids = [context.current_team_id]
        if not team_ids:
            raise AppError(422, "TEAM_SCOPE_REQUIRED", "At least one Team is required")
        return sorted(set(team_ids))
