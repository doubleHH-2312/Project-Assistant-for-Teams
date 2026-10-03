from datetime import UTC, date, datetime

import pytest

from project_assistant.core.errors import AppError
from project_assistant.integrations.llm.provider import LLMResult
from project_assistant.modules.templates.models import ReportTemplate
from project_assistant.modules.users.models import User
from project_assistant.modules.weekly_reports.models import (
    ReportScope,
    WeeklyReport,
    WeeklyReportStatus,
)
from project_assistant.modules.weekly_reports.schemas import WeeklyGenerateRequest
from project_assistant.modules.weekly_reports.service import WeeklyReportService

MULTI_SCHEMA = {
    "type": "object",
    "required": ["teams"],
    "properties": {
        "teams": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["teamId", "projects"],
                "properties": {
                    "teamId": {"type": "string"},
                    "projects": {"type": "array"},
                },
                "additionalProperties": False,
            },
        }
    },
    "additionalProperties": False,
}


def _actor() -> User:
    return User(
        id="lead-1",
        tenant_id="tenant-1",
        external_user_id="entra-lead-1",
        name="Lead",
        email="lead@example.test",
    )


def _confirmed_team_report(team_id: str) -> WeeklyReport:
    now = datetime(2026, 10, 3, 9, tzinfo=UTC)
    return WeeklyReport(
        id=f"weekly-{team_id}",
        scope=ReportScope.TEAM,
        subject_user_id=None,
        team_id=team_id,
        week_start=date(2026, 9, 28),
        week_end=date(2026, 10, 2),
        content_json={"projects": [{"projectId": f"project-{team_id}"}]},
        missing_contributors=[],
        input_record_ids=[f"member-{team_id}"],
        generation_source="MOCK",
        generation_metadata={},
        status=WeeklyReportStatus.CONFIRMED,
        template_id=f"template-{team_id}",
        template_version=1,
        created_by="lead-1",
        confirmed_by="lead-1",
        confirmed_at=now,
        created_at=now,
        updated_at=now,
    )


class RecordingAuthorization:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...], object]] = []

    async def require(self, actor_id, team_ids, permission):  # type: ignore[no-untyped-def]
        self.calls.append((actor_id, tuple(team_ids), permission))
        return {}


class CapturingProvider:
    def __init__(self) -> None:
        self.evidence: list[dict] = []

    async def generate(self, template, evidence):  # type: ignore[no-untyped-def]
        self.evidence = evidence
        return LLMResult(
            content={
                "teams": [
                    {"teamId": "team-a", "projects": [{"projectId": "project-team-a"}]}
                ]
            },
            provider="mock",
            metadata={"mode": "test"},
        )


class MultiTeamRepository:
    def __init__(self) -> None:
        self.team_reports = [_confirmed_team_report("team-a")]
        self.tenant_team_ids = ["team-a", "team-b"]
        self.saved: WeeklyReport | None = None
        self.saved_team_ids: list[str] = []
        self.saved_references = []

    async def list_team_ids_in_tenant(self, team_ids, tenant_id):  # type: ignore[no-untyped-def]
        assert tenant_id == "tenant-1"
        return [team_id for team_id in team_ids if team_id in self.tenant_team_ids]

    async def find_multiteam_report(self, tenant_id, team_ids, week_start):  # type: ignore[no-untyped-def]
        return None

    async def get_active_tenant_template(self, tenant_id, scope):  # type: ignore[no-untyped-def]
        assert tenant_id == "tenant-1"
        assert scope == ReportScope.MULTI_TEAM
        return ReportTemplate(
            id="template-multi",
            tenant_id="tenant-1",
            team_id=None,
            name="default-multi-team",
            scope=ReportScope.MULTI_TEAM,
            version=1,
            schema_json=MULTI_SCHEMA,
            active=True,
        )

    async def list_confirmed_team_reports(self, team_ids, week_start, week_end):  # type: ignore[no-untyped-def]
        assert list(team_ids) == ["team-a", "team-b"]
        return self.team_reports

    async def save_generated(self, report, team_ids, references):  # type: ignore[no-untyped-def]
        self.saved = report
        self.saved_team_ids = list(team_ids)
        self.saved_references = list(references)
        return report


@pytest.mark.asyncio
async def test_multiteam_generation_requires_all_teams_and_uses_confirmed_team_reports() -> None:
    repository = MultiTeamRepository()
    authorization = RecordingAuthorization()
    provider = CapturingProvider()
    service = WeeklyReportService(
        repository,  # type: ignore[arg-type]
        provider,  # type: ignore[arg-type]
        authorization,  # type: ignore[arg-type]
    )

    report = await service.generate(
        _actor(),
        WeeklyGenerateRequest(
            scope=ReportScope.MULTI_TEAM,
            teamIds=["team-b", "team-a", "team-a"],
            weekStart=date(2026, 9, 28),
        ),
    )

    assert authorization.calls[0][1] == ("team-a", "team-b")
    assert report.scope == ReportScope.MULTI_TEAM
    assert report.team_id is None
    assert report.status == WeeklyReportStatus.GENERATED
    assert report.missing_contributors == ["team-b"]
    assert repository.saved_team_ids == ["team-a", "team-b"]
    assert provider.evidence == [
        {
            "teamReportId": "weekly-team-a",
            "teamId": "team-a",
            "projects": [{"projectId": "project-team-a"}],
            "evidenceIds": ["weekly-team-a"],
        }
    ]
    assert [reference.source_id for reference in repository.saved_references] == [
        "weekly-team-a"
    ]


@pytest.mark.asyncio
async def test_week_start_must_be_monday_before_any_generation() -> None:
    repository = MultiTeamRepository()
    authorization = RecordingAuthorization()
    provider = CapturingProvider()
    service = WeeklyReportService(
        repository,  # type: ignore[arg-type]
        provider,  # type: ignore[arg-type]
        authorization,  # type: ignore[arg-type]
    )

    with pytest.raises(AppError) as invalid:
        await service.generate(
            _actor(),
            WeeklyGenerateRequest(
                scope=ReportScope.MULTI_TEAM,
                teamIds=["team-a", "team-b"],
                weekStart=date(2026, 9, 29),
            ),
        )

    assert invalid.value.code == "WEEK_START_INVALID"
    assert authorization.calls == []
    assert repository.saved is None


@pytest.mark.asyncio
async def test_multiteam_generation_rejects_team_outside_actor_tenant() -> None:
    repository = MultiTeamRepository()
    repository.tenant_team_ids = ["team-a"]
    authorization = RecordingAuthorization()
    provider = CapturingProvider()
    service = WeeklyReportService(
        repository,  # type: ignore[arg-type]
        provider,  # type: ignore[arg-type]
        authorization,  # type: ignore[arg-type]
    )

    with pytest.raises(AppError) as hidden:
        await service.generate(
            _actor(),
            WeeklyGenerateRequest(
                scope=ReportScope.MULTI_TEAM,
                teamIds=["team-a", "team-b"],
                weekStart=date(2026, 9, 28),
            ),
        )

    assert hidden.value.code == "TEAM_NOT_FOUND"
    assert authorization.calls == []
    assert provider.evidence == []
