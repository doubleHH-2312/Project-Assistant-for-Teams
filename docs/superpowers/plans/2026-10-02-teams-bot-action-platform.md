# Teams Bot Action Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an extensible, team-scoped Microsoft Teams bot and role-aware web application that capture structured work evidence, generate human-confirmed reports, and run as a lightweight Vercel/Supabase deployment.

**Architecture:** Keep the existing FastAPI/React modular monolith. Introduce Team Membership as the authorization source, append-only evidence/audit records, and a typed Action Registry whose handlers call the same application services as web routes. Mount Microsoft Teams SDK v2 into FastAPI through `FastAPIAdapter`; keep GPT and the company model behind one OpenAI-compatible LLM adapter.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy async, Alembic, PostgreSQL/Supabase, Microsoft Teams SDK for Python v2, httpx, Pydantic, React 19, TypeScript strict, TanStack Query, React Hook Form, Vite, Vitest, Playwright, Vercel.

**Spec:** `docs/superpowers/specs/2026-10-02-teams-bot-action-platform-design.md`

## Global Constraints

- One Teams group maps to one internal Team; one Team owns multiple Projects.
- Roles are assigned per active Team Membership: `MEMBER`, `TECH_LEAD`, or `PM`.
- Tech Lead inherits Member permissions; PM receives every action only on assigned Teams.
- Monday-Friday reporting uses each Team's IANA timezone; default backfill window is seven calendar days.
- Database records are authoritative; an LLM may transform supplied evidence but may not create facts.
- Weekly reports remain drafts until explicitly confirmed; confirmed reports are immutable revisions.
- Structured product data is the only bot memory; ordinary Teams messages are never stored or indexed.
- Shared conversations never receive report contents unless a user explicitly publishes a confirmed report.
- Mock authentication and Teams SDK `skip_auth` are legal only when `APP_ENV` is `local` or `test`.
- Mock LLM remains deterministic in local/CI; GPT is the first real target for the OpenAI-compatible adapter.
- Real provider output is always locally validated against the active JSON Schema.
- Vercel/Supabase is the MVP deployment profile; scheduled workers are visibly disabled there.
- Existing Alembic migrations are immutable; all schema evolution uses new revisions.

## Review Focus

- A repeated Teams activity must return its stored result without duplicating a report, status event, or publication; Task 4 pins this with dispatcher idempotency tests.
- A personal-chat user with several memberships must select a Team, while a bound group/channel must reject payloads that attempt another Team; Task 6 pins both cases.
- Editing a Daily Report must preserve the original blocker date and append a superseding status event; Task 3 pins this timeline behavior.
- A company endpoint that supports Chat Completions but not `json_schema` must work with `json_object` or prompt-only mode while still failing malformed output locally; Task 5 pins all capability modes.
- A Vercel cold start must initialize Teams routing once and use Supabase transaction pooling without connection reuse assumptions; Task 10 pins import, initialization, and engine configuration.

---

## Planned file map

### Backend domain and persistence

- Create `apps/backend/src/project_assistant/modules/memberships/{models,repository,service}.py` for team-scoped role assignment and permission checks.
- Create `apps/backend/src/project_assistant/modules/audit/{models,repository,service}.py` for invocation outcomes, status events, and publication audit.
- Create `apps/backend/src/project_assistant/modules/actions/{contracts,parser,registry,dispatcher,factory}.py` for transport-neutral command dispatch.
- Create `apps/backend/src/project_assistant/modules/actions/handlers/{daily,history,weekly,overview,help}.py` for thin action adapters.
- Create `apps/backend/src/project_assistant/modules/publications/{models,repository,service}.py` for explicit idempotent publication.
- Create `apps/backend/src/project_assistant/integrations/teams/{app,context,presenters,cards}.py` around Microsoft Teams SDK v2.
- Replace the vendor-specific implementation in `integrations/llm/provider.py` with an OpenAI-compatible adapter and provider factory.
- Modify existing user, team, daily, weekly, notification, seed, router, and model registry files to consume memberships and explicit Team scope.
- Create additive Alembic revisions `20261002_0002_team_memberships.py`,
  `20261002_0003_remove_legacy_user_scope.py`, `20261002_0004_audit_events.py`, and
  `20261002_0005_weekly_multiteam.py`.

### API, contract, and frontend

