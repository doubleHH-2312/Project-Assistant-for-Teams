import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from project_assistant.modules.notifications.models import TeamsConversation


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    success: bool
    external_id: str | None = None
    error_code: str | None = None


class TeamsTransport(Protocol):
    async def send_proactive(
        self, conversation: TeamsConversation, payload: dict[str, Any]
    ) -> DeliveryResult: ...


class MockTeamsTransport:
    """Deterministic local transport; it never claims real Teams delivery."""

    async def send_proactive(
        self, conversation: TeamsConversation, payload: dict[str, Any]
    ) -> DeliveryResult:
        del conversation, payload
        return DeliveryResult(success=True, external_id=f"mock-{uuid.uuid4()}")

