"""Add team-scoped memberships and tenant configuration."""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20261002_0002"
down_revision: str | None = "20261001_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column(
            "tenant_id",
            sa.String(128),
            nullable=False,
            server_default="legacy-tenant",
        ),
    )
    op.add_column(
        "teams",
        sa.Column(
            "backfill_window_days",
            sa.Integer(),
            nullable=False,
            server_default="7",
        ),
    )
    op.create_index("ix_teams_tenant_id", "teams", ["tenant_id"])
    op.add_column(
        "users",
        sa.Column(
            "tenant_id",
            sa.String(128),
            nullable=False,
            server_default="legacy-tenant",
        ),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_table(
        "team_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "MEMBER",
                "TECH_LEAD",
                "PM",
                name="team_role",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "team_id", name="uq_team_membership_user_team"),
    )
    op.create_index("ix_team_memberships_user_id", "team_memberships", ["user_id"])
    op.create_index("ix_team_memberships_team_id", "team_memberships", ["team_id"])
    op.create_index("ix_team_memberships_role", "team_memberships", ["role"])

    connection = op.get_bind()
    legacy_users = connection.execute(
        sa.text("SELECT id, team_id, role, active FROM users ORDER BY id")
    ).mappings()
    membership_table = sa.table(
        "team_memberships",
        sa.column("id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("team_id", sa.String),
        sa.column("role", sa.String),
        sa.column("active", sa.Boolean),
        sa.column("joined_at", sa.DateTime(timezone=True)),
        sa.column("left_at", sa.DateTime(timezone=True)),
    )
    joined_at = datetime.now(UTC)
    rows = [
        {
            "id": f"migrated-{index:026d}",
            "user_id": row["id"],
            "team_id": row["team_id"],
            "role": "TECH_LEAD" if row["role"] == "LEAD" else row["role"],
            "active": bool(row["active"]),
            "joined_at": joined_at,
            "left_at": None,
        }
        for index, row in enumerate(legacy_users, start=1)
    ]
    if rows:
        op.bulk_insert(membership_table, rows)


def downgrade() -> None:
    op.drop_index("ix_team_memberships_role", table_name="team_memberships")
    op.drop_index("ix_team_memberships_team_id", table_name="team_memberships")
    op.drop_index("ix_team_memberships_user_id", table_name="team_memberships")
    op.drop_table("team_memberships")
    op.drop_index("ix_users_tenant_id", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("tenant_id")
    op.drop_index("ix_teams_tenant_id", table_name="teams")
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_column("backfill_window_days")
        batch_op.drop_column("tenant_id")
