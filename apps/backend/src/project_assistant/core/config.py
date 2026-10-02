from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
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
    auth_mode: Literal["local", "entra"] = "local"
    dev_auth_enabled: bool = True
    dev_default_user_id: str = "user-member-1"
    entra_tenant_id: str | None = None
    entra_client_id: str | None = None
    entra_jwks_url: str | None = None
    llm_provider: Literal["mock", "internal"] = "mock"
    internal_llm_base_url: str | None = None
    internal_llm_api_key: str | None = Field(default=None, repr=False)
    internal_llm_model: str | None = None
    teams_transport: Literal["mock", "sdk"] = "mock"
    teams_app_id: str | None = None
    teams_app_password: str | None = Field(default=None, repr=False)
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
        if self.llm_provider == "internal" and not all(
            [self.internal_llm_base_url, self.internal_llm_api_key, self.internal_llm_model]
        ):
            raise ValueError("Internal LLM mode requires endpoint, API key, and model")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
