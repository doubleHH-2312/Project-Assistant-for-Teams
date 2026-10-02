import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from project_assistant.core.config import get_settings
from project_assistant.core.database import SessionFactory
from project_assistant.integrations.teams.transport import MockTeamsTransport
from project_assistant.modules.notifications.repository import SqlAlchemyNotificationRepository
from project_assistant.modules.notifications.service import NotificationService
from project_assistant.modules.teams.models import Team
from project_assistant.worker.schedule import dispatch_due_reminders

logger = logging.getLogger(__name__)


async def run_once(now_utc: datetime | None = None) -> int:
    settings = get_settings()
    if settings.teams_transport != "mock":
        raise RuntimeError("Teams SDK transport is not configured; keep TEAMS_TRANSPORT=mock")

    async with SessionFactory() as session:
        teams = list(await session.scalars(select(Team)))
        service = NotificationService(
            SqlAlchemyNotificationRepository(session), MockTeamsTransport()
        )
        return await dispatch_due_reminders(
            teams,
            now_utc or datetime.now(UTC),
            service.send_daily_reminders,
        )


async def worker_loop() -> None:
    logger.info("Project Assistant reminder worker started")
    while True:
        try:
            dispatched = await run_once()
            if dispatched:
                logger.info("Dispatched reminder runs", extra={"team_count": dispatched})
        except Exception:
            logger.exception("Reminder worker iteration failed")
        await asyncio.sleep(30)


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
