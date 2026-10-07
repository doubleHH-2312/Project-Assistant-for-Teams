# Current Handoff

## State

- Date: 2026-10-05 (Asia/Ho_Chi_Minh).
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
  running. The current release-final database is migrated through `0008`, seeded, and
  contains the final E2E run's mock data.
- `dist/project-assistant-teams.zip` is locally validated and contains the manifest
  plus two icons. It still requires real app registration, hostname and tenant smoke.
- Vercel/Supabase is the lightweight deployment profile; AWS remains deferred.

## Final verification evidence

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

- Teams/Entra: public HTTPS hostname, bot/app registrations, redirect/resource values,
  tenant consent/policy and test users.
- GPT: approved model, API key and company data policy.
- Company LLM: base URL, auth scheme, model/deployment ID and structured-output mode.
- Vercel/Supabase: project ownership, environment secrets, direct migration URL,
  transaction-pooler URL and public-domain smoke.

## Next action

1. Fixed Entra SSO token verification in `auth.py` for custom API audience URIs and auto-provisioning Entra users.
2. Regenerated Azure App Registration client secret and updated `TEAMS_APP_PASSWORD` on Vercel production.
3. Reload Teams Tab to view Web App, and test Bot messaging with `/help` or direct chat.

