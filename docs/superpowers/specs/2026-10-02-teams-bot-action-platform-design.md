# Teams Bot Action Platform Design

**Date:** 2026-10-02

**Status:** Approved for implementation
**Product:** Project Assistant Tool MVP

## 1. Intent and success criteria

Project Assistant becomes a Microsoft Teams bot that can participate in group
conversations and can also be used in personal chat. Users discover repeatable
workflows through slash and mention commands, complete structured forms, and receive
private drafts or summaries. A standalone React web application exposes the same
domain capabilities with the same authorization rules.

The MVP succeeds when:

- Teams users can invoke `/daily`, `/history`, `/weekly`, `/daily-summary`,
  `/weekly-team`, `/weekly-multi-team`, and `/help` in supported contexts.
- `@Project Assistant /command` and personal bot chat use the same handlers.
- Adding an action requires a definition, handler, permission, input schema, and
  presenter without editing command-dispatch infrastructure.
- Every invocation, report submission, status change, confirmation, and publication
  has an append-only audit record with server-generated timestamps.
- Weekly reports contain only traceable structured evidence and remain drafts until a
  human confirms them.
- Team and multi-team authorization prevents cross-team data disclosure.
- The web app and Teams bot call the same application use cases.
- The lightweight deployment runs on Vercel with Supabase PostgreSQL; the architecture
  retains adapter seams for later container/RDS deployment.

## 2. Scope

### 2.1 MVP scope

- Structured project, work-item, daily-report, weekly-report, status-event, membership,
  conversation-binding, and action-invocation data.
- Teams personal, group-chat, and team/channel bot scopes.
- Slash and mention command discovery.
- Adaptive Card or dialog-based data collection.
- Member, Tech Lead, and PM authorization scoped through team memberships.
- Member, team, and multi-team weekly generation with explicit review and confirmation.
- Web workflows for all supported roles.
- Local Docker development plus Vercel/Supabase demo deployment.

### 2.2 Explicitly outside MVP

- Passive ingestion, indexing, or storage of Teams chat/channel messages.
- Natural-language autonomous task execution.
- Editing or impersonating another user's Daily Report.
- Precise scheduled reminders on the free serverless deployment.
- AWS infrastructure, queues, long-running workers, and high-availability production
  topology. These remain a scale-up path.

The bot has access to structured data stored by the product, but a caller only sees
data authorized for the selected team scope.

## 3. Canonical domain model

### 3.1 Organization model

- A **Team** is the internal representation of one Teams group or team conversation.
- A Team owns zero or more Projects.
- A User may be a member of multiple Teams.
- A **Team Membership** assigns exactly one role to one user in one Team.
- Roles are `MEMBER`, `TECH_LEAD`, and `PM`; role is not global to the User.
- A Teams Conversation Binding maps an installed Teams conversation to one internal
  Team. Personal conversations do not bind to one Team and require team selection when
  the actor has multiple memberships.

### 3.2 Report hierarchy

```text
Daily Reports and Work Item Status Events
  -> Member Weekly Draft
  -> Member Confirmation
  -> Team Weekly Draft
  -> Tech Lead or PM Confirmation
  -> Multi-team Weekly Draft
  -> Eligible Tech Lead or PM Confirmation
```

- A Member Weekly Report belongs to one Team and one Member, but groups that member's
  work by Project.
- A Team Weekly Report belongs to one Team, groups evidence by Project, and uses only
  confirmed Member Weekly Reports.
- A Multi-team Weekly Report groups evidence by Team then Project and uses only
  confirmed Team Weekly Reports.
- Unconfirmed expected contributors appear in `missingContributors`.
- Confirmed reports are immutable. Changes require a Revision with `supersedes_id`.

### 3.3 Optional weekly sections

Each Project section has evidence-backed task groups and optional human-editable
sections:

- `completedTasks`
- `inProgressTasks`
- `blockers`
- `risks`
- `issues`
- `lessonsLearned`
- `nextActions`

The LLM may summarize supplied evidence but must not create a project fact. Generated
items retain evidence references.

## 4. Action platform architecture

### 4.1 Request flow

```text
Teams Activity Adapter or Web Route
  -> Context Resolver
  -> Action Dispatcher (Teams only)
  -> Authorization Policy
  -> Action Handler / Web Controller
  -> Shared Application Use Case
  -> Repository + LLMProvider + TeamsTransport
  -> Action Result
  -> Teams Presenter or Web DTO
```

