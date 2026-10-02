from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from project_assistant.core.database import Base
from project_assistant.modules.actions.contracts import ActionResult


class ActionResultRecord(Base):
    __tablename__ = "action_results"

    invocation_id: Mapped[str] = mapped_column(
        ForeignKey("action_invocations.id"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(64))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    data_json: Mapped[dict[str, Any]] = mapped_column("data", JSON, default=dict)
    private: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def to_result(self) -> ActionResult:
        return ActionResult(
            kind=self.kind,
            message=self.message,
            result_ref=self.result_ref,
            data=self.data_json,
            private=self.private,
        )


class ActionResultStore(Protocol):
    async def get(self, invocation_id: str) -> ActionResult | None: ...

    async def save(
        self, invocation_id: str, result: ActionResult
    ) -> ActionResult: ...


class SqlAlchemyActionResultStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, invocation_id: str) -> ActionResult | None:
        record = await self.session.get(ActionResultRecord, invocation_id)
        return record.to_result() if record is not None else None

    async def save(self, invocation_id: str, result: ActionResult) -> ActionResult:
        record = ActionResultRecord(
            invocation_id=invocation_id,
            kind=result.kind,
            message=result.message,
            result_ref=result.result_ref,
            data_json=dict(result.data),
            private=result.private,
        )
        self.session.add(record)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            existing = await self.get(invocation_id)
            if existing is not None:
                return existing
            raise
        return result
