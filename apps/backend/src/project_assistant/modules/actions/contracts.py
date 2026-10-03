from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel

from project_assistant.modules.memberships.service import Permission


class ConversationType(StrEnum):
    PERSONAL = "PERSONAL"
    GROUP_CHAT = "GROUP_CHAT"
    TEAM_CHANNEL = "TEAM_CHANNEL"


class ConversationContext(StrEnum):
    PERSONAL = "PERSONAL"
    GROUP_CHAT = "GROUP_CHAT"
    TEAM_CHANNEL = "TEAM_CHANNEL"


@dataclass(frozen=True)
class ActionDefinition:
    name: str
    aliases: tuple[str, ...]
    allowed_contexts: frozenset[ConversationContext]
    required_permission: Permission | None
    input_schema: type[BaseModel]


@dataclass(frozen=True)
class ActionContext:
    actor_id: str
    tenant_id: str
    conversation_id: str
    conversation_type: ConversationType
    current_team_id: str | None
    correlation_id: str
    idempotency_key: str
    timezone: str = "UTC"
    source: str = "TEAMS"


@dataclass(frozen=True)
class ActionResult:
    kind: str
    message: str | None = None
    result_ref: str | None = None
    data: Mapping[str, Any] = field(default_factory=dict)
    private: bool = True


class ActionHandler(Protocol):
    definition: ActionDefinition

    async def execute(
        self, context: ActionContext, payload: BaseModel
    ) -> ActionResult: ...
