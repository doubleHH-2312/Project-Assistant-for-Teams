from datetime import date

import pytest

from project_assistant.modules.actions.contracts import (
    ActionContext,
    ActionDefinition,
    ConversationContext,
    ConversationType,
)
from project_assistant.modules.actions.handlers.help import HelpActionHandler, HelpActionInput
from project_assistant.modules.actions.handlers.overview import (
    DailySummaryActionHandler,
    DailySummaryActionInput,
)
from project_assistant.modules.actions.registry import ActionRegistry
from project_assistant.modules.memberships.service import Permission
from project_assistant.modules.teams.overview import (
    ActiveBlocker,
    Coverage,
    ReporterSummary,
    TeamOverview,
)


class RecordingOverviewService:
    async def get_overview(self, team_id: str, reporting_date: date) -> TeamOverview:
        return TeamOverview(
            reportingDate=reporting_date,
            coverage=Coverage(submitted=1, expected=2, percentage=50),
            missingReporters=[ReporterSummary(id="user-2", name="Member Two")],
            statusCounts={"BLOCKED": 1},
            blockers=[
                ActiveBlocker(
                    reportId="daily-1",
                    userId="user-1",
                    projectId="project-1",
                    workItemId="item-1",
                    effectiveBlocker="Waiting for access",
                    blockedSince=date(2026, 10, 1),
                    ageDays=3,
                    nextAction="Escalate",
                )
            ],
        )


class FakeHelpAuthorization:
    def __init__(self, permissions: set[Permission]) -> None:
        self.permissions = permissions

    async def list_permissions(self, actor_id: str) -> frozenset[Permission]:
        assert actor_id == "user-1"
        return frozenset(self.permissions)


class DefinitionOnlyHandler:
    def __init__(self, name: str, permission: Permission | None) -> None:
        self.definition = ActionDefinition(
            name=name,
            aliases=(),
            allowed_contexts=frozenset(ConversationContext),
            required_permission=permission,
            input_schema=HelpActionInput,
        )

    async def execute(self, context, payload):  # type: ignore[no-untyped-def]
        raise AssertionError("not executed")


def context() -> ActionContext:
    return ActionContext(
        actor_id="user-1",
        tenant_id="tenant-1",
        conversation_id="conversation-1",
        conversation_type=ConversationType.PERSONAL,
        current_team_id=None,
        correlation_id="correlation-1",
        idempotency_key="activity-1:summary",
        timezone="UTC",
    )


@pytest.mark.asyncio
async def test_daily_summary_exposes_exact_blocker_event_date() -> None:
    handler = DailySummaryActionHandler(RecordingOverviewService())  # type: ignore[arg-type]

    result = await handler.execute(
        context(),
        DailySummaryActionInput(teamId="team-1", reportingDate=date(2026, 10, 3)),
    )

    blocker = result.data["blockers"][0]
    assert blocker["blockedSince"] == "2026-10-01"
    assert blocker["projectId"] == "project-1"


@pytest.mark.asyncio
async def test_help_lists_only_actions_allowed_by_inherited_permissions() -> None:
    registry = ActionRegistry()
    registry.register(DefinitionOnlyHandler("daily", Permission.SUBMIT_OWN_DAILY))
    registry.register(DefinitionOnlyHandler("daily-summary", Permission.VIEW_TEAM_DAILY_SUMMARY))
    help_handler = HelpActionHandler(
        registry,
        FakeHelpAuthorization({Permission.SUBMIT_OWN_DAILY}),  # type: ignore[arg-type]
    )
    registry.register(help_handler)

    result = await help_handler.execute(context(), HelpActionInput())

    assert [action["name"] for action in result.data["actions"]] == ["daily", "help"]
