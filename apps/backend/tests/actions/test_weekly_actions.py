from datetime import date
from importlib import import_module

import pytest

from project_assistant.modules.actions.contracts import (
    ActionContext,
    ConversationContext,
    ConversationType,
)
from project_assistant.modules.weekly_reports.models import (
    ReportScope,
    WeeklyReport,
    WeeklyReportStatus,
)


def _weekly_handlers():  # type: ignore[no-untyped-def]
    try:
        return import_module("project_assistant.modules.actions.handlers.weekly")
    except ModuleNotFoundError:
        pytest.fail("Weekly action handlers are not implemented")


class RecordingWeeklyService:
    def __init__(self) -> None:
        self.calls = []

    async def generate(self, actor, request):  # type: ignore[no-untyped-def]
        self.calls.append((actor, request))
        return WeeklyReport(
            id="weekly-1",
            scope=request.scope,
            subject_user_id=(actor.id if request.scope == ReportScope.MEMBER else None),
            team_id=request.team_id,
            week_start=request.week_start,
            week_end=date(2026, 10, 2),
            content_json={"projects": []},
            missing_contributors=[],
            input_record_ids=[],
            generation_source="MOCK",
            generation_metadata={},
            status=WeeklyReportStatus.GENERATED,
            template_id="template-1",
            template_version=1,
            created_by=actor.id,
        )


def _context(conversation_type: ConversationType) -> ActionContext:
    return ActionContext(
        actor_id="user-1",
        tenant_id="tenant-1",
        conversation_id="conversation-1",
        conversation_type=conversation_type,
        current_team_id=None,
        correlation_id="correlation-1",
        idempotency_key="activity-1:weekly",
        timezone="Asia/Ho_Chi_Minh",
    )


@pytest.mark.asyncio
async def test_member_and_team_weekly_actions_create_private_drafts() -> None:
    module = _weekly_handlers()
    service = RecordingWeeklyService()
    member_handler = module.MemberWeeklyActionHandler(service)
    team_handler = module.TeamWeeklyActionHandler(service)

    member = await member_handler.execute(
        _context(ConversationType.PERSONAL),
        module.WeeklyActionInput(teamId="team-1", weekStart=date(2026, 9, 28)),
    )
    team = await team_handler.execute(
        _context(ConversationType.TEAM_CHANNEL),
        module.WeeklyActionInput(teamId="team-1", weekStart=date(2026, 9, 28)),
    )

    assert [call[1].scope for call in service.calls] == [
        ReportScope.MEMBER,
        ReportScope.TEAM,
    ]
    assert member.kind == "weekly_draft"
    assert team.kind == "weekly_team_draft"
    assert member.private is True
    assert team.private is True
    assert member.result_ref == "weekly-1"


@pytest.mark.asyncio
async def test_multiteam_action_accepts_only_personal_context_and_selected_teams() -> None:
    module = _weekly_handlers()
    service = RecordingWeeklyService()
    handler = module.MultiTeamWeeklyActionHandler(service)

    result = await handler.execute(
        _context(ConversationType.PERSONAL),
        module.MultiTeamWeeklyActionInput(
            teamIds=["team-b", "team-a"], weekStart=date(2026, 9, 28)
        ),
    )

    assert handler.definition.allowed_contexts == frozenset(
        {ConversationContext.PERSONAL}
    )
    assert service.calls[0][1].team_ids == ["team-a", "team-b"]
    assert service.calls[0][1].scope == ReportScope.MULTI_TEAM
    assert result.kind == "weekly_multi_team_draft"
    assert result.private is True
