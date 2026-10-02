from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from project_assistant.core.database import Base
from project_assistant.modules.notifications.models import NotificationLog
from project_assistant.modules.teams.models import Team
from project_assistant.modules.templates.models import ReportTemplate
from project_assistant.modules.users.models import User
from project_assistant.modules.weekly_reports.models import (
    ReportScope,
    WeeklyReport,
    WeeklyReportStatus,
)


def test_notification_delivery_is_unique_per_user_type_and_target_date() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        team = Team(id="team-1", name="Ops")
        user = User(
            id="user-1",
            external_user_id="entra-1",
            name="Member",
            email="member@example.test",
        )
        session.add_all([team, user])
        session.commit()
        session.add(
            NotificationLog(
                user_id=user.id,
                type="DAILY_REMINDER",
                target_date=date(2026, 10, 1),
                delivery_status="SENT",
                correlation_id="corr-1",
            )
        )
        session.commit()
        session.add(
            NotificationLog(
                user_id=user.id,
                type="DAILY_REMINDER",
                target_date=date(2026, 10, 1),
                delivery_status="RETRYING",
                correlation_id="corr-2",
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()
    engine.dispose()


def test_weekly_report_preserves_scope_template_and_source_ids() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        team = Team(id="team-1", name="Ops")
        user = User(
            id="user-1",
            external_user_id="entra-1",
            name="Member",
            email="member@example.test",
        )
        template = ReportTemplate(
            id="template-1",
            team_id=team.id,
            name="default-member",
            scope=ReportScope.MEMBER,
            version=1,
            schema_json={"type": "object"},
            active=True,
        )
        report = WeeklyReport(
            id="weekly-1",
            scope=ReportScope.MEMBER,
            subject_user_id=user.id,
            team_id=team.id,
            week_start=date(2026, 9, 28),
            week_end=date(2026, 10, 2),
            content_json={"completed": ["OPS-001"]},
            missing_contributors=[],
            input_record_ids=["daily-1"],
            generation_source="MOCK_LLM",
            generation_metadata={"provider": "mock"},
            status=WeeklyReportStatus.GENERATED,
            template_id=template.id,
            template_version=template.version,
            created_by=user.id,
        )
        session.add_all([team, user, template, report])
        session.commit()

        stored = session.scalar(select(WeeklyReport).where(WeeklyReport.id == report.id))
        assert stored is not None
        assert stored.scope == ReportScope.MEMBER
        assert stored.input_record_ids == ["daily-1"]
        assert stored.template_version == 1
    engine.dispose()
