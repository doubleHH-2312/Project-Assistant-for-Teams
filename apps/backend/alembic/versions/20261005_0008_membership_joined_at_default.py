"""Add the database default required by Team Membership inserts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0008"
down_revision: str | None = "20261002_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("team_memberships") as batch:
        batch.alter_column(
            "joined_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        )


def downgrade() -> None:
    with op.batch_alter_table("team_memberships") as batch:
        batch.alter_column(
            "joined_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=None,
        )
