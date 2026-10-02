# Project Assistant Tool - Agent Instructions

## Required startup sequence

Before changing application code:

1. Read this file.
2. Read `context-memory/README.md`.
3. Read `context-memory/current-handoff.md` and `context-memory/progress.md`.
4. Read relevant entries in `context-memory/decisions.md`.
5. Mark the selected task `IN_PROGRESS` in `context-memory/progress.md`.

Before ending a work session, record verification evidence in `progress.md`, append
new architectural/product decisions when applicable, and refresh
`current-handoff.md`.

## Product invariants

- The database is the source of truth.
- LLMs transform supplied evidence; they never create project facts.
- Weekly reports require an explicit human confirmation.
- Teams, Entra ID, and LLM providers stay behind adapters.
- Team-specific behavior is configuration-driven.
- Keep the MVP a modular monolith and do not silently expand scope.
- When evidence contradicts the specification, update the decision log before code.

## Security

- Never commit credentials, tenant secrets, access tokens, private keys, or real
  confidential project data.
- Mock authentication may run only when `APP_ENV` is `local` or `test`.
- The backend enforces authentication, authorization, ownership, and tenant scope.
- Validate all external input and redact sensitive values from logs.

## Engineering workflow

- Prefer Controller -> Service -> Domain -> Repository dependency direction.
- Keep routes thin and business rules independent from web frameworks.
- Treat OpenAPI as the API source of truth; regenerate the TypeScript client after
  contract changes.
- Never edit an applied migration; add a new migration.
- Add behavior-focused tests for domain rules and critical workflows.
- A task is done only after relevant lint, type checks, tests, and smoke checks pass.
- Report assumptions, changed files, API/schema changes, executed verification, and
  genuine follow-ups in the delivery summary.

## Skill routing

Skills installed in `.agents/skills/` and enabled plugins are workflow tools, not
project documentation. At the start of each task:

1. Check the available skill catalog before exploration or implementation.
2. Apply process skills first (planning/execution, TDD, debugging, verification).
3. Apply domain skills next (architecture/domain modeling, backend, frontend/UI,
   security, testing, delivery).
4. Read every selected `SKILL.md` fully and follow referenced required material.

For an approved multi-step plan, maintain both the Superpowers execution ledger and
the committed `context-memory/progress.md`. The ledger is execution evidence;
`context-memory/` is the durable project handoff.

Root and scoped `AGENTS.md` files define repository policy and take precedence when
skill instructions overlap with project-specific rules.

## Verification and delivery

- New behavior follows RED -> GREEN -> REFACTOR. Record the failing and passing
  command output; configuration and prose-only changes do not require tests.
- On an unexpected failure, use the systematic debugging workflow before changing
  production code.
- Before any completion claim, run fresh full verification and read the output.
- Review the complete Git diff for scope, security, migrations, API contracts,
  accessibility, and accidental files before handoff.
