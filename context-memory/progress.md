# Progress

Statuses: `READY`, `IN_PROGRESS`, `BLOCKED`, `DONE`.

| Task | Status | Owner | Verification evidence | Next action |
|---|---|---|---|---|
| CTX-001 Context memory baseline | DONE | Codex | Files created before application source | Start foundation |
| FND-001 Repository/tooling skeleton | DONE | Codex | Ruff/mypy/web lint/test/build pass | Maintain toolchain |
| FND-002 Database schema/migrations/seed | DONE | Codex | Migration test; FK-enforced seed test; PostgreSQL seed smoke | Use Alembic in deployed environments |
| DLY-001 Daily report API/domain | DONE | Codex | Domain/service/API tests; live POST smoke with effectiveBlocker | Add generated client drift gate |
| DLY-002 Daily report web flow | DONE | Codex | Vitest render test; production Vite build; live web container | Add browser E2E |
| MON-001 Overview and member activity | DONE | Codex | Overview tests; live coverage changed 60% to 80% after report | Add drill-down screens |
| MON-002 Reminder worker | DONE | Codex | Schedule/service tests; worker container stays running | Real delivery belongs to INT-001 |
| WKL-001 Member weekly workflow | DONE | Codex | Service/API tests; live generate and confirm smoke with mock LLM | Add browser E2E |
| WKL-002 Team weekly workflow/revisions | DONE | Codex | Confirmed-only aggregation and immutability/revision tests | Add browser E2E |
| WKL-003 Project-grouped multi-team weekly | DONE | Codex | Task 7: Project-grouped Member/Team output, Team-grouped multi-Team output, normalized evidence links, tenant/all-Team RBAC, immutable revision path, explicit idempotent publication, and three private weekly actions; fresh 75 backend tests + Ruff + strict mypy pass | Wire weekly actions into Teams adapter and web/API surfaces |
| INT-001 Teams adapter/manifest | DONE | Codex | Teams SDK v2 FastAPI adapter, authenticated `/api/messages`, install/binding/context handlers, privacy presenters, proactive transport and bot manifest; ZIP contains exactly manifest + icons | Real tenant smoke tracked separately by GATE-TEAMS |
| INT-002 OpenAI-compatible LLM adapter | DONE | Codex | Task 5: GPT/custom `/chat/completions` contract, 3 structured-output modes, bounded timeout/429/5xx retry, secret-safe config, malformed output and local schema rejection; fresh 54 backend tests pass | Real GPT/company smoke remains gated on credentials/data policy |
| GATE-LLM Real LLM endpoint smoke | BLOCKED | External | No API key/model approval stored; company capability contract incomplete | Supply approved GPT or company endpoint configuration |
| OPS-001 Containers/CI/runbooks | DONE | Codex | GitHub Actions runs deterministic quality, migration, OpenAPI, browser, image, smoke, package and secret gates; three Compose images build and HTTP smoke passes | Open real cloud gates when account access is supplied |
| QA-001 Full review and verification | DONE | Codex | Fresh `make verify`: 99 backend + 8 frontend tests, lint, strict typecheck, OpenAPI, migrations, builds, secret and Teams package checks pass; Playwright 4/4, container build and HTTP smoke pass | Run gated Teams, LLM and Vercel/Supabase smoke when credentials exist |
| ARC-002 Teams bot/action platform design | DONE | Codex | User approved written spec; added OpenAI-compatible GPT-first/company-LLM adapter decision D-014 | Write implementation plan |
| PLN-001 Teams bot/action implementation plan | DONE | Codex | 11-task TDD plan self-reviewed for spec coverage, type consistency, review risks and deployment gates | User confirmation, then Task 1 |
| BOT-001 Extensible Teams action platform | DONE | Codex | Approved plan Tasks 1-11 complete; action core, reporting, Teams SDK adapter, role-aware web, cloud profile, CI and acceptance verification delivered | Real integrations remain separately gated |
| RBAC-001 Team-scoped memberships | DONE | Codex | Tasks 1-2: membership migration/backfill, two-Team seed, inherited permission policy, explicit Team-scoped repositories and legacy scope removal; fresh 26 backend tests + Ruff + strict mypy pass | Use policy in Action Dispatcher |
| AUD-001 Invocation and status-event audit | DONE | Codex | Task 3: two-phase invocation lifecycle, sanitized metadata, idempotency constraint, atomic Daily/event/success persistence, immutable superseding timeline; blocker-date regression and fresh 29 backend tests + Ruff + mypy pass | Feed timeline evidence into actions/reports |
| BOT-002 Typed Action Registry/Dispatcher | DONE | Codex | Task 4: mention/slash parser, collision-safe registry, typed validation/context/RBAC dispatch, durable idempotent ActionResult replay, audited failure/denial/success; fresh 40 backend tests + Ruff + mypy pass | Register concrete action handlers |
| BOT-003 Daily reporting actions | DONE | Codex | Task 6: `/daily`, `/history`, `/daily-summary`, `/help`; Team selection/binding, permission-filtered help, Team-local default/backfill checks, scoped form choices, immutable blocker dates; fresh 62 backend tests + Ruff + strict mypy pass | Build project-grouped weekly actions |
| BOT-004 Microsoft Teams bot adapter | DONE | Codex | Task 8: 87 backend tests, Ruff, strict mypy, frontend lint/typecheck pass; manifest package contains exactly 3 root files; unauthenticated SDK mode rejected outside local/test | Build generated OpenAPI client and role-aware web surfaces |
| WEB-001 OpenAPI client and role-aware web app | DONE | Codex | 91 backend tests and 8 frontend tests pass; OpenAPI export/drift check, strict TypeScript, ESLint and Vite build pass; navigation is scoped by server-returned Team permissions | Add Playwright acceptance coverage in Task 11 |
| GATE-TEAMS Real Teams/Entra smoke | BLOCKED | External | SDK and installable package are complete locally; no real tenant/app registration/public HTTPS host supplied | Configure Azure Bot endpoint `/api/messages`, sideload package and run personal/group/channel smoke |
| OPS-002 Vercel/Supabase demo deployment | DONE | Codex | 97 backend tests pass; Vercel ASGI warm-import, Supabase transaction-pooler options, readiness modes and fail-closed production config are tested; runbook documents migration and rollback | Real preview/production smoke remains externally gated |
