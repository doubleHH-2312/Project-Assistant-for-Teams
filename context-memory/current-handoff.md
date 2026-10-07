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

1. Azure App Registration `f3ab6a30-1e75-4c22-9974-87c58049ac5a` has been verified via Azure CLI (`identifierUris`, `access_as_user` scope, and pre-authorized Teams client IDs are active).
2. Upload/update `dist/project-assistant-teams.zip` in Teams to apply the updated manifest with `webApplicationInfo`.
3. Verify Bot Messaging Endpoint in Azure/Teams Developer Portal points to `https://project-assistant-for-teams.vercel.app/api/messages`.

