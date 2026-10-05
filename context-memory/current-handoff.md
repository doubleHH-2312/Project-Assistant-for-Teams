# Current Handoff

## State

- Date: 2026-10-05 (Asia/Ho_Chi_Minh).
- The approved conversational design for the extensible Teams bot, team-scoped RBAC,
  append-only audit/status history, multi-team reporting, and Vercel/Supabase demo
  deployment is now captured in
  `docs/superpowers/specs/2026-10-02-teams-bot-action-platform-design.md`.
- The user approved the written spec and 11-task TDD implementation plan at
  `docs/superpowers/plans/2026-10-02-teams-bot-action-platform.md`. Tasks 1-8 are
  implemented. Every Daily create/edit starts an invocation
  and appends a server-timestamped Work Item Status Event; the report, event, and
  successful outcome commit atomically. Task 4 adds the typed parser/registry/dispatcher
  and persists private Action Results separately for cold-start-safe idempotent replay.
- Task 5 replaces the former internal-only branch with one OpenAI-compatible provider
  for GPT and the future company endpoint. Provider switching is configuration-only;
  no real credential is stored or used in tests.
- Task 6 registers concrete `/daily`, `/history`, `/daily-summary`, and `/help`
  handlers. Personal chat prompts for Team selection, group-bound scope cannot be
  overridden, Daily forms expose only active Team projects/work items, and blocker
  summaries use append-only status event dates. Seed data now carries matching
  invocation and event records.
- Task 7 adds Project-grouped Member/Team weekly evidence, Team-then-Project
  multi-Team reports, tenant-scoped multi-Team templates, normalized evidence links,
  immutable revisions, explicit idempotent publication, and private `/weekly`,
  `/weekly-team`, and `/weekly-multi-team` handlers. The deterministic mock preserves
  evidence IDs and leaves risk/issue/lesson sections empty when evidence is absent.
- Task 8 adds the Microsoft Teams SDK v2 adapter at `/api/messages`, personal/group/
  channel activity context mapping, PM-only group-to-Team bindings, install capture,
  Adaptive Cards, privacy-aware presentation, proactive delivery failure semantics,
  and a bot-enabled v1.23 manifest. Ordinary chat text is discarded before any
  identity lookup or persistence; shared conversations never receive private report
  bodies.
- Task 9 adds deterministic OpenAPI export and drift checking, generated TypeScript
  contracts, `/me` Team memberships/permissions, Daily history/options, publication,
  and a responsive Fluent UI web application. Member, Tech Lead and PM navigation is
  derived from the active Team permissions; weekly confirmation, revision and Teams
  publication are separate explicit controls.
- Task 10 adds a Vercel ASGI entrypoint that reuses the shared FastAPI singleton,
  Supabase transaction-pooler-safe asyncpg settings, structured readiness modes and a
  deployment/migration/rollback runbook. No real cloud deployment has been claimed.
- D-014 records the GPT-first OpenAI-compatible adapter; switching to the company LLM
  is configuration-only after its endpoint passes the shared contract tests.
- A runnable local web vertical slice is available at `http://localhost:5173` when the
  Compose stack is running. The current stack was built, started, and seeded.
- API, PostgreSQL, worker, and web containers are running; API reports healthy.
- A Teams v1.23 bot + personal-tab package is generated at
  `dist/project-assistant-teams.zip`. It contains only `manifest.json`, `color.png`,
  and `outline.png`; example values are non-production and no tenant smoke is claimed.
- `AGENTS.md` routes the installed `.agents/skills/` plus Superpowers workflows and
  requires context-memory handoff discipline.

## Verification performed

- Backend: Task 10 fresh run passed 97 tests; Ruff and strict mypy passed. Migration
  tests cover clean install, legacy Daily `team_id` backfill, audit, and action-result
  storage.
- Frontend: 8 Vitest tests, ESLint, strict TypeScript and Vite production build passed.
- Contracts: deterministic OpenAPI export and generated TypeScript drift checks pass.
- Containers: API, worker, and web images built; Compose health ordering passed.
- Live HTTP: web HTML and proxied liveness returned 200; overview returned seeded data;
  daily `BLOCKED` report returned the expected fallback `effectiveBlocker`; member
  weekly generation and confirmation succeeded using the deterministic mock LLM.
- Teams package: fresh ZIP layout inspection found exactly the manifest and two icons
  at root. Adapter tests cover endpoint registration, skip-auth rejection, mention/
  slash parsing, passive-message discard, bindings, privacy, cards and missing
  proactive-conversation failure.

## Next action

Continue Task 11 under RED -> GREEN -> REFACTOR: add Playwright acceptance coverage,
deterministic CI/security/migration gates, local demo instructions, run full verification
and review the complete diff before final handoff.

## External blockers

- Teams/Entra: public HTTPS hostname, app registrations, redirect/resource values,
  tenant policy/consent, bot registration, and test users.
- GPT: API key, approved model and data policy are needed only for a real-provider smoke.
- Company LLM: base URL, auth, model and structured-output capability are still needed
  for its contract smoke; implementation targets the shared OpenAI-compatible shape.
- Vercel/Supabase: project ownership, environment configuration, public domain and
  hosting-plan suitability must be supplied before a real deployment smoke test.
- AWS is deferred as a future scale-up path rather than an active MVP gate.
