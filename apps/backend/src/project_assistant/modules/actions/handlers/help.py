from typing import Protocol

from pydantic import BaseModel, ConfigDict

from project_assistant.modules.actions.contracts import (
    ActionContext,
    ActionDefinition,
    ActionResult,
    ConversationContext,
)
from project_assistant.modules.actions.registry import ActionRegistry
from project_assistant.modules.memberships.service import Permission


class HelpActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HelpAuthorization(Protocol):
    async def list_permissions(self, actor_id: str) -> frozenset[Permission]: ...


class HelpActionHandler:
    definition = ActionDefinition(
        name="help",
        aliases=("commands",),
        allowed_contexts=frozenset(ConversationContext),
        required_permission=None,
        input_schema=HelpActionInput,
    )

    def __init__(
        self, registry: ActionRegistry, authorization: HelpAuthorization
    ) -> None:
        self.registry = registry
        self.authorization = authorization

    async def execute(
        self, context: ActionContext, payload: BaseModel
    ) -> ActionResult:
        if not isinstance(payload, HelpActionInput):
            raise TypeError("HelpActionHandler requires HelpActionInput")
        permissions = await self.authorization.list_permissions(context.actor_id)
        conversation = ConversationContext(context.conversation_type.value)
        actions = [
            {
                "name": handler.definition.name,
                "command": f"/{handler.definition.name}",
            }
            for handler in self.registry.handlers()
            if conversation in handler.definition.allowed_contexts
            and (
                handler.definition.required_permission is None
                or handler.definition.required_permission in permissions
            )
        ]
        actions.sort(key=lambda action: action["name"])
        return ActionResult(
            kind="help",
            message="Available actions.",
            data={"actions": actions},
        )
