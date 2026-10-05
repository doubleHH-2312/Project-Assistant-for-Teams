from sqlalchemy.pool import NullPool

from project_assistant.core.config import Settings
from project_assistant.core.database import engine_options, normalize_database_url


def test_serverless_database_uses_transaction_pooler_safe_options() -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_deployment_mode="serverless",
        database_url="postgresql://postgres.example:secret@pooler.example.test:6543/postgres",
    )

    assert normalize_database_url(settings.database_url) == (
        "postgresql+asyncpg://postgres.example:secret@pooler.example.test:6543/postgres"
    )
    assert engine_options(settings) == {
        "poolclass": NullPool,
        "connect_args": {"statement_cache_size": 0, "ssl": "require"},
    }


def test_persistent_database_keeps_application_pool() -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_deployment_mode="persistent",
    )

    assert engine_options(settings) == {"pool_pre_ping": True}
