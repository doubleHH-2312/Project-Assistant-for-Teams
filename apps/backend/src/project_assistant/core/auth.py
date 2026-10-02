import asyncio
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

import jwt
from fastapi import Depends, Request
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.core.config import Settings, get_settings
from project_assistant.core.database import get_session
from project_assistant.core.errors import AppError
from project_assistant.modules.users.models import User, UserRole


class EntraTokenVerifier:
    def __init__(self, settings: Settings) -> None:
        if not settings.entra_jwks_url:
            raise ValueError("Entra JWKS URL is required")
        self.settings = settings
        self.jwks_client = PyJWKClient(settings.entra_jwks_url)

    def verify(self, token: str) -> dict[str, Any]:
        signing_key = self.jwks_client.get_signing_key_from_jwt(token)
        issuer = f"https://login.microsoftonline.com/{self.settings.entra_tenant_id}/v2.0"
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self.settings.entra_client_id,
            issuer=issuer,
        )
        return claims


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    settings = get_settings()
    if settings.auth_mode == "local":
        if not settings.dev_auth_enabled or settings.app_env not in {"local", "test"}:
            raise AppError(401, "AUTH_DISABLED", "Local authentication is disabled")
        user_id = request.headers.get("X-Dev-User-ID", settings.dev_default_user_id)
        user = await session.scalar(select(User).where(User.id == user_id, User.active.is_(True)))
    else:
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise AppError(401, "AUTH_REQUIRED", "Bearer token is required")
        token = authorization.removeprefix("Bearer ").strip()
        try:
            claims = await asyncio.to_thread(EntraTokenVerifier(settings).verify, token)
        except (jwt.PyJWTError, ValueError) as error:
            raise AppError(401, "TOKEN_INVALID", "Access token is invalid") from error
        object_id = claims.get("oid")
        tenant_id = claims.get("tid")
        if not object_id or tenant_id != settings.entra_tenant_id:
            raise AppError(401, "TOKEN_INVALID", "Access token identity is invalid")
        user = await session.scalar(
            select(User).where(User.external_user_id == object_id, User.active.is_(True))
        )
    if user is None:
        raise AppError(403, "USER_NOT_PROVISIONED", "User is not provisioned")
    return user


def require_roles(
    *roles: UserRole,
) -> Callable[[Annotated[User, Depends(get_current_user)]], Coroutine[Any, Any, User]]:
    async def authorize(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise AppError(403, "FORBIDDEN", "The current role cannot perform this action")
        return user

    return authorize

