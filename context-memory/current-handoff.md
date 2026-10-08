# Current Handoff

## State

- Date: 2026-10-09 (Asia/Ho_Chi_Minh).
- The approved 11-task plan in
  `docs/superpowers/plans/2026-10-02-teams-bot-action-platform.md` is implemented.
- The product now has one modular FastAPI backend, a PostgreSQL worker path, a
  role-aware React web app, and a Microsoft Teams SDK v2 bot adapter/package.
- Team Membership is the authorization source. Tech Lead inherits Member actions;
  PM has all actions only in assigned Teams. Multi-Team reports require eligibility
  in every selected Team.
- Daily submissions and edits create server-timestamped, append-only action and
  status evidence. Member, Team and multi-Team weekly reports preserve direct evidence
  lineage, require human confirmation, and use immutable revisions.
- GPT and the company model share one OpenAI-compatible adapter. Local/CI uses the
  deterministic mock and never claims a real-provider result.
- The standalone demo is available at `http://localhost:5173` while Compose is
  running. The current clean E2E database is migrated through `0008`, seeded, and
  contains the final E2E run's mock data.
- `dist/project-assistant-teams.zip` is locally validated and contains the manifest
  plus two icons. It still requires real app registration, hostname and tenant smoke.
- Vercel/Supabase is the lightweight deployment profile; AWS remains deferred.
- CI prevention policy is versioned in `docs/engineering/ci-rules.md`, enforced for
  coding agents by the root `AGENTS.md`, and surfaced to human reviewers through the
  pull-request template. The change matrix defines the minimum verification by surface.
- Commit `8b54b59` includes identity fallbacks in `core/auth.py` and Teams `context.py`
  that were not part of the CI startup fix. Falling back to `tenant-demo` or
  `entra-user-1` weakens fail-closed tenant/identity handling; remediation is tracked as
  `SEC-001` and should precede the next production deployment.
- The replacement Teams bot credentials are valid and the production endpoint is live.
  Locally, the SDK now receives the configured single-tenant ID instead of silently
  assuming a multi-tenant bot; production deployment remains pending behind `SEC-001`.

## Final verification evidence

- 2026-10-09 Teams single-tenant SDK fix: RED regression observed
  `teams_app.options.tenant_id is None` plus skipped issuer validation. GREEN passes
  after mapping `ENTRA_TENANT_ID` into the SDK. Fresh
  `UV_CACHE_DIR=/tmp/project-assistant-uv-cache make verify` passes Ruff/ESLint,
  strict mypy/TypeScript, 102 backend and 11 frontend tests, migrations,
  OpenAPI/client drift, Python/web builds, secret scan over 224 files, and Teams ZIP
  validation. Microsoft client-credential validation returned HTTP 200; unsigned
  production `/api/messages` remains correctly rejected with 401.
- 2026-10-09 CI prevention rules: confirmed the rulebook and PR template exist, every
  documented Make target is present, cross-file references resolve, and
  `git diff --check` passes. This was a prose/process-only change, so application tests
  were not rerun.
- 2026-10-09 CI regression: OpenAPI drift, cleanup without `.env`, and blank Compose
  database URLs were fixed first. The later browser failure was traced to calendar
  defaults mixing UTC, host-local time, and the configured Team timezone. RED evidence
  covered Daily (`2026-10-08` instead of `2026-10-09`), History excluding the saved
  report, Weekly selecting Sunday `2026-10-04` instead of Monday `2026-10-05`, and
  Overview requesting the prior UTC date. All four surfaces now use one Team-calendar
  utility. A fresh-volume Compose demo migrated and seeded successfully; Playwright
  passed 4/4 and the HTTP smoke passed. Fresh `make verify` passes 101 backend and 11
  frontend tests plus all lint, type, migration, OpenAPI/client drift, build,
  secret-scan, and package gates.
- 2026-10-09: `UV_CACHE_DIR=/tmp/project-assistant-uv-cache make verify` passes:
  Ruff formatting/lint, strict mypy over 84 source files, ESLint and strict TypeScript;
  100 backend and 8 frontend tests; migration and deterministic OpenAPI/client drift
  checks; Python/web builds; secret scan over 221 files; Teams ZIP validation.
- `make verify`: Ruff format/lint, strict mypy over 83 source files, ESLint and strict
  TypeScript pass; 99 backend and 8 frontend tests pass; two clean migration tests,
  deterministic OpenAPI/client drift, Python/web production builds, repository secret
  scan over 218 files, and Teams ZIP validation pass.
- `make e2e` on a clean PostgreSQL volume: 4/4 Chromium tests pass, covering keyboard
  skip-link/landmarks, Member authorization denial, Daily -> History -> Member Weekly,
  Tech Lead Team Overview -> Team Weekly, and PM multi-Team confirmation/publication.
- `make build-images && make smoke`: API, worker and web images build; Compose config,
  web HTML and proxied liveness checks pass.
- Review found no full-report/secret logging, production dev-auth/Teams skip-auth
  bypass, unstated tenant scope, generated contract drift, or accidental test output.

## External gates

- Teams/Entra: replacement bot credentials are valid and the production endpoint/JWT
  gate are active. The single-tenant SDK fix is verified locally but not deployed;
  after `SEC-001`, deploy it, sideload the replacement app package, and capture one
  real `ping` in Vercel logs.
- GPT: approved model, API key and company data policy.
- Company LLM: base URL, auth scheme, model/deployment ID and structured-output mode.
- Vercel/Supabase: project ownership, environment secrets, direct migration URL,
  transaction-pooler URL and public-domain smoke.

## Next action

1. Configure GitHub `main` branch protection to require `CI / verify`, an up-to-date
   branch, and at least one approval without administrator bypass.
2. Complete `SEC-001`, then deploy the verified Teams single-tenant SDK configuration
   and confirm production logs no longer report a missing tenant or skipped issuer.
3. Sideload the replacement package and send `ping` while tailing production logs; only
   investigate JWT/handler/database/reply code if that activity reaches Vercel and
   returns an error.
4. Fix the Vercel health-route mismatch tracked as `OPS-004`; `/health/ready` currently
   resolves to the SPA rather than the FastAPI readiness handler.
