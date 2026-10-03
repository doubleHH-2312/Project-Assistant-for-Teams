"""Add multi-team reporting, evidence links, and explicit publications."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261002_0006"
down_revision: str | None = "20261002_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("report_templates") as batch:
        batch.alter_column("team_id", existing_type=sa.String(36), nullable=True)
        batch.alter_column(
            "scope",
            existing_type=sa.String(6),
            type_=sa.String(10),
            existing_nullable=False,
        )
        batch.add_column(sa.Column("tenant_id", sa.String(128), nullable=True))
        batch.create_index("ix_report_templates_tenant_id", ["tenant_id"])
        batch.create_unique_constraint(
            "uq_template_tenant_name_version", ["tenant_id", "name", "version"]
        )
        batch.create_check_constraint(
            "ck_report_template_scope_owner",
            "(scope = 'MULTI_TEAM' AND tenant_id IS NOT NULL AND team_id IS NULL) OR "
            "(scope != 'MULTI_TEAM' AND team_id IS NOT NULL)",
        )
    with op.batch_alter_table("weekly_reports") as batch:
        batch.alter_column("team_id", existing_type=sa.String(36), nullable=True)
        batch.alter_column(
            "scope",
            existing_type=sa.String(6),
            type_=sa.String(10),
            existing_nullable=False,
        )
        batch.create_check_constraint(
            "ck_weekly_report_scope_team",
            "(scope = 'MULTI_TEAM' AND team_id IS NULL) OR "
            "(scope != 'MULTI_TEAM' AND team_id IS NOT NULL)",
        )
    op.create_table(
        "weekly_report_teams",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "weekly_report_id",
            sa.String(36),
            sa.ForeignKey("weekly_reports.id"),
            nullable=False,
        ),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=False),
        sa.UniqueConstraint(
            "weekly_report_id", "team_id", name="uq_weekly_report_team"
        ),
    )
    op.create_index(
        "ix_weekly_report_teams_weekly_report_id",
        "weekly_report_teams",
        ["weekly_report_id"],
    )
    op.create_index("ix_weekly_report_teams_team_id", "weekly_report_teams", ["team_id"])
    op.create_table(
        "report_evidence_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "weekly_report_id",
            sa.String(36),
            sa.ForeignKey("weekly_reports.id"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id"),
            nullable=True,
        ),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "weekly_report_id",
            "source_type",
            "source_id",
            name="uq_report_evidence_source",
        ),
    )
    for column in [
        "weekly_report_id",
        "source_type",
        "source_id",
        "team_id",
        "project_id",
        "recorded_at",
    ]:
        op.create_index(
            f"ix_report_evidence_links_{column}", "report_evidence_links", [column]
        )
    op.create_table(
        "report_publications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "weekly_report_id",
            sa.String(36),
            sa.ForeignKey("weekly_reports.id"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("conversation_id", sa.String(256), nullable=False),
        sa.Column("idempotency_key", sa.String(256), nullable=False, unique=True),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    for column in ["weekly_report_id", "actor_id", "conversation_id"]:
        op.create_index(
            f"ix_report_publications_{column}", "report_publications", [column]
        )


def downgrade() -> None:
    op.drop_table("report_publications")
    op.drop_table("report_evidence_links")
    op.drop_table("weekly_report_teams")
    op.execute("DELETE FROM weekly_reports WHERE scope = 'MULTI_TEAM'")
    op.execute("DELETE FROM report_templates WHERE scope = 'MULTI_TEAM'")
    with op.batch_alter_table("weekly_reports") as batch:
        batch.drop_constraint("ck_weekly_report_scope_team", type_="check")
        batch.alter_column("team_id", existing_type=sa.String(36), nullable=False)
        batch.alter_column(
            "scope",
            existing_type=sa.String(10),
            type_=sa.String(6),
            existing_nullable=False,
        )
    with op.batch_alter_table("report_templates") as batch:
        batch.drop_constraint("ck_report_template_scope_owner", type_="check")
        batch.drop_constraint("uq_template_tenant_name_version", type_="unique")
        batch.drop_index("ix_report_templates_tenant_id")
        batch.drop_column("tenant_id")
        batch.alter_column("team_id", existing_type=sa.String(36), nullable=False)
        batch.alter_column(
            "scope",
            existing_type=sa.String(10),
            type_=sa.String(6),
            existing_nullable=False,
        )
