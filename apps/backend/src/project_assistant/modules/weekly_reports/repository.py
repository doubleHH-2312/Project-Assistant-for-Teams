from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.modules.daily_reports.models import DailyReport
from project_assistant.modules.memberships.models import TeamMembership, TeamRole
from project_assistant.modules.projects.models import Project
from project_assistant.modules.templates.models import ReportTemplate
from project_assistant.modules.users.models import User
from project_assistant.modules.weekly_reports.models import (
    ReportScope,
    WeeklyReport,
    WeeklyReportStatus,
)


class SqlAlchemyWeeklyReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_template(
        self, team_id: str, scope: ReportScope
    ) -> ReportTemplate | None:
        return await self.session.scalar(
            select(ReportTemplate).where(
                ReportTemplate.team_id == team_id,
                ReportTemplate.scope == scope,
                ReportTemplate.active.is_(True),
            )
        )

    async def get_template(self, template_id: str, team_id: str) -> ReportTemplate | None:
        return await self.session.scalar(
            select(ReportTemplate).where(
                ReportTemplate.id == template_id,
                ReportTemplate.team_id == team_id,
            )
        )

    async def list_daily_reports(
        self, user_id: str, team_id: str, week_start: date, week_end: date
    ) -> list[DailyReport]:
        reports = await self.session.scalars(
            select(DailyReport)
            .join(Project, Project.id == DailyReport.project_id)
            .where(
                DailyReport.user_id == user_id,
                Project.team_id == team_id,
                DailyReport.report_date >= week_start,
                DailyReport.report_date <= week_end,
            )
            .order_by(DailyReport.report_date, DailyReport.work_item_id)
        )
        return list(reports)

    async def list_confirmed_member_reports(
        self, team_id: str, week_start: date, week_end: date
    ) -> list[WeeklyReport]:
        reports = await self.session.scalars(
            select(WeeklyReport)
            .where(
                WeeklyReport.team_id == team_id,
                WeeklyReport.scope == ReportScope.MEMBER,
                WeeklyReport.status == WeeklyReportStatus.CONFIRMED,
                WeeklyReport.week_start == week_start,
                WeeklyReport.week_end == week_end,
            )
            .order_by(WeeklyReport.subject_user_id)
        )
        return list(reports)

    async def list_expected_member_ids(self, team_id: str) -> list[str]:
        user_ids = await self.session.scalars(
            select(User.id)
            .join(TeamMembership, TeamMembership.user_id == User.id)
            .where(
                TeamMembership.team_id == team_id,
                TeamMembership.role == TeamRole.MEMBER,
                TeamMembership.active.is_(True),
                User.active.is_(True),
            )
            .order_by(User.id)
        )
        return list(user_ids)

    async def find_report(
        self, scope: ReportScope, team_id: str, subject_user_id: str | None, week_start: date
    ) -> WeeklyReport | None:
        query = select(WeeklyReport).where(
            WeeklyReport.scope == scope,
            WeeklyReport.team_id == team_id,
            WeeklyReport.week_start == week_start,
        )
        query = query.where(
            WeeklyReport.subject_user_id == subject_user_id
            if subject_user_id is not None
            else WeeklyReport.subject_user_id.is_(None)
        )
        return await self.session.scalar(query.order_by(WeeklyReport.created_at.desc()))

    async def get_by_id(self, report_id: str, team_id: str) -> WeeklyReport | None:
        return await self.session.scalar(
            select(WeeklyReport).where(
                WeeklyReport.id == report_id,
                WeeklyReport.team_id == team_id,
            )
        )

    async def save(self, report: WeeklyReport) -> WeeklyReport:
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)
        return report
