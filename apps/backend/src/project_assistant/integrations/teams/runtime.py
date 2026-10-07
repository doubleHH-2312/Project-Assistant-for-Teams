from collections.abc import Mapping
from typing import Any

from microsoft_teams.api import InstalledActivity  # type: ignore[attr-defined]
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from project_assistant.core.config import Settings
from project_assistant.integrations.llm.factory import build_llm_provider
from project_assistant.modules.actions.contracts import ActionContext, ActionResult
from project_assistant.modules.actions.dispatcher import ActionDispatcher
from project_assistant.modules.actions.factory import build_reporting_action_registry
from project_assistant.modules.actions.parser import ParsedCommand
from project_assistant.modules.actions.results import SqlAlchemyActionResultStore
from project_assistant.modules.audit.repository import SqlAlchemyAuditRepository
from project_assistant.modules.audit.service import AuditService
from project_assistant.modules.daily_reports.repository import (
    SqlAlchemyDailyReportRepository,
)
from project_assistant.modules.daily_reports.service import DailyReportService
from project_assistant.modules.memberships.repository import (
    SqlAlchemyMembershipRepository,
)
from project_assistant.modules.memberships.service import AuthorizationService
from project_assistant.modules.teams.overview import TeamOverviewService
from project_assistant.modules.teams.repository import SqlAlchemyOverviewRepository
from project_assistant.modules.users.models import User
from project_assistant.modules.weekly_reports.repository import (
    SqlAlchemyWeeklyReportRepository,
)
from project_assistant.modules.weekly_reports.service import WeeklyReportService

from .context import (
    SqlAlchemyTeamsContextRepository,
    TeamsContextResolver,
    TeamsInstallationService,
)


class SessionScopedTeamsContextResolver:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def resolve(self, activity: Any, action: str) -> ActionContext:
        async with self.session_factory() as session:
            return await TeamsContextResolver(SqlAlchemyTeamsContextRepository(session)).resolve(
                activity, action
            )


class SessionScopedActionDispatcher:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self.session_factory = session_factory
        self.settings = settings

    async def dispatch(
        self,
        command: ParsedCommand,
        context: ActionContext,
        payload: Mapping[str, Any],
    ) -> ActionResult:
        async with self.session_factory() as session:
            authorization = AuthorizationService(SqlAlchemyMembershipRepository(session))
            audit_service = AuditService(SqlAlchemyAuditRepository(session))
            daily_service = DailyReportService(
                SqlAlchemyDailyReportRepository(session),
                authorization,
                audit_service,
            )
            overview_service = TeamOverviewService(SqlAlchemyOverviewRepository(session))
            weekly_service = WeeklyReportService(
                SqlAlchemyWeeklyReportRepository(session),
                build_llm_provider(self.settings),
                authorization,
            )
            registry = build_reporting_action_registry(
                daily_service,
                daily_service,
                overview_service,
                weekly_service,
                authorization,
            )
            dispatcher = ActionDispatcher(
                registry,
                authorization,
                audit_service,
                SqlAlchemyActionResultStore(session),
            )
            return await dispatcher.dispatch(command, context, payload)


class SessionScopedInstallationRecorder:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def record(self, activity: InstalledActivity) -> None:
        tenant_id = activity.conversation.tenant_id or activity.from_.tenant_id
        external_user_id = activity.from_.aad_object_id
        if not tenant_id or not external_user_id:
            return
        async with self.session_factory() as session:
            repository = SqlAlchemyTeamsContextRepository(session)
            actor: User | None = await repository.get_user(tenant_id, external_user_id)
            if actor is None:
                return
            authorization = AuthorizationService(SqlAlchemyMembershipRepository(session))
            service = TeamsInstallationService(repository, authorization)
            await service.record_installation(
                actor=actor,
                tenant_id=tenant_id,
                conversation_id=activity.conversation.id,
                conversation_type=activity.conversation.conversation_type or "personal",
                service_url=activity.service_url or "",
            )
