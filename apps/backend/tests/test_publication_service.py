from datetime import date
from importlib import import_module

import pytest

from project_assistant.core.errors import AppError
from project_assistant.modules.publications.models import ReportPublication
from project_assistant.modules.users.models import User
from project_assistant.modules.weekly_reports.models import (
    ReportScope,
    WeeklyReport,
    WeeklyReportStatus,
)


def _service_type():  # type: ignore[no-untyped-def]
    try:
        return import_module("project_assistant.modules.publications.service").PublicationService
    except ModuleNotFoundError:
        pytest.fail("Publication service is not implemented")


def _actor() -> User:
    return User(
        id="lead-1",
        tenant_id="tenant-1",
        external_user_id="entra-lead",
        name="Lead",
        email="lead@example.test",
    )


def _report(status: WeeklyReportStatus) -> WeeklyReport:
    return WeeklyReport(
        id="weekly-1",
        scope=ReportScope.TEAM,
        team_id="team-1",
        week_start=date(2026, 9, 28),
        week_end=date(2026, 10, 2),
        content_json={"projects": []},
        missing_contributors=[],
        input_record_ids=[],
        generation_source="MOCK",
        generation_metadata={},
        status=status,
        template_id="template-team",
        template_version=1,
        created_by="lead-1",
    )


class PublicationRepository:
    def __init__(self, report: WeeklyReport) -> None:
        self.report = report
        self.by_key: dict[str, ReportPublication] = {}

    async def find_by_idempotency_key(self, key: str):  # type: ignore[no-untyped-def]
        return self.by_key.get(key)

    async def get_report(self, report_id: str):  # type: ignore[no-untyped-def]
        return self.report if report_id == self.report.id else None

    async def list_report_team_ids(self, report_id: str):  # type: ignore[no-untyped-def]
        return [self.report.team_id] if self.report.team_id else []

    async def save(self, publication: ReportPublication):
        publication.id = publication.id or "publication-1"
        self.by_key[publication.idempotency_key] = publication
        return publication


class RecordingAuthorization:
    def __init__(self) -> None:
        self.calls = []

    async def require(self, actor_id, team_ids, permission):  # type: ignore[no-untyped-def]
        self.calls.append((actor_id, list(team_ids), permission))
        return {}


@pytest.mark.asyncio
async def test_confirmed_report_publication_is_explicit_and_idempotent() -> None:
    repository = PublicationRepository(_report(WeeklyReportStatus.CONFIRMED))
    authorization = RecordingAuthorization()
    service = _service_type()(repository, authorization)

    first = await service.publish(_actor(), "weekly-1", "conversation-1", "publish-key-1")
    replay = await service.publish(_actor(), "weekly-1", "conversation-1", "publish-key-1")

    assert replay is first
    assert first.weekly_report_id == "weekly-1"
    assert first.conversation_id == "conversation-1"
    assert len(repository.by_key) == 1
    assert len(authorization.calls) == 1


@pytest.mark.asyncio
async def test_unconfirmed_report_cannot_be_published() -> None:
    repository = PublicationRepository(_report(WeeklyReportStatus.GENERATED))
    service = _service_type()(repository, RecordingAuthorization())

    with pytest.raises(AppError) as private_draft:
        await service.publish(_actor(), "weekly-1", "conversation-1", "publish-key-2")

    assert private_draft.value.code == "WEEKLY_REPORT_NOT_CONFIRMED"
    assert repository.by_key == {}


@pytest.mark.asyncio
async def test_idempotency_key_cannot_be_reused_for_another_destination() -> None:
    repository = PublicationRepository(_report(WeeklyReportStatus.CONFIRMED))
    service = _service_type()(repository, RecordingAuthorization())
    await service.publish(_actor(), "weekly-1", "conversation-1", "publish-key-reused")

    with pytest.raises(AppError) as reused:
        await service.publish(_actor(), "weekly-1", "conversation-2", "publish-key-reused")

    assert reused.value.code == "IDEMPOTENCY_KEY_REUSED"