- Create `apps/backend/src/project_assistant/api/context.py` for correlation/idempotency/transport context.
- Create `apps/backend/src/project_assistant/api/teams.py` only for setup/diagnostic endpoints not registered directly by Teams SDK.
- Create `scripts/export-openapi.py` and generated `docs/api/openapi.json` plus `packages/api-client/src/schema.d.ts`.
- Split `apps/web/src/app/App.tsx` into route shell, session/team context, and feature folders under `apps/web/src/features/`.
- Add History, Member Weekly, Team Overview, Team Weekly, and Multi-team Weekly screens and behavior tests.

### Teams packaging and deployment

- Extend `apps/teams-app/manifest/manifest.template.json` with bot scopes and command lists.
- Create versioned Adaptive Cards under `apps/teams-app/adaptive-cards/` for each structured action.
- Create `api/index.py`, `vercel.json`, `docs/runbooks/vercel-supabase.md`, and CI workflows.
- Add Playwright configuration and standalone end-to-end specs under `tests/e2e/`.

## Task 1: Team Membership schema and migration

**Files:**
- Create: `apps/backend/src/project_assistant/modules/memberships/models.py`
- Create: `apps/backend/src/project_assistant/modules/memberships/repository.py`
- Create: `apps/backend/alembic/versions/20261002_0002_team_memberships.py`
- Modify: `apps/backend/src/project_assistant/modules/users/models.py`
- Modify: `apps/backend/src/project_assistant/modules/teams/models.py`
- Modify: `apps/backend/src/project_assistant/modules/model_registry.py`
- Modify: `apps/backend/src/project_assistant/seed.py`
- Test: `apps/backend/tests/test_membership_models.py`
- Test: `apps/backend/tests/test_migrations.py`
- Test: `apps/backend/tests/test_seed.py`

**Interfaces:**
- Produces: `TeamRole`, `TeamMembership`, and repository methods `get_active(user_id, team_id)`, `list_active_for_user(user_id)`, and `list_expected_members(team_id)`.
- Produces: `User.tenant_id`; `Team.tenant_id`, `Team.backfill_window_days`; removes global `User.role` and `User.team_id` after migration backfill.

- [x] **Step 1: Write failing schema and migration tests**

  Assert `(user_id, team_id)` uniqueness, the three exact role values, tenant fields, seven-day default, legacy `LEAD -> TECH_LEAD` data migration, and removal of global role/team columns after upgrade.

- [x] **Step 2: Run RED tests**

  Run: `uv run pytest apps/backend/tests/test_membership_models.py apps/backend/tests/test_migrations.py apps/backend/tests/test_seed.py -q`

  Expected: FAIL because membership tables/models do not exist.

- [x] **Step 3: Implement models, additive migration, model registration, and multi-team seed data**

  Seed at least two Teams, two Projects per Team, one cross-team Tech Lead, one cross-team PM, and members with different membership combinations. Preserve deterministic IDs used by tests and the dev identity selector.

- [x] **Step 4: Run GREEN tests and static checks**

  Run: `uv run pytest apps/backend/tests/test_membership_models.py apps/backend/tests/test_migrations.py apps/backend/tests/test_seed.py -q && uv run ruff check apps/backend/src apps/backend/tests && uv run mypy apps/backend/src`

  Expected: PASS.

- [x] **Step 5: Commit**

  `git commit -m "feat: add team-scoped memberships"`

## Task 2: Permission policy and team-scoped repositories

**Files:**
- Create: `apps/backend/src/project_assistant/modules/memberships/service.py`
- Modify: `apps/backend/src/project_assistant/core/auth.py`
- Modify: `apps/backend/src/project_assistant/modules/daily_reports/repository.py`
- Modify: `apps/backend/src/project_assistant/modules/teams/repository.py`
- Modify: `apps/backend/src/project_assistant/modules/weekly_reports/repository.py`
- Modify: `apps/backend/src/project_assistant/modules/notifications/repository.py`
- Test: `apps/backend/tests/test_authorization_service.py`
- Test: `apps/backend/tests/test_scoped_repositories.py`

**Interfaces:**
- Produces: `Permission` enum and `AuthorizationService.require(actor_id: str, team_ids: Collection[str], permission: Permission) -> dict[str, TeamMembership]`.
- Produces: repository methods whose team-bearing reads require `team_id`; no method returns cross-team records by implicit user scope.

