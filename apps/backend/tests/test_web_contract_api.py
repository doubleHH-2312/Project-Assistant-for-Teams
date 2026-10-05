from datetime import UTC, date, datetime

import httpx
import pytest

from project_assistant.api.session import SessionSnapshot, TeamAccess, get_session_service
from project_assistant.core.auth import get_current_user
from project_assistant.main import app
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.daily_reports.router import get_daily_report_service
from project_assistant.modules.publications.models import ReportPublication
from project_assistant.modules.publications.router import get_publication_service
from project_assistant.modules.users.models import User

ACTOR = User(
    id="user-1",
    tenant_id="tenant-1",
    external_user_id="entra-1",
    name="Linh Nguyen",
    email="linh@example.test",
)


class StubSessionService:
    async def get(self, actor: User) -> SessionSnapshot:
        return SessionSnapshot(
            id=actor.id,
            name=actor.name,
            email=actor.email,
            tenantId=actor.tenant_id,
            teams=[
                TeamAccess(
                    teamId="team-1",
                    teamName="Platform Team",
                    timezone="Asia/Ho_Chi_Minh",
                    role="TECH_LEAD",
                    permissions=[
                        "SUBMIT_OWN_DAILY",
                        "VIEW_TEAM_DAILY_SUMMARY",
                    ],
                )
            ],
        )


class StubDailyService:
    async def list_history(self, actor, filters):  # type: ignore[no-untyped-def]
        now = datetime(2026, 10, 3, 9, tzinfo=UTC)
        return [
            DailyReport(
                id="daily-1",
                team_id=filters.team_id,
                user_id=actor.id,
                project_id="project-1",
                work_item_id="work-1",
                report_date=date(2026, 10, 2),
                status=WorkStatus.BLOCKED,
                work_summary="Waiting for access",
                blocker=None,
                next_action="Escalate",
                source="WEB",
                submitted_at=now,
                created_at=now,
                updated_at=now,
            )
        ]


class StubPublicationService:
    async def publish(
        self,
        actor: User,
        report_id: str,
        conversation_id: str,
        idempotency_key: str,
    ) -> ReportPublication:
        return ReportPublication(
            id="publication-1",
            weekly_report_id=report_id,
            actor_id=actor.id,
            conversation_id=conversation_id,
            idempotency_key=idempotency_key,
            published_at=datetime(2026, 10, 3, 10, tzinfo=UTC),
        )


async def _actor() -> User:
    return ACTOR


@pytest.mark.asyncio
async def test_session_and_team_access_contract() -> None:
    async def session_service() -> StubSessionService:
        return StubSessionService()

    app.dependency_overrides[get_current_user] = _actor
    app.dependency_overrides[get_session_service] = session_service
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            me = await client.get("/api/v1/me")
            teams = await client.get("/api/v1/teams")
    finally:
        app.dependency_overrides.clear()

    assert me.status_code == 200
    assert me.json()["teams"][0]["role"] == "TECH_LEAD"
    assert teams.json()[0]["teamId"] == "team-1"
    assert "VIEW_TEAM_DAILY_SUMMARY" in teams.json()[0]["permissions"]


@pytest.mark.asyncio
async def test_team_scoped_history_contract_preserves_recorded_dates() -> None:
    async def daily_service() -> StubDailyService:
        return StubDailyService()

    app.dependency_overrides[get_current_user] = _actor
    app.dependency_overrides[get_daily_report_service] = daily_service
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/daily-reports/history",
                params={
                    "teamId": "team-1",
                    "dateFrom": "2026-09-28",
                    "dateTo": "2026-10-03",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["reportDate"] == "2026-10-02"
    assert response.json()[0]["effectiveBlocker"] == "Waiting for access"


@pytest.mark.asyncio
async def test_publication_requires_and_returns_idempotency_contract() -> None:
    async def publication_service() -> StubPublicationService:
        return StubPublicationService()

    app.dependency_overrides[get_current_user] = _actor
    app.dependency_overrides[get_publication_service] = publication_service
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            missing = await client.post(
                "/api/v1/weekly-reports/weekly-1/publish",
                json={"conversationId": "conversation-1"},
            )
            published = await client.post(
                "/api/v1/weekly-reports/weekly-1/publish",
                headers={"Idempotency-Key": "publish-1"},
                json={"conversationId": "conversation-1"},
            )
    finally:
        app.dependency_overrides.clear()

    assert missing.status_code == 422
    assert set(missing.json()) == {"code", "message", "details", "correlationId"}
    assert published.status_code == 201
    assert published.json()["idempotencyKey"] == "publish-1"


@pytest.mark.asyncio
async def test_request_validation_uses_standard_error_envelope() -> None:
    app.dependency_overrides[get_current_user] = _actor
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/daily-reports", json={})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["code"] == "REQUEST_VALIDATION_FAILED"
    assert response.json()["correlationId"]
