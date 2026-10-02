"""Persist transport-neutral action results for idempotent replay."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261002_0005"
down_revision: str | None = "20261002_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "action_results",
        sa.Column(
            "invocation_id",
            sa.String(36),
            sa.ForeignKey("action_invocations.id"),
            primary_key=True,
        ),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("result_ref", sa.String(128), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("private", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("action_results")
