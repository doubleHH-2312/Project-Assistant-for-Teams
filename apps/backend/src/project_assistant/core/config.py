from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["local", "test", "staging", "production"] = "local"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+asyncpg://project_assistant:project_assistant@localhost:5432/"
        "project_assistant"
    )
    database_deployment_mode: Literal["persistent", "serverless"] = "persistent"
    scheduled_jobs_enabled: bool = False
    auth_mode: Literal["local", "entra"] = "local"
    dev_auth_enabled: bool = True
    dev_default_user_id: str = "user-member-1"
    entra_tenant_id: str | None = None
    entra_client_id: str | None = None
    entra_jwks_url: str | None = None
    llm_provider: Literal["mock", "openai_compatible"] = "mock"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr | None = Field(default=None, repr=False)
    llm_model: str | None = None
    llm_structured_output_mode: Literal["json_schema", "json_object", "prompt"] = (
        "json_schema"
    )
    llm_timeout_seconds: float = 20
    llm_max_attempts: int = 2
    teams_transport: Literal["mock", "sdk"] = "mock"
    teams_app_id: str | None = None
    teams_app_password: SecretStr | None = Field(default=None, repr=False)
    teams_skip_auth: bool = False
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_security_modes(self) -> "Settings":
        if self.app_env in {"staging", "production"} and (
            self.dev_auth_enabled or self.auth_mode == "local"
        ):
            raise ValueError("Local authentication is forbidden outside local/test")
        if self.auth_mode == "entra" and not all(
            [self.entra_tenant_id, self.entra_client_id, self.entra_jwks_url]
        ):
            raise ValueError("Entra authentication requires tenant, client, and JWKS settings")
        if self.llm_provider == "openai_compatible" and not all(
            [self.llm_base_url, self.llm_api_key, self.llm_model]
        ):
            raise ValueError("OpenAI-compatible LLM mode requires base URL, API key and model")
        if self.llm_timeout_seconds <= 0 or self.llm_max_attempts < 1:
            raise ValueError("LLM timeout and max attempts must be positive")
        if self.teams_skip_auth and self.app_env not in {"local", "test"}:
            raise ValueError(
                "Teams unauthenticated mode is forbidden outside local/test"
            )
        if self.database_deployment_mode == "serverless" and self.scheduled_jobs_enabled:
            raise ValueError("Scheduled jobs cannot run inside the serverless API process")
        if self.teams_transport == "sdk" and not self.teams_skip_auth and not all(
            [self.teams_app_id, self.teams_app_password, self.entra_tenant_id]
        ):
            raise ValueError(
                "Authenticated Teams SDK mode requires app ID, app password, and tenant ID"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
