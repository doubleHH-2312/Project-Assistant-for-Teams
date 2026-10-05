"""Vercel ASGI entrypoint using the shared FastAPI application singleton."""

from project_assistant.main import app

__all__ = ["app"]
