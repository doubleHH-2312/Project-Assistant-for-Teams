import pytest
from pydantic import BaseModel

from project_assistant.modules.actions.contracts import (
    ActionContext,
    ActionDefinition,
    ActionResult,
    ConversationContext,
)
from project_assistant.modules.actions.registry import ActionRegistry
from project_assistant.modules.memberships.service import Permission


class EmptyInput(BaseModel):
    pass


class StubHandler:
    def __init__(self, name: str, aliases: tuple[str, ...] = ()) -> None:
        self.definition = ActionDefinition(
            name=name,
            aliases=aliases,
            allowed_contexts=frozenset({ConversationContext.PERSONAL}),
            required_permission=Permission.VIEW_OWN_HISTORY,
            input_schema=EmptyInput,
        )

    async def execute(self, context: ActionContext, payload: BaseModel) -> ActionResult:
        del context, payload
        return ActionResult(kind="message", message="ok")


def test_registry_resolves_canonical_name_and_alias() -> None:
    registry = ActionRegistry()
    handler = StubHandler("history", aliases=("recent",))

    registry.register(handler)

    assert registry.resolve("/history") is handler
    assert registry.resolve("RECENT") is handler
    assert registry.resolve("missing") is None


def test_registry_rejects_duplicate_name_or_alias() -> None:
    registry = ActionRegistry()
    registry.register(StubHandler("history", aliases=("recent",)))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(StubHandler("recent"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(StubHandler("other", aliases=("history",)))