The Action Registry is a deep module for command discovery and dispatch. It does not
contain business rules. Teams handlers and web controllers remain thin and call the
same use cases.

The LLM boundary exposes one transport-neutral `LLMProvider`. A deterministic mock is
used in local tests and CI. Real evaluation first uses GPT through an
`OpenAICompatibleLLMProvider`; the company model later uses the same adapter by
changing its base URL, API key, model name, and declared capability mode. Domain and
reporting services do not branch on the vendor name.

### 4.2 Action interfaces

```python
@dataclass(frozen=True)
class ActionDefinition:
    name: str
    aliases: tuple[str, ...]
    allowed_contexts: frozenset[ConversationContext]
    required_permission: Permission
    input_schema: type[BaseModel]


@dataclass(frozen=True)
class ActionContext:
    actor_id: str
    tenant_id: str
    conversation_id: str
    conversation_type: ConversationType
    current_team_id: str | None
    correlation_id: str
    idempotency_key: str


class ActionHandler(Protocol):
    definition: ActionDefinition

    async def execute(
        self, context: ActionContext, payload: BaseModel
    ) -> ActionResult: ...
```

`ActionRegistry.register(handler)` rejects duplicate action names and aliases.
`ActionDispatcher.dispatch(command, context, payload)` resolves the handler, validates
the context and input, checks authorization, records the invocation, and returns a
transport-neutral result.

### 4.3 Commands and permissions

| Command | Contexts | Permission |
|---|---|---|
| `/daily` | personal, group chat, team/channel | `SUBMIT_OWN_DAILY` |
| `/history` | personal, group chat, team/channel | `VIEW_OWN_HISTORY` |
| `/weekly` | personal, group chat, team/channel | `GENERATE_OWN_WEEKLY` |
| `/daily-summary` | personal, group chat, team/channel | `VIEW_TEAM_DAILY_SUMMARY` |
| `/weekly-team` | personal, group chat, team/channel | `GENERATE_TEAM_WEEKLY` |
| `/weekly-multi-team` | personal only | `GENERATE_MULTI_TEAM_WEEKLY` |
| `/help` | all bot contexts | provisioned user |

Member permissions are the first three action permissions. Tech Lead inherits Member
permissions and gains team-summary/team-weekly permissions. PM has every action on
Teams where the PM has an active membership. A Tech Lead can generate a multi-team
report only when the Lead has an active `TECH_LEAD` membership in every selected Team;
a PM must have an active `PM` membership in every selected Team.

No role can edit another user's Daily Report or confirm another Member's Member Weekly
Report.

### 4.4 Adding an action

Adding `/blockers`, for example, requires:

1. A typed input model.
2. An `ActionDefinition` and `ActionHandler`.
3. A named permission and policy rule.
4. Registration in the application registry factory.
5. Manifest command metadata.
6. A Teams presenter and, only when needed, a web consumer.
7. Handler contract, authorization, input-validation, and presentation tests.

The parser, dispatcher, Teams endpoint, identity resolver, and existing handlers do not
change.

## 5. Teams interaction design

### 5.1 Supported entry points

- Personal chat with the bot.
- Slash command targeted to the bot.
- `@Project Assistant /command` in a group chat or channel.
- Adaptive Card or dialog submit.
- Installation and conversation-update events.

The manifest declares `personal`, `groupChat`, and `team` bot scopes and command lists
for the supported scopes. Teams may surface those commands through its command menu;
the application parser independently accepts both `/command` in personal chat and
`@Project Assistant /command` in group or channel conversations. The activity adapter
verifies the Bot Framework activity, strips only this bot's mention, and passes
normalized command text to the dispatcher.

### 5.2 Installation

On group/team installation, the bot stores the tenant, conversation, service URL, and
installation metadata. An authorized PM binds the conversation to an existing Team or
creates the internal Team. The bot sends one concise welcome card with available
commands. It does not ingest prior or future ordinary conversation messages.

### 5.3 Visibility and publication

- Input forms, personal history, drafts, and summaries never render as sensitive
  content in a shared conversation. A group/channel invocation opens a dialog or
  continues in an authorized 1:1 bot conversation; the shared conversation receives
  only a non-sensitive acknowledgement when Teams requires a visible response.
- `Confirm` makes a Weekly Report authoritative and immutable.
- `Publish to Team` is a separate audited, idempotent delivery action.
- Nothing is posted publicly merely because a report was generated or confirmed.

## 6. Action workflows

