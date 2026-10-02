from datetime import UTC, datetime

import httpx
import pytest

from project_assistant.core.auth import get_current_user
from project_assistant.main import app
from project_assistant.modules.daily_reports.models import DailyReport
from project_assistant.modules.daily_reports.router import get_daily_report_service
from project_assistant.modules.users.models import User, UserRole


class StubDailyReportService:
    async def create(self, actor: User, request):  # type: ignore[no-untyped-def]
        now = datetime(2026, 10, 1, 10, tzinfo=UTC)
        return DailyReport(
            id="daily-1",
            user_id=actor.id,
            project_id=request.project_id,
            work_item_id=request.work_item_id,
            report_date=request.report_date,
            status=request.status,
            work_summary=request.work_summary,
            blocker=request.blocker,
            next_action=request.next_action,
            created_at=now,
            updated_at=now,
        )


@pytest.mark.asyncio
async def test_create_daily_report_returns_camel_case_contract() -> None:
    actor = User(
        id="user-1",
        external_user_id="entra-1",
        name="Member",
        email="member@example.test",
        role=UserRole.MEMBER,
        team_id="team-1",
    )
    async def override_actor() -> User:
        return actor

    async def override_service() -> StubDailyReportService:
        return StubDailyReportService()

    app.dependency_overrides[get_current_user] = override_actor
    app.dependency_overrides[get_daily_report_service] = override_service
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/daily-reports",
                json={
                    "projectId": "project-1",
                    "workItemId": "item-1",
                    "reportDate": "2026-10-01",
                    "status": "BLOCKED",
                    "workSummary": "Waiting for data",
                    "blocker": None,
                    "nextAction": "Resume integration",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["effectiveBlocker"] == "Waiting for data"
    assert response.json()["workItemId"] == "item-1"
