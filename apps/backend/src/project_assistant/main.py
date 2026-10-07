import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from project_assistant.api.session import router as session_router
from project_assistant.api.system import router as system_router
from project_assistant.core.config import get_settings
from project_assistant.core.database import SessionFactory
from project_assistant.core.errors import (
    AppError,
    app_error_handler,
    request_validation_error_handler,
)
from project_assistant.modules.daily_reports.router import router as daily_report_router
from project_assistant.modules.publications.router import router as publication_router
from project_assistant.modules.teams.router import router as team_router
from project_assistant.modules.weekly_reports.router import router as weekly_report_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    teams_app = getattr(app.state, "teams_app", None)
    if teams_app is not None and not getattr(app.state, "teams_initialized", False):
        await teams_app.initialize()
        app.state.teams_initialized = True
    try:
        yield
    finally:
        if teams_app is not None and getattr(app.state, "teams_initialized", False):
            await teams_app.stop()
            app.state.teams_initialized = False


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
    app.add_exception_handler(
        RequestValidationError,
        request_validation_error_handler,  # type: ignore[arg-type]
    )
    app.include_router(system_router)
    app.include_router(session_router, prefix=settings.api_prefix)
    app.include_router(daily_report_router, prefix=settings.api_prefix)
    app.include_router(team_router, prefix=settings.api_prefix)
    app.include_router(weekly_report_router, prefix=settings.api_prefix)
    app.include_router(publication_router, prefix=settings.api_prefix)
    if settings.teams_transport == "sdk":
        from project_assistant.integrations.llm.factory import build_llm_provider
        from project_assistant.integrations.teams.app import create_teams_app
        from project_assistant.integrations.teams.runtime import (
            SessionScopedActionDispatcher,
            SessionScopedInstallationRecorder,
            SessionScopedTeamsContextResolver,
        )

        app.state.teams_app = create_teams_app(
            app,
            settings,
            SessionScopedActionDispatcher(SessionFactory, settings),
            build_llm_provider(settings),
            context_resolver=SessionScopedTeamsContextResolver(SessionFactory),
            installation_recorder=SessionScopedInstallationRecorder(SessionFactory),
        )
        app.state.teams_initialized = False
    return app


app = create_app()
