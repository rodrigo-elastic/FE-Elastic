# syntax=docker/dockerfile:1.7
#
# FE Copilot production image.
# Multi-stage: stage 1 builds a venv with Python deps + native build toolchain
# for weasyprint; stage 2 ships only the venv + runtime libs + app code.
# Target: Fly.io shared-cpu-1x, 256 MB, region mia.

############################################
# Stage 1: builder
############################################
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VENV_PATH=/opt/venv

# Build-time system deps: cairo/pango/gdk-pixbuf/ffi headers needed to compile
# the wheels weasyprint pulls in (cffi, pycairo). gcc + pkg-config tie it together.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        pkg-config \
        libcairo2-dev \
        libpango-1.0-0 \
        libpango1.0-dev \
        libpangoft2-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libgdk-pixbuf-2.0-dev \
        libffi-dev \
        libssl-dev \
        ca-certificates \
        curl \
 && rm -rf /var/lib/apt/lists/*

# Create the venv that stage 2 will copy verbatim.
RUN python -m venv ${VENV_PATH}
ENV PATH="${VENV_PATH}/bin:${PATH}"

# Install Python deps first (better layer caching: requirements.txt rarely
# changes). Pin pip itself to a known-good line.
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip==24.2 setuptools==75.1.0 wheel==0.44.0 \
 && pip install -r /tmp/requirements.txt

# ELSER chunk corpus pre-warm hook. We do NOT download model weights at build
# time (ELSER lives in the ES cluster, not in this image). This step is left as
# a no-op cache touchpoint so the layer exists for future pre-warming work.
# If a corpus tarball is ever vendored under data/elser_cache/, it will be
# copied as-is and remain cache-friendly.
COPY data/ /build/data/
RUN mkdir -p /build/data/elser_cache \
 && find /build/data/elser_cache -type f -name '*.json' -print0 \
        | xargs -0 -r -I{} echo "elser-cache-touch: {}" \
 || true

############################################
# Stage 2: runtime
############################################
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VENV_PATH=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH=backend \
    APP_ENV=production \
    LOG_LEVEL=INFO \
    RUNTIME_DIR=/app/runtime \
    APP_HOST=0.0.0.0 \
    APP_PORT=8123

# Runtime-only libs (no -dev headers): the shared objects weasyprint loads at
# import time, plus fonts so generated PDFs are not empty rectangles.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libcairo2 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        fonts-dejavu-core \
        fonts-liberation \
        ca-certificates \
        curl \
        tini \
 && rm -rf /var/lib/apt/lists/*

# Bring the prebuilt venv across.
COPY --from=builder /opt/venv /opt/venv

# Non-root runtime user.
RUN groupadd --system --gid 1001 feuser \
 && useradd  --system --uid 1001 --gid feuser --home /app --shell /usr/sbin/nologin feuser

WORKDIR /app

# Copy app payload. Order: smallest/most-stable first for layer reuse.
COPY --chown=feuser:feuser backend/  /app/backend/
COPY --chown=feuser:feuser frontend/ /app/frontend/
COPY --chown=feuser:feuser docs/     /app/docs/
COPY --chown=feuser:feuser data/     /app/data/

# Empty runtime dir owned by feuser; the app writes audit.jsonl, briefs/, etc here.
RUN mkdir -p /app/runtime \
 && chown -R feuser:feuser /app/runtime

USER feuser

EXPOSE 8123

# Container-level healthcheck. Fly also probes via fly.toml, but keeping this
# means `docker run` and `docker ps` show health locally.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent --show-error http://127.0.0.1:8123/api/v1/health || exit 1

# tini reaps zombies and forwards SIGTERM cleanly to uvicorn on Fly suspend.
ENTRYPOINT ["/usr/bin/tini", "--", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8123"]
