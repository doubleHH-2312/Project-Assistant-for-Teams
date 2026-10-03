import uuid
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from jsonschema import ValidationError, validate

from project_assistant.core.errors import AppError
from project_assistant.integrations.llm.provider import LLMProvider, LLMProviderError
from project_assistant.modules.audit.models import WorkItemStatusEvent
from project_assistant.modules.daily_reports.models import DailyReport
from project_assistant.modules.memberships.service import AuthorizationService, Permission
from project_assistant.modules.templates.models import ReportTemplate
from project_assistant.modules.weekly_reports.evidence import (
    EvidenceBundle,
    EvidenceReference,
    build_member_evidence,
    build_multiteam_evidence,
    build_team_evidence,
    collect_scope_ids,
    validate_evidence_references,
)
from project_assistant.modules.weekly_reports.models import (
    ReportScope,
    WeeklyReport,
    WeeklyReportStatus,
)
from project_assistant.modules.weekly_reports.schemas import (
    WeeklyGenerateRequest,
    WeeklyUpdateRequest,
)


class WeeklyReportRepository(Protocol):
    async def get_active_template(
        self, team_id: str, scope: ReportScope
    ) -> ReportTemplate | None: ...

    async def get_active_tenant_template(
        self, tenant_id: str, scope: ReportScope
    ) -> ReportTemplate | None: ...

    async def list_team_ids_in_tenant(
        self, team_ids: list[str], tenant_id: str
    ) -> list[str]: ...

    async def get_template(
        self, template_id: str, team_id: str | None
    ) -> ReportTemplate | None: ...

    async def list_daily_reports(
        self, user_id: str, team_id: str, week_start: date, week_end: date
    ) -> list[DailyReport]: ...

    async def list_status_events(
        self, daily_report_ids: list[str]
    ) -> list[WorkItemStatusEvent]: ...

    async def list_confirmed_member_reports(
        self, team_id: str, week_start: date, week_end: date
    ) -> list[WeeklyReport]: ...

    async def list_confirmed_team_reports(
        self, team_ids: list[str], week_start: date, week_end: date
    ) -> list[WeeklyReport]: ...

    async def list_expected_member_ids(self, team_id: str) -> list[str]: ...

    async def find_report(
        self,
        scope: ReportScope,
        team_id: str,
        subject_user_id: str | None,
        week_start: date,
    ) -> WeeklyReport | None: ...

    async def find_multiteam_report(
        self, tenant_id: str, team_ids: list[str], week_start: date
    ) -> WeeklyReport | None: ...

    async def save_generated(
        self,
        report: WeeklyReport,
        team_ids: list[str],
        references: tuple[EvidenceReference, ...],
    ) -> WeeklyReport: ...

    async def save(self, report: WeeklyReport) -> WeeklyReport: ...

    async def save_revision(
        self, report: WeeklyReport, team_ids: list[str], supersedes_id: str
    ) -> WeeklyReport: ...

    async def get_by_id(
        self, report_id: str, team_id: str | None
    ) -> WeeklyReport | None: ...

    async def list_report_team_ids(self, report_id: str) -> list[str]: ...


