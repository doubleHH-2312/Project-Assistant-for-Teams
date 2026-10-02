from datetime import date

import httpx
import pytest

from project_assistant.core.auth import get_current_user
from project_assistant.main import app
from project_assistant.modules.users.models import User
from project_assistant.modules.weekly_reports.models import (
    ReportScope,
    WeeklyReport,
    WeeklyReportStatus,
)
from project_assistant.modules.weekly_reports.router import get_weekly_report_service


class StubWeeklyService:
    async def generate(self, actor: User, request):  # type: ignore[no-untyped-def]
        return WeeklyReport(
            id="weekly-1",
            scope=request.scope,
            subject_user_id=actor.id,
            team_id=request.team_id,
            week_start=request.week_start,
            week_end=date(2026, 10, 2),
            content_json={"completed": ["OPS-001"]},
            missing_contributors=[],
            input_record_ids=["daily-1"],
            generation_source="MOCK",
            generation_metadata={"mode": "mock"},
            status=WeeklyReportStatus.GENERATED,
            template_id="template-member",
            template_version=1,
            created_by=actor.id,
        )


@pytest.mark.asyncio
async def test_generate_weekly_report_returns_traceable_contract() -> None:
    actor = User(
        id="user-1",
        external_user_id="entra-1",
        name="Member",
        email="member@example.test",
    )

    async def override_actor() -> User:
        return actor

    async def override_service() -> StubWeeklyService:
        return StubWeeklyService()

    app.dependency_overrides[get_current_user] = override_actor
    app.dependency_overrides[get_weekly_report_service] = override_service
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/weekly-reports/generate",
                json={
                    "teamId": "team-1",
                    "scope": ReportScope.MEMBER,
                    "weekStart": "2026-09-28",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["inputRecordIds"] == ["daily-1"]
    assert response.json()["generationSource"] == "MOCK"
