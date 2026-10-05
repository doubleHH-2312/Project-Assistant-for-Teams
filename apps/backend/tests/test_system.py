import httpx
import pytest
from pydantic import ValidationError

from project_assistant.core.config import Settings
from project_assistant.integrations.llm.factory import build_llm_provider
from project_assistant.integrations.llm.provider import (
    MockLLMProvider,
    OpenAICompatibleLLMProvider,
)
from project_assistant.main import app


@pytest.mark.asyncio
async def test_liveness_and_correlation_id() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/live", headers={"X-Correlation-ID": "test-id"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Correlation-ID"] == "test-id"


@pytest.mark.asyncio
async def test_readiness_exposes_serverless_integration_modes() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["database"]["deploymentMode"] in {"persistent", "serverless"}
    assert body["auth"]["mode"] in {"local", "entra"}
    assert body["llm"]["provider"] in {"mock", "openai_compatible"}
    assert body["teams"]["transport"] in {"mock", "sdk"}
    assert body["scheduledJobsEnabled"] is False


def test_production_rejects_local_auth_and_teams_skip_auth() -> None:
    with pytest.raises(ValidationError, match="Local authentication"):
        Settings(_env_file=None, app_env="production", auth_mode="local")
    with pytest.raises(ValidationError, match="Teams unauthenticated"):
        Settings(
            _env_file=None,
            app_env="production",
            auth_mode="entra",
            dev_auth_enabled=False,
            entra_tenant_id="tenant",
            entra_client_id="client",
            entra_jwks_url="https://login.example.test/jwks",
            teams_skip_auth=True,
        )


def test_llm_configuration_builds_mock_or_openai_compatible_provider() -> None:
    mock_settings = Settings(_env_file=None, app_env="test", llm_provider="mock")
    real_settings = Settings(
        _env_file=None,
        app_env="test",
        llm_provider="openai_compatible",
        llm_base_url="https://api.openai.com/v1",
        llm_api_key="test-secret-key",
        llm_model="gpt-test",
        llm_structured_output_mode="json_schema",
    )

    assert isinstance(build_llm_provider(mock_settings), MockLLMProvider)
    provider = build_llm_provider(real_settings)
    assert isinstance(provider, OpenAICompatibleLLMProvider)
    assert "test-secret-key" not in repr(real_settings)
    assert "test-secret-key" not in repr(provider)


def test_openai_compatible_configuration_requires_key_and_model() -> None:
    with pytest.raises(ValidationError, match="API key and model"):
        Settings(
            _env_file=None,
            app_env="test",
            llm_provider="openai_compatible",
            llm_api_key=None,
            llm_model=None,
        )
