.PHONY: bootstrap dev demo down seed lint typecheck test web-test e2e build migrate migration build-images smoke teams-package openapi openapi-check

bootstrap:
	uv sync --all-groups
	corepack pnpm install

dev:
	docker compose -f infra/docker/compose.yml up --build

demo:
	docker compose -f infra/docker/compose.yml up -d --build
	docker compose -f infra/docker/compose.yml exec -T api python -m project_assistant.seed

down:
	docker compose -f infra/docker/compose.yml down

seed:
	docker compose -f infra/docker/compose.yml exec -T api python -m project_assistant.seed

lint:
	uv run ruff check apps/backend/src apps/backend/tests
	corepack pnpm --filter @project-assistant/web lint

typecheck:
	uv run mypy apps/backend/src
	corepack pnpm --filter @project-assistant/web typecheck

test:
	uv run pytest

web-test:
	corepack pnpm --filter @project-assistant/web test

e2e:
	corepack pnpm exec playwright test

build:
	uv build
	corepack pnpm --filter @project-assistant/web build

migrate:
	uv run alembic -c apps/backend/alembic.ini upgrade head

migration:
	uv run alembic -c apps/backend/alembic.ini revision --autogenerate -m "$(name)"

build-images:
	docker compose -f infra/docker/compose.yml build

smoke:
	docker compose -f infra/docker/compose.yml config --quiet
	curl --fail --silent http://localhost:5173/ >/dev/null
	curl --fail --silent http://localhost:5173/health/live >/dev/null

teams-package:
	./scripts/package-teams-app.sh

openapi:
	uv run python scripts/export-openapi.py
	corepack pnpm --filter @project-assistant/api-client generate

openapi-check:
	uv run python scripts/export-openapi.py --check
	corepack pnpm --filter @project-assistant/api-client generate:check
