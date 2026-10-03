from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ConfigDict, Field

from project_assistant.core.errors import AppError
from project_assistant.modules.actions.contracts import (
    ActionContext,
    ActionDefinition,
    ActionResult,
    ConversationContext,
    ConversationType,
)
from project_assistant.modules.actions.dispatcher import ActionDispatcher
from project_assistant.modules.actions.parser import ParsedCommand
from project_assistant.modules.actions.registry import ActionRegistry
from project_assistant.modules.audit.models import ActionInvocation, InvocationStatus
from project_assistant.modules.audit.service import AuditService
from project_assistant.modules.memberships.models import TeamMembership, TeamRole
from project_assistant.modules.memberships.service import Permission


class DailyInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    team_id: str | None = Field(default=None, alias="teamId")
    summary: str = Field(min_length=1)


class FakeAuditRepository:
    def __init__(self) -> None:
        self.invocations: dict[str, ActionInvocation] = {}

    async def find_by_idempotency_key(self, key: str) -> ActionInvocation | None:
        return next(
            (
                invocation
                for invocation in self.invocations.values()
                if invocation.idempotency_key == key
            ),
            None,
        )

    async def get(self, invocation_id: str) -> ActionInvocation | None:
        return self.invocations.get(invocation_id)

    async def save(self, invocation: ActionInvocation) -> ActionInvocation:
        self.invocations[invocation.id] = invocation
        return invocation


class FakeAuthorization:
    def __init__(self, error: AppError | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, tuple[str, ...], Permission]] = []

    async def require(
        self, actor_id: str, team_ids: list[str], permission: Permission
    ) -> dict[str, object]:
        self.calls.append((actor_id, tuple(team_ids), permission))
        if self.error is not None:
            raise self.error
        return {}

    async def list_permitted_teams(
        self, actor_id: str, permission: Permission
    ) -> list[TeamMembership]:
        return [
            TeamMembership(
                id="membership-1",
                user_id=actor_id,
                team_id="team-1",
                role=TeamRole.MEMBER,
            )
        ]


class FakeResultStore:
    def __init__(self) -> None:
        self.results: dict[str, ActionResult] = {}

    async def get(self, invocation_id: str) -> ActionResult | None:
        return self.results.get(invocation_id)

    async def save(self, invocation_id: str, result: ActionResult) -> ActionResult:
        return self.results.setdefault(invocation_id, result)


class StubHandler:
    def __init__(
        self,
        *,
        allowed_contexts: frozenset[ConversationContext] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.definition = ActionDefinition(
            name="daily",
            aliases=("report-daily",),
            allowed_contexts=allowed_contexts
            or frozenset(
                {
                    ConversationContext.PERSONAL,
                    ConversationContext.GROUP_CHAT,
                    ConversationContext.TEAM_CHANNEL,
                }
            ),
            required_permission=Permission.SUBMIT_OWN_DAILY,
            input_schema=DailyInput,
        )
        self.error = error
        self.calls = 0

    async def execute(
        self, context: ActionContext, payload: BaseModel
    ) -> ActionResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert isinstance(payload, DailyInput)
        return ActionResult(
            kind="acknowledgement",
            message=f"Saved for {payload.team_id}",
            result_ref="daily-1",
        )


def action_context(
    *,
    conversation_type: ConversationType = ConversationType.PERSONAL,
    idempotency_key: str = "activity-1:daily",
    current_team_id: str | None = "team-1",
) -> ActionContext:
    return ActionContext(
        actor_id="user-1",
        tenant_id="tenant-1",
        conversation_id="conversation-1",
        conversation_type=conversation_type,
        current_team_id=current_team_id,
        correlation_id="correlation-1",
        idempotency_key=idempotency_key,
        timezone="Asia/Ho_Chi_Minh",
    )


def make_dispatcher(
    handler: StubHandler,
    authorization: FakeAuthorization | None = None,
) -> tuple[
    ActionDispatcher,
    FakeAuditRepository,
    FakeAuthorization,
    FakeResultStore,
    ActionRegistry,
]:
    registry = ActionRegistry()
    registry.register(handler)
    audit_repository = FakeAuditRepository()
    authorization = authorization or FakeAuthorization()
    result_store = FakeResultStore()
    dispatcher = ActionDispatcher(
        registry,
        authorization,  # type: ignore[arg-type]
        AuditService(
            audit_repository,
            clock=lambda: datetime(2026, 10, 2, 8, tzinfo=UTC),
        ),
        result_store,
    )
    return dispatcher, audit_repository, authorization, result_store, registry


@pytest.mark.asyncio
async def test_unknown_command_is_not_audited() -> None:
    dispatcher, audit_repository, _, _, _ = make_dispatcher(StubHandler())

    result = await dispatcher.dispatch(
        ParsedCommand(name="missing", arguments=()), action_context(), {}
    )

    assert result.kind == "unknown_command"
    assert not audit_repository.invocations


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("allowed_contexts", "payload", "expected_code"),
    [
        (
            frozenset({ConversationContext.PERSONAL}),
            {"teamId": "team-1", "summary": "ok"},
            "ACTION_CONTEXT_INVALID",
        ),
        (None, {"teamId": "team-1", "summary": ""}, "ACTION_PAYLOAD_INVALID"),
    ],
)
async def test_context_and_payload_failures_are_audited(
    allowed_contexts: frozenset[ConversationContext] | None,
    payload: dict[str, str],
    expected_code: str,
) -> None:
    handler = StubHandler(allowed_contexts=allowed_contexts)
    dispatcher, audit_repository, _, _, _ = make_dispatcher(handler)
    context = action_context(conversation_type=ConversationType.GROUP_CHAT)

    with pytest.raises(AppError) as failure:
        await dispatcher.dispatch(ParsedCommand(name="daily", arguments=()), context, payload)

    invocation = next(iter(audit_repository.invocations.values()))
    assert failure.value.code == expected_code
    assert invocation.status == InvocationStatus.FAILED
    assert invocation.error_code == expected_code
    assert handler.calls == 0


