import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from project_assistant.core.database import Base
from project_assistant.modules.daily_reports.models import WorkStatus


class InvocationStatus(StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    DENIED = "DENIED"


@dataclass(frozen=True)
class RequestAuditContext:
    action: str
    actor_id: str
    tenant_id: str
    team_id: str | None
    project_id: str | None
    conversation_id: str
    conversation_type: str
    timezone: str
    correlation_id: str
    idempotency_key: str
    source: str
    metadata: dict[str, object] = field(default_factory=dict)


class ActionInvocation(Base):
    __tablename__ = "action_invocations"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_action_invocation_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action: Mapped[str] = mapped_column(String(100), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    conversation_id: Mapped[str] = mapped_column(String(256))
    conversation_type: Mapped[str] = mapped_column(String(32))
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    local_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    local_date: Mapped[date] = mapped_column(Date, index=True)
    timezone: Mapped[str] = mapped_column(String(64))
    correlation_id: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256))
    status: Mapped[InvocationStatus] = mapped_column(
        SAEnum(InvocationStatus, name="invocation_status", native_enum=False),
        index=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkItemStatusEvent(Base):
    __tablename__ = "work_item_status_events"
    __table_args__ = (
        UniqueConstraint("action_invocation_id", name="uq_status_event_action_invocation"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    daily_report_id: Mapped[str] = mapped_column(ForeignKey("daily_reports.id"), index=True)
    action_invocation_id: Mapped[str] = mapped_column(
        ForeignKey("action_invocations.id"), index=True
    )
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    work_item_id: Mapped[str] = mapped_column(ForeignKey("work_items.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[WorkStatus] = mapped_column(
        SAEnum(WorkStatus, name="status_event_work_status", native_enum=False),
        index=True,
    )
    effective_blocker: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_date: Mapped[date] = mapped_column(Date, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    local_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    local_date: Mapped[date] = mapped_column(Date, index=True)
    timezone: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32))
    supersedes_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("work_item_status_events.id"), nullable=True, index=True
    )
