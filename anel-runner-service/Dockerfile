# ANEL Runner Service - Network-isolated UDP Gateway
# Must run with network_mode: host to receive UDP broadcasts

FROM python:3.11-slim AS builder

WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir poetry==1.7.1

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Configure poetry to not create virtualenv (we're in a container)
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-dev --no-interaction --no-ansi

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash anel

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY anel_runner/ ./anel_runner/
COPY config.yaml ./

# Change ownership
RUN chown -R anel:anel /app

# Switch to non-root user (note: may need root for binding to privileged ports)
# USER anel

# Expose REST API port
EXPOSE 8001

# UDP ports (documentation only - use network_mode: host)
# EXPOSE 9975/udp
# EXPOSE 9977/udp

# Environment variables
ENV PORT=8001
ENV HOST=0.0.0.0
ENV LOG_LEVEL=INFO
ENV BIND_ADDRESS=0.0.0.0

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

# Run the service
CMD ["python", "-m", "uvicorn", "anel_runner.main:app", "--host", "0.0.0.0", "--port", "8001"]
