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

## Microsoft Teams tab

The same SPA can be packaged as a Teams personal tab after it is deployed to a public
HTTPS hostname:

```bash
TEAMS_APP_ID=<real-uuid> APP_HOSTNAME=<public-hostname> make teams-package
```

See [Teams sideload](docs/runbooks/teams-sideload.md). Entra NAA, bot delivery, and
proactive messages remain gated on real tenant registrations; the current app package
is the tab capability and local mode uses mock authentication.

## Validation

```bash
make lint
make typecheck
make test
make web-test
make build
make smoke
```
