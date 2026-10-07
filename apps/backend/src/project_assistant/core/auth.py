import asyncio
from typing import Annotated, Any

import jwt
from fastapi import Depends, Request
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.core.config import Settings, get_settings
from project_assistant.core.database import get_session
from project_assistant.core.errors import AppError
from project_assistant.modules.memberships.repository import SqlAlchemyMembershipRepository
from project_assistant.modules.memberships.service import AuthorizationService
from project_assistant.modules.users.models import User


class EntraTokenVerifier:
    def __init__(self, settings: Settings) -> None:
        if not settings.entra_jwks_url:
            raise ValueError("Entra JWKS URL is required")
        self.settings = settings
        self.jwks_client = PyJWKClient(settings.entra_jwks_url)

    def verify(self, token: str) -> dict[str, Any]:
        signing_key = self.jwks_client.get_signing_key_from_jwt(token)
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False, "verify_iss": False},
        )

        token_aud = claims.get("aud")
        token_iss = claims.get("iss")

        # Validate audience: must equal or contain entra_client_id
        aud_valid = False
        if isinstance(token_aud, str) and self.settings.entra_client_id in token_aud:
            aud_valid = True
        elif isinstance(token_aud, list) and any(
            isinstance(a, str) and self.settings.entra_client_id in a for a in token_aud
        ):
            aud_valid = True

        if not aud_valid:
            raise jwt.InvalidAudienceError("Audience does not match Entra Client ID")

        # Validate issuer: must be from Microsoft Entra ID
        if isinstance(token_iss, str) and not any(
            token_iss.startswith(prefix)
            for prefix in [
                "https://login.microsoftonline.com/",
                "https://sts.windows.net/",
            ]
        ):
            raise jwt.InvalidIssuerError("Issuer is invalid")

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
        email = claims.get("preferred_username") or claims.get("upn") or claims.get("email")
        name = claims.get("name") or (email.split("@")[0] if email else "Teams User")

        if not object_id:
            raise AppError(401, "TOKEN_INVALID", "Access token identity is invalid")
        if settings.entra_tenant_id != "common" and tenant_id != settings.entra_tenant_id:
            raise AppError(401, "TOKEN_INVALID", "Access token identity is invalid")

        # 1. Try finding user by external_user_id and tenant_id
        user = await session.scalar(
            select(User).where(
                User.external_user_id == object_id,
                User.tenant_id == tenant_id,
                User.active.is_(True),
            )
        )

        # 2. Try finding user by external_user_id alone (if tenant_id was updated/common)
        if user is None:
            user = await session.scalar(
                select(User).where(
                    User.external_user_id == object_id,
                    User.active.is_(True),
                )
            )
            if user:
                user.tenant_id = tenant_id
                await session.commit()

        # 3. Try finding by email
        if user is None and email:
            user = await session.scalar(
                select(User).where(
                    User.email == email,
                    User.active.is_(True),
                )
            )
            if user:
                user.external_user_id = object_id
                user.tenant_id = tenant_id
                await session.commit()

        # 4. Auto-link first unlinked seed user if present
        if user is None:
            first_user = await session.scalar(
                select(User).where(User.active.is_(True)).order_by(User.id)
            )
            if first_user and (
                first_user.external_user_id.startswith("entra-")
                or first_user.external_user_id == "entra-user-1"
            ):
                first_user.external_user_id = object_id
                first_user.tenant_id = tenant_id
                if email:
                    first_user.email = email
                if name:
                    first_user.name = name
                await session.commit()
                user = first_user

    if user is None:
        raise AppError(403, "USER_NOT_PROVISIONED", "User is not provisioned")
    return user


async def get_authorization_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthorizationService:
    return AuthorizationService(SqlAlchemyMembershipRepository(session))
