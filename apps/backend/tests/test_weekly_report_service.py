from datetime import date

import pytest

from project_assistant.core.errors import AppError
from project_assistant.integrations.llm.provider import (
    LLMProviderError,
    LLMResult,
    MockLLMProvider,
)
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.templates.models import ReportTemplate
from project_assistant.modules.users.models import User
from project_assistant.modules.weekly_reports.models import (
    ReportScope,
    WeeklyReport,
    WeeklyReportStatus,
)
from project_assistant.modules.weekly_reports.schemas import (
    WeeklyGenerateRequest,
    WeeklyUpdateRequest,
)
from project_assistant.modules.weekly_reports.service import WeeklyReportService

SCHEMA = {
    "type": "object",
    "required": ["completed", "in_progress", "blockers", "next_week", "support_required"],
    "properties": {
        key: {"type": "array", "items": {"type": "string"}}
        for key in ["completed", "in_progress", "blockers", "next_week", "support_required"]
    },
    "additionalProperties": False,
}


class FakeWeeklyRepository:
    def __init__(self) -> None:
        self.templates = {
            scope: ReportTemplate(
                id=f"template-{scope.value.lower()}",
                team_id="team-1",
                name=f"default-{scope.value.lower()}",
                scope=scope,
                version=1,
                schema_json=SCHEMA,
                active=True,
            )
            for scope in ReportScope
        }
        self.daily_reports: list[DailyReport] = []
        self.member_reports: list[WeeklyReport] = []
        self.expected_members = ["user-1", "user-2"]
        self.saved: list[WeeklyReport] = []
        self.saved_references = []
        self.tenant_team_ids = {"team-1"}

    async def get_active_tenant_template(self, tenant_id, scope):  # type: ignore[no-untyped-def]
        return None

    async def list_team_ids_in_tenant(self, team_ids, tenant_id):  # type: ignore[no-untyped-def]
        return sorted(team_id for team_id in team_ids if team_id in self.tenant_team_ids)

    async def get_active_template(
        self, team_id: str, scope: ReportScope
    ) -> ReportTemplate | None:
        return self.templates.get(scope)

    async def get_template(self, template_id: str, team_id: str) -> ReportTemplate | None:
        return next(
            (
                template
                for template in self.templates.values()
                if template.id == template_id and template.team_id == team_id
            ),
            None,
        )

    async def list_daily_reports(
        self, user_id: str, team_id: str, week_start: date, week_end: date
    ) -> list[DailyReport]:
        del team_id
        return [
            report
            for report in self.daily_reports
            if report.user_id == user_id and week_start <= report.report_date <= week_end
        ]

    async def list_status_events(self, daily_report_ids):  # type: ignore[no-untyped-def]
        return []

    async def list_confirmed_member_reports(
        self, team_id: str, week_start: date, week_end: date
    ) -> list[WeeklyReport]:
        return [
            report
            for report in self.member_reports
            if report.status == WeeklyReportStatus.CONFIRMED
            and report.week_start == week_start
            and report.week_end == week_end
        ]

    async def list_expected_member_ids(self, team_id: str) -> list[str]:
        return self.expected_members

    async def list_confirmed_team_reports(self, team_ids, week_start, week_end):  # type: ignore[no-untyped-def]
        return []

    async def find_multiteam_report(self, tenant_id, team_ids, week_start):  # type: ignore[no-untyped-def]
        return None

    async def find_report(
        self, scope: ReportScope, team_id: str, subject_user_id: str | None, week_start: date
    ) -> WeeklyReport | None:
        return next(
            (
                report
                for report in self.saved
                if report.scope == scope
                and report.team_id == team_id
                and report.subject_user_id == subject_user_id
                and report.week_start == week_start
            ),
            None,
        )

    async def save(self, report: WeeklyReport) -> WeeklyReport:
        if report.id is None:
            report.id = f"weekly-{len(self.saved) + 1}"
        if report not in self.saved:
            self.saved.append(report)
        return report

    async def save_generated(self, report, team_ids, references):  # type: ignore[no-untyped-def]
        self.saved_references = list(references)
        return await self.save(report)

    async def save_revision(self, report, team_ids, supersedes_id):  # type: ignore[no-untyped-def]
        return await self.save(report)

    async def get_by_id(self, report_id: str, team_id: str) -> WeeklyReport | None:
        return next(
            (
                report
                for report in self.saved
                if report.id == report_id and report.team_id == team_id
            ),
            None,
        )

    async def list_report_team_ids(self, report_id: str) -> list[str]:
        report = next(item for item in self.saved if item.id == report_id)
        return [report.team_id] if report.team_id else []


