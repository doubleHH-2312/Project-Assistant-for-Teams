from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


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
    }.issubset(tables)
