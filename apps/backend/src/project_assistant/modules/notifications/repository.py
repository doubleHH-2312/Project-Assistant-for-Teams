from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.modules.daily_reports.models import DailyReport
from project_assistant.modules.memberships.models import TeamMembership, TeamRole
from project_assistant.modules.notifications.models import NotificationLog, TeamsConversation
from project_assistant.modules.projects.models import Project
from project_assistant.modules.users.models import User


class SqlAlchemyNotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_expected_reporters(self, team_id: str) -> list[User]:
        result = await self.session.scalars(
            select(User)
            .join(TeamMembership, TeamMembership.user_id == User.id)
            .where(
                TeamMembership.team_id == team_id,
                TeamMembership.role == TeamRole.MEMBER,
                TeamMembership.active.is_(True),
                User.active.is_(True),
            )
        )
        return list(result)

    async def has_daily_report(
        self, user_id: str, team_id: str, target_date: date
    ) -> bool:
        report_id = await self.session.scalar(
            select(DailyReport.id)
            .join(Project, Project.id == DailyReport.project_id)
            .where(
                DailyReport.user_id == user_id,
                DailyReport.report_date == target_date,
                Project.team_id == team_id,
            )
        )
        return report_id is not None

    async def get_conversation(self, user_id: str) -> TeamsConversation | None:
        return await self.session.get(TeamsConversation, user_id)

    async def claim_notification(
        self, user_id: str, notification_type: str, target_date: date, correlation_id: str
    ) -> NotificationLog | None:
        statement = (
            insert(NotificationLog)
            .values(
                user_id=user_id,
                type=notification_type,
                target_date=target_date,
                delivery_status="PENDING",
                correlation_id=correlation_id,
            )
            .on_conflict_do_nothing(constraint="uq_notification_user_type_target")
            .returning(NotificationLog)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def complete_notification(self, log: NotificationLog, status: str) -> None:
        log.delivery_status = status
        await self.session.commit()
