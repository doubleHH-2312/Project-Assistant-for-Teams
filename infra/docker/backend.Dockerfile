FROM python:3.13-slim AS runtime
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock* ./
COPY apps/backend/src ./apps/backend/src
COPY apps/backend/alembic ./apps/backend/alembic
COPY apps/backend/alembic.ini ./apps/backend/alembic.ini
RUN uv sync --no-dev
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/apps/backend/src"
CMD ["uvicorn", "project_assistant.main:app", "--host", "0.0.0.0", "--port", "8000"]
