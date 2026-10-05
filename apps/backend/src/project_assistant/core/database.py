from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from project_assistant.core.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


def normalize_database_url(value: str) -> str:
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+asyncpg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+asyncpg://", 1)
    return value


def engine_options(settings: Settings) -> dict[str, Any]:
    if settings.database_deployment_mode == "serverless":
        return {
            "poolclass": NullPool,
            "connect_args": {"statement_cache_size": 0, "ssl": "require"},
        }
    return {"pool_pre_ping": True}


settings = get_settings()
engine = create_async_engine(
    normalize_database_url(settings.database_url),
    **engine_options(settings),
)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


async def create_schema() -> None:
    # Local/test convenience only. Deployed environments use Alembic migrations.
    from project_assistant.modules import model_registry  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
