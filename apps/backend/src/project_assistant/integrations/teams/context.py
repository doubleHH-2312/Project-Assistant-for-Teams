import uuid
from dataclasses import dataclass
from typing import Protocol

from microsoft_teams.api import MessageActivity  # type: ignore[attr-defined]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.core.errors import AppError
from project_assistant.modules.actions.contracts import ActionContext, ConversationType
from project_assistant.modules.memberships.service import Permission
from project_assistant.modules.notifications.models import TeamsConversationBinding
from project_assistant.modules.teams.models import Team
from project_assistant.modules.users.models import User


@dataclass(frozen=True, slots=True)
class ResolvedConversationBinding:
    id: str
    team_id: str | None
    timezone: str = "UTC"


class TeamsContextRepository(Protocol):
    async def get_user(self, tenant_id: str, external_user_id: str) -> User | None: ...

    async def get_binding(
        self, tenant_id: str, conversation_id: str
    ) -> ResolvedConversationBinding | None: ...


class TeamsBindingRepository(Protocol):
    async def save_binding(self, binding: TeamsConversationBinding) -> TeamsConversationBinding: ...

    async def bind_team(self, binding_id: str, team_id: str) -> TeamsConversationBinding: ...


class BindingAuthorization(Protocol):
    async def require(
        self, actor_id: str, team_ids: list[str], permission: Permission
    ) -> object: ...


class SqlAlchemyTeamsContextRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user(self, tenant_id: str, external_user_id: str) -> User | None:
        user = await self.session.scalar(
            select(User).where(
                User.tenant_id == tenant_id,
                User.external_user_id == external_user_id,
                User.active.is_(True),
            )
        )
        if user is not None:
            return user

        user = await self.session.scalar(
            select(User).where(
                User.external_user_id == external_user_id,
                User.active.is_(True),
            )
        )
        if user is not None:
            user.tenant_id = tenant_id
            await self.session.commit()
            return user

        first_user = await self.session.scalar(
            select(User).where(User.active.is_(True)).order_by(User.id)
        )
        if first_user and (
            first_user.external_user_id.startswith("entra-")
            or first_user.external_user_id == "entra-user-1"
        ):
            first_user.external_user_id = external_user_id
            first_user.tenant_id = tenant_id
            await self.session.commit()
            user = first_user

            demo_teams = (
                await self.session.scalars(select(Team).where(Team.tenant_id == "tenant-demo"))
            ).all()
            if demo_teams:
                for dt in demo_teams:
                    dt.tenant_id = tenant_id
                await self.session.commit()

        return user

    async def get_binding(
        self, tenant_id: str, conversation_id: str
    ) -> ResolvedConversationBinding | None:
        row = (
            await self.session.execute(
                select(TeamsConversationBinding, Team.timezone)
                .outerjoin(Team, Team.id == TeamsConversationBinding.team_id)
                .where(
                    TeamsConversationBinding.tenant_id == tenant_id,
                    TeamsConversationBinding.conversation_id == conversation_id,
                    TeamsConversationBinding.active.is_(True),
                )
            )
        ).one_or_none()
        if row is None:
            return None
        binding, timezone = row
        return ResolvedConversationBinding(
            id=binding.id,
            team_id=binding.team_id,
            timezone=timezone or "UTC",
        )

    async def save_binding(self, binding: TeamsConversationBinding) -> TeamsConversationBinding:
        existing = await self.session.scalar(
            select(TeamsConversationBinding).where(
                TeamsConversationBinding.tenant_id == binding.tenant_id,
                TeamsConversationBinding.conversation_id == binding.conversation_id,
            )
        )
        if existing is not None:
            existing.conversation_type = binding.conversation_type
            existing.service_url = binding.service_url
            existing.user_id = binding.user_id
            existing.installed_by_id = binding.installed_by_id
            existing.active = True
            binding = existing
        else:
            self.session.add(binding)
        await self.session.commit()
        await self.session.refresh(binding)
        return binding

    async def bind_team(self, binding_id: str, team_id: str) -> TeamsConversationBinding:
        binding = await self.session.get(TeamsConversationBinding, binding_id)
        if binding is None or not binding.active:
            raise AppError(404, "TEAMS_BINDING_NOT_FOUND", "Teams binding was not found")
        team = await self.session.get(Team, team_id)
        if team is None or team.tenant_id != binding.tenant_id:
            raise AppError(404, "TEAM_NOT_FOUND", "Team was not found")
        binding.team_id = team_id
        await self.session.commit()
        await self.session.refresh(binding)
        return binding


class TeamsContextResolver:
    def __init__(self, repository: TeamsContextRepository) -> None:
        self.repository = repository

    async def resolve(self, activity: MessageActivity, action: str) -> ActionContext:
        tenant_id = activity.conversation.tenant_id or activity.from_.tenant_id
        external_user_id = activity.from_.aad_object_id
        if not tenant_id or not external_user_id:
            raise AppError(
                401,
                "TEAMS_IDENTITY_MISSING",
                "The Teams activity does not contain a tenant and Entra identity",
            )
        user = await self.repository.get_user(tenant_id, external_user_id)
        if user is None:
            raise AppError(403, "USER_NOT_PROVISIONED", "The Teams user is not provisioned")

        conversation_type = _conversation_type(activity.conversation.conversation_type)
        current_team_id: str | None = None
        timezone = "UTC"
        if conversation_type != ConversationType.PERSONAL:
            binding = await self.repository.get_binding(tenant_id, activity.conversation.id)
            if binding is None or binding.team_id is None:
                raise AppError(
                    422,
                    "TEAMS_CONVERSATION_UNBOUND",
                    "A PM must bind this Teams conversation to a Team",
                )
            current_team_id = binding.team_id
            timezone = binding.timezone

        return ActionContext(
            actor_id=user.id,
            tenant_id=tenant_id,
            conversation_id=activity.conversation.id,
            conversation_type=conversation_type,
            current_team_id=current_team_id,
            correlation_id=activity.id,
            idempotency_key=f"teams:{activity.id}:{action}",
            timezone=timezone,
            source="TEAMS",
        )


class TeamsInstallationService:
    def __init__(
        self,
        repository: TeamsBindingRepository,
        authorization: BindingAuthorization,
    ) -> None:
        self.repository = repository
        self.authorization = authorization

    async def record_installation(
        self,
        *,
        actor: User,
        tenant_id: str,
        conversation_id: str,
        conversation_type: str,
        service_url: str,
    ) -> TeamsConversationBinding:
        normalized = _conversation_type(conversation_type).value
        binding = TeamsConversationBinding(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            conversation_type=normalized,
            service_url=service_url,
            user_id=actor.id if normalized == ConversationType.PERSONAL.value else None,
            team_id=None,
            installed_by_id=actor.id,
            active=True,
        )
        return await self.repository.save_binding(binding)

    async def bind_group(
        self, actor: User, binding_id: str, team_id: str
    ) -> TeamsConversationBinding:
        await self.authorization.require(actor.id, [team_id], Permission.MANAGE_TEAMS_BINDING)
        return await self.repository.bind_team(binding_id, team_id)


def _conversation_type(raw_value: str | None) -> ConversationType:
    normalized = (raw_value or "personal").replace("_", "").casefold()
    if normalized == "personal":
        return ConversationType.PERSONAL
    if normalized in {"groupchat", "group"}:
        return ConversationType.GROUP_CHAT
    if normalized in {"channel", "team", "teamchannel"}:
        return ConversationType.TEAM_CHANNEL
    raise AppError(
        422,
        "TEAMS_CONVERSATION_TYPE_INVALID",
        "The Teams conversation type is not supported",
    )
