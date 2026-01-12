#!/bin/bash
set -e

echo "Starting MuTech Control Service..."

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
while ! nc -z postgres 5432; do
  sleep 0.1
done
echo "PostgreSQL is ready!"

# Run Alembic migrations
echo "Running database migrations..."
cd /app
alembic upgrade head

# Start the FastAPI application
echo "Starting FastAPI application..."
exec uvicorn mutech_control.main:app --host 0.0.0.0 --port 8000
