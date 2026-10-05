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

- Member 1 and Member 2: submit daily evidence and generate a member weekly report.
- Tech Lead: inspect team coverage/blockers and generate a team weekly report after
  contributors confirm their member reports.
- PM: all Member and Tech Lead actions plus multi-Team reporting and Team integration
  settings.

The web navigation is calculated from the active Team membership returned by the
backend. A user may hold different roles in different Teams. Changing the current Team
must immediately remove actions that are not allowed in that Team.

Demo paths:

1. As Member 1, create a Daily update, open History, and confirm the exact report date.
2. Generate My weekly, review the JSON evidence, save if edited, then confirm.
3. As Tech Lead, inspect Team overview and generate Team weekly from confirmed member
   reports.
4. As PM, select at least two eligible Teams for Multi-team weekly. Confirmation does
   not publish; Teams publication requires a conversation ID and a separate checkbox.

The integration badge must say `Local / mock`. This is not evidence that Entra,
Teams delivery, or the internal LLM works.

## Verify and stop

```bash
make smoke
make e2e
docker compose -f infra/docker/compose.yml ps
make down
```

The database volume is preserved by `make down`. To remove it deliberately, use the
Compose volume-removal option only after confirming demo data is disposable.
