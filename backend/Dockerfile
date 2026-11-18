# syntax=docker/dockerfile:1
# Build tùy chọn sau proxy có CA riêng (ví dụ proxy doanh nghiệp):
#   docker build --secret id=extra_ca,src=/path/ca-bundle.crt ...
# CA chỉ được dùng trong các bước tải gói, KHÔNG được ghi vào image.
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export PIP_CERT=/run/secrets/extra_ca; fi; \
    pip install --no-cache-dir uv==0.11.32
WORKDIR /app

FROM base AS deps
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen --no-dev --no-install-project

FROM deps AS dev
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen --no-install-project
COPY . .
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen
ENV PATH="/app/.venv/bin:$PATH"

FROM deps AS runtime
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen --no-dev \
    && groupadd --system app && useradd --system --gid app --home /app app \
    && mkdir -p /var/log/nichepilot && chown app:app /var/log/nichepilot
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["uvicorn", "nichepilot.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
