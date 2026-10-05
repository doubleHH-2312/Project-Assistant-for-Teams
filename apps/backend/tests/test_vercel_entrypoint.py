import importlib
import json
from pathlib import Path

from fastapi import FastAPI


def test_vercel_entrypoint_reuses_single_application_on_warm_import() -> None:
    entrypoint = importlib.import_module("api.index")
    first_app = entrypoint.app

    reloaded = importlib.reload(entrypoint)

    assert isinstance(first_app, FastAPI)
    assert reloaded.app is first_app


def test_vercel_config_builds_spa_and_routes_api_to_python_function() -> None:
    config = json.loads(Path("vercel.json").read_text())

    assert config["buildCommand"] == "corepack pnpm --filter @project-assistant/web build"
    assert config["outputDirectory"] == "apps/web/dist"
    assert any(rewrite["source"] == "/api/:path*" for rewrite in config["rewrites"])


def test_local_demo_migrates_before_seed_without_startup_schema_mutation() -> None:
    makefile = Path("Makefile").read_text()
    dockerfile = Path("infra/docker/backend.Dockerfile").read_text()
    main_module = Path("apps/backend/src/project_assistant/main.py").read_text()

    migrate = "exec -T api alembic -c apps/backend/alembic.ini upgrade head"
    seed = "exec -T api python -m project_assistant.seed"
    assert migrate in makefile
    assert makefile.index(migrate) < makefile.index(seed)
    assert "COPY apps/backend/alembic " in dockerfile
    assert "await create_schema()" not in main_module