class AllowAuthorization:
    async def require(self, actor_id, team_ids, permission):  # type: ignore[no-untyped-def]
        del actor_id, team_ids, permission
        return {}


def user(user_id: str = "user-1") -> User:
    return User(
        id=user_id,
        external_user_id=f"entra-{user_id}",
        name="User",
        email=f"{user_id}@example.test",
    )


@pytest.mark.asyncio
async def test_member_generation_uses_daily_evidence_and_preserves_ids() -> None:
    repository = FakeWeeklyRepository()
    repository.daily_reports.append(
        DailyReport(
            id="daily-1",
            team_id="team-1",
            user_id="user-1",
            project_id="project-1",
            work_item_id="OPS-001",
            report_date=date(2026, 9, 28),
            status=WorkStatus.DONE,
            work_summary="Implemented validation",
            next_action="Start integration",
        )
    )
    service = WeeklyReportService(
        repository, MockLLMProvider(), AllowAuthorization()  # type: ignore[arg-type]
    )

    report = await service.generate(
        user(),
        WeeklyGenerateRequest(
            teamId="team-1", scope=ReportScope.MEMBER, weekStart=date(2026, 9, 28)
        ),
    )

    assert report.input_record_ids == ["daily-1"]
    assert report.content_json["completed"] == ["OPS-001: Implemented validation"]
    assert report.status == WeeklyReportStatus.GENERATED


@pytest.mark.asyncio
async def test_team_generation_uses_only_confirmed_member_reports_and_lists_missing() -> None:
    repository = FakeWeeklyRepository()
    repository.member_reports.extend(
        [
            WeeklyReport(
                id="member-confirmed",
                scope=ReportScope.MEMBER,
                subject_user_id="user-1",
                team_id="team-1",
                week_start=date(2026, 9, 28),
                week_end=date(2026, 10, 2),
                content_json={"completed": ["OPS-001"]},
                missing_contributors=[],
                input_record_ids=["daily-1"],
                generation_source="MOCK_LLM",
                generation_metadata={},
                status=WeeklyReportStatus.CONFIRMED,
                template_id="template-member",
                template_version=1,
                created_by="user-1",
                confirmed_by="user-1",
            ),
            WeeklyReport(
                id="member-unconfirmed",
                scope=ReportScope.MEMBER,
                subject_user_id="user-2",
                team_id="team-1",
                week_start=date(2026, 9, 28),
                week_end=date(2026, 10, 2),
                content_json={"completed": ["MUST NOT APPEAR"]},
                missing_contributors=[],
                input_record_ids=["daily-2"],
                generation_source="MOCK_LLM",
                generation_metadata={},
                status=WeeklyReportStatus.GENERATED,
                template_id="template-member",
                template_version=1,
                created_by="user-2",
            ),
        ]
    )
    service = WeeklyReportService(
        repository, MockLLMProvider(), AllowAuthorization()  # type: ignore[arg-type]
    )

    report = await service.generate(
        user("user-lead"),
        WeeklyGenerateRequest(
            teamId="team-1", scope=ReportScope.TEAM, weekStart=date(2026, 9, 28)
        ),
    )

    assert report.input_record_ids == ["member-confirmed"]
    assert report.missing_contributors == ["user-2"]
    assert "MUST NOT APPEAR" not in str(report.content_json)


