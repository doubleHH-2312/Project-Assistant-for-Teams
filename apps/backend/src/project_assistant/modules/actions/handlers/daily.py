from dataclasses import dataclass
from datetime import date
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from project_assistant.core.errors import AppError
from project_assistant.modules.actions.contracts import (
    ActionContext,
    ActionDefinition,
    ActionResult,
    ConversationContext,
)
from project_assistant.modules.audit.models import RequestAuditContext
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.daily_reports.schemas import DailyReportCreate
from project_assistant.modules.daily_reports.service import ActorIdentity
from project_assistant.modules.memberships.service import Permission


class DailyActionInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    team_id: str | None = Field(default=None, alias="teamId")
    project_id: str | None = Field(default=None, alias="projectId")
    work_item_id: str | None = Field(default=None, alias="workItemId")
    report_date: date | None = Field(default=None, alias="reportDate")
    status: WorkStatus | None = None
    work_summary: str | None = Field(
        default=None, alias="workSummary", min_length=1, max_length=4000
    )
    blocker: str | None = Field(default=None, max_length=4000)
    next_action: str | None = Field(
        default=None, alias="nextAction", min_length=1, max_length=2000
    )


@dataclass(frozen=True)
class _Actor:
    id: str


class DailySubmitService(Protocol):
    async def get_form_options(
        self, actor: ActorIdentity, team_id: str
    ) -> dict[str, list[dict[str, str]]]: ...

    async def create(
        self,
        actor: ActorIdentity,
        team_id: str,
        request: DailyReportCreate,
        audit: RequestAuditContext,
    ) -> DailyReport: ...


class DailyActionHandler:
    definition = ActionDefinition(
        name="daily",
        aliases=("report-daily",),
        allowed_contexts=frozenset(ConversationContext),
        required_permission=Permission.SUBMIT_OWN_DAILY,
        input_schema=DailyActionInput,
    )

    def __init__(self, service: DailySubmitService) -> None:
        self.service = service

    async def execute(
        self, context: ActionContext, payload: BaseModel
    ) -> ActionResult:
        if not isinstance(payload, DailyActionInput):
            raise TypeError("DailyActionHandler requires DailyActionInput")
        team_id = context.current_team_id or payload.team_id
        if context.current_team_id and payload.team_id not in {
            None,
            context.current_team_id,
        }:
            raise AppError(422, "TEAM_SCOPE_MISMATCH", "Payload Team does not match scope")
        if team_id is None:
            return ActionResult(
                kind="team_selection",
                message="Select a Team to continue.",
                data={"action": "daily"},
            )
        required = {
            "projectId": payload.project_id,
            "workItemId": payload.work_item_id,
            "status": payload.status,
            "workSummary": payload.work_summary,
            "nextAction": payload.next_action,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            options = await self.service.get_form_options(_Actor(context.actor_id), team_id)
            return ActionResult(
                kind="form",
                message="Complete the Daily Report form.",
                data={
                    "action": "daily",
                    "teamId": team_id,
                    "requiredFields": missing,
                    **options,
                },
            )
        assert payload.project_id is not None
        assert payload.work_item_id is not None
        assert payload.status is not None
        assert payload.work_summary is not None
        assert payload.next_action is not None
        request = DailyReportCreate(
            team_id=team_id,
            project_id=payload.project_id,
            work_item_id=payload.work_item_id,
            report_date=payload.report_date,
            status=payload.status,
            work_summary=payload.work_summary,
            blocker=payload.blocker,
            next_action=payload.next_action,
        )
        report = await self.service.create(
            _Actor(context.actor_id),
            team_id,
            request,
            RequestAuditContext(
                action=self.definition.name,
                actor_id=context.actor_id,
                tenant_id=context.tenant_id,
                team_id=team_id,
                project_id=payload.project_id,
                conversation_id=context.conversation_id,
                conversation_type=context.conversation_type.value,
                timezone=context.timezone,
                correlation_id=context.correlation_id,
                idempotency_key=context.idempotency_key,
                source=context.source,
                metadata={"command": self.definition.name},
            ),
        )
        return ActionResult(
            kind="daily_saved",
            message="Daily Report saved.",
            result_ref=report.id,
            data={
                "teamId": report.team_id,
                "reportDate": report.report_date.isoformat(),
                "status": report.status.value,
            },
        )
