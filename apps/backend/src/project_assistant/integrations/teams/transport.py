import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from microsoft_teams.apps import App  # type: ignore[import-untyped]

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
        del payload
        if not conversation.conversation_id or not conversation.service_url:
            return DeliveryResult(
                success=False,
                error_code="MISSING_CONVERSATION_ID",
            )
        return DeliveryResult(success=True, external_id=f"mock-{uuid.uuid4()}")


class SDKTeamsTransport:
    def __init__(self, app: App) -> None:
        self.app = app

    async def send_proactive(
        self, conversation: TeamsConversation, payload: dict[str, Any]
    ) -> DeliveryResult:
        if not conversation.conversation_id or not conversation.service_url:
            return DeliveryResult(
                success=False,
                error_code="MISSING_CONVERSATION_ID",
            )
        try:
            sent = await self.app.send(
                conversation.conversation_id,
                str(payload.get("text") or payload.get("message") or "Reminder"),
            )
        except Exception:
            return DeliveryResult(success=False, error_code="TEAMS_DELIVERY_FAILED")
        return DeliveryResult(success=True, external_id=sent.id)