- [x] **Step 1: Write failing role-inheritance and denial tests**

  Cover inactive membership, Member denial, Tech Lead inheritance, PM all-actions-on-assigned-Teams, and all-selected-Teams requirement for multi-team generation.

- [x] **Step 2: Write failing repository scope tests**

  Seed identically named work items and reports in two Teams and assert every team-scoped method returns only the requested Team.

- [x] **Step 3: Run RED tests**

  Run: `uv run pytest apps/backend/tests/test_authorization_service.py apps/backend/tests/test_scoped_repositories.py -q`

  Expected: FAIL on missing policy and obsolete global-role filters.

- [x] **Step 4: Implement policy and replace global-role authorization**

  Map Member to own Daily/History/Member Weekly, Tech Lead to inherited plus Daily Summary/Team Weekly/Multi-team, and PM to all permissions. Return 404 for inaccessible Team resources and 403 for a known action without permission.

- [x] **Step 5: Run GREEN tests and existing service suite**

  Run: `uv run pytest apps/backend/tests/test_authorization_service.py apps/backend/tests/test_scoped_repositories.py apps/backend/tests/test_daily_report_service.py apps/backend/tests/test_team_overview_service.py apps/backend/tests/test_weekly_report_service.py -q`

  Expected: PASS after updating fixtures to Team Membership.

- [x] **Step 6: Commit**

  `git commit -m "feat: enforce team-scoped permissions"`

## Task 3: Append-only invocation and status-event audit

**Files:**
- Create: `apps/backend/src/project_assistant/modules/audit/models.py`
- Create: `apps/backend/src/project_assistant/modules/audit/repository.py`
- Create: `apps/backend/src/project_assistant/modules/audit/service.py`
- Create: `apps/backend/alembic/versions/20261002_0004_audit_events.py`
- Modify: `apps/backend/src/project_assistant/modules/daily_reports/models.py`
- Modify: `apps/backend/src/project_assistant/modules/daily_reports/repository.py`
- Modify: `apps/backend/src/project_assistant/modules/daily_reports/service.py`
- Modify: `apps/backend/src/project_assistant/modules/model_registry.py`
- Test: `apps/backend/tests/test_audit_models.py`
- Test: `apps/backend/tests/test_daily_status_timeline.py`

**Interfaces:**
- Produces: `InvocationStatus`, `ActionInvocation`, `WorkItemStatusEvent`, and `RequestAuditContext`.
- Produces: `AuditService.start(context: RequestAuditContext) -> ActionInvocation`, `succeed(invocation_id: str, result_ref: str | None) -> ActionInvocation`, `fail(invocation_id: str, code: str) -> ActionInvocation`, and `deny(invocation_id: str, code: str) -> ActionInvocation`.
- Produces: `DailyReportRepository.save_with_event_and_success(report: DailyReport, event: WorkItemStatusEvent, invocation_id: str) -> DailyReport` so the domain record, event, and success transition share one transaction.
- Produces: `DailyReportService.create(actor: User, team_id: str, request: DailyReportCreate, audit: RequestAuditContext) -> DailyReport` and the corresponding typed `update` method; both append an event with `recorded_at`, Team-local date/time, business `report_date`, effective blocker, source, and `supersedes_event_id`.

- [x] **Step 1: Write failing append-only and uniqueness tests**

  Assert correlation/idempotency constraints, sanitized metadata, immutable prior events, and event linkage to the Daily Report.

- [x] **Step 2: Write the blocker-date regression test**

  Record `BLOCKED` on `2026-10-04`, update/resubmit later, then assert the timeline still exposes the original date and the new event points to the superseded event.

- [x] **Step 3: Run RED tests**

  Run: `uv run pytest apps/backend/tests/test_audit_models.py apps/backend/tests/test_daily_status_timeline.py -q`

  Expected: FAIL because audit/event storage is absent.

- [x] **Step 4: Implement models, migration, two-phase invocation lifecycle, and transactional Daily+Event+success save**

  Persist `PENDING` separately so failures survive rollback; commit Daily Report, status event, and `SUCCEEDED` outcome in one transaction. Never put full report content, tokens, or secrets in invocation metadata.

