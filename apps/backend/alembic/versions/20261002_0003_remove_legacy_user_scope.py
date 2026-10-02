"""Remove legacy global role and team columns from users."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261002_0003"
down_revision: str | None = "20261002_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_users_team_id", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("role")
        batch_op.drop_column("team_id")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "role",
                sa.Enum("MEMBER", "LEAD", "PM", name="user_role", native_enum=False),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=True)
        )

    connection = op.get_bind()
    memberships = connection.execute(
        sa.text(
            """
            SELECT user_id, team_id, role
            FROM team_memberships
            WHERE active = true
            ORDER BY user_id, team_id
            """
        )
    ).mappings()
    restored_users: set[str] = set()
    for membership in memberships:
        user_id = str(membership["user_id"])
        if user_id in restored_users:
            continue
        role = "LEAD" if membership["role"] == "TECH_LEAD" else membership["role"]
        connection.execute(
            sa.text("UPDATE users SET team_id = :team_id, role = :role WHERE id = :user_id"),
            {"team_id": membership["team_id"], "role": role, "user_id": user_id},
        )
        restored_users.add(user_id)
    op.create_index("ix_users_team_id", "users", ["team_id"])
