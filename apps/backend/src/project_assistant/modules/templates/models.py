from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from project_assistant.core.database import Base
from project_assistant.modules.weekly_reports.models import ReportScope


class ReportTemplate(Base):
    __tablename__ = "report_templates"
    __table_args__ = (
        UniqueConstraint("team_id", "name", "version", name="uq_template_team_name_version"),
        UniqueConstraint("tenant_id", "name", "version", name="uq_template_tenant_name_version"),
        CheckConstraint(
            "(scope = 'MULTI_TEAM' AND tenant_id IS NOT NULL AND team_id IS NULL) OR "
            "(scope != 'MULTI_TEAM' AND team_id IS NOT NULL)",
            name="ck_report_template_scope_owner",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), nullable=True, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    scope: Mapped[ReportScope] = mapped_column(
        SAEnum(ReportScope, name="report_scope", native_enum=False)
    )
    version: Mapped[int] = mapped_column(Integer)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
