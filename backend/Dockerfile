FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Тесты: `docker compose run --rm --build tests`.
FROM base AS test
RUN uv sync --frozen --no-install-project
COPY . .
CMD ["pytest"]

FROM base AS runtime
COPY . .
EXPOSE 8000
# Миграции и справочники — при каждом старте: оба шага идемпотентны.
CMD ["sh", "-c", "alembic upgrade head && python -m app.assessment.catalog && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