- [x] **Step 5: Run GREEN, migration, and daily regression tests**

  Run: `uv run pytest apps/backend/tests/test_audit_models.py apps/backend/tests/test_daily_status_timeline.py apps/backend/tests/test_daily_report_model.py apps/backend/tests/test_daily_report_service.py apps/backend/tests/test_migrations.py -q`

  Expected: PASS.

- [x] **Step 6: Commit**

  `git commit -m "feat: preserve action and status history"`

## Task 4: Typed Action Registry, parser, and dispatcher

**Files:**
- Create: `apps/backend/src/project_assistant/modules/actions/contracts.py`
- Create: `apps/backend/src/project_assistant/modules/actions/parser.py`
- Create: `apps/backend/src/project_assistant/modules/actions/registry.py`
- Create: `apps/backend/src/project_assistant/modules/actions/dispatcher.py`
- Create: `apps/backend/src/project_assistant/modules/actions/factory.py`
- Test: `apps/backend/tests/actions/test_parser.py`
- Test: `apps/backend/tests/actions/test_registry.py`
- Test: `apps/backend/tests/actions/test_dispatcher.py`

**Interfaces:**
- Produces: `ConversationContext`, `ConversationType`, `ActionDefinition`, `ActionContext`, `ActionResult`, `ActionHandler` exactly as approved in the spec.
- Produces: `parse_command(text: str, bot_mention_text: str | None) -> ParsedCommand | None`.
- Produces: `ActionRegistry.register(handler)` and `ActionDispatcher.dispatch(command, context, payload) -> ActionResult`.

- [ ] **Step 1: Write failing parser/registry contract tests**

  Cover `/daily`, `@Project Assistant /weekly-team`, whitespace/case normalization, aliases, unknown text without storing it, and duplicate name/alias rejection.

- [ ] **Step 2: Write failing dispatcher tests**

  Cover context restriction, validation error, denied invocation, successful invocation, handler failure, and replay of the same activity/idempotency key returning the stored result exactly once.

- [ ] **Step 3: Run RED tests**

  Run: `uv run pytest apps/backend/tests/actions -q`

  Expected: FAIL because the action module does not exist.

- [ ] **Step 4: Implement transport-neutral contracts, parser, registry, factory, and dispatcher**

  Dispatcher order is resolve -> start audit -> context check -> payload validation -> permission check -> handler -> persist sanitized outcome. It never imports FastAPI or Microsoft Teams SDK.

- [ ] **Step 5: Run GREEN and strict type checks**

  Run: `uv run pytest apps/backend/tests/actions -q && uv run mypy apps/backend/src && uv run ruff check apps/backend/src apps/backend/tests`

  Expected: PASS.

- [ ] **Step 6: Commit**

  `git commit -m "feat: add extensible action dispatcher"`

## Task 5: GPT-first OpenAI-compatible LLM provider

**Files:**
- Modify: `apps/backend/src/project_assistant/core/config.py`
- Modify: `apps/backend/src/project_assistant/integrations/llm/provider.py`
- Create: `apps/backend/src/project_assistant/integrations/llm/factory.py`
- Modify: `apps/backend/src/project_assistant/modules/weekly_reports/router.py`
- Modify: `.env.example`
- Create: `apps/backend/tests/test_openai_compatible_provider.py`
- Modify: `apps/backend/tests/test_system.py`

**Interfaces:**
- Produces: `StructuredOutputMode = Literal["json_schema", "json_object", "prompt"]`.
- Produces: `OpenAICompatibleLLMProvider(base_url, api_key, model, output_mode, timeout_seconds, max_attempts)` using `POST {base_url}/chat/completions`.
- Produces: `build_llm_provider(settings) -> LLMProvider` for `mock` and `openai_compatible` only.

- [ ] **Step 1: Write failing request/response contract tests with `httpx.MockTransport`**

  Assert GPT/custom base URLs, bearer auth, model, system/evidence messages, each structured-output mode, parsed `choices[0].message.content`, provider metadata without API key, and no evidence omitted.

- [ ] **Step 2: Write failing resilience tests**

  Assert bounded retry for timeout/transport/429/5xx, no retry for other 4xx, malformed JSON rejection, and local JSON Schema rejection before report persistence.

- [ ] **Step 3: Run RED tests**

  Run: `uv run pytest apps/backend/tests/test_openai_compatible_provider.py apps/backend/tests/test_weekly_report_service.py -q`

  Expected: FAIL on missing adapter/configuration.