class InvalidProvider:
    async def generate(self, template: dict, evidence: list[dict]) -> LLMResult:
        return LLMResult(content={"invented": ["not allowed"]}, provider="invalid", metadata={})


class UnavailableProvider:
    async def generate(self, template: dict, evidence: list[dict]) -> LLMResult:
        del template, evidence
        raise LLMProviderError("LLM_UNAVAILABLE", "sensitive upstream detail")


@pytest.mark.asyncio
async def test_invalid_llm_output_is_rejected_without_persistence() -> None:
    repository = FakeWeeklyRepository()
    service = WeeklyReportService(
        repository, InvalidProvider(), AllowAuthorization()  # type: ignore[arg-type]
    )

    with pytest.raises(AppError) as invalid:
        await service.generate(
            user(),
            WeeklyGenerateRequest(
                teamId="team-1",
                scope=ReportScope.MEMBER,
                weekStart=date(2026, 9, 28),
            ),
        )

    assert invalid.value.code == "LLM_OUTPUT_INVALID"
    assert repository.saved == []


@pytest.mark.asyncio
async def test_provider_failure_is_sanitized_without_persistence() -> None:
    repository = FakeWeeklyRepository()
    service = WeeklyReportService(
        repository, UnavailableProvider(), AllowAuthorization()  # type: ignore[arg-type]
    )

    with pytest.raises(AppError) as unavailable:
        await service.generate(
            user(),
            WeeklyGenerateRequest(
                teamId="team-1",
                scope=ReportScope.MEMBER,
                weekStart=date(2026, 9, 28),
            ),
        )

    assert unavailable.value.status_code == 503
    assert unavailable.value.code == "LLM_UNAVAILABLE"
    assert "sensitive" not in unavailable.value.message
    assert repository.saved == []


@pytest.mark.asyncio
async def test_single_team_generation_hides_team_outside_actor_tenant() -> None:
    repository = FakeWeeklyRepository()
    repository.tenant_team_ids.clear()
    service = WeeklyReportService(
        repository, MockLLMProvider(), AllowAuthorization()  # type: ignore[arg-type]
    )

    with pytest.raises(AppError) as hidden:
        await service.generate(
            user(),
            WeeklyGenerateRequest(
                teamId="team-1",
                scope=ReportScope.MEMBER,
                weekStart=date(2026, 9, 28),
            ),
        )

    assert hidden.value.code == "TEAM_NOT_FOUND"
    assert repository.saved == []


@pytest.mark.asyncio
async def test_confirmed_report_is_immutable_and_revision_supersedes_it() -> None:
    repository = FakeWeeklyRepository()
    confirmed = WeeklyReport(
        id="weekly-confirmed",
        scope=ReportScope.MEMBER,
        subject_user_id="user-1",
        team_id="team-1",
        week_start=date(2026, 9, 28),
        week_end=date(2026, 10, 2),
        content_json={"completed": ["OPS-001"]},
        missing_contributors=[],
        input_record_ids=["daily-1"],
        generation_source="MOCK",
        generation_metadata={},
        status=WeeklyReportStatus.CONFIRMED,
        template_id="template-member",
        template_version=1,
        created_by="user-1",
        confirmed_by="user-1",
    )
    repository.saved.append(confirmed)
    service = WeeklyReportService(
        repository, MockLLMProvider(), AllowAuthorization()  # type: ignore[arg-type]
    )

    with pytest.raises(AppError) as immutable:
        await service.update(
            user(),
            "team-1",
            confirmed.id,
            WeeklyUpdateRequest(contentJson={"completed": ["Changed"]}),
        )
    revision = await service.create_revision(user(), "team-1", confirmed.id)

    assert immutable.value.code == "WEEKLY_REPORT_IMMUTABLE"
    assert revision.status == WeeklyReportStatus.DRAFT
    assert revision.supersedes_id == confirmed.id
    assert revision.content_json == confirmed.content_json
