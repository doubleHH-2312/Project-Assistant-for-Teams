from dataclasses import dataclass
from datetime import date
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from project_assistant.modules.actions.contracts import (
    ActionContext,
    ActionDefinition,
    ActionResult,
    ConversationContext,
)
from project_assistant.modules.memberships.service import Permission
from project_assistant.modules.weekly_reports.models import ReportScope, WeeklyReport
from project_assistant.modules.weekly_reports.schemas import WeeklyGenerateRequest
from project_assistant.modules.weekly_reports.service import WeeklyActor


class WeeklyActionInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    team_id: str | None = Field(default=None, alias="teamId")
    week_start: date | None = Field(default=None, alias="weekStart")


class MultiTeamWeeklyActionInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    team_ids: list[str] = Field(default_factory=list, alias="teamIds")
    week_start: date | None = Field(default=None, alias="weekStart")


@dataclass(frozen=True)
class _Actor:
    id: str
    tenant_id: str


class WeeklyGenerationService(Protocol):
    async def generate(
        self, actor: WeeklyActor, request: WeeklyGenerateRequest
    ) -> WeeklyReport: ...


class _SingleTeamWeeklyActionHandler:
    scope: ReportScope
    result_kind: str
    definition: ActionDefinition

    def __init__(self, service: WeeklyGenerationService) -> None:
        self.service = service

    async def execute(self, context: ActionContext, payload: BaseModel) -> ActionResult:
        if not isinstance(payload, WeeklyActionInput):
            raise TypeError("Weekly action requires WeeklyActionInput")
        team_id = context.current_team_id or payload.team_id
        if team_id is None:
            return ActionResult(
                kind="team_selection",
                message="Select a Team to continue.",
                data={"action": self.definition.name},
            )
        if payload.week_start is None:
            return ActionResult(
                kind="form",
                message="Select the Monday for the reporting week.",
                data={"action": self.definition.name, "teamId": team_id},
            )
        report = await self.service.generate(
            _Actor(context.actor_id, context.tenant_id),
            WeeklyGenerateRequest(
                team_id=team_id,
                scope=self.scope,
                week_start=payload.week_start,
            ),
        )
        return _draft_result(self.result_kind, report)


class MemberWeeklyActionHandler(_SingleTeamWeeklyActionHandler):
    scope = ReportScope.MEMBER
    result_kind = "weekly_draft"
    definition = ActionDefinition(
        name="weekly",
        aliases=("weekly-member",),
        allowed_contexts=frozenset(ConversationContext),
        required_permission=Permission.GENERATE_OWN_WEEKLY,
        input_schema=WeeklyActionInput,
    )


class TeamWeeklyActionHandler(_SingleTeamWeeklyActionHandler):
    scope = ReportScope.TEAM
    result_kind = "weekly_team_draft"
    definition = ActionDefinition(
        name="weekly-team",
        aliases=("team-weekly",),
        allowed_contexts=frozenset(ConversationContext),
        required_permission=Permission.GENERATE_TEAM_WEEKLY,
        input_schema=WeeklyActionInput,
    )


class MultiTeamWeeklyActionHandler:
    definition = ActionDefinition(
        name="weekly-multi-team",
        aliases=("multi-team-weekly",),
        allowed_contexts=frozenset({ConversationContext.PERSONAL}),
        required_permission=Permission.GENERATE_MULTI_TEAM_WEEKLY,
        input_schema=MultiTeamWeeklyActionInput,
    )

    def __init__(self, service: WeeklyGenerationService) -> None:
        self.service = service

    async def execute(self, context: ActionContext, payload: BaseModel) -> ActionResult:
        if not isinstance(payload, MultiTeamWeeklyActionInput):
            raise TypeError("Multi-team weekly action requires MultiTeamWeeklyActionInput")
        team_ids = sorted(set(payload.team_ids))
        if len(team_ids) < 2 or payload.week_start is None:
            return ActionResult(
                kind="form",
                message="Select at least two Teams and a reporting week.",
                data={"action": self.definition.name, "teamIds": team_ids},
            )
        report = await self.service.generate(
            _Actor(context.actor_id, context.tenant_id),
            WeeklyGenerateRequest(
                team_ids=team_ids,
                scope=ReportScope.MULTI_TEAM,
                week_start=payload.week_start,
            ),
        )
        return _draft_result("weekly_multi_team_draft", report)


def _draft_result(kind: str, report: WeeklyReport) -> ActionResult:
    return ActionResult(
        kind=kind,
        message="Weekly Report draft generated. Review and confirm it before publishing.",
        result_ref=report.id,
        data={
            "reportId": report.id,
            "scope": report.scope.value,
            "teamId": report.team_id,
            "weekStart": report.week_start.isoformat(),
            "weekEnd": report.week_end.isoformat(),
            "content": report.content_json,
            "missingContributors": report.missing_contributors,
            "status": report.status.value,
        },
        private=True,
    )
