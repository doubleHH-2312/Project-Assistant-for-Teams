from datetime import UTC, date, datetime

import pytest

from project_assistant.core.errors import AppError
from project_assistant.modules.actions.contracts import ActionContext, ConversationType
from project_assistant.modules.actions.handlers.daily import (
    DailyActionHandler,
    DailyActionInput,
)
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.daily_reports.service import resolve_report_date


class RecordingDailyService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object, object]] = []

    async def get_form_options(self, actor, team_id):  # type: ignore[no-untyped-def]
        return {
            "projects": [{"id": "project-1", "name": "Project One"}],
            "workItems": [
                {
                    "id": "item-1",
                    "projectId": "project-1",
                    "code": "ITEM-1",
                    "title": "Ship MVP",
                }
            ],
        }

    async def create(self, actor, team_id, request, audit):  # type: ignore[no-untyped-def]
        self.calls.append((actor.id, team_id, request, audit))
        now = datetime(2026, 10, 3, 8, tzinfo=UTC)
        return DailyReport(
            id="daily-1",
            team_id=team_id,
            user_id=actor.id,
            project_id=request.project_id,
            work_item_id=request.work_item_id,
            report_date=request.report_date or date(2026, 10, 3),
            status=request.status,
            work_summary=request.work_summary,
            blocker=request.blocker,
            next_action=request.next_action,
            source="TEAMS",
            submitted_at=now,
            created_at=now,
            updated_at=now,
        )


def context(current_team_id: str | None) -> ActionContext:
    return ActionContext(
        actor_id="user-1",
        tenant_id="tenant-1",
        conversation_id="conversation-1",
        conversation_type=(
            ConversationType.TEAM_CHANNEL
            if current_team_id
            else ConversationType.PERSONAL
        ),
        current_team_id=current_team_id,
        correlation_id="correlation-1",
        idempotency_key="activity-1:daily",
        timezone="Asia/Ho_Chi_Minh",
    )


def complete_payload(team_id: str | None = None) -> DailyActionInput:
    return DailyActionInput(
        teamId=team_id,
        projectId="project-1",
        workItemId="item-1",
        status=WorkStatus.BLOCKED,
        workSummary="Waiting for access",
        blocker=None,
        nextAction="Request access",
    )


@pytest.mark.asyncio
async def test_daily_action_uses_bound_team_and_shared_daily_service() -> None:
    service = RecordingDailyService()
    handler = DailyActionHandler(service)  # type: ignore[arg-type]

    result = await handler.execute(context("team-1"), complete_payload())

    actor_id, team_id, request, audit = service.calls[0]
    assert result.kind == "daily_saved"
    assert result.result_ref == "daily-1"
    assert actor_id == "user-1"
    assert team_id == "team-1"
    assert request.team_id == "team-1"
    assert request.report_date is None
    assert audit.idempotency_key == "activity-1:daily"


@pytest.mark.asyncio
async def test_daily_action_personal_chat_uses_selected_team_and_incomplete_input_is_form() -> None:
    service = RecordingDailyService()
    handler = DailyActionHandler(service)  # type: ignore[arg-type]

    selected = await handler.execute(context(None), complete_payload("team-2"))
    form = await handler.execute(
        context("team-1"), DailyActionInput(teamId=None)
    )

    assert selected.result_ref == "daily-1"
    assert service.calls[0][1] == "team-2"
    assert form.kind == "form"
    assert form.data["action"] == "daily"
    assert "projectId" in form.data["requiredFields"]
    assert form.data["projects"] == [{"id": "project-1", "name": "Project One"}]
    assert form.data["workItems"][0]["projectId"] == "project-1"


def test_report_date_defaults_to_team_local_day_and_enforces_backfill_window() -> None:
    local_today = date(2026, 10, 10)

    assert resolve_report_date(None, local_today, 7) == local_today
    assert resolve_report_date(date(2026, 10, 3), local_today, 7) == date(2026, 10, 3)
    with pytest.raises(AppError) as too_old:
        resolve_report_date(date(2026, 10, 2), local_today, 7)
    with pytest.raises(AppError) as future:
        resolve_report_date(date(2026, 10, 11), local_today, 7)

    assert too_old.value.code == "REPORT_DATE_OUTSIDE_BACKFILL_WINDOW"
    assert future.value.code == "REPORT_DATE_IN_FUTURE"
