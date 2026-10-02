from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_initial_migration_builds_expected_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "migration.db"
    config = Config("apps/backend/alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path}")
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert {
        "teams",
        "users",
        "projects",
        "work_items",
        "daily_reports",
        "report_templates",
        "weekly_reports",
        "notification_logs",
        "team_memberships",
    }.issubset(tables)


def test_membership_migration_backfills_legacy_user_scope(tmp_path: Path) -> None:
    database_path = tmp_path / "membership-migration.db"
    database_url = f"sqlite:///{database_path}"
    config = Config("apps/backend/alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "20261001_0001")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO teams (
                    id, name, timezone, daily_reminder_time, weekly_report_day,
                    weekly_template_id
                ) VALUES (
                    'team-legacy', 'Legacy Team', 'Asia/Ho_Chi_Minh', '16:30:00', 4,
                    NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO users (
                    id, external_user_id, name, email, role, team_id, active
                ) VALUES (
                    'user-lead', 'entra-lead', 'Legacy Lead', 'lead@example.test',
                    'LEAD', 'team-legacy', 1
                )
                """
            )
        )
    engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "team_memberships" in inspector.get_table_names()
    assert {column["name"] for column in inspector.get_columns("teams")} >= {
        "tenant_id",
        "backfill_window_days",
    }
    assert "tenant_id" in {
        column["name"] for column in inspector.get_columns("users")
    }
    with engine.connect() as connection:
        membership = connection.execute(
            text(
                """
                SELECT user_id, team_id, role, active
                FROM team_memberships
                WHERE user_id = 'user-lead'
                """
            )
        ).mappings().one()
        team = connection.execute(
            text(
                """
                SELECT tenant_id, backfill_window_days
                FROM teams
                WHERE id = 'team-legacy'
                """
            )
        ).mappings().one()
        user_tenant = connection.execute(
            text("SELECT tenant_id FROM users WHERE id = 'user-lead'")
        ).scalar_one()
    engine.dispose()

    assert dict(membership) == {
        "user_id": "user-lead",
        "team_id": "team-legacy",
        "role": "TECH_LEAD",
        "active": True,
    }
    assert dict(team) == {"tenant_id": "legacy-tenant", "backfill_window_days": 7}
    assert user_tenant == "legacy-tenant"
