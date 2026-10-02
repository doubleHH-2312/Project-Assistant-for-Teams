from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol

from project_assistant.integrations.teams.transport import TeamsTransport
from project_assistant.modules.notifications.models import NotificationLog, TeamsConversation
from project_assistant.modules.users.models import User


@dataclass(frozen=True, slots=True)
class ReminderRunResult:
    sent: int = 0
    failed: int = 0
    skipped_reported: int = 0
    skipped_duplicate: int = 0


class NotificationRepository(Protocol):
    async def list_expected_reporters(self, team_id: str) -> list[User]: ...

    async def has_daily_report(self, user_id: str, target_date: date) -> bool: ...

    async def get_conversation(self, user_id: str) -> TeamsConversation | None: ...

    async def claim_notification(
        self, user_id: str, notification_type: str, target_date: date, correlation_id: str
    ) -> NotificationLog | None: ...

    async def complete_notification(self, log: NotificationLog, status: str) -> None: ...


class NotificationService:
    def __init__(self, repository: NotificationRepository, transport: TeamsTransport) -> None:
        self.repository = repository
        self.transport = transport

    async def send_daily_reminders(
        self, team_id: str, target_date: date, correlation_id: str
    ) -> ReminderRunResult:
        sent = failed = skipped_reported = skipped_duplicate = 0
        for user in await self.repository.list_expected_reporters(team_id):
            if await self.repository.has_daily_report(user.id, target_date):
                skipped_reported += 1
                continue
            log = await self.repository.claim_notification(
                user.id, "DAILY_REMINDER", target_date, correlation_id
            )
            if log is None:
                skipped_duplicate += 1
                continue
            conversation = await self.repository.get_conversation(user.id)
            if conversation is None:
                await self.repository.complete_notification(log, "FAILED_NO_CONVERSATION")
                failed += 1
                continue
            result = await self.transport.send_proactive(
                conversation,
                {
                    "type": "dailyReminder",
                    "targetDate": target_date.isoformat(),
                    "actionUrl": "/daily",
                },
            )
            if result.success:
                log.sent_at = datetime.now(UTC)
                await self.repository.complete_notification(log, "SENT")
                sent += 1
            else:
                await self.repository.complete_notification(log, result.error_code or "FAILED")
                failed += 1
        return ReminderRunResult(
            sent=sent,
            failed=failed,
            skipped_reported=skipped_reported,
            skipped_duplicate=skipped_duplicate,
        )

