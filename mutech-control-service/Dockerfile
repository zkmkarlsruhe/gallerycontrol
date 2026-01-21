# MuTech Control Service - Main FastAPI Application

FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry==1.7.1

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Configure poetry to not create virtualenv (we're in a container)
RUN poetry config virtualenvs.create false

# Install dependencies (no dev deps)
RUN poetry install --only main --no-interaction --no-ansi

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash mutech

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY mutech_control/ ./mutech_control/
COPY config/ ./config/
COPY alembic.ini ./
COPY entrypoint.sh ./

# Copy static frontend if exists
COPY static/ ./static/

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Change ownership
RUN chown -R mutech:mutech /app

# Expose API port
EXPOSE 8000

# Environment variables
ENV PORT=8000
ENV HOST=0.0.0.0
ENV ENVIRONMENT=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run as non-root
USER mutech

# Run the service
ENTRYPOINT ["./entrypoint.sh"]
