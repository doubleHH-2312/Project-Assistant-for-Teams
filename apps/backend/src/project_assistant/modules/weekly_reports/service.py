from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from jsonschema import ValidationError, validate

from project_assistant.core.errors import AppError
from project_assistant.integrations.llm.provider import LLMProvider
from project_assistant.modules.daily_reports.models import DailyReport
from project_assistant.modules.templates.models import ReportTemplate
from project_assistant.modules.users.models import User, UserRole
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

    async def get_template(self, template_id: str) -> ReportTemplate | None: ...

    async def list_daily_reports(
        self, user_id: str, week_start: date, week_end: date
    ) -> list[DailyReport]: ...

    async def list_confirmed_member_reports(
        self, team_id: str, week_start: date, week_end: date
    ) -> list[WeeklyReport]: ...

    async def list_expected_member_ids(self, team_id: str) -> list[str]: ...

    async def find_report(
        self, scope: ReportScope, team_id: str, subject_user_id: str | None, week_start: date
    ) -> WeeklyReport | None: ...

    async def save(self, report: WeeklyReport) -> WeeklyReport: ...

    async def get_by_id(self, report_id: str) -> WeeklyReport | None: ...


class WeeklyReportService:
    def __init__(self, repository: WeeklyReportRepository, provider: LLMProvider) -> None:
        self.repository = repository
        self.provider = provider

    async def generate(self, actor: User, request: WeeklyGenerateRequest) -> WeeklyReport:
        if request.week_start.weekday() != 0:
            raise AppError(422, "WEEK_START_INVALID", "Week start must be a Monday")
        week_end = request.week_start + timedelta(days=4)
        subject_user_id: str | None
        if request.scope == ReportScope.MEMBER:
            subject_user_id = request.subject_user_id or actor.id
            if subject_user_id != actor.id and actor.role != UserRole.LEAD:
                raise AppError(403, "FORBIDDEN", "Members can generate only their own report")
        else:
            if actor.role != UserRole.LEAD:
                raise AppError(403, "FORBIDDEN", "Only a Lead can generate a team report")
            subject_user_id = None
        existing = await self.repository.find_report(
            request.scope, actor.team_id, subject_user_id, request.week_start
        )
        if existing is not None:
            if existing.status == WeeklyReportStatus.CONFIRMED:
                raise AppError(
                    409,
                    "WEEKLY_REPORT_CONFIRMED",
                    "Confirmed reports require a revision",
                )
            return existing
        template = await self.repository.get_active_template(actor.team_id, request.scope)
        if template is None:
            raise AppError(422, "TEMPLATE_NOT_FOUND", "No active template exists for this scope")
        evidence: list[dict[str, Any]]
        input_ids: list[str]
        missing: list[str] = []
        if request.scope == ReportScope.MEMBER:
            assert subject_user_id is not None
            daily_reports = await self.repository.list_daily_reports(
                subject_user_id, request.week_start, week_end
            )
            evidence = [self._daily_evidence(report) for report in daily_reports]
            input_ids = [report.id for report in daily_reports]
        else:
            member_reports = await self.repository.list_confirmed_member_reports(
                actor.team_id, request.week_start, week_end
            )
            evidence = [
                {
                    "id": report.id,
                    "subjectUserId": report.subject_user_id,
                    "content": report.content_json,
                }
                for report in member_reports
            ]
            input_ids = [report.id for report in member_reports]
            confirmed_ids = {report.subject_user_id for report in member_reports}
            expected_ids = await self.repository.list_expected_member_ids(actor.team_id)
            missing = sorted(user_id for user_id in expected_ids if user_id not in confirmed_ids)
        result = await self.provider.generate(template.schema_json, evidence)
        try:
            validate(instance=result.content, schema=template.schema_json)
        except ValidationError as error:
            raise AppError(
                502,
                "LLM_OUTPUT_INVALID",
                "The generated report did not match the active template",
                {"path": [str(part) for part in error.path]},
            ) from error
        report = WeeklyReport(
            scope=request.scope,
            subject_user_id=subject_user_id,
            team_id=actor.team_id,
            week_start=request.week_start,
            week_end=week_end,
            content_json=result.content,
            missing_contributors=missing,
            input_record_ids=input_ids,
            generation_source=result.provider.upper(),
            generation_metadata={**result.metadata, "evidenceCount": len(evidence)},
            status=WeeklyReportStatus.GENERATED,
            template_id=template.id,
            template_version=template.version,
            created_by=actor.id,
        )
        return await self.repository.save(report)

    async def confirm(self, actor: User, report: WeeklyReport) -> WeeklyReport:
        self._authorize_editor(actor, report)
        if report.status == WeeklyReportStatus.CONFIRMED:
            return report
        report.status = WeeklyReportStatus.CONFIRMED
        report.confirmed_by = actor.id
        report.confirmed_at = datetime.now(UTC)
        return await self.repository.save(report)

    async def get(self, actor: User, report_id: str) -> WeeklyReport:
        return await self._get_authorized(actor, report_id)

    async def confirm_by_id(self, actor: User, report_id: str) -> WeeklyReport:
        return await self.confirm(actor, await self._get_authorized(actor, report_id))

    async def update(
        self, actor: User, report_id: str, request: WeeklyUpdateRequest
    ) -> WeeklyReport:
        report = await self._get_authorized(actor, report_id)
        if report.status == WeeklyReportStatus.CONFIRMED:
            raise AppError(
                409, "WEEKLY_REPORT_IMMUTABLE", "Confirmed reports cannot be edited"
            )
        template = await self.repository.get_template(report.template_id)
        if template is None:
            raise AppError(422, "TEMPLATE_NOT_FOUND", "The report template was not found")
        try:
            validate(instance=request.content_json, schema=template.schema_json)
        except ValidationError as error:
            raise AppError(
                422,
                "REPORT_CONTENT_INVALID",
                "The edited report does not match its template",
                {"path": [str(part) for part in error.path]},
            ) from error
        report.content_json = request.content_json
        report.status = WeeklyReportStatus.EDITED
        return await self.repository.save(report)

    async def create_revision(self, actor: User, report_id: str) -> WeeklyReport:
        report = await self._get_authorized(actor, report_id)
        if report.status != WeeklyReportStatus.CONFIRMED:
            raise AppError(409, "REVISION_NOT_REQUIRED", "Only confirmed reports need revisions")
        revision = WeeklyReport(
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
        return await self.repository.save(revision)

    async def _get_authorized(self, actor: User, report_id: str) -> WeeklyReport:
        report = await self.repository.get_by_id(report_id)
        if report is None or report.team_id != actor.team_id:
            raise AppError(404, "WEEKLY_REPORT_NOT_FOUND", "Weekly report was not found")
        self._authorize_editor(actor, report)
        return report

    @staticmethod
    def _authorize_editor(actor: User, report: WeeklyReport) -> None:
        if report.scope == ReportScope.MEMBER and report.subject_user_id != actor.id:
            raise AppError(403, "FORBIDDEN", "Only the subject member can edit this report")
        if report.scope == ReportScope.TEAM and actor.role != UserRole.LEAD:
            raise AppError(403, "FORBIDDEN", "Only a Lead can edit a team report")

    @staticmethod
    def _daily_evidence(report: DailyReport) -> dict[str, Any]:
        return {
            "id": report.id,
            "workItemId": report.work_item_id,
            "reportDate": report.report_date.isoformat(),
            "status": report.status.value,
            "workSummary": report.work_summary,
            "effectiveBlocker": report.effective_blocker,
            "nextAction": report.next_action,
        }
