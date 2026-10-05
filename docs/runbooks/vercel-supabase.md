# Vercel and Supabase demo deployment

This profile hosts the React SPA and one FastAPI ASGI function on Vercel, backed by
Supabase Postgres. It is for a lightweight demo. It does not replace the future
persistent worker or AWS scale-up profile.

## Runtime shape

- `api/index.py` exports the same module-level FastAPI `app` used locally.
- `DATABASE_DEPLOYMENT_MODE=serverless` disables SQLAlchemy's application pool, sets
  asyncpg `statement_cache_size=0`, and requires TLS.
- `SCHEDULED_JOBS_ENABLED=false` is mandatory. Vercel is not the reminder worker.
- Daily, weekly, audit and idempotency state remains in PostgreSQL across cold starts.
- Teams and LLM clients remain adapters. A deployment is not ready for live Teams or
  GPT merely because the web application starts.

Vercel supports an ASGI `app` exported by a Python function and currently supports
Python 3.13. Supabase recommends its shared transaction pooler for serverless clients,
TLS, and `statement_cache_size=0` for asyncpg because transaction mode does not support
prepared statements.

References:

- [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)
- [Vercel FastAPI guide](https://vercel.com/kb/guide/ship-a-fastapi-app-on-vercel)
- [Supabase Postgres connections](https://supabase.com/docs/guides/database/connecting-to-postgres)

## Create and configure

1. Create one Supabase project in the closest suitable region.
2. Copy the shared pooler transaction-mode connection string for application traffic.
   It normally uses port `6543`. Store it only as Vercel `DATABASE_URL`.
3. Copy the direct connection string for migrations. Store it only in the protected
   CI or operator environment as `DATABASE_MIGRATION_URL`; do not expose it to the SPA.
4. Create a Vercel project from this repository and keep the repository root as its
   root directory. The checked-in `vercel.json` builds `apps/web/dist` and routes
   `/api/*` to the Python ASGI function.
5. Configure Preview and Production variables separately. Never reuse a production
   database for untrusted preview branches.

Required server variables:

```text
APP_ENV=production
AUTH_MODE=entra
DEV_AUTH_ENABLED=false
DATABASE_DEPLOYMENT_MODE=serverless
DATABASE_URL=<Supabase transaction pooler URL>
SCHEDULED_JOBS_ENABLED=false
CORS_ORIGINS=https://<vercel-domain>
ENTRA_TENANT_ID=<secret/configured value>
ENTRA_CLIENT_ID=<secret/configured value>
ENTRA_JWKS_URL=<validated Microsoft URL>
TEAMS_TRANSPORT=sdk
TEAMS_SKIP_AUTH=false
TEAMS_APP_ID=<secret/configured value>
TEAMS_APP_PASSWORD=<secret>
```

Set `LLM_PROVIDER=mock` for the deterministic demo. For an approved GPT or company
endpoint, set `LLM_PROVIDER=openai_compatible`, base URL, model, API key, and structured
output mode. Never prefix server secrets with `VITE_`.

Build-time SPA variables:

```text
VITE_API_URL=/api/v1
VITE_AUTH_MODE=entra
VITE_ENTRA_CLIENT_ID=<public application client ID>
VITE_ENTRA_TENANT_ID=<public tenant identifier when policy permits>
```

## Migrate and verify

Run migrations from a controlled operator or CI job using the direct database URL:

```bash
DATABASE_URL="$DATABASE_MIGRATION_URL" uv run alembic -c apps/backend/alembic.ini upgrade head
```

Do not run Alembic from a request or application cold start. After deployment, verify:

1. `/health/live` returns `200`.
2. `/health/ready` reports `database.deploymentMode=serverless` and
   `scheduledJobsEnabled=false`.
3. An Entra-authenticated user can load `/api/v1/me` and sees only active Team
   memberships.
4. Create one Daily update, reload the page, and confirm it remains in History.
5. Generate a mock weekly draft, confirm it, and verify publication still requires an
   explicit action.

Real Teams and real LLM checks remain separate gates and require approved credentials,
tenant consent, a public domain, and data-policy approval.

## Free-plan constraints and rollback

- Cold starts and connection churn are expected. Do not add keep-alive traffic to
  evade free-plan sleeping or usage limits.
- Exact reminder scheduling is disabled. Add a separately owned scheduler/worker only
  when the product requires it.
- Check current Vercel and Supabase quotas before a demo; free-plan limits can change.
- For application rollback, redeploy the previous known-good Vercel deployment.
- Database migrations are forward-only. Use a new corrective migration; never edit an
  applied revision. Take a logical backup before destructive schema changes.
- If readiness fails after a release, stop writes, restore the previous deployment,
  inspect correlated logs, and apply a forward database correction if necessary.