class WeeklyActor(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def tenant_id(self) -> str: ...


class WeeklyReportService:
    def __init__(
        self,
        repository: WeeklyReportRepository,
        provider: LLMProvider,
        authorization: AuthorizationService,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.authorization = authorization

    async def generate(
        self, actor: WeeklyActor, request: WeeklyGenerateRequest
    ) -> WeeklyReport:
        if request.week_start.weekday() != 0:
            raise AppError(422, "WEEK_START_INVALID", "Week start must be a Monday")
        if request.scope == ReportScope.MULTI_TEAM:
            return await self._generate_multiteam(actor, request)
        assert request.team_id is not None
        return await self._generate_for_team(actor, request)

    async def _generate_for_team(
        self, actor: WeeklyActor, request: WeeklyGenerateRequest
    ) -> WeeklyReport:
        assert request.team_id is not None
        visible_team_ids = await self.repository.list_team_ids_in_tenant(
            [request.team_id], actor.tenant_id
        )
        if visible_team_ids != [request.team_id]:
            raise AppError(404, "TEAM_NOT_FOUND", "Team was not found")
        week_end = request.week_start + timedelta(days=4)
        subject_user_id: str | None
        if request.scope == ReportScope.MEMBER:
            await self.authorization.require(
                actor.id, [request.team_id], Permission.GENERATE_OWN_WEEKLY
            )
            subject_user_id = request.subject_user_id or actor.id
            if subject_user_id != actor.id:
                raise AppError(403, "FORBIDDEN", "Members can generate only their own report")
        else:
            await self.authorization.require(
                actor.id, [request.team_id], Permission.GENERATE_TEAM_WEEKLY
            )
            subject_user_id = None
        existing = await self.repository.find_report(
            request.scope, request.team_id, subject_user_id, request.week_start
        )
        if existing is not None:
            return self._existing_or_revision_required(existing)
        template = await self.repository.get_active_template(
            request.team_id, request.scope
        )
        if template is None:
            raise AppError(422, "TEMPLATE_NOT_FOUND", "No active template exists for this scope")
        missing: list[str] = []
        if request.scope == ReportScope.MEMBER:
            assert subject_user_id is not None
            daily_reports = await self.repository.list_daily_reports(
                subject_user_id, request.team_id, request.week_start, week_end
            )
            events = await self.repository.list_status_events(
                [report.id for report in daily_reports]
            )
            bundle = build_member_evidence(daily_reports, events)
        else:
            member_reports = await self.repository.list_confirmed_member_reports(
                request.team_id, request.week_start, week_end
            )
            bundle = build_team_evidence(member_reports)
            confirmed_ids = {report.subject_user_id for report in member_reports}
            expected_ids = await self.repository.list_expected_member_ids(request.team_id)
            missing = sorted(
                user_id for user_id in expected_ids if user_id not in confirmed_ids
            )
        return await self._generate_and_save(
            actor=actor,
            scope=request.scope,
            subject_user_id=subject_user_id,
            team_id=request.team_id,
            team_ids=[request.team_id],
            week_start=request.week_start,
            week_end=week_end,
            template=template,
            bundle=bundle,
            missing=missing,
        )

    async def _generate_multiteam(
        self, actor: WeeklyActor, request: WeeklyGenerateRequest
    ) -> WeeklyReport:
        team_ids = sorted(set(request.team_ids))
        visible_team_ids = await self.repository.list_team_ids_in_tenant(
            team_ids, actor.tenant_id
        )
        if visible_team_ids != team_ids:
            raise AppError(404, "TEAM_NOT_FOUND", "Team was not found")
        await self.authorization.require(
            actor.id, team_ids, Permission.GENERATE_MULTI_TEAM_WEEKLY
        )
        existing = await self.repository.find_multiteam_report(
            actor.tenant_id, team_ids, request.week_start
        )
        if existing is not None:
            return self._existing_or_revision_required(existing)
        template = await self.repository.get_active_tenant_template(
            actor.tenant_id, ReportScope.MULTI_TEAM
        )
        if template is None:
            raise AppError(422, "TEMPLATE_NOT_FOUND", "No active multi-team template exists")
        week_end = request.week_start + timedelta(days=4)
        team_reports = await self.repository.list_confirmed_team_reports(
            team_ids, request.week_start, week_end
        )
        bundle = build_multiteam_evidence(team_reports)
        contributed = {report.team_id for report in team_reports}
        missing = sorted(team_id for team_id in team_ids if team_id not in contributed)
        return await self._generate_and_save(
            actor=actor,
            scope=ReportScope.MULTI_TEAM,
            subject_user_id=None,
            team_id=None,
            team_ids=team_ids,
            week_start=request.week_start,
            week_end=week_end,
            template=template,
            bundle=bundle,
            missing=missing,
        )

    async def _generate_and_save(
        self,
        *,
        actor: WeeklyActor,
        scope: ReportScope,
        subject_user_id: str | None,
        team_id: str | None,
        team_ids: list[str],
        week_start: date,
        week_end: date,
        template: ReportTemplate,
        bundle: EvidenceBundle,
        missing: list[str],
    ) -> WeeklyReport:
        try:
            result = await self.provider.generate(template.schema_json, bundle.payload)
        except LLMProviderError as error:
            status_code = 503 if error.code == "LLM_UNAVAILABLE" else 502
            raise AppError(
                status_code,
                error.code,
                "Report generation is temporarily unavailable",
            ) from error
        self._validate_generated(
            result.content,
            template.schema_json,
            {reference.source_id for reference in bundle.references},
            scope_ids=collect_scope_ids(bundle.payload),
        )
        report = WeeklyReport(
            id=str(uuid.uuid4()),
            scope=scope,
            subject_user_id=subject_user_id,
            team_id=team_id,
            week_start=week_start,
            week_end=week_end,
            content_json=result.content,
            missing_contributors=missing,
            input_record_ids=[reference.source_id for reference in bundle.references],
            generation_source=result.provider.upper(),
            generation_metadata={
                **result.metadata,
                "evidenceCount": len(bundle.references),
            },
            status=WeeklyReportStatus.GENERATED,
            template_id=template.id,
            template_version=template.version,
            created_by=actor.id,
        )
        return await self.repository.save_generated(report, team_ids, bundle.references)

    async def confirm(self, actor: WeeklyActor, report: WeeklyReport) -> WeeklyReport:
        await self._authorize_editor(actor, report)
        if report.status == WeeklyReportStatus.CONFIRMED:
            return report
        report.status = WeeklyReportStatus.CONFIRMED
        report.confirmed_by = actor.id
        report.confirmed_at = datetime.now(UTC)
        return await self.repository.save(report)

    async def get(
        self, actor: WeeklyActor, team_id: str | None, report_id: str
    ) -> WeeklyReport:
        return await self._get_authorized(actor, team_id, report_id)

    async def confirm_by_id(
        self, actor: WeeklyActor, team_id: str | None, report_id: str
    ) -> WeeklyReport:
        return await self.confirm(actor, await self._get_authorized(actor, team_id, report_id))

    async def update(
        self,
        actor: WeeklyActor,
        team_id: str | None,
        report_id: str,
        request: WeeklyUpdateRequest,
    ) -> WeeklyReport:
        report = await self._get_authorized(actor, team_id, report_id)
        if report.status == WeeklyReportStatus.CONFIRMED:
            raise AppError(
                409, "WEEKLY_REPORT_IMMUTABLE", "Confirmed reports cannot be edited"
            )
        template = await self.repository.get_template(report.template_id, report.team_id)
        if template is None:
            raise AppError(422, "TEMPLATE_NOT_FOUND", "The report template was not found")
        self._validate_generated(
            request.content_json,
            template.schema_json,
            set(report.input_record_ids),
            status_code=422,
            code="REPORT_CONTENT_INVALID",
        )
        report.content_json = request.content_json
        report.status = WeeklyReportStatus.EDITED
        return await self.repository.save(report)

    async def create_revision(
        self, actor: WeeklyActor, team_id: str | None, report_id: str
    ) -> WeeklyReport:
        report = await self._get_authorized(actor, team_id, report_id)
        if report.status != WeeklyReportStatus.CONFIRMED:
            raise AppError(409, "REVISION_NOT_REQUIRED", "Only confirmed reports need revisions")
        team_ids = await self._team_ids(report)
        revision = WeeklyReport(
            id=str(uuid.uuid4()),
            scope=report.scope,
            subject_user_id=report.subject_user_id,
            team_id=report.team_id,
            week_start=report.week_start,
            week_end=report.week_end,
            content_json=deepcopy(report.content_json),
            missing_contributors=list(report.missing_contributors),
            input_record_ids=list(report.input_record_ids),
            generation_source="MANUAL_REVISION",
            generation_metadata={"supersedes": report.id},
            status=WeeklyReportStatus.DRAFT,
            template_id=report.template_id,
            template_version=report.template_version,
            created_by=actor.id,
            supersedes_id=report.id,
        )
        return await self.repository.save_revision(revision, team_ids, report.id)

    async def _get_authorized(
        self, actor: WeeklyActor, team_id: str | None, report_id: str
    ) -> WeeklyReport:
        report = await self.repository.get_by_id(report_id, team_id)
        if report is None:
            raise AppError(404, "WEEKLY_REPORT_NOT_FOUND", "Weekly report was not found")
        await self._authorize_editor(actor, report)
        return report

    async def _authorize_editor(
        self, actor: WeeklyActor, report: WeeklyReport
    ) -> None:
        if report.scope == ReportScope.MEMBER and report.subject_user_id != actor.id:
            raise AppError(403, "FORBIDDEN", "Only the subject member can edit this report")
        if report.scope == ReportScope.MULTI_TEAM:
            await self.authorization.require(
                actor.id,
                await self._team_ids(report),
                Permission.GENERATE_MULTI_TEAM_WEEKLY,
            )
            return
        assert report.team_id is not None
        permission = (
            Permission.GENERATE_OWN_WEEKLY
            if report.scope == ReportScope.MEMBER
            else Permission.GENERATE_TEAM_WEEKLY
        )
        await self.authorization.require(actor.id, [report.team_id], permission)

    async def _team_ids(self, report: WeeklyReport) -> list[str]:
        if report.team_id is not None:
            return [report.team_id]
        team_ids = await self.repository.list_report_team_ids(report.id)
        if not team_ids:
            raise AppError(409, "WEEKLY_REPORT_SCOPE_INVALID", "Report has no Team scope")
        return team_ids

    @staticmethod
    def _existing_or_revision_required(existing: WeeklyReport) -> WeeklyReport:
        if existing.status == WeeklyReportStatus.CONFIRMED:
            raise AppError(
                409,
                "WEEKLY_REPORT_CONFIRMED",
                "Confirmed reports require a revision",
            )
        return existing

    @staticmethod
    def _validate_generated(
        content: dict[str, Any],
        schema: dict[str, Any],
        allowed_source_ids: set[str],
        *,
        scope_ids: tuple[set[str], set[str]] | None = None,
        status_code: int = 502,
        code: str = "LLM_OUTPUT_INVALID",
    ) -> None:
        try:
            validate(instance=content, schema=schema)
            team_ids, project_ids = scope_ids or (None, None)
            validate_evidence_references(
                content,
                allowed_source_ids,
                allowed_team_ids=team_ids,
                allowed_project_ids=project_ids,
            )
        except (ValidationError, ValueError) as error:
            path = (
                [str(part) for part in error.path]
                if isinstance(error, ValidationError)
                else []
            )
            raise AppError(
                status_code,
                code,
                "The report content did not match its evidence and template",
                {"path": path},
            ) from error
