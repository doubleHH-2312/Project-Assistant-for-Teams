# Current Handoff

## State

- Date: 2026-10-03 (Asia/Ho_Chi_Minh).
- The approved conversational design for the extensible Teams bot, team-scoped RBAC,
  append-only audit/status history, multi-team reporting, and Vercel/Supabase demo
  deployment is now captured in
  `docs/superpowers/specs/2026-10-02-teams-bot-action-platform-design.md`.
- The user approved the written spec and 11-task TDD implementation plan at
  `docs/superpowers/plans/2026-10-02-teams-bot-action-platform.md`. Tasks 1-6 are
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
- D-014 records the GPT-first OpenAI-compatible adapter; switching to the company LLM
  is configuration-only after its endpoint passes the shared contract tests.
- A runnable local web vertical slice is available at `http://localhost:5173` when the
  Compose stack is running. The current stack was built, started, and seeded.
- API, PostgreSQL, worker, and web containers are running; API reports healthy.
- A Teams v1.23 personal-tab package template, icons, adaptive card, and packaging
  script exist. The generated demo ZIP uses non-production example values and is not
  for tenant installation.
- `AGENTS.md` routes the installed `.agents/skills/` plus Superpowers workflows and
  requires context-memory handoff discipline.

## Verification performed

- Backend: Task 6 fresh run passed 62 tests; Ruff and strict mypy passed. Migration
  tests cover clean install, legacy Daily `team_id` backfill, audit, and action-result
  storage.
- Frontend: Vitest, ESLint, TypeScript and Vite production build passed.
- Containers: API, worker, and web images built; Compose health ordering passed.
- Live HTTP: web HTML and proxied liveness returned 200; overview returned seeded data;
  daily `BLOCKED` report returned the expected fallback `effectiveBlocker`; member
  weekly generation and confirmation succeeded using the deterministic mock LLM.
- Teams package: ZIP layout inspected and manifest instance validated against the
  official Microsoft v1.23 schema. Python's meta-schema check cannot parse Microsoft's
  Unicode `\\p{L}` regex, so validation used `Draft7Validator.iter_errors` directly.

## Next action

Continue Task 7 under RED -> GREEN -> REFACTOR: build project-grouped Member, Team,
and Multi-team weekly evidence; add evidence links, multi-team persistence, explicit
publication, and the three weekly action handlers.

## External blockers

- Teams/Entra: public HTTPS hostname, app registrations, redirect/resource values,
  tenant policy/consent, bot registration, and test users.
- GPT: API key, approved model and data policy are needed only for a real-provider smoke.
- Company LLM: base URL, auth, model and structured-output capability are still needed
  for its contract smoke; implementation targets the shared OpenAI-compatible shape.
- Vercel/Supabase: project ownership, environment configuration, public domain and
  hosting-plan suitability must be supplied before a real deployment smoke test.
- AWS is deferred as a future scale-up path rather than an active MVP gate.
