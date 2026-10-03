from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from project_assistant.core.errors import AppError
from project_assistant.modules.actions.contracts import (
    ActionContext,
    ActionDefinition,
    ActionResult,
    ConversationContext,
)
from project_assistant.modules.daily_reports.models import DailyReport, WorkStatus
from project_assistant.modules.daily_reports.schemas import DailyHistoryFilters
from project_assistant.modules.daily_reports.service import ActorIdentity
from project_assistant.modules.memberships.service import Permission


class HistoryActionInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    team_id: str | None = Field(default=None, alias="teamId")
    project_id: str | None = Field(default=None, alias="projectId")
    date_from: date | None = Field(default=None, alias="dateFrom")
    date_to: date | None = Field(default=None, alias="dateTo")
    status: WorkStatus | None = None


@dataclass(frozen=True)
class _Actor:
    id: str


class HistoryService(Protocol):
    async def list_history(
        self, actor: ActorIdentity, filters: DailyHistoryFilters
    ) -> list[DailyReport]: ...


class HistoryActionHandler:
    definition = ActionDefinition(
        name="history",
        aliases=("daily-history",),
        allowed_contexts=frozenset(ConversationContext),
        required_permission=Permission.VIEW_OWN_HISTORY,
        input_schema=HistoryActionInput,
    )

    def __init__(
        self,
        service: HistoryService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.service = service
        self.clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self, context: ActionContext, payload: BaseModel
    ) -> ActionResult:
        if not isinstance(payload, HistoryActionInput):
            raise TypeError("HistoryActionHandler requires HistoryActionInput")
        team_id = context.current_team_id or payload.team_id
        if team_id is None:
            return ActionResult(
                kind="team_selection",
                message="Select a Team to view history.",
                data={"action": "history"},
            )
        date_to = payload.date_to or self.clock().astimezone(
            ZoneInfo(context.timezone)
        ).date()
        date_from = payload.date_from or first_of_reporting_days(date_to, 7)
        if date_from > date_to:
            raise AppError(422, "HISTORY_DATE_RANGE_INVALID", "Date range is invalid")
        reports = await self.service.list_history(
            _Actor(context.actor_id),
            DailyHistoryFilters(
                team_id=team_id,
                project_id=payload.project_id,
                date_from=date_from,
                date_to=date_to,
                status=payload.status,
            ),
        )
        return ActionResult(
            kind="history",
            message="Daily Report history.",
            data={"teamId": team_id, "dates": group_history(reports)},
        )


def first_of_reporting_days(last_date: date, count: int) -> date:
    current = last_date
    found = 0
    while True:
        if current.weekday() < 5:
            found += 1
            if found == count:
                return current
        current -= timedelta(days=1)


def group_history(reports: list[DailyReport]) -> list[dict[str, Any]]:
    grouped: dict[date, dict[str, dict[str, list[DailyReport]]]] = {}
    for report in reports:
        grouped.setdefault(report.report_date, {}).setdefault(
            report.project_id, {}
        ).setdefault(report.work_item_id, []).append(report)
    dates: list[dict[str, Any]] = []
    for report_date in sorted(grouped, reverse=True):
        projects: list[dict[str, Any]] = []
        for project_id in sorted(grouped[report_date]):
            work_items = [
                {
                    "workItemId": work_item_id,
                    "reports": [
                        {
                            "id": report.id,
                            "status": report.status.value,
                            "workSummary": report.work_summary,
                            "effectiveBlocker": report.effective_blocker,
                            "nextAction": report.next_action,
                        }
                        for report in grouped[report_date][project_id][work_item_id]
                    ],
                }
                for work_item_id in sorted(grouped[report_date][project_id])
            ]
            projects.append({"projectId": project_id, "workItems": work_items})
        dates.append({"date": report_date.isoformat(), "projects": projects})
    return dates
