# syntax=docker/dockerfile:1

# ---- builder: resolve + install dependencies into a venv ----
FROM python:3.11-slim AS builder

# uv from its official image (pin a tag in real life for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Use the base image's system Python (not a uv-managed standalone one) so the
# venv copied into the runtime stage points at an interpreter that exists there.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_PREFERENCE=only-system \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Deps only first, so this layer caches unless pyproject/uv.lock change.
# (--frozen omitted on purpose: the committed uv.lock may lag pyproject; uv will
#  resolve as needed. Run `uv lock` and commit for fully reproducible builds.)
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --no-install-project

# App code (we run via PYTHONPATH, so the project itself isn't installed).
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# ---- runtime: slim image, non-root ----
FROM python:3.11-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

RUN useradd -r -u 1000 appuser
WORKDIR /app
COPY --from=builder /app /app
USER appuser

EXPOSE 8000

# API by default; workers/jobs override the command (see k8s manifests).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