- [ ] **Step 4: Implement adapter and provider factory**

  Use `LLM_BASE_URL=https://api.openai.com/v1`, `LLM_MODEL`, secret `LLM_API_KEY`, `LLM_STRUCTURED_OUTPUT_MODE`, `LLM_TIMEOUT_SECONDS`, and `LLM_MAX_ATTEMPTS`. Keep schema validation in the weekly application service for all modes.

- [ ] **Step 5: Run GREEN and configuration security tests**

  Run: `uv run pytest apps/backend/tests/test_openai_compatible_provider.py apps/backend/tests/test_weekly_report_service.py apps/backend/tests/test_system.py -q`

  Expected: PASS with no real network or secret.

- [ ] **Step 6: Commit**

  `git commit -m "feat: add OpenAI-compatible report generation"`

## Task 6: Daily, history, overview, and help actions

**Files:**
- Create: `apps/backend/src/project_assistant/modules/actions/handlers/daily.py`
- Create: `apps/backend/src/project_assistant/modules/actions/handlers/history.py`
- Create: `apps/backend/src/project_assistant/modules/actions/handlers/overview.py`
- Create: `apps/backend/src/project_assistant/modules/actions/handlers/help.py`
- Modify: `apps/backend/src/project_assistant/modules/daily_reports/schemas.py`
- Modify: `apps/backend/src/project_assistant/modules/daily_reports/service.py`
- Modify: `apps/backend/src/project_assistant/modules/teams/overview.py`
- Modify: `apps/backend/src/project_assistant/modules/actions/factory.py`
- Test: `apps/backend/tests/actions/test_daily_actions.py`
- Test: `apps/backend/tests/actions/test_history_actions.py`
- Test: `apps/backend/tests/actions/test_overview_actions.py`

**Interfaces:**
- Produces registered `/daily`, `/history`, `/daily-summary`, and `/help` handlers.
- Produces history filters `team_id`, optional `project_id`, `date_from`, `date_to`, and `status` with a seven-reporting-day default.
- Produces Daily date resolution from Team timezone when absent and backfill validation against `backfill_window_days`.

- [ ] **Step 1: Write failing Daily action tests**

  Cover Team-bound context, personal-chat Team selection, payload Team mismatch rejection, server-derived local date, allowed seven-day backfill, older rejection, and atomic event/audit behavior.

- [ ] **Step 2: Write failing History/Overview/Help tests**

  Assert own-history only, grouping by date/Project/Work Item, exact blocker event dates in Daily Summary, role denial, and permission-filtered help output.

- [ ] **Step 3: Run RED tests**

  Run: `uv run pytest apps/backend/tests/actions/test_daily_actions.py apps/backend/tests/actions/test_history_actions.py apps/backend/tests/actions/test_overview_actions.py -q`

  Expected: FAIL on missing handlers and Team-aware use cases.

- [ ] **Step 4: Implement handlers and Team-aware service methods**

  Handlers translate typed action payloads to existing services and return transport-neutral form, list, or summary results. They contain no SQL and no Teams SDK types.

