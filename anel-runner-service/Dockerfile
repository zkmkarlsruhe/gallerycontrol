# ANEL Runner Service

FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.7.1

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

COPY anel_runner/ ./anel_runner/
COPY config.yaml ./

EXPOSE 8001

ENV PORT=8001
ENV HOST=0.0.0.0
ENV LOG_LEVEL=INFO
ENV BIND_ADDRESS=0.0.0.0

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

CMD ["python", "-m", "uvicorn", "anel_runner.main:app", "--host", "0.0.0.0", "--port", "8001"]
