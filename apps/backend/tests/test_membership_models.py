from datetime import UTC, datetime
from importlib import import_module

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from project_assistant.core.database import Base
from project_assistant.modules.teams.models import Team
from project_assistant.modules.users.models import User


def _membership_types():  # type: ignore[no-untyped-def]
    try:
        module = import_module("project_assistant.modules.memberships.models")
    except ModuleNotFoundError:
        pytest.fail("Team Membership model is not implemented")
    return module.TeamMembership, module.TeamRole


def test_membership_roles_are_team_scoped_and_unique() -> None:
    team_membership, team_role = _membership_types()

    assert {role.value for role in team_role} == {"MEMBER", "TECH_LEAD", "PM"}

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        team = Team(id="team-1", tenant_id="tenant-1", name="Platform")
        user = User(
            id="user-1",
            tenant_id="tenant-1",
            external_user_id="entra-user-1",
            name="Member",
            email="member@example.test",
            role="MEMBER",
            team_id=team.id,
        )
        session.add_all([team, user])
        session.flush()
        session.add(
            team_membership(
                id="membership-1",
                user_id=user.id,
                team_id=team.id,
                role=team_role.MEMBER,
                joined_at=datetime(2026, 10, 2, tzinfo=UTC),
            )
        )
        session.commit()
        session.add(
            team_membership(
                id="membership-2",
                user_id=user.id,
                team_id=team.id,
                role=team_role.PM,
                joined_at=datetime(2026, 10, 2, tzinfo=UTC),
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()
    engine.dispose()


def test_team_defaults_to_seven_day_backfill_window() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        team = Team(id="team-1", tenant_id="tenant-1", name="Platform")
        session.add(team)
        session.flush()

        assert team.backfill_window_days == 7
    engine.dispose()
