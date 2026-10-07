import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from project_assistant.modules.audit.models import WorkItemStatusEvent
from project_assistant.modules.daily_reports.models import DailyReport
from project_assistant.modules.memberships.models import TeamMembership, TeamRole
from project_assistant.modules.projects.models import Project
from project_assistant.modules.teams.models import Team
from project_assistant.modules.templates.models import ReportTemplate
from project_assistant.modules.users.models import User
from project_assistant.modules.weekly_reports.evidence import EvidenceReference
from project_assistant.modules.weekly_reports.models import (
    ReportEvidenceLink,
    ReportScope,
    WeeklyReport,
    WeeklyReportStatus,
    WeeklyReportTeam,
)


class SqlAlchemyWeeklyReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_template(self, team_id: str, scope: ReportScope) -> ReportTemplate | None:
        return await self.session.scalar(
            select(ReportTemplate).where(
                ReportTemplate.team_id == team_id,
                ReportTemplate.tenant_id.is_(None),
                ReportTemplate.scope == scope,
                ReportTemplate.active.is_(True),
            )
        )

    async def get_active_tenant_template(
        self, tenant_id: str, scope: ReportScope
    ) -> ReportTemplate | None:
        return await self.session.scalar(
            select(ReportTemplate).where(
                ReportTemplate.team_id.is_(None),
                ReportTemplate.tenant_id == tenant_id,
                ReportTemplate.scope == scope,
                ReportTemplate.active.is_(True),
            )
        )

    async def list_team_ids_in_tenant(self, team_ids: list[str], tenant_id: str) -> list[str]:
        if not team_ids:
            return []
        visible = await self.session.scalars(
            select(Team.id)
            .where(Team.id.in_(team_ids), Team.tenant_id == tenant_id)
            .order_by(Team.id)
        )
        return list(visible)

    async def get_template(self, template_id: str, team_id: str | None) -> ReportTemplate | None:
        query = select(ReportTemplate).where(ReportTemplate.id == template_id)
        query = query.where(
            ReportTemplate.team_id == team_id
            if team_id is not None
            else ReportTemplate.team_id.is_(None)
        )
        return await self.session.scalar(query)

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

    async def list_status_events(self, daily_report_ids: list[str]) -> list[WorkItemStatusEvent]:
        if not daily_report_ids:
            return []
        events = await self.session.scalars(
            select(WorkItemStatusEvent)
            .where(WorkItemStatusEvent.daily_report_id.in_(daily_report_ids))
            .order_by(WorkItemStatusEvent.recorded_at, WorkItemStatusEvent.id)
        )
        return list(events)

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

    async def list_confirmed_team_reports(
        self, team_ids: list[str], week_start: date, week_end: date
    ) -> list[WeeklyReport]:
        if not team_ids:
            return []
        reports = await self.session.scalars(
            select(WeeklyReport)
            .where(
                WeeklyReport.team_id.in_(team_ids),
                WeeklyReport.scope == ReportScope.TEAM,
                WeeklyReport.status == WeeklyReportStatus.CONFIRMED,
                WeeklyReport.week_start == week_start,
                WeeklyReport.week_end == week_end,
            )
            .order_by(WeeklyReport.team_id, WeeklyReport.id)
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

    async def find_multiteam_report(
        self, tenant_id: str, team_ids: list[str], week_start: date
    ) -> WeeklyReport | None:
        selected = sorted(set(team_ids))
        if not selected:
            return None
        candidate_ids = (
            select(WeeklyReportTeam.weekly_report_id)
            .join(Team, Team.id == WeeklyReportTeam.team_id)
            .where(
                WeeklyReportTeam.team_id.in_(selected),
                Team.tenant_id == tenant_id,
            )
            .group_by(WeeklyReportTeam.weekly_report_id)
            .having(func.count(WeeklyReportTeam.team_id) == len(selected))
            .subquery()
        )
        return await self.session.scalar(
            select(WeeklyReport)
            .join(
                candidate_ids,
                candidate_ids.c.weekly_report_id == WeeklyReport.id,
            )
            .where(
                WeeklyReport.scope == ReportScope.MULTI_TEAM,
                WeeklyReport.team_id.is_(None),
                WeeklyReport.week_start == week_start,
                ~WeeklyReport.id.in_(
                    select(WeeklyReportTeam.weekly_report_id).where(
                        ~WeeklyReportTeam.team_id.in_(selected)
                    )
                ),
            )
            .order_by(WeeklyReport.created_at.desc())
        )

    async def get_by_id(self, report_id: str, team_id: str | None) -> WeeklyReport | None:
        query = select(WeeklyReport).where(WeeklyReport.id == report_id)
        query = query.where(
            WeeklyReport.team_id == team_id
            if team_id is not None
            else WeeklyReport.team_id.is_(None)
        )
        return await self.session.scalar(query)

    async def list_report_team_ids(self, report_id: str) -> list[str]:
        team_ids = await self.session.scalars(
            select(WeeklyReportTeam.team_id)
            .where(WeeklyReportTeam.weekly_report_id == report_id)
            .order_by(WeeklyReportTeam.team_id)
        )
        return list(team_ids)

    async def save_generated(
        self,
        report: WeeklyReport,
        team_ids: list[str],
        references: tuple[EvidenceReference, ...],
    ) -> WeeklyReport:
        self.session.add(report)
        await self.session.flush()
        self.session.add_all(
            [
                WeeklyReportTeam(
                    id=str(uuid.uuid4()),
                    weekly_report_id=report.id,
                    team_id=team_id,
                )
                for team_id in sorted(set(team_ids))
            ]
        )
        self.session.add_all(
            [
                ReportEvidenceLink(
                    id=str(uuid.uuid4()),
                    weekly_report_id=report.id,
                    source_type=reference.source_type,
                    source_id=reference.source_id,
                    team_id=reference.team_id,
                    project_id=reference.project_id,
                    recorded_at=reference.recorded_at,
                )
                for reference in references
            ]
        )
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def save_revision(
        self, report: WeeklyReport, team_ids: list[str], supersedes_id: str
    ) -> WeeklyReport:
        source_links = list(
            await self.session.scalars(
                select(ReportEvidenceLink).where(
                    ReportEvidenceLink.weekly_report_id == supersedes_id
                )
            )
        )
        references = tuple(
            EvidenceReference(
                source_type=link.source_type,
                source_id=link.source_id,
                team_id=link.team_id,
                project_id=link.project_id,
                recorded_at=link.recorded_at,
            )
            for link in source_links
        )
        return await self.save_generated(report, team_ids, references)

    async def save(self, report: WeeklyReport) -> WeeklyReport:
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)
        return report
