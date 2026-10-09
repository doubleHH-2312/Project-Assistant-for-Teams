# CI Safety Rules

These rules keep local development, pull requests, and the `main` workflow on the
same deterministic path. They apply to humans and coding agents.

## Non-negotiable rules

1. **Run the repository gate, not an approximation.** Before handing off or pushing
   application, infrastructure, dependency, or generated-code changes, run a fresh
   `make verify` and read the complete result. A previous run does not count after a
   later code change.
2. **Do not weaken a gate to make CI green.** Do not add `continue-on-error`, skip a
   failing test, lower type or lint strictness, hide an error, or add an unconditional
   retry. Diagnose the first failure and fix its root cause.
3. **Keep OpenAPI and the generated client atomic.** The backend contract is the source
   of truth. After a route or schema contract changes, run `make openapi`, inspect both
   generated diffs, and commit them with the implementation. Never hand-edit
   `docs/api/openapi.json` or `packages/api-client/src/schema.d.ts`.
   `make openapi-check` must pass before handoff.
4. **Treat migrations as append-only release artifacts.** Never edit an applied
   migration. Add a new migration, test upgrade from an empty database, and keep ORM
   models, migration code, and tests in the same change. `make migration-check` is
   necessary but does not replace a clean PostgreSQL migration smoke for migration or
   Compose changes.
5. **Keep `.env.example` executable.** It is the credential-free configuration used by
   CI and must contain non-empty, safe local values for every variable required during
   import or Compose startup. Docker URLs use Compose service names, not `localhost`.
   Never commit `.env` or real credentials.
6. **Make startup and cleanup safe under partial failure.** A service may fail before
   the full stack starts. Cleanup steps must still run and must tolerate an absent
   local `.env`. Inspect the failing container logs before changing health checks or
   dependency ordering.
7. **Separate instants from calendar dates.** Store and compare event instants in UTC.
   Derive Daily dates, History ranges, Overview dates, and reporting weeks from the
   configured Team IANA timezone. Reuse the shared Team-calendar helpers and add a
   boundary test where UTC and Team dates differ.
8. **Run E2E from deterministic state.** Browser acceptance starts from a newly
   migrated and seeded database volume. Tests must not depend on records created by an
   earlier run, execution order outside the declared serial flow, wall-clock UTC, or a
   real external service. A retry may expose a defect; it must not be the fix.
9. **Keep CI offline-safe and secret-safe.** Unit and E2E tests use deterministic mock
   Teams and LLM adapters. Do not require production tenants, API keys, or confidential
   data. `make security-check` must remain part of the full gate.
10. **Review the delivered diff.** Before handoff, run `git diff --check` and inspect
    `git status --short` plus the complete diff for generated drift, credentials,
    accidental artifacts, unrelated edits, API/schema changes, and migration scope.

## Required checks by change type

`make verify` is the baseline for every non-documentation change. Run the additional
checks in the matching rows; when several rows apply, combine them.

| Change | Required evidence before handoff |
|---|---|
| Documentation only | `git diff --check`; verify changed links and commands against the repository |
| Backend behavior | Focused RED/GREEN tests, then `make verify` |
| API route or schema | Focused tests, `make openapi`, inspect generated diffs, then `make verify` |
| ORM model or migration | Focused migration tests, `make migration-check`, empty-PostgreSQL upgrade, then `make verify` |
| Web behavior | Focused Vitest RED/GREEN, frontend lint/typecheck/build, then `make verify` |
| Date, timezone, schedule | UTC/Team boundary tests, clean-state `make e2e`, then `make verify` |
| `.env.example`, Docker, Makefile, CI workflow | `make verify`, clean `make demo`, `make e2e`, `make build-images`, and `make smoke` |
| Teams manifest/package | `make teams-package-check`, then `make verify` |

## Clean acceptance procedure

Use an isolated database volume when validating a CI-sensitive change so an already
confirmed report or another prior test record cannot alter the result.

```bash
# Run this in a clean worktree where .env does not already exist.
cp .env.example .env
export PROJECT_ASSISTANT_DB_VOLUME="docker_project-assistant-db-e2e-$(date +%s)"
make demo
make e2e
make build-images
make smoke
make down
```

Do not delete an existing developer volume just to obtain a clean run. Use a new,
explicitly named volume and report it in the verification evidence. Do not overwrite
an existing developer `.env`; `.env` remains untracked.

## Failure protocol

When CI fails:

1. Record the first failing command and its exact error. Later cleanup failures are
   secondary until proven otherwise.
2. Reproduce that command locally with the same committed/example configuration.
3. Use a focused failing test or deterministic reproduction before changing behavior.
4. Fix the root cause, rerun the focused check, then rerun every downstream gate the
   failure prevented.
5. Finish with a fresh `make verify`; for CI-sensitive changes, repeat the clean
   acceptance procedure above.
6. Record RED/GREEN evidence and genuine follow-ups in `context-memory/progress.md` and
   refresh `context-memory/current-handoff.md`.

## Pull-request and branch policy

- Pull requests must complete `.github/pull_request_template.md`; unchecked applicable
  gates block merge.
- `main` should require the `CI / verify` status check, an up-to-date branch, and at
  least one approval. Administrators should not bypass a failing required check.
- Merge only the commit that produced the reviewed green result. If the diff changes,
  rerun the applicable checks.
- CI configuration changes require reviewer attention to permissions, secret exposure,
  cache keys, cleanup behavior, and parity with documented local commands.
