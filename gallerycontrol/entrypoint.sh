#!/bin/bash
set -e

echo "Starting GalleryControl..."

# Extract database host from DATABASE_URL
# Format: postgresql+asyncpg://user:pass@host:port/db
if [ -n "$DATABASE_URL" ]; then
    # Extract host:port from URL
    DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:/]*\).*/\1/p')
    DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_PORT=${DB_PORT:-5432}
else
    DB_HOST=${DB_HOST:-gallerycontrol-postgres}
    DB_PORT=${DB_PORT:-5432}
fi

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
while ! nc -z "$DB_HOST" "$DB_PORT"; do
    sleep 0.5
done
echo "PostgreSQL is ready!"

# Run Alembic migrations
echo "Running database migrations..."
cd /app
alembic upgrade head

# Start the FastAPI application
echo "Starting FastAPI application..."
exec uvicorn gallerycontrol.main:app --host 0.0.0.0 --port ${PORT:-8000}
