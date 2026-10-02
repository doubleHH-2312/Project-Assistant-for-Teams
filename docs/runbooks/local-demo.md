# Local demo runbook

## Start

Prerequisites: Docker with Compose v2, `uv`, Node.js with Corepack, and `make`.

```bash
cp .env.example .env
make bootstrap
make demo
```

`make demo` builds and starts PostgreSQL, FastAPI, the reminder worker, and the React
SPA, then seeds deterministic data. Open <http://localhost:5173>.

Use the demo identity selector in the header:

- Member 1–2: submit daily evidence and generate a member weekly report.
- Tech Lead: inspect team coverage/blockers and generate a team weekly report after
  contributors confirm their member reports.
- PM: read-only product role for supported views.

The integration badge must say `Local / mock`. This is not evidence that Entra,
Teams delivery, or the internal LLM works.

## Verify and stop

```bash
make smoke
docker compose -f infra/docker/compose.yml ps
make down
```

The database volume is preserved by `make down`. To remove it deliberately, use the
Compose volume-removal option only after confirming demo data is disposable.
