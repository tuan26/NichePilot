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
# E1 – PII NER tùy chọn (quyết định I2): CHỈ image dev khi chủ sở hữu bật INSTALL_PII_NER=true.
# Stage `runtime` (production) không bao giờ cài nhóm `pii-ner` hay model spaCy; model không bao giờ tải lúc chạy.
ARG INSTALL_PII_NER=false
ARG SPACY_MODEL_URL=https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
ARG SPACY_MODEL_SHA256=1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    if [ "$INSTALL_PII_NER" = "true" ]; then \
      uv sync --frozen --no-install-project --extra pii-ner \
      && python -c "import urllib.request; urllib.request.urlretrieve('$SPACY_MODEL_URL', '/tmp/en_core_web_sm-3.8.0-py3-none-any.whl')" \
      && echo "$SPACY_MODEL_SHA256  /tmp/en_core_web_sm-3.8.0-py3-none-any.whl" | sha256sum -c - \
      && uv pip install --no-deps /tmp/en_core_web_sm-3.8.0-py3-none-any.whl && rm /tmp/en_core_web_sm-3.8.0-py3-none-any.whl; \
    else \
      uv sync --frozen --no-install-project; \
    fi
COPY . .
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    if [ "$INSTALL_PII_NER" = "true" ]; then uv sync --frozen --extra pii-ner --inexact; else uv sync --frozen; fi
ENV PATH="/app/.venv/bin:$PATH"

FROM deps AS runtime
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen --no-dev \
    && groupadd --system app && useradd --system --gid app --home /app app \
    && mkdir -p /var/log/nichepilot /var/lib/nichepilot/erasure-ledger /var/lib/nichepilot/searxng \
    && chown app:app /var/log/nichepilot /var/lib/nichepilot/erasure-ledger /var/lib/nichepilot/searxng
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["uvicorn", "nichepilot.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
