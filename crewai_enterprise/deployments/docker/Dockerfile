# ==============================================================================
# Multi-Stage Production Dockerfile for CrewAI Enterprise
# ==============================================================================

# --- Stage 1: Build Dependencies ---
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip uv

COPY pyproject.toml ./
RUN uv pip install --system --no-cache \
    pydantic pydantic-settings fastapi "uvicorn[standard]" \
    celery redis httpx opentelemetry-api opentelemetry-sdk \
    typer rich python-dotenv pytest pytest-asyncio

# --- Stage 2: Minimal Distroless/Production Runtime ---
FROM python:3.11-slim-bookworm AS runner

WORKDIR /app

# Create non-root system user for security compliance
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source code
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup configs/ ./configs/
COPY --chown=appuser:appgroup pyproject.toml ./

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

CMD ["uvicorn", "src.crewai_core.interfaces.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