- [ ] **Step 5: Run GREEN and daily/overview regressions**

  Run: `uv run pytest apps/backend/tests/actions apps/backend/tests/test_daily_report_service.py apps/backend/tests/test_team_overview_service.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit**

  `git commit -m "feat: expose daily reporting actions"`

## Task 7: Project-grouped member, team, and multi-team weekly reports

**Files:**
- Create: `apps/backend/alembic/versions/20261002_0005_weekly_multiteam.py`
- Modify: `apps/backend/src/project_assistant/modules/templates/models.py`
- Modify: `apps/backend/src/project_assistant/modules/weekly_reports/{models,schemas,repository,service,router}.py`
- Create: `apps/backend/src/project_assistant/modules/actions/handlers/weekly.py`
- Create: `apps/backend/src/project_assistant/modules/weekly_reports/evidence.py`
- Create: `apps/backend/src/project_assistant/modules/publications/{models,repository,service}.py`
- Extend: `apps/backend/alembic/versions/20261002_0005_weekly_multiteam.py` with evidence-link and publication tables
- Modify: `apps/backend/src/project_assistant/seed.py`
- Test: `apps/backend/tests/test_weekly_evidence.py`
- Test: `apps/backend/tests/test_multiteam_weekly_service.py`
- Test: `apps/backend/tests/test_publication_service.py`
- Modify: `apps/backend/tests/test_weekly_report_service.py`

**Interfaces:**
- Extends: `ReportScope` with `MULTI_TEAM`; makes `WeeklyReport.team_id` nullable only for that scope.
- Produces: `WeeklyReportTeam`, `ReportEvidenceLink`, optional Project sections, and tenant-scoped multi-team templates.
- Produces registered `/weekly`, `/weekly-team`, `/weekly-multi-team` handlers.
- Produces `PublicationService.publish(actor, report_id, conversation_id, idempotency_key)` separate from confirmation.

- [ ] **Step 1: Write failing evidence and migration tests**

  Assert Member output groups Tasks by Project, Team output consumes only confirmed Member reports, Multi-team output groups Team then Project and consumes only confirmed Team reports, and every item retains evidence links.

- [ ] **Step 2: Write failing authorization/state/publication tests**

  Cover all-Team Tech Lead/PM authorization, missing contributors, Monday validation per Team timezone, immutable confirmation, revision linkage, private draft behavior, explicit publish, and duplicate publish suppression.

- [ ] **Step 3: Run RED tests**

  Run: `uv run pytest apps/backend/tests/test_weekly_evidence.py apps/backend/tests/test_multiteam_weekly_service.py apps/backend/tests/test_publication_service.py apps/backend/tests/test_weekly_report_service.py -q`

  Expected: FAIL because structured grouping, multi-team scope, and publication do not exist.

- [ ] **Step 4: Implement schema, evidence builder, use cases, handlers, and seed templates**

  For `MULTI_TEAM`, resolve the tenant-scoped active template; record selected Teams through `weekly_report_teams`; never fall back to unscoped queries. Optional risks/issues/lessons fields remain empty unless supplied by evidence or human edit.

- [ ] **Step 5: Run GREEN plus migration and malformed-LLM tests**

  Run: `uv run pytest apps/backend/tests/test_weekly_evidence.py apps/backend/tests/test_multiteam_weekly_service.py apps/backend/tests/test_publication_service.py apps/backend/tests/test_weekly_report_service.py apps/backend/tests/test_migrations.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit**

  `git commit -m "feat: add project-grouped multi-team reporting"`

## Task 8: Microsoft Teams SDK v2 adapter, cards, and manifest

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `apps/backend/src/project_assistant/integrations/teams/app.py`
- Create: `apps/backend/src/project_assistant/integrations/teams/context.py`
- Create: `apps/backend/src/project_assistant/integrations/teams/presenters.py`
- Create: `apps/backend/src/project_assistant/integrations/teams/cards.py`
- Modify: `apps/backend/src/project_assistant/integrations/teams/transport.py`
- Modify: `apps/backend/src/project_assistant/modules/notifications/models.py`
- Create: `apps/backend/alembic/versions/20261002_0006_teams_bindings.py`
- Modify: `apps/backend/src/project_assistant/main.py`
- Modify: `apps/teams-app/manifest/manifest.template.json`
- Create: `apps/teams-app/adaptive-cards/{daily,team-selector,weekly-review,summary}.json`
- Test: `apps/backend/tests/teams/test_context.py`
- Test: `apps/backend/tests/teams/test_presenters.py`
- Test: `apps/backend/tests/teams/test_app.py`
- Test: `apps/backend/tests/teams/test_installation.py`

**Interfaces:**
- Produces: `create_teams_app(fastapi_app: FastAPI, settings: Settings, dispatcher: ActionDispatcher) -> microsoft_teams.apps.App` using `FastAPIAdapter` and `microsoft-teams-apps>=2.0.16,<2.1`.
- Produces: authenticated `/api/messages`, message/card-submit/install handlers, conversation bindings for personal/group/team/channel scopes, and proactive transport.

- [ ] **Step 1: Add the pinned SDK dependency and write failing adapter tests**

  Assert one initialization per FastAPI lifespan, auth required outside local/test, `/api/messages` registration, slash and mention parsing, no storage of ordinary message text, and activity-to-ActionContext identity mapping.

- [ ] **Step 2: Write failing installation/privacy/card tests**

  Cover PM-only group binding, personal chat without one fixed Team, welcome/help cards, group invocation returning only non-sensitive acknowledgement, personal/dialog continuation, submit idempotency, and missing conversation delivery failure.