### 6.1 Daily

The bot resolves the Team from group context or asks for a Team in personal context.
The user selects an active Project and Work Item, then enters status, work summary,
blocker, and next action. The backend derives the default reporting date from the Team
timezone.

Users may backfill within `Team.backfill_window_days`. The system stores business
`report_date` separately from server-generated `submitted_at`. The UI clearly labels a
backfilled record. Submission atomically writes the Daily Report, Work Item Status
Event, and successful Action Invocation outcome.

### 6.2 History

History defaults to the actor's last seven reporting days and groups records by date,
Project, and Work Item. The actor can filter by Project, date range, and status. It
never returns another member's private report.

### 6.3 Member weekly

The use case reads the actor's Daily Reports and status events for one Team and one
Monday-Friday week, groups evidence by Project, invokes the configured LLM provider,
validates output against the versioned template schema, and returns a private draft.
The Member edits optional sections and confirms explicitly.

### 6.4 Daily summary

Tech Lead and PM receive Team coverage, missing reporters, status counts, active
blockers with exact recorded dates, and Project grouping. The result links to the web
dashboard for drill-down.

### 6.5 Team weekly

The use case reads confirmed Member Weekly Reports for one Team/week. It records
missing contributors, groups evidence by Project, generates a draft, and requires Tech
Lead or PM review and confirmation.

### 6.6 Multi-team weekly

This personal-chat-only action accepts multiple Team IDs. Authorization succeeds only
when the actor has the required role in every Team. It reads confirmed Team Weekly
Reports, groups output by Team then Project, and requires review and confirmation.

## 7. Audit and temporal accuracy

### 7.1 Action Invocation

Every trigger creates an append-only `action_invocations` record containing:

- action, actor, tenant, team/project when resolved, and conversation identifiers;
- UTC trigger time, Team-local date/time, and captured timezone;
- correlation ID and idempotency key;
- pending/succeeded/failed/denied status and sanitized error code;
- sanitized metadata only, never access tokens, credentials, or complete report text.

### 7.2 Work Item Status Event

Daily creation or edit appends a status event containing the authoritative server
recorded time, local date, status, effective blocker, evidence link, source, and
optional superseded-event link. Previous events are not updated or deleted.

If a block is recorded on 2026-10-04, later reports state that exact date. A later
submission can resolve the block without erasing the original event. A backfilled
record retains both its business date and later submission timestamp.

### 7.3 Idempotency

Teams retries must reuse an idempotency key derived from the activity/invoke ID and
action. Daily submit, generation, confirmation, publication, and notification claims
have database uniqueness protection. Replaying a completed request returns the stored
result; it does not duplicate a domain record or public message.

## 8. Database design

### 8.1 Identity and tenancy

- `users`: tenant-scoped Entra identity and profile; no global role.
- `team_memberships`: `(user_id, team_id)` unique, role, active state, lifecycle dates.
- `teams`: tenant, name, timezone, backfill window, reporting configuration.
- `teams_conversation_bindings`: tenant/conversation unique mapping to Team plus service
  and installation metadata.

### 8.2 Reporting and evidence

- `projects` and `work_items` retain Team ownership through Project.
- `daily_reports` add explicit `team_id`, source, submitted/edit timestamps, and keep
  uniqueness `(user_id, work_item_id, report_date)`.
- `work_item_status_events` form the append-only status timeline.
- `weekly_reports` add `MULTI_TEAM` scope and optional structured sections.
- `weekly_report_teams` records every Team in a weekly scope.
- `report_evidence_links` normalizes traceable input type, input ID, and recorded time.
- `action_invocations` stores trigger/outcome audit data.

All repository methods require explicit actor/team scope. Multi-team queries accept an
authorized set of Team IDs and never fall back to unscoped access.

## 9. Web application

The existing React SPA is expanded into role-aware routes for Daily entry, personal
history/timeline, Member Weekly review, Team daily dashboard, blocker timeline, Team
Weekly review, and Multi-team Weekly review. The backend remains the authorization
authority; hiding controls is not authorization.

The web app consumes the generated OpenAPI TypeScript client. Loading, empty, error,
forbidden, stale/retry, and confirmation states are explicit. Teams tab and standalone
web use the same SPA and Entra identity adapter when the real integration gate opens.

## 10. Error handling and safety

