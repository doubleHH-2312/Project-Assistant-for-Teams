from datetime import date

import pytest

from project_assistant.integrations.teams.transport import DeliveryResult
from project_assistant.modules.notifications.models import NotificationLog, TeamsConversation
from project_assistant.modules.notifications.service import NotificationService
from project_assistant.modules.users.models import User, UserRole


class FakeNotificationRepository:
    def __init__(self, users: list[User]) -> None:
        self.users = users
        self.reported = {"user-1"}
        self.conversations = {
            "user-2": TeamsConversation(
                user_id="user-2",
                conversation_id="conversation-2",
                tenant_id="tenant-1",
                service_url="https://teams.example.test",
            )
        }
        self.logs: list[NotificationLog] = []

    async def list_expected_reporters(self, team_id: str) -> list[User]:
        return self.users

    async def has_daily_report(self, user_id: str, target_date: date) -> bool:
        return user_id in self.reported

    async def get_conversation(self, user_id: str) -> TeamsConversation | None:
        return self.conversations.get(user_id)

    async def claim_notification(
        self, user_id: str, notification_type: str, target_date: date, correlation_id: str
    ) -> NotificationLog | None:
        existing = next(
            (
                log
                for log in self.logs
                if log.user_id == user_id
                and log.type == notification_type
                and log.target_date == target_date
            ),
            None,
        )
        if existing is not None:
            return None
        log = NotificationLog(
            user_id=user_id,
            type=notification_type,
            target_date=target_date,
            delivery_status="PENDING",
            correlation_id=correlation_id,
        )
        self.logs.append(log)
        return log

    async def complete_notification(self, log: NotificationLog, status: str) -> None:
        log.delivery_status = status


class FakeTeamsTransport:
    def __init__(self) -> None:
        self.sent_to: list[str] = []

    async def send_proactive(
        self, conversation: TeamsConversation, payload: dict
    ) -> DeliveryResult:
        self.sent_to.append(conversation.conversation_id)
        return DeliveryResult(success=True, external_id="activity-1")


def member(index: int) -> User:
    return User(
        id=f"user-{index}",
        external_user_id=f"entra-{index}",
        name=f"Member {index}",
        email=f"member{index}@example.test",
        role=UserRole.MEMBER,
        team_id="team-1",
    )


@pytest.mark.asyncio
async def test_reminders_skip_reported_users_and_deduplicate_retries() -> None:
    repository = FakeNotificationRepository([member(1), member(2)])
    transport = FakeTeamsTransport()
    service = NotificationService(repository, transport)

    first = await service.send_daily_reminders("team-1", date(2026, 10, 1), "corr-1")
    second = await service.send_daily_reminders("team-1", date(2026, 10, 1), "corr-2")

    assert first.sent == 1
    assert first.skipped_reported == 1
    assert second.sent == 0
    assert second.skipped_duplicate == 1
    assert transport.sent_to == ["conversation-2"]
