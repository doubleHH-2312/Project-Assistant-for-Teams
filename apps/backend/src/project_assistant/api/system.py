from fastapi import APIRouter

from project_assistant.core.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ready",
        "database": {"deploymentMode": settings.database_deployment_mode},
        "auth": {"mode": settings.auth_mode},
        "llm": {"provider": settings.llm_provider},
        "teams": {"transport": settings.teams_transport},
        "scheduledJobsEnabled": settings.scheduled_jobs_enabled,
    }


@router.get("/version")
async def version() -> dict[str, str]:
    return {"version": get_settings().app_version}
