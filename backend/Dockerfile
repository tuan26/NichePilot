# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv
WORKDIR /app

FROM base AS deps
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

FROM deps AS dev
RUN uv sync --frozen --no-install-project
COPY . .
RUN uv sync --frozen
ENV PATH="/app/.venv/bin:$PATH"

FROM deps AS runtime
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
RUN uv sync --frozen --no-dev \
    && groupadd --system app && useradd --system --gid app --home /app app \
    && mkdir -p /var/log/nichepilot && chown app:app /var/log/nichepilot
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["uvicorn", "nichepilot.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
