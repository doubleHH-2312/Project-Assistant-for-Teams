import uuid
from collections.abc import Awaitable, Callable, Iterable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from project_assistant.modules.teams.models import Team


def is_reminder_due(team: Team, now_utc: datetime) -> bool:
    """Return whether a team's daily reminder is due in the current minute."""
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")

    local_now = now_utc.astimezone(ZoneInfo(team.timezone))
    reminder_time = team.daily_reminder_time
    return (
        local_now.weekday() < 5
        and local_now.hour == reminder_time.hour
        and local_now.minute == reminder_time.minute
    )


ReminderSender = Callable[[str, date, str], Awaitable[object]]


async def dispatch_due_reminders(
    teams: Iterable[Team], now_utc: datetime, send: ReminderSender
) -> int:
    """Dispatch one idempotent reminder run for each team due this minute."""
    dispatched = 0
    for team in teams:
        if not is_reminder_due(team, now_utc):
            continue
        local_date = now_utc.astimezone(ZoneInfo(team.timezone)).date()
        await send(team.id, local_date, str(uuid.uuid4()))
        dispatched += 1
    return dispatched
