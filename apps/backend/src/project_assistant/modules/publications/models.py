import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from project_assistant.core.database import Base


class ReportPublication(Base):
    __tablename__ = "report_publications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    weekly_report_id: Mapped[str] = mapped_column(
        ForeignKey("weekly_reports.id"), index=True
    )
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(String(256), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256), unique=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
