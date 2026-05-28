# GalleryControl - Admin Guide

This guide covers system administration, configuration, and maintenance of the GalleryControl.

## Documentation

| Document | Description |
|----------|-------------|
| [Configuration](configuration.md) | YAML config files, environment variables, tuning |
| [Database](database.md) | Migrations, schema, backup/restore |
| [Device Protocols](protocols.md) | PJLink, NETIO, ANEL, Shell details |
| [Artwork Protection](protection.md) | Time slices, runtime limits, cooldown |
| [Scheduling](scheduling.md) | Cron jobs, system tasks, Admin Panel |
| [Satellites](satellites.md) | Remote network relay deployment |
| [Asset Tracking](assets.md) | Projector lamp hours monitoring |
| [Monitoring](monitoring.md) | State polling, SSE events, logging |
| [API Reference](api.md) | REST endpoints, Fast-Lane API |
| [Troubleshooting](troubleshooting.md) | Common issues and solutions |
| [System Internals](internals.md) | Deep-dive into how it works |

---

## System Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                 GalleryControl Service                       │
│                    (FastAPI + React)                         │
│                     Port: 8000                               │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  PostgreSQL   │  │  ANEL Runner  │  │   Satellite   │
│  Port: 5432   │  │  Port: 8001   │  │    Daemons    │
└───────────────┘  └───────────────┘  └───────────────┘
```

### Service Descriptions

| Service | Purpose | Port |
|---------|---------|------|
| **Main Service** | Web interface, API, device control | 8000 |
| **PostgreSQL** | Data storage | 5432 |
| **ANEL Runner** | UDP control for ANEL devices | 8001 |
| **Satellite Daemon** | WebSocket relay for remote networks | varies |

---

## Installation

### Docker Deployment (Recommended)

```bash
# Clone repository
git clone <repository-url>
cd gallerycontrol

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start services
docker-compose up -d
```

### Manual Installation

```bash
# Install Python dependencies
cd gallerycontrol
poetry install

# Set up database
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/gallerycontrol"
poetry run alembic upgrade head

# Build frontend
cd frontend
npm install
npm run build
cd ..

# Start service
poetry run uvicorn gallerycontrol.main:app --host 0.0.0.0 --port 8000
```

---

## Quick Links

- **Staff Guide:** [../staff-guide/README.md](../staff-guide/README.md)
- **API Docs:** `/docs` (Swagger UI) or `/redoc` (ReDoc)
- **Health Check:** `GET /health`

## Support

For technical assistance, contact the ZKM technical team.

**Logs Location:**
- Application logs: stdout/stderr
- Database logs: PostgreSQL logs
- Frontend errors: Browser console
