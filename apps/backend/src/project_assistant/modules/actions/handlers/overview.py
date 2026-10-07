from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from project_assistant.modules.actions.contracts import (
    ActionContext,
    ActionDefinition,
    ActionResult,
    ConversationContext,
)
from project_assistant.modules.memberships.service import Permission
from project_assistant.modules.teams.overview import TeamOverview


class DailySummaryActionInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    team_id: str | None = Field(default=None, alias="teamId")
    reporting_date: date | None = Field(default=None, alias="reportingDate")


class OverviewService(Protocol):
    async def get_overview(self, team_id: str, reporting_date: date) -> TeamOverview: ...


class DailySummaryActionHandler:
    definition = ActionDefinition(
        name="daily-summary",
        aliases=("summary",),
        allowed_contexts=frozenset(ConversationContext),
        required_permission=Permission.VIEW_TEAM_DAILY_SUMMARY,
        input_schema=DailySummaryActionInput,
    )

    def __init__(
        self,
        service: OverviewService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.service = service
        self.clock = clock or (lambda: datetime.now(UTC))

    async def execute(self, context: ActionContext, payload: BaseModel) -> ActionResult:
        if not isinstance(payload, DailySummaryActionInput):
            raise TypeError("DailySummaryActionHandler requires DailySummaryActionInput")
        team_id = context.current_team_id or payload.team_id
        if team_id is None:
            return ActionResult(
                kind="team_selection",
                message="Select a Team to view its Daily Summary.",
                data={"action": "daily-summary"},
            )
        reporting_date = (
            payload.reporting_date or self.clock().astimezone(ZoneInfo(context.timezone)).date()
        )
        overview = await self.service.get_overview(team_id, reporting_date)
        return ActionResult(
            kind="daily_summary",
            message="Team Daily Summary.",
            data=overview.model_dump(by_alias=True, mode="json"),
        )
