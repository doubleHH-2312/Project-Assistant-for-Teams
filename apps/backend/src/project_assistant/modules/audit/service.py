import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from project_assistant.core.errors import AppError
from project_assistant.modules.audit.models import (
    ActionInvocation,
    InvocationStatus,
    RequestAuditContext,
)

_SENSITIVE_METADATA_PARTS = (
    "authorization",
    "blocker",
    "content",
    "credential",
    "password",
    "reporttext",
    "secret",
    "summary",
    "token",
)
_SAFE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,99}$")


class AuditRepository(Protocol):
    async def find_by_idempotency_key(self, key: str) -> ActionInvocation | None: ...

    async def get(self, invocation_id: str) -> ActionInvocation | None: ...

    async def save(self, invocation: ActionInvocation) -> ActionInvocation: ...


class AuditService:
    def __init__(
        self,
        repository: AuditRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(UTC))

    async def start(self, context: RequestAuditContext) -> ActionInvocation:
        existing = await self.repository.find_by_idempotency_key(context.idempotency_key)
        if existing is not None:
            return existing
        triggered_at = self._utc_now()
        try:
            local_datetime = triggered_at.astimezone(ZoneInfo(context.timezone))
        except ZoneInfoNotFoundError as error:
            raise AppError(422, "TIMEZONE_INVALID", "The Team timezone is invalid") from error
        invocation = ActionInvocation(
            id=str(uuid.uuid4()),
            action=context.action,
            actor_id=context.actor_id,
            tenant_id=context.tenant_id,
            team_id=context.team_id,
            project_id=context.project_id,
            conversation_id=context.conversation_id,
            conversation_type=context.conversation_type,
            triggered_at=triggered_at,
            local_datetime=local_datetime,
            local_date=local_datetime.date(),
            timezone=context.timezone,
            correlation_id=context.correlation_id,
            idempotency_key=context.idempotency_key,
            status=InvocationStatus.PENDING,
            metadata_json=sanitize_metadata(context.metadata),
        )
        return await self.repository.save(invocation)

    async def succeed(
        self, invocation_id: str, result_ref: str | None = None
    ) -> ActionInvocation:
        return await self._finish(
            invocation_id,
            InvocationStatus.SUCCEEDED,
            result_ref=result_ref,
        )

    async def fail(self, invocation_id: str, code: str) -> ActionInvocation:
        return await self._finish(invocation_id, InvocationStatus.FAILED, error_code=code)

    async def deny(self, invocation_id: str, code: str) -> ActionInvocation:
        return await self._finish(invocation_id, InvocationStatus.DENIED, error_code=code)

    async def _finish(
        self,
        invocation_id: str,
        status: InvocationStatus,
        *,
        result_ref: str | None = None,
        error_code: str | None = None,
    ) -> ActionInvocation:
        invocation = await self.repository.get(invocation_id)
        if invocation is None:
            raise AppError(404, "INVOCATION_NOT_FOUND", "Action invocation was not found")
        if invocation.status != InvocationStatus.PENDING:
            return invocation
        invocation.status = status
        invocation.result_ref = result_ref[:128] if result_ref else None
        invocation.error_code = self._safe_error_code(error_code)
        invocation.completed_at = self._utc_now()
        return await self.repository.save(invocation)

    def _utc_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _safe_error_code(code: str | None) -> str | None:
        if code is None:
            return None
        return code if _SAFE_ERROR_CODE.fullmatch(code) else "INTERNAL_ERROR"


def sanitize_metadata(metadata: dict[str, object]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for index, (key, value) in enumerate(metadata.items()):
        if index >= 20:
            break
        normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
        if any(part in normalized_key for part in _SENSITIVE_METADATA_PARTS):
            continue
        if isinstance(value, bool | int | float) or value is None:
            sanitized[key[:64]] = value
        elif isinstance(value, str):
            sanitized[key[:64]] = value[:256]
        elif isinstance(value, list) and all(
            isinstance(item, bool | int | float | str) or item is None for item in value
        ):
            sanitized[key[:64]] = [
                item[:256] if isinstance(item, str) else item for item in value[:20]
            ]
    return sanitized
