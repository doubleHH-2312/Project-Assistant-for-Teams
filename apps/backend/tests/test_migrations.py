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
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
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
        "action_invocations",
        "action_results",
        "work_item_status_events",
        "weekly_report_teams",
        "report_evidence_links",
        "report_publications",
        "teams_conversation_bindings",
    }.issubset(tables)
    daily_columns = {
        column["name"] for column in inspector.get_columns("daily_reports")
    }
    assert {"team_id", "source", "submitted_at", "last_edited_at"}.issubset(
        daily_columns
    )
    weekly_team_id = next(
        column
        for column in inspector.get_columns("weekly_reports")
        if column["name"] == "team_id"
    )
    template_columns = {
        column["name"]: column
        for column in inspector.get_columns("report_templates")
    }
    weekly_scope = next(
        column
        for column in inspector.get_columns("weekly_reports")
        if column["name"] == "scope"
    )
    assert weekly_team_id["nullable"] is True
    assert weekly_scope["type"].length >= len("MULTI_TEAM")
    assert template_columns["team_id"]["nullable"] is True
    assert template_columns["tenant_id"]["nullable"] is True
    assert template_columns["scope"]["type"].length >= len("MULTI_TEAM")
    binding_columns = {
        column["name"]
        for column in inspector.get_columns("teams_conversation_bindings")
    }
    assert {
        "tenant_id",
        "conversation_id",
        "conversation_type",
        "service_url",
        "user_id",
        "team_id",
        "installed_by_id",
        "active",
    }.issubset(binding_columns)
    engine.dispose()


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
        connection.execute(
            text(
                """
                INSERT INTO projects (id, team_id, name, status)
                VALUES ('project-legacy', 'team-legacy', 'Legacy Project', 'ACTIVE')
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO work_items (
                    id, project_id, code, title, status, priority
                ) VALUES (
                    'item-legacy', 'project-legacy', 'LEG-1', 'Legacy Item',
                    'IN_PROGRESS', 0
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO daily_reports (
                    id, user_id, project_id, work_item_id, report_date, status,
                    work_summary, blocker, next_action
                ) VALUES (
                    'daily-legacy', 'user-lead', 'project-legacy', 'item-legacy',
                    '2026-10-01', 'BLOCKED', 'Waiting for access', NULL,
                    'Request access'
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
    assert {column["name"] for column in inspector.get_columns("users")} & {
        "role",
        "team_id",
    } == set()
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
        daily_team = connection.execute(
            text("SELECT team_id FROM daily_reports WHERE id = 'daily-legacy'")
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
    assert daily_team == "team-legacy"
