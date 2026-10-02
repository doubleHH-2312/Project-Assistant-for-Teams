"""Initial Project Assistant schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261001_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("daily_reminder_time", sa.Time(), nullable=False),
        sa.Column("weekly_report_day", sa.Integer(), nullable=False),
        sa.Column("weekly_template_id", sa.String(36), nullable=True),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("external_user_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column(
            "role",
            sa.Enum("MEMBER", "LEAD", "PM", name="user_role", native_enum=False),
            nullable=False,
        ),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("external_user_id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_external_user_id", "users", ["external_user_id"])
    op.create_index("ix_users_team_id", "users", ["team_id"])
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
    )
    op.create_index("ix_projects_team_id", "projects", ["team_id"])
    op.create_table(
        "work_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("planned_end_date", sa.Date(), nullable=True),
        sa.UniqueConstraint("project_id", "code", name="uq_work_item_code"),
    )
    op.create_index("ix_work_items_project_id", "work_items", ["project_id"])
    op.create_table(
        "report_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column(
            "scope",
            sa.Enum("MEMBER", "TEAM", name="report_scope", native_enum=False),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("team_id", "name", "version", name="uq_template_team_name_version"),
    )
    op.create_index("ix_report_templates_team_id", "report_templates", ["team_id"])
    op.create_index("ix_report_templates_active", "report_templates", ["active"])
    op.create_table(
        "daily_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("work_item_id", sa.String(36), sa.ForeignKey("work_items.id"), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "NOT_STARTED",
                "IN_PROGRESS",
                "BLOCKED",
                "READY_FOR_REVIEW",
                "DONE",
                name="work_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("work_summary", sa.Text(), nullable=False),
        sa.Column("blocker", sa.Text(), nullable=True),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "user_id", "work_item_id", "report_date", name="uq_daily_report_user_item_date"
        ),
    )
    for column in ["user_id", "project_id", "work_item_id", "report_date"]:
        op.create_index(f"ix_daily_reports_{column}", "daily_reports", [column])
    op.create_table(
        "weekly_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "scope",
            sa.Enum("MEMBER", "TEAM", name="report_scope", native_enum=False),
            nullable=False,
        ),
        sa.Column("subject_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("missing_contributors", sa.JSON(), nullable=False),
        sa.Column("input_record_ids", sa.JSON(), nullable=False),
        sa.Column("generation_source", sa.String(64), nullable=False),
        sa.Column("generation_metadata", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "GENERATED",
                "EDITED",
                "CONFIRMED",
                name="weekly_report_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("report_templates.id")),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("confirmed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("supersedes_id", sa.String(36), sa.ForeignKey("weekly_reports.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in ["scope", "subject_user_id", "team_id", "week_start"]:
        op.create_index(f"ix_weekly_reports_{column}", "weekly_reports", [column])
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_status", sa.String(32), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "user_id", "type", "target_date", name="uq_notification_user_type_target"
        ),
    )
    for column in ["user_id", "target_date", "correlation_id"]:
        op.create_index(f"ix_notification_logs_{column}", "notification_logs", [column])
    op.create_table(
        "teams_conversations",
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("conversation_id", sa.String(256), nullable=False, unique=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("service_url", sa.String(512), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("teams_conversations")
    op.drop_table("notification_logs")
    op.drop_table("weekly_reports")
    op.drop_table("daily_reports")
    op.drop_table("report_templates")
    op.drop_table("work_items")
    op.drop_table("projects")
    op.drop_table("users")
    op.drop_table("teams")
