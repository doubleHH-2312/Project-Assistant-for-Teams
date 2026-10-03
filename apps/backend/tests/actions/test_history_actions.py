from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from project_assistant.modules.actions.contracts import ActionContext, ConversationType
from project_assistant.modules.actions.handlers.history import (
    HistoryActionHandler,
    HistoryActionInput,
)
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus


class RecordingHistoryService:
    def __init__(self) -> None:
        now = datetime(2026, 10, 3, 8, tzinfo=UTC)
        self.reports = [
            DailyReport(
                id="daily-1",
                team_id="team-1",
                user_id="user-1",
                project_id="project-a",
                work_item_id="item-1",
                report_date=date(2026, 10, 2),
                status=WorkStatus.DONE,
                work_summary="Completed API",
                next_action="Review",
                source="TEAMS",
                submitted_at=now,
                created_at=now,
                updated_at=now,
            ),
            DailyReport(
                id="daily-2",
                team_id="team-1",
                user_id="user-1",
                project_id="project-a",
                work_item_id="item-2",
                report_date=date(2026, 10, 2),
                status=WorkStatus.BLOCKED,
                work_summary="Waiting for access",
                next_action="Escalate",
                source="TEAMS",
                submitted_at=now,
                created_at=now,
                updated_at=now,
            ),
            DailyReport(
                id="daily-3",
                team_id="team-1",
                user_id="user-1",
                project_id="project-b",
                work_item_id="item-3",
                report_date=date(2026, 10, 1),
                status=WorkStatus.IN_PROGRESS,
                work_summary="Built UI",
                next_action="Test",
                source="TEAMS",
                submitted_at=now,
                created_at=now,
                updated_at=now,
            ),
        ]
        self.actor_ids: list[str] = []

    async def list_history(self, actor, filters):  # type: ignore[no-untyped-def]
        self.actor_ids.append(actor.id)
        assert filters.date_from == date(2026, 9, 24)
        assert filters.date_to == date(2026, 10, 3)
        return self.reports


def context() -> ActionContext:
    return ActionContext(
        actor_id="user-1",
        tenant_id="tenant-1",
        conversation_id="conversation-1",
        conversation_type=ConversationType.PERSONAL,
        current_team_id=None,
        correlation_id="correlation-1",
        idempotency_key="activity-1:history",
        timezone="UTC",
    )


@pytest.mark.asyncio
async def test_history_defaults_to_seven_reporting_days_and_groups_own_records() -> None:
    service = RecordingHistoryService()
    handler = HistoryActionHandler(
        service,  # type: ignore[arg-type]
        clock=lambda: datetime(2026, 10, 3, 8, tzinfo=UTC),
    )

    result = await handler.execute(context(), HistoryActionInput(teamId="team-1"))

    assert service.actor_ids == ["user-1"]
    assert result.kind == "history"
    dates = result.data["dates"]
    assert [group["date"] for group in dates] == ["2026-10-02", "2026-10-01"]
    assert dates[0]["projects"][0]["projectId"] == "project-a"
    assert [item["workItemId"] for item in dates[0]["projects"][0]["workItems"]] == [
        "item-1",
        "item-2",
    ]


def test_history_payload_cannot_request_another_user() -> None:
    with pytest.raises(ValidationError):
        HistoryActionInput.model_validate({"teamId": "team-1", "userId": "user-2"})
