from collections.abc import Iterable

from project_assistant.modules.actions.contracts import ActionHandler
from project_assistant.modules.actions.dispatcher import ActionDispatcher, AuthorizationPolicy
from project_assistant.modules.actions.handlers.daily import (
    DailyActionHandler,
    DailySubmitService,
)
from project_assistant.modules.actions.handlers.help import HelpActionHandler
from project_assistant.modules.actions.handlers.history import (
    HistoryActionHandler,
    HistoryService,
)
from project_assistant.modules.actions.handlers.overview import (
    DailySummaryActionHandler,
    OverviewService,
)
from project_assistant.modules.actions.handlers.weekly import (
    MemberWeeklyActionHandler,
    MultiTeamWeeklyActionHandler,
    TeamWeeklyActionHandler,
    WeeklyGenerationService,
)
from project_assistant.modules.actions.registry import ActionRegistry
from project_assistant.modules.actions.results import ActionResultStore
from project_assistant.modules.audit.service import AuditService
from project_assistant.modules.memberships.service import AuthorizationService


def build_action_registry(handlers: Iterable[ActionHandler] = ()) -> ActionRegistry:
    registry = ActionRegistry()
    for handler in handlers:
        registry.register(handler)
    return registry


def build_reporting_action_registry(
    daily_service: DailySubmitService,
    history_service: HistoryService,
    overview_service: OverviewService,
    weekly_service: WeeklyGenerationService,
    authorization: AuthorizationService,
) -> ActionRegistry:
    registry = build_action_registry(
        (
            DailyActionHandler(daily_service),
            HistoryActionHandler(history_service),
            DailySummaryActionHandler(overview_service),
            MemberWeeklyActionHandler(weekly_service),
            TeamWeeklyActionHandler(weekly_service),
            MultiTeamWeeklyActionHandler(weekly_service),
        )
    )
    registry.register(HelpActionHandler(registry, authorization))
    return registry


def build_action_dispatcher(
    authorization: AuthorizationPolicy,
    audit_service: AuditService,
    result_store: ActionResultStore,
    handlers: Iterable[ActionHandler] = (),
) -> ActionDispatcher:
    return ActionDispatcher(
        build_action_registry(handlers),
        authorization,
        audit_service,
        result_store,
    )
