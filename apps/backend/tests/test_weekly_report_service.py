from datetime import date

import pytest

from project_assistant.core.errors import AppError
from project_assistant.integrations.llm.provider import LLMResult, MockLLMProvider
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
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

    async def get_active_template(
        self, team_id: str, scope: ReportScope
    ) -> ReportTemplate | None:
        return self.templates.get(scope)

    async def get_template(self, template_id: str) -> ReportTemplate | None:
        return next(
            (template for template in self.templates.values() if template.id == template_id), None
        )

    async def list_daily_reports(
        self, user_id: str, week_start: date, week_end: date
    ) -> list[DailyReport]:
        return [
            report
            for report in self.daily_reports
            if report.user_id == user_id and week_start <= report.report_date <= week_end
        ]

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

    async def get_by_id(self, report_id: str) -> WeeklyReport | None:
        return next((report for report in self.saved if report.id == report_id), None)


def user(role: UserRole = UserRole.MEMBER, user_id: str = "user-1") -> User:
    return User(
        id=user_id,
        external_user_id=f"entra-{user_id}",
        name="User",
        email=f"{user_id}@example.test",
        role=role,
        team_id="team-1",
    )


@pytest.mark.asyncio
async def test_member_generation_uses_daily_evidence_and_preserves_ids() -> None:
    repository = FakeWeeklyRepository()
    repository.daily_reports.append(
        DailyReport(
            id="daily-1",
            user_id="user-1",
            project_id="project-1",
            work_item_id="OPS-001",
            report_date=date(2026, 9, 28),
            status=WorkStatus.DONE,
            work_summary="Implemented validation",
            next_action="Start integration",
        )
    )
    service = WeeklyReportService(repository, MockLLMProvider())

    report = await service.generate(
        user(), WeeklyGenerateRequest(scope=ReportScope.MEMBER, weekStart=date(2026, 9, 28))
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
    service = WeeklyReportService(repository, MockLLMProvider())

    report = await service.generate(
        user(UserRole.LEAD, "user-lead"),
        WeeklyGenerateRequest(scope=ReportScope.TEAM, weekStart=date(2026, 9, 28)),
    )

    assert report.input_record_ids == ["member-confirmed"]
    assert report.missing_contributors == ["user-2"]
    assert "MUST NOT APPEAR" not in str(report.content_json)


class InvalidProvider:
    async def generate(self, template: dict, evidence: list[dict]) -> LLMResult:
        return LLMResult(content={"invented": ["not allowed"]}, provider="invalid", metadata={})


@pytest.mark.asyncio
async def test_invalid_llm_output_is_rejected_without_persistence() -> None:
    repository = FakeWeeklyRepository()
    service = WeeklyReportService(repository, InvalidProvider())

    with pytest.raises(AppError) as invalid:
        await service.generate(
            user(), WeeklyGenerateRequest(scope=ReportScope.MEMBER, weekStart=date(2026, 9, 28))
        )

    assert invalid.value.code == "LLM_OUTPUT_INVALID"
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
    service = WeeklyReportService(repository, MockLLMProvider())

    with pytest.raises(AppError) as immutable:
        await service.update(
            user(),
            confirmed.id,
            WeeklyUpdateRequest(contentJson={"completed": ["Changed"]}),
        )
    revision = await service.create_revision(user(), confirmed.id)

    assert immutable.value.code == "WEEKLY_REPORT_IMMUTABLE"
    assert revision.status == WeeklyReportStatus.DRAFT
    assert revision.supersedes_id == confirmed.id
    assert revision.content_json == confirmed.content_json
