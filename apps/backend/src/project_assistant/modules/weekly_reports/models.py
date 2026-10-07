import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from project_assistant.core.database import Base


class ReportScope(StrEnum):
    MEMBER = "MEMBER"
    TEAM = "TEAM"
    MULTI_TEAM = "MULTI_TEAM"


class WeeklyReportStatus(StrEnum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    EDITED = "EDITED"
    CONFIRMED = "CONFIRMED"


class WeeklyReport(Base):
    __tablename__ = "weekly_reports"
    __table_args__ = (
        CheckConstraint(
            "(scope = 'MULTI_TEAM' AND team_id IS NULL) OR "
            "(scope != 'MULTI_TEAM' AND team_id IS NOT NULL)",
            name="ck_weekly_report_scope_team",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope: Mapped[ReportScope] = mapped_column(
        SAEnum(ReportScope, name="report_scope", native_enum=False), index=True
    )
    subject_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), nullable=True, index=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)
    week_end: Mapped[date] = mapped_column(Date)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    missing_contributors: Mapped[list[str]] = mapped_column(JSON, default=list)
    input_record_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    generation_source: Mapped[str] = mapped_column(String(64))
    generation_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[WeeklyReportStatus] = mapped_column(
        SAEnum(WeeklyReportStatus, name="weekly_report_status", native_enum=False)
    )
    template_id: Mapped[str] = mapped_column(ForeignKey("report_templates.id"))
    template_version: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    confirmed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("weekly_reports.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WeeklyReportTeam(Base):
    __tablename__ = "weekly_report_teams"
    __table_args__ = (
        UniqueConstraint("weekly_report_id", "team_id", name="uq_weekly_report_team"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    weekly_report_id: Mapped[str] = mapped_column(ForeignKey("weekly_reports.id"), index=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), index=True)


class ReportEvidenceLink(Base):
    __tablename__ = "report_evidence_links"
    __table_args__ = (
        UniqueConstraint(
            "weekly_report_id",
            "source_type",
            "source_id",
            name="uq_report_evidence_source",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    weekly_report_id: Mapped[str] = mapped_column(ForeignKey("weekly_reports.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    source_id: Mapped[str] = mapped_column(String(36), index=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), index=True)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
