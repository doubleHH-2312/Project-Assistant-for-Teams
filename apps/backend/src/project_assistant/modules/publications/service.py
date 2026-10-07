import uuid
from collections.abc import Collection
from typing import Protocol

from project_assistant.core.errors import AppError
from project_assistant.modules.memberships.models import TeamMembership
from project_assistant.modules.memberships.service import Permission
from project_assistant.modules.publications.models import ReportPublication
from project_assistant.modules.users.models import User
from project_assistant.modules.weekly_reports.models import (
    ReportScope,
    WeeklyReport,
    WeeklyReportStatus,
)


class PublicationRepository(Protocol):
    async def find_by_idempotency_key(self, key: str) -> ReportPublication | None: ...

    async def get_report(self, report_id: str) -> WeeklyReport | None: ...

    async def list_report_team_ids(self, report_id: str) -> list[str]: ...

    async def save(self, publication: ReportPublication) -> ReportPublication: ...


class AuthorizationPolicy(Protocol):
    async def require(
        self,
        actor_id: str,
        team_ids: Collection[str],
        permission: Permission,
    ) -> dict[str, TeamMembership]: ...


class PublicationService:
    def __init__(
        self,
        repository: PublicationRepository,
        authorization: AuthorizationPolicy,
    ) -> None:
        self.repository = repository
        self.authorization = authorization

    async def publish(
        self,
        actor: User,
        report_id: str,
        conversation_id: str,
        idempotency_key: str,
    ) -> ReportPublication:
        existing = await self.repository.find_by_idempotency_key(idempotency_key)
        if existing is not None:
            if existing.actor_id != actor.id:
                raise AppError(404, "PUBLICATION_NOT_FOUND", "Publication was not found")
            self._require_same_request(existing, report_id, conversation_id)
            return existing
        report = await self.repository.get_report(report_id)
        if report is None:
            raise AppError(404, "WEEKLY_REPORT_NOT_FOUND", "Weekly report was not found")
        if report.status != WeeklyReportStatus.CONFIRMED:
            raise AppError(
                409,
                "WEEKLY_REPORT_NOT_CONFIRMED",
                "Only confirmed reports can be published",
            )
        permission, team_ids = await self._permission_and_teams(actor, report)
        await self.authorization.require(actor.id, team_ids, permission)
        publication = await self.repository.save(
            ReportPublication(
                id=str(uuid.uuid4()),
                weekly_report_id=report.id,
                actor_id=actor.id,
                conversation_id=conversation_id,
                idempotency_key=idempotency_key,
            )
        )
        if publication.actor_id != actor.id:
            raise AppError(404, "PUBLICATION_NOT_FOUND", "Publication was not found")
        self._require_same_request(publication, report_id, conversation_id)
        return publication

    async def _permission_and_teams(
        self, actor: User, report: WeeklyReport
    ) -> tuple[Permission, list[str]]:
        if report.scope == ReportScope.MEMBER:
            if report.subject_user_id != actor.id:
                raise AppError(403, "FORBIDDEN", "Only the subject can publish this report")
            permission = Permission.GENERATE_OWN_WEEKLY
        elif report.scope == ReportScope.TEAM:
            permission = Permission.GENERATE_TEAM_WEEKLY
        else:
            permission = Permission.GENERATE_MULTI_TEAM_WEEKLY
        team_ids = (
            [report.team_id]
            if report.team_id is not None
            else await self.repository.list_report_team_ids(report.id)
        )
        if not team_ids:
            raise AppError(409, "WEEKLY_REPORT_SCOPE_INVALID", "Report has no Team scope")
        return permission, team_ids

    @staticmethod
    def _require_same_request(
        publication: ReportPublication,
        report_id: str,
        conversation_id: str,
    ) -> None:
        if (
            publication.weekly_report_id != report_id
            or publication.conversation_id != conversation_id
        ):
            raise AppError(
                409,
                "IDEMPOTENCY_KEY_REUSED",
                "The idempotency key belongs to another publication request",
            )
