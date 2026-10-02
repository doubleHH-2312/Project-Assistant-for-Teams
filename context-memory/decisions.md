# Decision Log

Append new decisions. Do not rewrite existing records; add a superseding record.

## 2026-10-01 — D-001 Modular monolith

- Decision: Use one Python application package with separate API and worker processes.
- Reason: Fast MVP delivery while retaining clear domain and integration boundaries.
- Impact: Shared database and deployable image; modules communicate in process.

## 2026-10-01 — D-002 Portable AWS-first deployment

- Decision: Target ECS/RDS but use the same containers in Docker Compose on local or
  internal servers.
- Reason: AWS is the target while infrastructure permissions may be delayed.
- Impact: Avoid AWS-only behavior in application code.

## 2026-10-01 — D-003 Authentication modes

- Decision: Entra ID is production identity. Local/test may use an explicit mock
  identity provider; startup must reject mock auth in production.
- Reason: Enable a reliable demo without weakening production authentication.

## 2026-10-01 — D-004 Weekly scope and evidence

- Decision: Support member and team weekly reports. Team reports aggregate confirmed
  member reports only. Confirmed reports are immutable and revised explicitly.
- Reason: Preserve human-reviewed evidence and traceability.

## 2026-10-01 — D-005 Contract-first external integrations

- Decision: Teams and internal LLM implementations share interfaces with deterministic
  mocks. Real smoke tests are gated on permissions/contracts.
- Reason: External access is not currently available.

## 2026-10-01 — D-006 Execute in the initial checkout

- Decision: Continue bootstrap in the current checkout instead of creating a linked
  worktree.
- Reason: The repository is on an unborn `main` branch with no `HEAD`; the current
  uncommitted baseline is the only safe source for a worktree.
- Impact: Create an initial verified commit before requiring worktrees for later
  feature branches.

## 2026-10-01 — D-007 Skill routing after agent setup

- Decision: Discover installed project skills under `.agents/skills/` and use the
  Superpowers plugin for execution/TDD/debugging/verification workflows.
- Reason: The user replaced the earlier `.codex/skills/` setup.
- Impact: `AGENTS.md` describes capability-based routing instead of hard-coded skill
  filenames that may become stale.

## 2026-10-01 — D-008 Runnable web output before gated integrations

- Decision: Ship the standalone React/FastAPI/PostgreSQL vertical slice as the first
  runnable output, and package the same SPA as a Teams personal tab template.
- Reason: The user needs a tangible app now, while Teams/Entra credentials and a public
  HTTPS deployment are not available.
- Impact: Local mock mode is demonstrable end-to-end. The Teams ZIP is not evidence of
  real tenant, Entra, bot, or proactive-message integration.

## 2026-10-01 — D-009 Explicit seed dependency phases

- Decision: Flush deterministic seed records in foreign-key dependency phases instead
  of relying on ORM unit-of-work ordering without relationships.
- Reason: PostgreSQL and SQLite with foreign keys enabled both rejected the previous
  single-flush seed order.
- Impact: Seed remains idempotent and portable while domain models stay relationship-free.

## 2026-10-02 — D-010 Shared Action Registry

- Decision: Teams commands use a typed Action Registry and dispatcher; bot handlers and
  web controllers call the same application use cases and authorization policies.
- Reason: New actions must be addable without duplicating domain rules or modifying
  dispatch infrastructure.
- Impact: Teams is an adapter, not the owner of business logic.

## 2026-10-02 — D-011 Team-scoped role and evidence hierarchy

- Decision: Assign roles through Team Memberships. Member weekly reports belong to one
  Team; team reports use confirmed member reports; multi-team reports use confirmed
  team reports.
- Reason: Users can participate in multiple Teams, and cross-team reporting must not
  expose data to a Lead without the required role in every selected Team.
- Impact: Replace global `User.role` and single `User.team_id` with memberships via a
  new migration and compatibility transition.

## 2026-10-02 — D-012 Append-only action and status audit

- Decision: Persist every action attempt and every submitted Work Item status as
  append-only, server-timestamped records. Business report date and submission time are
  separate for backfills.
- Reason: Weekly reports must reproduce exact blocker dates without relying on users to
  type dates or on mutable current-state snapshots.
- Impact: Edits append superseding events; audit and evidence tables require retention
  and idempotency constraints.

## 2026-10-02 — D-013 Lightweight Vercel/Supabase deployment

- Decision: Deploy the demo SPA and FastAPI function on Vercel with Supabase PostgreSQL;
  defer AWS/Terraform and persistent workers until scale or reliability requires them.
  This supersedes D-002 as the active MVP deployment target; D-002 remains the
  documented scale-up path.
- Reason: The current product is a lightweight structured-reporting tool and should use
  a low-cost/free demo profile.
- Impact: Precise scheduled jobs are disabled in the free profile; serverless database
  pooling and hosting-plan usage constraints become explicit adapters/gates.

## 2026-10-02 — D-014 OpenAI-compatible LLM adapter

- Decision: Test real generation with GPT first, using one OpenAI-compatible adapter
  configured by base URL, API key, model and structured-output capability. Reuse that
  adapter for the company LLM when its compatibility contract is available.
- Reason: The company endpoint follows the GPT endpoint shape, so vendor-specific
  business logic would add duplication without improving the domain boundary.
- Impact: Mock remains deterministic for local/CI; every real response is validated
  locally against the report JSON Schema; switching provider is an environment-only
  operation once contract tests pass.
