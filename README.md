# Project Assistant Tool

Microsoft Teams-centered daily reporting, operational monitoring, and human-reviewed
weekly reporting. The MVP is a Python/FastAPI modular monolith with a React web app,
PostgreSQL, a separate worker process, and adapters for Teams plus GPT/company
OpenAI-compatible LLM endpoints.

## Start here

Agents must read `AGENTS.md` and `context-memory/` before changing code.

```bash
cp .env.example .env
make bootstrap
make demo
```

- Web: http://localhost:5173
- API/OpenAPI: http://localhost:8000/docs
- Liveness: http://localhost:8000/health/live

Local mode uses seeded identities and mock Teams/LLM transports. Production startup
rejects development authentication. `make down` stops the stack without deleting its
PostgreSQL volume. See [local demo](docs/runbooks/local-demo.md) for the tested flow.

## Microsoft Teams bot and web app

The same SPA can be packaged as a Teams personal tab after it is deployed to a public
HTTPS hostname:

```bash
TEAMS_APP_ID=<real-uuid> APP_HOSTNAME=<public-hostname> make teams-package
```

The package contains a bot for personal chat, group chat, and Team/channel scopes plus
the web tab. Mention the bot and use `/help`, `/daily`, `/history`, `/daily-summary`,
`/weekly`, `/weekly-team`, or `/weekly-multi-team`; the dispatcher returns only actions
allowed by the user's role in the selected Team. See
[Teams sideload](docs/runbooks/teams-sideload.md). Entra identity, live bot delivery,
and proactive messages remain gated on real tenant registrations.

## Lightweight cloud profile

The demo deployment target is Vercel plus Supabase. The Vercel Python function exports
the same FastAPI app, while Supabase transaction-pooler traffic disables prepared
statements and local connection pooling. Scheduled reminders are deliberately disabled
in this serverless profile. Follow the
[Vercel/Supabase runbook](docs/runbooks/vercel-supabase.md); no real cloud deployment is
claimed until the external account and credential gates are opened.

## Validation

```bash
make lint
make typecheck
make test
make web-test
make build
make smoke
make verify
```

Browser acceptance runs against the deterministic Compose demo:

```bash
make demo
corepack pnpm exec playwright install chromium
make e2e
```
