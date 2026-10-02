from datetime import time

from sqlalchemy import Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from project_assistant.core.database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), default="legacy-tenant", index=True)
    name: Mapped[str] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    daily_reminder_time: Mapped[time] = mapped_column(Time, default=time(16, 30))
    weekly_report_day: Mapped[int] = mapped_column(Integer, default=4)
    weekly_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    backfill_window_days: Mapped[int] = mapped_column(Integer, default=7)
