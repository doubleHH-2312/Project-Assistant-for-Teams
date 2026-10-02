from collections.abc import Iterable

from project_assistant.modules.actions.contracts import ActionHandler
from project_assistant.modules.actions.dispatcher import ActionDispatcher, AuthorizationPolicy
from project_assistant.modules.actions.registry import ActionRegistry
from project_assistant.modules.actions.results import ActionResultStore
from project_assistant.modules.audit.service import AuditService


def build_action_registry(handlers: Iterable[ActionHandler] = ()) -> ActionRegistry:
    registry = ActionRegistry()
    for handler in handlers:
        registry.register(handler)
    return registry


def build_action_dispatcher(
    authorization: AuthorizationPolicy,
    audit_service: AuditService,
    result_store: ActionResultStore,
    handlers: Iterable[ActionHandler] = (),
) -> ActionDispatcher:
    return ActionDispatcher(
        build_action_registry(handlers),
        authorization,
        audit_service,
        result_store,
    )
