"""Add append-only action invocation and work-status audit."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261002_0004"
down_revision: str | None = "20261002_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("daily_reports", sa.Column("team_id", sa.String(36), nullable=True))
    op.add_column(
        "daily_reports",
        sa.Column("source", sa.String(32), nullable=False, server_default="WEB"),
    )
    op.add_column(
        "daily_reports",
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "daily_reports",
        sa.Column("last_edited_at", sa.DateTime(timezone=True), nullable=True),
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE daily_reports
            SET team_id = (
                SELECT projects.team_id
                FROM projects
                WHERE projects.id = daily_reports.project_id
            )
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE daily_reports
            SET submitted_at = COALESCE(created_at, CURRENT_TIMESTAMP)
            """
        )
    )
    with op.batch_alter_table("daily_reports") as batch_op:
        batch_op.alter_column("team_id", existing_type=sa.String(36), nullable=False)
        batch_op.alter_column(
            "submitted_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
        batch_op.create_foreign_key(
            "fk_daily_reports_team_id_teams", "teams", ["team_id"], ["id"]
        )
    op.create_index("ix_daily_reports_team_id", "daily_reports", ["team_id"])

    op.create_table(
        "action_invocations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("conversation_id", sa.String(256), nullable=False),
        sa.Column("conversation_type", sa.String(32), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("local_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(256), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "SUCCEEDED",
                "FAILED",
                "DENIED",
                name="invocation_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("result_ref", sa.String(128), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_action_invocation_idempotency"
        ),
    )
    for column in [
        "action",
        "actor_id",
        "tenant_id",
        "team_id",
        "project_id",
        "triggered_at",
        "local_date",
        "correlation_id",
        "status",
    ]:
        op.create_index(
            f"ix_action_invocations_{column}", "action_invocations", [column]
        )

    op.create_table(
        "work_item_status_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "daily_report_id",
            sa.String(36),
            sa.ForeignKey("daily_reports.id"),
            nullable=False,
        ),
        sa.Column(
            "action_invocation_id",
            sa.String(36),
            sa.ForeignKey("action_invocations.id"),
            nullable=False,
        ),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column(
            "project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False
        ),
        sa.Column(
            "work_item_id", sa.String(36), sa.ForeignKey("work_items.id"), nullable=False
        ),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "NOT_STARTED",
                "IN_PROGRESS",
                "BLOCKED",
                "READY_FOR_REVIEW",
                "DONE",
                name="status_event_work_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("effective_blocker", sa.Text(), nullable=True),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("local_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column(
            "supersedes_event_id",
            sa.String(36),
            sa.ForeignKey("work_item_status_events.id"),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "action_invocation_id", name="uq_status_event_action_invocation"
        ),
    )
    for column in [
        "daily_report_id",
        "action_invocation_id",
        "team_id",
        "project_id",
        "work_item_id",
        "user_id",
        "status",
        "business_date",
        "recorded_at",
        "local_date",
        "supersedes_event_id",
    ]:
        op.create_index(
            f"ix_work_item_status_events_{column}",
            "work_item_status_events",
            [column],
        )


def downgrade() -> None:
    op.drop_table("work_item_status_events")
    op.drop_table("action_invocations")
    op.drop_index("ix_daily_reports_team_id", table_name="daily_reports")
    with op.batch_alter_table("daily_reports") as batch_op:
        batch_op.drop_constraint("fk_daily_reports_team_id_teams", type_="foreignkey")
        batch_op.drop_column("last_edited_at")
        batch_op.drop_column("submitted_at")
        batch_op.drop_column("source")
        batch_op.drop_column("team_id")
