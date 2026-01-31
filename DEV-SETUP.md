# GalleryControl Service - Dev Setup

## Quick Start (from container)

### 1. Start PostgreSQL
```bash
docker compose up -d
```

### 2. Install Dependencies
```bash
cd gallerycontrol-service
poetry install --no-root
```

### 3. Run Migrations
```bash
DATABASE_URL="postgresql+asyncpg://mutech:mutech_password@172.17.0.1:5432/mutech" poetry run alembic upgrade head
```

### 4. Start FastAPI Server
```bash
DATABASE_URL="postgresql+asyncpg://mutech:mutech_password@172.17.0.1:5432/mutech" \
ENVIRONMENT="development" \
LOG_LEVEL="DEBUG" \
poetry run uvicorn gallerycontrol.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Connect to PostgreSQL
```bash
PGPASSWORD=mutech_password psql -h 172.17.0.1 -p 5432 -U mutech -d mutech
```

## Network Notes

- PostgreSQL container runs on `workspace_default` network at `192.168.80.2`
- From agent container, connect via Docker host gateway: `172.17.0.1:5432`
- Port 5432 is exposed to host

## Database Credentials

| Setting   | Value            |
|-----------|------------------|
| Host      | 172.17.0.1       |
| Port      | 5432             |
| Database  | mutech           |
| User      | mutech           |
| Password  | mutech_password  |

## API Endpoints

- Health: http://localhost:8000/health
- API Docs: http://localhost:8000/docs
- OpenAPI: http://localhost:8000/openapi.json
