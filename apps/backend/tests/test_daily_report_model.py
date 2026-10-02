from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from project_assistant.core.database import Base
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.projects.models import Project
from project_assistant.modules.teams.models import Team
from project_assistant.modules.users.models import User
from project_assistant.modules.work_items.models import WorkItem


def test_daily_report_rejects_duplicate_user_work_item_and_date() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        team = Team(id="team-1", name="Ops", timezone="Asia/Ho_Chi_Minh")
        user = User(
            id="user-1",
            external_user_id="entra-1",
            name="Member One",
            email="member@example.test",
        )
        project = Project(id="project-1", team_id=team.id, name="MVP")
        item = WorkItem(id="item-1", project_id=project.id, code="OPS-001", title="Build")
        session.add_all([team, user, project, item])
        session.commit()

        first = DailyReport(
            id="report-1",
            team_id=team.id,
            user_id=user.id,
            project_id=project.id,
            work_item_id=item.id,
            report_date=date(2026, 10, 1),
            status=WorkStatus.IN_PROGRESS,
            work_summary="First",
            next_action="Continue",
        )
        duplicate = DailyReport(
            id="report-2",
            team_id=team.id,
            user_id=user.id,
            project_id=project.id,
            work_item_id=item.id,
            report_date=date(2026, 10, 1),
            status=WorkStatus.DONE,
            work_summary="Duplicate",
            next_action="None",
        )
        session.add(first)
        session.commit()
        session.add(duplicate)

        with pytest.raises(IntegrityError):
            session.commit()

    engine.dispose()


def test_blocked_report_uses_summary_as_effective_blocker_without_mutating_raw_value() -> None:
    report = DailyReport(
        team_id="team-1",
        user_id="user-1",
        project_id="project-1",
        work_item_id="item-1",
        report_date=date(2026, 10, 1),
        status=WorkStatus.BLOCKED,
        work_summary="Waiting for approved sample data",
        blocker=None,
        next_action="Resume when data arrives",
    )

    assert report.blocker is None
    assert report.effective_blocker == "Waiting for approved sample data"
