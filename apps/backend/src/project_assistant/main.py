import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from project_assistant.api.system import router as system_router
from project_assistant.core.config import get_settings
from project_assistant.core.database import create_schema
from project_assistant.core.errors import AppError, app_error_handler
from project_assistant.modules.daily_reports.router import router as daily_report_router
from project_assistant.modules.teams.router import router as team_router
from project_assistant.modules.weekly_reports.router import router as weekly_report_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.app_env in {"local", "test"}:
        await create_schema()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    app = FastAPI(title="Project Assistant API", version=settings.app_version, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def correlation_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = request.state.correlation_id
        return response

    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.include_router(system_router)
    app.include_router(daily_report_router, prefix=settings.api_prefix)
    app.include_router(team_router, prefix=settings.api_prefix)
    app.include_router(weekly_report_router, prefix=settings.api_prefix)
    return app


app = create_app()
