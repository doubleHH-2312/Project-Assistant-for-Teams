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
| INT-001 Teams adapter/manifest | BLOCKED | Codex | v1.23 tab manifest instance validates; ZIP has three root files | Need public HTTPS host, app registration and tenant sideload |
| INT-002 OpenAI-compatible LLM adapter | DONE | Codex | Task 5: GPT/custom `/chat/completions` contract, 3 structured-output modes, bounded timeout/429/5xx retry, secret-safe config, malformed output and local schema rejection; fresh 54 backend tests pass | Real GPT/company smoke remains gated on credentials/data policy |
| GATE-LLM Real LLM endpoint smoke | BLOCKED | External | No API key/model approval stored; company capability contract incomplete | Supply approved GPT or company endpoint configuration |
| OPS-001 Containers/CI/IaC/runbooks | IN_PROGRESS | Codex | API/worker/web images build; Compose health and proxy smoke pass | Add GitHub Actions and Terraform baseline |
| QA-001 Full review and verification | IN_PROGRESS | Codex | Fresh: 19 backend + 1 web test pass; lint/type/build/Compose/manifest/live health pass | Add Playwright, accessibility and security review |
| ARC-002 Teams bot/action platform design | DONE | Codex | User approved written spec; added OpenAI-compatible GPT-first/company-LLM adapter decision D-014 | Write implementation plan |
| PLN-001 Teams bot/action implementation plan | DONE | Codex | 11-task TDD plan self-reviewed for spec coverage, type consistency, review risks and deployment gates | User confirmation, then Task 1 |
| BOT-001 Extensible Teams action platform | IN_PROGRESS | Codex | Approved plan `docs/superpowers/plans/2026-10-02-teams-bot-action-platform.md`; SDD ledger initialized | Execute Tasks 1-11 |
| RBAC-001 Team-scoped memberships | DONE | Codex | Tasks 1-2: membership migration/backfill, two-Team seed, inherited permission policy, explicit Team-scoped repositories and legacy scope removal; fresh 26 backend tests + Ruff + strict mypy pass | Use policy in Action Dispatcher |
| AUD-001 Invocation and status-event audit | DONE | Codex | Task 3: two-phase invocation lifecycle, sanitized metadata, idempotency constraint, atomic Daily/event/success persistence, immutable superseding timeline; blocker-date regression and fresh 29 backend tests + Ruff + mypy pass | Feed timeline evidence into actions/reports |
| BOT-002 Typed Action Registry/Dispatcher | DONE | Codex | Task 4: mention/slash parser, collision-safe registry, typed validation/context/RBAC dispatch, durable idempotent ActionResult replay, audited failure/denial/success; fresh 40 backend tests + Ruff + mypy pass | Register concrete action handlers |
| OPS-002 Vercel/Supabase demo deployment | READY | Unassigned | Pending approved spec/plan | After runnable bot/web slice |
