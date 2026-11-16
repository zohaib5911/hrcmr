# syntax=docker/dockerfile:1
#
# API image (plan.md T0.4): multi-stage, slim, runs as a non-root user, base images pinned by digest.
# The worker service reuses this image with a different start command.
#
#   docker build -t brand-api:dev api/
#
# Refresh the pins deliberately: pull the new tag, read its digest with
#   docker image inspect --format '{{index .RepoDigests 0}}' <image>
# then update the two digests below and rebuild.

ARG PYTHON_IMAGE=python:3.12-slim-trixie@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159

FROM ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 AS uv

# --- builder: resolve and install locked dependencies into a virtualenv --------------------------
FROM ${PYTHON_IMAGE} AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
# --frozen: install exactly what uv.lock says and fail if it is out of date. No dev tools.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# --- runtime: no uv, no compilers, no package manager caches --------------------------------------
FROM ${PYTHON_IMAGE} AS runtime
# Security fixes for the base image's own packages (a fixed apt CVE is not in the base tag yet).
# WeasyPrint (plan section 2): text-only inspection PDFs need Pango and a Unicode font.
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent \
        --shell /usr/sbin/nologin app
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
# Code is owned by root and read-only to the app user.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini gunicorn.conf.py ./
RUN python -m compileall -q app alembic gunicorn.conf.py

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request as u; u.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/v1/health', timeout=3)"]

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app.main:create_app()"]
