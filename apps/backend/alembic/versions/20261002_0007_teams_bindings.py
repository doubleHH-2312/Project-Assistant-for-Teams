"""Add Microsoft Teams conversation installation and Team bindings."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261002_0007"
down_revision: str | None = "20261002_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "teams_conversation_bindings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("conversation_id", sa.String(256), nullable=False),
        sa.Column("conversation_type", sa.String(32), nullable=False),
        sa.Column("service_url", sa.String(512), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column(
            "installed_by_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "conversation_id",
            name="uq_teams_binding_tenant_conversation",
        ),
    )
    for column in ["tenant_id", "conversation_id", "user_id", "team_id", "installed_by_id"]:
        op.create_index(
            f"ix_teams_conversation_bindings_{column}",
            "teams_conversation_bindings",
            [column],
        )


def downgrade() -> None:
    op.drop_table("teams_conversation_bindings")
