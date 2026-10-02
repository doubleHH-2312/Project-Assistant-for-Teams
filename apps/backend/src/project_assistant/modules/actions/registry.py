from project_assistant.modules.actions.contracts import ActionHandler


def normalize_action_name(name: str) -> str:
    return name.strip().removeprefix("/").lower()


class ActionRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, ActionHandler] = {}

    def register(self, handler: ActionHandler) -> None:
        names = tuple(
            normalize_action_name(name)
            for name in (handler.definition.name, *handler.definition.aliases)
        )
        if not names[0] or any(not name for name in names):
            raise ValueError("Action names and aliases must not be empty")
        if len(set(names)) != len(names):
            raise ValueError("Action name or alias is already registered")
        collision = next((name for name in names if name in self._handlers), None)
        if collision is not None:
            raise ValueError(f"Action name or alias '{collision}' is already registered")
        for name in names:
            self._handlers[name] = handler

    def resolve(self, name: str) -> ActionHandler | None:
        return self._handlers.get(normalize_action_name(name))

    def handlers(self) -> tuple[ActionHandler, ...]:
        unique: dict[int, ActionHandler] = {}
        for handler in self._handlers.values():
            unique[id(handler)] = handler
        return tuple(unique.values())