- [ ] **Step 3: Run RED tests**

  Run: `uv run pytest apps/backend/tests/teams -q`

  Expected: FAIL because Teams SDK adapter and bindings are absent.

- [ ] **Step 4: Implement SDK factory, handlers, presenters, bindings, cards, and bot manifest**

  Set bot scopes to `personal`, `groupChat`, and `team`; declare command lists; point bot endpoint documentation to `/api/messages`. Never use `skip_auth=True` in staging/production.

- [ ] **Step 5: Run GREEN and package validation**

  Run: `uv run pytest apps/backend/tests/teams -q && make teams-package && unzip -l dist/project-assistant-teams.zip`

  Expected: tests PASS and ZIP contains only manifest plus required icon assets at its root.

- [ ] **Step 6: Commit**

  `git commit -m "feat: add Microsoft Teams bot adapter"`

## Task 9: OpenAPI contract and role-aware web application

**Files:**
- Create: `scripts/export-openapi.py`
- Create: `docs/api/openapi.json`
- Create: `packages/api-client/src/schema.d.ts`
- Modify: `packages/api-client/{package.json,src/index.ts}`
- Modify: `apps/web/src/app/App.tsx`
- Create: `apps/web/src/app/{router,session}.tsx`
- Create: `apps/web/src/features/daily/DailyPage.tsx`
- Create: `apps/web/src/features/history/HistoryPage.tsx`
- Create: `apps/web/src/features/overview/OverviewPage.tsx`
- Create: `apps/web/src/features/weekly/{MemberWeeklyPage,TeamWeeklyPage,MultiTeamWeeklyPage,WeeklyEditor}.tsx`
- Create: `apps/web/src/components/{AppShell,AsyncState,PermissionGate,TeamSelector}.tsx`
- Modify: `apps/web/src/app/styles.css`
- Add tests beside each page/component.
- Modify: `Makefile`

**Interfaces:**
- Produces generated OpenAPI types and a typed client with `getSession`, `listTeams`, Daily/History/Overview, weekly generate/edit/confirm/revise, and publish methods.
- Produces navigation filtered by server-returned permissions, explicit current Team selection, and separate confirm/publish controls.

- [ ] **Step 1: Write failing backend API contract tests**

  Cover `/me`, memberships/permissions, Team-scoped daily/history/overview endpoints, all weekly scopes, idempotency headers, consistent error envelope, and publication.

- [ ] **Step 2: Expose thin routes and generate OpenAPI/client types**

  Run `uv run python scripts/export-openapi.py` then `corepack pnpm --filter @project-assistant/api-client generate`; add `make openapi-check` that fails on drift.

- [ ] **Step 3: Write failing frontend behavior tests**

  Cover Member/Tech Lead/PM navigation, multi-Team selector, loading/empty/error/forbidden/stale retry, Daily history timeline dates, weekly edit-confirm-revise, and explicit publish confirmation.

- [ ] **Step 4: Run RED frontend tests**

  Run: `corepack pnpm --filter @project-assistant/web test`

  Expected: FAIL because feature pages and generated methods are absent.

- [ ] **Step 5: Implement route shell and feature pages using only generated client contracts**

  Preserve keyboard navigation, labels, focus visibility, minimum 44px targets, responsive layouts, and integration-mode visibility. Backend authorization remains authoritative.

- [ ] **Step 6: Run GREEN frontend/API verification**

  Run: `uv run pytest apps/backend/tests -q && make openapi-check && corepack pnpm --filter @project-assistant/web test && corepack pnpm --filter @project-assistant/web lint && corepack pnpm --filter @project-assistant/web typecheck && corepack pnpm --filter @project-assistant/web build`

  Expected: PASS.

- [ ] **Step 7: Commit**

  `git commit -m "feat: add role-aware reporting web app"`

## Task 10: Vercel and Supabase deployment profile

**Files:**
- Create: `api/index.py`
- Create: `vercel.json`
- Modify: `apps/backend/src/project_assistant/core/config.py`
- Modify: `apps/backend/src/project_assistant/core/database.py`
- Modify: `apps/backend/src/project_assistant/api/system.py`
- Modify: `.env.example`
- Create: `docs/runbooks/vercel-supabase.md`
- Create: `apps/backend/tests/test_serverless_database.py`
- Create: `apps/backend/tests/test_vercel_entrypoint.py`

