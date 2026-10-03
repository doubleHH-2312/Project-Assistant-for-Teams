from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from project_assistant.core.config import get_settings
from project_assistant.modules.audit.models import (
    ActionInvocation,
    InvocationStatus,
    WorkItemStatusEvent,
)
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.memberships.models import TeamMembership, TeamRole
from project_assistant.modules.model_registry import (  # noqa: F401
    NotificationLog,
    Project,
    ReportTemplate,
    Team,
    User,
    WeeklyReport,
    WorkItem,
)
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
    tenant_id = "tenant-demo"
    team = Team(
        id="team-ops",
        tenant_id=tenant_id,
        name="Mock Ops Team",
        timezone="Asia/Ho_Chi_Minh",
        weekly_report_day=4,
    )
    platform_team = Team(
        id="team-platform",
        tenant_id=tenant_id,
        name="Mock Platform Team",
        timezone="Asia/Ho_Chi_Minh",
        weekly_report_day=4,
    )
    users = [
        User(
            id="user-lead",
            tenant_id=tenant_id,
            external_user_id="entra-lead",
            name="Lan Lead",
            email="lead@example.test",
        ),
        User(
            id="user-pm",
            tenant_id=tenant_id,
            external_user_id="entra-pm",
            name="Phuong PM",
            email="pm@example.test",
        ),
    ]
    members = [
        User(
            id=f"user-member-{index}",
            tenant_id=tenant_id,
            external_user_id=f"entra-member-{index}",
            name=f"Member {index}",
            email=f"member{index}@example.test",
        )
        for index in range(1, 6)
    ]
    users.extend(members)
    platform_member = User(
        id="user-member-6",
        tenant_id=tenant_id,
        external_user_id="entra-member-6",
        name="Member 6",
        email="member6@example.test",
    )
    users.append(platform_member)
    memberships = [
        TeamMembership(
            id="membership-lead-ops",
            user_id="user-lead",
            team_id=team.id,
            role=TeamRole.TECH_LEAD,
        ),
        TeamMembership(
            id="membership-lead-platform",
            user_id="user-lead",
            team_id=platform_team.id,
            role=TeamRole.TECH_LEAD,
        ),
        TeamMembership(
            id="membership-pm-ops",
            user_id="user-pm",
            team_id=team.id,
            role=TeamRole.PM,
        ),
        TeamMembership(
            id="membership-pm-platform",
            user_id="user-pm",
            team_id=platform_team.id,
            role=TeamRole.PM,
        ),
        *[
            TeamMembership(
                id=f"membership-member-{index}-ops",
                user_id=f"user-member-{index}",
                team_id=team.id,
                role=TeamRole.MEMBER,
            )
            for index in range(1, 6)
        ],
        TeamMembership(
            id="membership-member-1-platform",
            user_id="user-member-1",
            team_id=platform_team.id,
            role=TeamRole.MEMBER,
        ),
        TeamMembership(
            id="membership-member-6-platform",
            user_id=platform_member.id,
            team_id=platform_team.id,
            role=TeamRole.MEMBER,
        ),
    ]
    project = Project(
        id="project-mvp",
        team_id=team.id,
        name="Project Assistant MVP",
        status="ACTIVE",
        start_date=today - timedelta(days=14),
        target_date=today + timedelta(days=14),
    )
    projects = [
        project,
        Project(
            id="project-client-delivery",
            team_id=team.id,
            name="Client Delivery",
            status="ACTIVE",
            start_date=today - timedelta(days=7),
            target_date=today + timedelta(days=21),
        ),
        Project(
            id="project-platform-core",
            team_id=platform_team.id,
            name="Platform Core",
            status="ACTIVE",
            start_date=today - timedelta(days=21),
            target_date=today + timedelta(days=30),
        ),
        Project(
            id="project-platform-automation",
            team_id=platform_team.id,
            name="Platform Automation",
            status="ACTIVE",
            start_date=today - timedelta(days=10),
            target_date=today + timedelta(days=25),
        ),
    ]
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
    work_items.extend(
        [
            WorkItem(
                id="work-item-client-01",
                project_id="project-client-delivery",
                code="CLIENT-001",
                title="Prepare client reporting workflow",
                owner_id=members[0].id,
                status=WorkStatus.IN_PROGRESS.value,
                priority=2,
                planned_end_date=today + timedelta(days=8),
            ),
            WorkItem(
                id="work-item-client-02",
                project_id="project-client-delivery",
                code="CLIENT-002",
                title="Validate client report template",
                owner_id=members[1].id,
                status=WorkStatus.NOT_STARTED.value,
                priority=3,
                planned_end_date=today + timedelta(days=12),
            ),
            WorkItem(
                id="work-item-platform-01",
                project_id="project-platform-core",
                code="PLAT-001",
                title="Build shared platform capability",
                owner_id=platform_member.id,
                status=WorkStatus.IN_PROGRESS.value,
                priority=1,
                planned_end_date=today + timedelta(days=9),
            ),
            WorkItem(
                id="work-item-automation-01",
                project_id="project-platform-automation",
                code="AUTO-001",
                title="Automate report validation",
                owner_id=members[0].id,
                status=WorkStatus.NOT_STARTED.value,
                priority=2,
                planned_end_date=today + timedelta(days=15),
            ),
        ]
    )
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
    platform_member_template = ReportTemplate(
        id="template-platform-member-v1",
        team_id=platform_team.id,
        name="default-member",
        scope=ReportScope.MEMBER,
        version=1,
        schema_json=template_schema,
        active=True,
    )
    platform_team_template = ReportTemplate(
        id="template-platform-team-v1",
        team_id=platform_team.id,
        name="default-team",
        scope=ReportScope.TEAM,
        version=1,
        schema_json=template_schema,
        active=True,
    )
    # Models deliberately avoid ORM relationships, so establish FK layers explicitly.
    session.add_all([team, platform_team])
    session.flush()
    session.add_all(users)
    session.flush()
    session.add_all(memberships)
    session.flush()
    session.add_all(projects)
    session.flush()
    session.add_all(
        [
            *work_items,
            member_template,
            team_template,
            platform_member_template,
            platform_team_template,
        ]
    )
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
                    team_id=team.id,
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
                team_id=team.id,
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
                team_id=team.id,
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
    session.flush()

    invocation_rows: list[ActionInvocation] = []
    status_events: list[WorkItemStatusEvent] = []
    prior_event_by_work_item: dict[tuple[str, str], str] = {}
    team_timezone = ZoneInfo(team.timezone)
    for report in reports:
        invocation_id = f"seed-invocation-{report.id}"
        event_id = f"seed-event-{report.id}"
        local_datetime = datetime.combine(
            report.report_date,
            time(hour=9),
            tzinfo=team_timezone,
        )
        recorded_at = local_datetime.astimezone(UTC)
        invocation_rows.append(
            ActionInvocation(
                id=invocation_id,
                action="daily",
                actor_id=report.user_id,
                tenant_id=tenant_id,
                team_id=report.team_id,
                project_id=report.project_id,
                conversation_id="seed:demo",
                conversation_type="SEED",
                triggered_at=recorded_at,
                local_datetime=local_datetime,
                local_date=report.report_date,
                timezone=team.timezone,
                correlation_id=f"seed-{report.id}",
                idempotency_key=f"seed-{report.id}",
                status=InvocationStatus.SUCCEEDED,
                result_ref=report.id,
                metadata_json={"seed": True},
                completed_at=recorded_at,
            )
        )
        event_key = (report.user_id, report.work_item_id)
        status_events.append(
            WorkItemStatusEvent(
                id=event_id,
                daily_report_id=report.id,
                action_invocation_id=invocation_id,
                team_id=report.team_id,
                project_id=report.project_id,
                work_item_id=report.work_item_id,
                user_id=report.user_id,
                status=report.status,
                effective_blocker=report.effective_blocker,
                business_date=report.report_date,
                recorded_at=recorded_at,
                local_datetime=local_datetime,
                local_date=report.report_date,
                timezone=team.timezone,
                source="SEED",
                supersedes_event_id=prior_event_by_work_item.get(event_key),
            )
        )
        prior_event_by_work_item[event_key] = event_id
    session.add_all(invocation_rows)
    session.flush()
    session.add_all(status_events)

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
