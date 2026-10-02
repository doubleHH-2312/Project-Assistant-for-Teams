from fastapi import APIRouter

from project_assistant.core.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ready",
        "authMode": settings.auth_mode,
        "llmProvider": settings.llm_provider,
        "teamsTransport": settings.teams_transport,
    }


@router.get("/version")
async def version() -> dict[str, str]:
    return {"version": get_settings().app_version}