@pytest.mark.asyncio
async def test_permission_denial_is_recorded_without_running_handler() -> None:
    handler = StubHandler()
    authorization = FakeAuthorization(
        AppError(403, "FORBIDDEN", "This action is not permitted")
    )
    dispatcher, audit_repository, _, _, _ = make_dispatcher(handler, authorization)

    with pytest.raises(AppError) as denied:
        await dispatcher.dispatch(
            ParsedCommand(name="daily", arguments=()),
            action_context(),
            {"teamId": "team-1", "summary": "Worked on the API"},
        )

    invocation = next(iter(audit_repository.invocations.values()))
    assert denied.value.code == "FORBIDDEN"
    assert invocation.status == InvocationStatus.DENIED
    assert handler.calls == 0


@pytest.mark.asyncio
async def test_personal_action_without_team_returns_permitted_team_selection() -> None:
    handler = StubHandler()
    dispatcher, audit_repository, _, _, _ = make_dispatcher(handler)

    result = await dispatcher.dispatch(
        ParsedCommand(name="daily", arguments=()),
        action_context(current_team_id=None),
        {"summary": "Worked on the API"},
    )

    invocation = next(iter(audit_repository.invocations.values()))
    assert result.kind == "team_selection"
    assert result.data["teamIds"] == ["team-1"]
    assert invocation.status == InvocationStatus.SUCCEEDED
    assert handler.calls == 0


@pytest.mark.asyncio
async def test_successful_replay_returns_same_result_and_executes_once() -> None:
    handler = StubHandler()
    dispatcher, audit_repository, authorization, result_store, registry = make_dispatcher(
        handler
    )
    command = ParsedCommand(name="report-daily", arguments=())
    context = action_context()
    payload = {"teamId": "team-1", "summary": "Worked on the API"}

    first = await dispatcher.dispatch(command, context, payload)
    restarted_dispatcher = ActionDispatcher(
        registry,
        authorization,  # type: ignore[arg-type]
        AuditService(audit_repository),
        result_store,
    )
    replay = await restarted_dispatcher.dispatch(command, context, payload)

    invocation = next(iter(audit_repository.invocations.values()))
    assert replay == first
    assert first.result_ref == "daily-1"
    assert invocation.status == InvocationStatus.SUCCEEDED
    assert invocation.result_ref == "daily-1"
    assert handler.calls == 1
    assert len(authorization.calls) == 1


@pytest.mark.asyncio
async def test_handler_failure_is_recorded_and_sanitized() -> None:
    handler = StubHandler(error=RuntimeError("secret report body"))
    dispatcher, audit_repository, _, _, _ = make_dispatcher(handler)

    with pytest.raises(AppError) as failure:
        await dispatcher.dispatch(
            ParsedCommand(name="daily", arguments=()),
            action_context(),
            {"teamId": "team-1", "summary": "Worked on the API"},
        )

    invocation = next(iter(audit_repository.invocations.values()))
    assert failure.value.code == "ACTION_HANDLER_FAILED"
    assert invocation.status == InvocationStatus.FAILED
    assert invocation.error_code == "ACTION_HANDLER_FAILED"
    assert "secret" not in str(invocation.metadata_json).lower()
