from datetime import UTC, date, datetime, time

import pytest

from project_assistant.modules.teams.models import Team
from project_assistant.worker.schedule import dispatch_due_reminders, is_reminder_due


def test_reminder_schedule_uses_team_timezone_and_weekdays() -> None:
    team = Team(
        id="team-1",
        name="Ops",
        timezone="Asia/Ho_Chi_Minh",
        daily_reminder_time=time(16, 30),
    )

    assert is_reminder_due(team, datetime(2026, 10, 1, 9, 30, tzinfo=UTC)) is True
    assert is_reminder_due(team, datetime(2026, 10, 1, 9, 31, tzinfo=UTC)) is False
    assert is_reminder_due(team, datetime(2026, 10, 3, 9, 30, tzinfo=UTC)) is False


@pytest.mark.asyncio
async def test_dispatch_only_calls_due_teams() -> None:
    due = Team(
        id="team-due",
        name="Due",
        timezone="Asia/Ho_Chi_Minh",
        daily_reminder_time=time(16, 30),
    )
    later = Team(
        id="team-later",
        name="Later",
        timezone="UTC",
        daily_reminder_time=time(16, 30),
    )
    calls: list[tuple[str, date]] = []

    async def send(team_id: str, target_date: date, correlation_id: str) -> None:
        assert correlation_id
        calls.append((team_id, target_date))

    dispatched = await dispatch_due_reminders(
        [due, later], datetime(2026, 10, 1, 9, 30, tzinfo=UTC), send
    )

    assert dispatched == 1
    assert calls == [("team-due", date(2026, 10, 1))]