- Unknown commands return `/help` suggestions without invoking an LLM.
- Unauthorized actions return a private generic denial and append a denied invocation.
- Missing Team binding returns a setup card only to an eligible PM.
- Invalid or stale form payloads return field errors and do not partially write data.
- LLM timeout or malformed output leaves evidence unchanged and creates no report.
- OpenAI-compatible responses are validated locally against the active report JSON
  Schema even when the remote endpoint advertises structured-output support.
- Missing Teams installation/conversation data records delivery failure without
  claiming success.
- Structured logs include correlation and invocation IDs and redact secrets and full
  report content.

## 11. Lightweight deployment profile

### 11.1 Topology

```text
Teams and Browser -> Vercel HTTPS
  -> React/Vite static output
  -> FastAPI Python Function
       -> Supabase PostgreSQL through Supavisor transaction pooler
```

The repository adds a thin Vercel ASGI entrypoint that imports the existing FastAPI
application. Runtime uses SSL, SQLAlchemy `NullPool`, and disabled asyncpg statement
cache for transaction-pooler compatibility. Alembic migrations use a separate migration
URL outside request handling.

Vercel Hobby and Supabase Free are a demo profile, not a production SLA. Vercel Hobby
also has non-commercial/fair-use constraints; organizational production use requires
reviewing or upgrading the hosting plan.

### 11.2 Scheduling

The free deployment does not run a persistent worker. `SCHEDULED_JOBS_ENABLED=false`
is visible in configuration/health. Request-driven bot and web actions remain enabled.
Precise reminders and durable background generation move to a paid worker/queue profile
later. No keep-alive workaround is used to evade free-tier limits.

### 11.3 Deployment checks

CI runs formatting, lint, strict type checks, backend and frontend tests, migration
clean-install, OpenAPI drift, production web build, secret scan, and preview smoke.
Production deployment runs Alembic before traffic smoke. Required secrets live only in
Vercel/Supabase environment configuration.

The hosted LLM profile uses `LLM_PROVIDER=openai_compatible` with secret
`LLM_API_KEY`, plus `LLM_BASE_URL`, `LLM_MODEL`, and an explicit structured-output
capability setting. GPT is the first real test target. Moving to the company endpoint
must be an environment-only change after its compatibility contract passes the same
adapter tests.

## 12. Testing strategy

- Registry tests: duplicate names/aliases, unknown commands, context restrictions.
- Policy tests: role inheritance, inactive membership, cross-team denial, multi-team
  all-team requirement, ownership.
- Command parser tests: slash, mention stripping, aliases, malformed input.
- Daily tests: timezone date, backfill limit, report uniqueness, atomic event/audit,
  retry idempotency.
- Timeline tests: block start, resolution, correction/supersession, exact dates.
- Weekly tests: Project grouping, optional sections, confirmed-only aggregation,
  missing contributors, immutable confirmation, evidence links, multi-team grouping.
- LLM adapter tests: OpenAI-compatible request shape, GPT/custom base URLs, local JSON
  Schema validation, malformed JSON, timeout, bounded retry, and secret redaction.
- Teams tests: installation binding, personal/group/team contexts, private result,
  card execute/submit compatibility, publish deduplication.
- Web tests: every role, loading/empty/error/forbidden states, responsive/accessibility.
- Database tests: clean migration, constraints, concurrent idempotency, scoped queries.
- Deployment tests: Vercel import, serverless database configuration, health and bot
  endpoint smoke with mocks.

Real Teams/Entra E2E remains gated on tenant/app registrations and consent. Tests using
mock activities must not be reported as real Teams integration success.

## 13. Delivery sequence

The work is split into independently testable increments:

1. Membership/RBAC and migration.
2. Audit/status-event temporal model.
3. Action contracts, registry, dispatcher, and authorization.
4. Daily and history actions.
5. Member, team, and multi-team weekly workflows.
6. Teams activity adapter, cards/dialogs, installation, and manifest.
7. Role-aware web application expansion and generated client.
8. Vercel/Supabase deployment adapter, CI, and runbooks.
9. Full security, accessibility, migration, and standalone E2E hardening.

## 14. Locked assumptions

- Monday-Friday reporting week in each Team's timezone.
- Team role applies to all Projects owned by that Team.
- Default backfill window is configurable and initially seven calendar days.
- Daily Report ownership cannot be delegated in MVP.
- Confirm and Publish are separate actions.
- Structured product data is the only bot memory in MVP.
- PostgreSQL is the source of truth; the LLM has no independent memory.
- The current modular monolith remains; transport and deployment adapters may vary.
