from datetime import date, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from project_assistant.core.config import get_settings
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.model_registry import (  # noqa: F401
    NotificationLog,
    Project,
    ReportTemplate,
    Team,
    User,
    WeeklyReport,
    WorkItem,
)
from project_assistant.modules.users.models import UserRole
from project_assistant.modules.weekly_reports.models import ReportScope, WeeklyReportStatus


def _previous_business_days(reference_date: date, count: int) -> list[date]:
    days: list[date] = []
    candidate = reference_date - timedelta(days=1)
    while len(days) < count:
        if candidate.weekday() < 5:
            days.append(candidate)
        candidate -= timedelta(days=1)
    return list(reversed(days))


def seed_database(session: Session, reference_date: date | None = None) -> None:
    if session.scalar(select(Team.id).where(Team.id == "team-ops")) is not None:
        return

    today = reference_date or date.today()
    team = Team(
        id="team-ops",
        name="Mock Ops Team",
        timezone="Asia/Ho_Chi_Minh",
        weekly_report_day=4,
    )
    users = [
        User(
            id="user-lead",
            external_user_id="entra-lead",
            name="Lan Lead",
            email="lead@example.test",
            role=UserRole.LEAD,
            team_id=team.id,
        ),
        User(
            id="user-pm",
            external_user_id="entra-pm",
            name="Phuong PM",
            email="pm@example.test",
            role=UserRole.PM,
            team_id=team.id,
        ),
    ]
    members = [
        User(
            id=f"user-member-{index}",
            external_user_id=f"entra-member-{index}",
            name=f"Member {index}",
            email=f"member{index}@example.test",
            role=UserRole.MEMBER,
            team_id=team.id,
        )
        for index in range(1, 6)
    ]
    users.extend(members)
    project = Project(
        id="project-mvp",
        team_id=team.id,
        name="Project Assistant MVP",
        status="ACTIVE",
        start_date=today - timedelta(days=14),
        target_date=today + timedelta(days=14),
    )
    statuses = [
        WorkStatus.NOT_STARTED,
        WorkStatus.IN_PROGRESS,
        WorkStatus.BLOCKED,
        WorkStatus.READY_FOR_REVIEW,
        WorkStatus.DONE,
    ]
    work_items = [
        WorkItem(
            id=f"work-item-{index:02d}",
            project_id=project.id,
            code=f"OPS-{index:03d}",
            title=f"Demo work item {index}",
            owner_id=members[(index - 1) % len(members)].id,
            status=statuses[(index - 1) % len(statuses)].value,
            priority=((index - 1) % 4) + 1,
            planned_end_date=today + timedelta(days=index),
        )
        for index in range(1, 21)
    ]
    template_schema = {
        "type": "object",
        "required": ["completed", "in_progress", "blockers", "next_week", "support_required"],
        "properties": {
            key: {"type": "array", "items": {"type": "string"}}
            for key in ["completed", "in_progress", "blockers", "next_week", "support_required"]
        },
        "additionalProperties": False,
    }
    member_template = ReportTemplate(
        id="template-member-v1",
        team_id=team.id,
        name="default-member",
        scope=ReportScope.MEMBER,
        version=1,
        schema_json=template_schema,
        active=True,
    )
    team_template = ReportTemplate(
        id="template-team-v1",
        team_id=team.id,
        name="default-team",
        scope=ReportScope.TEAM,
        version=1,
        schema_json=template_schema,
        active=True,
    )
    # Models deliberately avoid ORM relationships, so establish FK layers explicitly.
    session.add(team)
    session.flush()
    session.add_all(users)
    session.flush()
    session.add(project)
    session.flush()
    session.add_all([*work_items, member_template, team_template])
    session.flush()

    reports: list[DailyReport] = []
    prior_days = _previous_business_days(today, 5)
    for day_index, report_day in enumerate(prior_days):
        for member_index, member in enumerate(members):
            is_repeated_blocker = member_index == 0 and day_index >= 2
            is_second_blocker = member_index == 1 and day_index == 4
            status = (
                WorkStatus.BLOCKED
                if is_repeated_blocker or is_second_blocker
                else statuses[(day_index + member_index + 1) % len(statuses)]
            )
            reports.append(
                DailyReport(
                    id=f"daily-{day_index}-{member_index}",
                    user_id=member.id,
                    project_id=project.id,
                    work_item_id=work_items[member_index].id,
                    report_date=report_day,
                    status=status,
                    work_summary=(
                        "Waiting for approved sample data"
                        if status == WorkStatus.BLOCKED
                        else f"Progressed {work_items[member_index].code}"
                    ),
                    blocker=None if status == WorkStatus.BLOCKED else None,
                    next_action=f"Continue {work_items[member_index].code}",
                )
            )
    for member_index, member in enumerate(members[:3]):
        reports.append(
            DailyReport(
                id=f"daily-today-{member_index}",
                user_id=member.id,
                project_id=project.id,
                work_item_id=work_items[member_index].id,
                report_date=today,
                status=WorkStatus.IN_PROGRESS,
                work_summary=f"Today's progress on {work_items[member_index].code}",
                next_action="Continue tomorrow",
            )
        )
    for member_index in range(2):
        reports.append(
            DailyReport(
                id=f"daily-extra-{member_index}",
                user_id=members[member_index].id,
                project_id=project.id,
                work_item_id=work_items[5 + member_index].id,
                report_date=prior_days[-1],
                status=WorkStatus.READY_FOR_REVIEW,
                work_summary=f"Prepared {work_items[5 + member_index].code} for review",
                next_action="Request review",
            )
        )
    session.add_all(reports)

    week_start = prior_days[0] - timedelta(days=prior_days[0].weekday())
    weekly_reports = [
        WeeklyReport(
            id="weekly-confirmed-member-1",
            scope=ReportScope.MEMBER,
            subject_user_id=members[0].id,
            team_id=team.id,
            week_start=week_start,
            week_end=week_start + timedelta(days=4),
            content_json={"completed": ["OPS-001"], "in_progress": [], "blockers": []},
            missing_contributors=[],
            input_record_ids=[report.id for report in reports if report.user_id == members[0].id],
            generation_source="MOCK_LLM",
            generation_metadata={"provider": "mock", "seed": True},
            status=WeeklyReportStatus.CONFIRMED,
            template_id=member_template.id,
            template_version=1,
            created_by=members[0].id,
            confirmed_by=members[0].id,
        ),
        WeeklyReport(
            id="weekly-generated-member-2",
            scope=ReportScope.MEMBER,
            subject_user_id=members[1].id,
            team_id=team.id,
            week_start=week_start,
            week_end=week_start + timedelta(days=4),
            content_json={"completed": [], "in_progress": ["OPS-002"], "blockers": []},
            missing_contributors=[],
            input_record_ids=[report.id for report in reports if report.user_id == members[1].id],
            generation_source="MOCK_LLM",
            generation_metadata={"provider": "mock", "seed": True},
            status=WeeklyReportStatus.GENERATED,
            template_id=member_template.id,
            template_version=1,
            created_by=members[1].id,
        ),
    ]
    session.add_all(weekly_reports)
    session.commit()


def main() -> None:
    settings = get_settings()
    sync_url = settings.database_url.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_engine(sync_url, pool_pre_ping=True)
    with Session(engine) as session:
        seed_database(session)
    engine.dispose()


if __name__ == "__main__":
    main()