**Interfaces:**
- Produces Vercel ASGI entrypoint `api.index:app` importing the same FastAPI application.
- Produces `DATABASE_DEPLOYMENT_MODE=serverless|persistent`; serverless uses SSL, `NullPool`, and asyncpg statement cache size zero.
- Produces health/readiness fields for database, Teams mode, LLM mode, and `scheduledJobsEnabled=false`.

- [ ] **Step 1: Write failing configuration and cold-start tests**

  Assert Vercel module import, one Teams initialization, serverless engine options, production rejection of local auth/Teams skip-auth, and visible disabled scheduler.

- [ ] **Step 2: Run RED tests**

  Run: `uv run pytest apps/backend/tests/test_serverless_database.py apps/backend/tests/test_vercel_entrypoint.py apps/backend/tests/test_system.py -q`

  Expected: FAIL because entrypoint/profile do not exist.

- [ ] **Step 3: Implement Vercel routing, Supabase pooler configuration, and runbook**

  Document transaction-pooler URL, direct migration URL, environment variables, preview smoke, migration procedure, free-plan limitations, rollback, and no keep-alive workaround. Do not place credentials or real project refs in Git.

- [ ] **Step 4: Run GREEN and deployment-config checks**

  Run: `uv run pytest apps/backend/tests/test_serverless_database.py apps/backend/tests/test_vercel_entrypoint.py apps/backend/tests/test_system.py -q && uv run python -m py_compile api/index.py`

  Expected: PASS.

- [ ] **Step 5: Commit**

  `git commit -m "feat: add Vercel Supabase deployment profile"`

## Task 11: CI, E2E, security, and final handoff

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `playwright.config.ts`
- Create: `tests/e2e/reporting-flow.spec.ts`
- Create: `tests/e2e/authorization.spec.ts`
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `docs/runbooks/local-demo.md`
- Modify: `docs/runbooks/teams-sideload.md`
- Modify: `context-memory/{progress,current-handoff,risks-and-dependencies}.md`

**Interfaces:**
- Produces standard gates: format check -> lint -> typecheck -> backend/frontend tests -> clean migration -> OpenAPI drift -> web build -> Playwright -> container build -> secret scan.
- Produces one documented standalone demo path and one explicitly gated real-Teams path.

- [ ] **Step 1: Write Playwright acceptance tests**

  Exercise Member Daily -> History -> Member Weekly confirmation, Tech Lead Daily Summary -> Team Weekly confirmation, PM Multi-team Weekly, forbidden Member views, and explicit publish confirmation with mock Teams transport.

- [ ] **Step 2: Implement CI and local commands**

  Add `make format-check`, `make openapi-check`, `make migration-check`, `make security-check`, and a deterministic `make verify` used by CI.

- [ ] **Step 3: Run focused browser tests**

  Run: `make demo` then `make e2e`.

  Expected: all standalone flows PASS; real Teams E2E remains marked gated, never simulated as verified.

- [ ] **Step 4: Run fresh full verification**

  Run: `make lint && make typecheck && make test && make web-test && make openapi-check && make build && make teams-package && make build-images && make smoke && make e2e`

  Expected: every command exits 0. Record exact counts and any externally gated checks.

- [ ] **Step 5: Review complete diff and security boundaries**

  Inspect migrations, tenant/team predicates, action metadata, secret patterns, SDK auth modes, full-report logging, generated contract drift, manifest domains, accessibility, and accidental files.

- [ ] **Step 6: Update durable handoff and commit**

  Mark completed task IDs with evidence, record unresolved Teams/Entra/Vercel/Supabase/company-LLM gates, refresh `current-handoff.md`, and commit with `chore: harden delivery workflow`.

## Execution order and checkpoints

Execute Tasks 1-4 as the authorization/action-core milestone, Tasks 5-7 as the reporting milestone, Task 8 as the locally testable Teams bot milestone, Task 9 as the complete web milestone, and Tasks 10-11 as deployment/hardening. After each milestone, run the listed regression commands and update both this checkbox ledger and `context-memory/progress.md` before starting the next milestone.

Actual GPT, company-LLM, Teams tenant, and Vercel/Supabase smoke tests require external credentials and are integration gates. Their absence does not justify fake success: contract-compatible mocks and local adapters may be complete while the real integration remains explicitly blocked.
