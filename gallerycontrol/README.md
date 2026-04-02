# GalleryControl

Open-source device control system for museums and galleries. Manages daily power-on/off routines for projectors, power strips, and custom devices across multiple exhibitions.

## Features

- **Multi-device support**: PJLink projectors, NETIO/ANEL power strips, custom shell commands
- **Scheduled automation**: Cron-based schedules for exhibitions, artworks, and individual devices
- **Artwork protection**: Runtime limits and cooldown timers for sensor-triggered installations
- **Real-time monitoring**: Live device state polling with SSE push updates
- **Visitor displays**: Configurable kiosk screens showing artwork availability
- **Satellite daemon**: Control devices on remote/NATed networks via WebSocket relay
- **Inventory email**: Emergency device list sent via email when the system is offline
- **Asset tracking**: Link physical devices to inventory assets, track projector lamp hours

## Quick Start

```bash
cp docker-compose.example.yml docker-compose.yml
cp .env.example .env
# Edit .env with your DB_PASSWORD

docker compose up -d
```

The web UI is available at `http://localhost:8000`.

## Development Setup

```bash
# Backend
cd gallerycontrol
poetry install
export DATABASE_URL="postgresql+asyncpg://gallerycontrol:password@localhost:5432/gallerycontrol"
alembic upgrade head
poetry run uvicorn gallerycontrol.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## Configuration

YAML configuration with environment variable substitution (`${VAR:-default}`):

```
config/
  default.yaml      # Base config (all settings with defaults)
  production.yaml   # Production overrides
```

Key config sections: `server`, `database`, `device_types`, `orchestrator`, `monitoring`, `scheduler`, `email`, `display`, `hostname_templates`.

## Supported Device Types

| Type | Protocol | Use Case |
|------|----------|----------|
| **PJLink** | TCP/4352 | Projectors (on/off, lamp hours, status) |
| **NETIO** | HTTP JSON | Network power strips (per-outlet control) |
| **ANEL** | UDP | Network power strips (per-outlet control) |
| **Shell** | SSH/HTTP | Custom commands for any device |

## Architecture

```
gallerycontrol/          # FastAPI backend (Python 3.12+)
  api/                   # REST API endpoints
  database/              # SQLAlchemy models + Alembic migrations
  devices/               # Device protocol managers
  orchestrator/          # Command orchestration + verification
  monitoring/            # State polling + service health
  scheduler/             # Cron-based task scheduler
  services/              # Business logic (protection, SSE, inventory)
  display_assets/        # Visitor kiosk display templates

frontend/                # React 19 + TypeScript + Vite
satellite-daemon/        # Remote device relay (Python)
anel_runner/             # ANEL UDP protocol service
```

## API Documentation

Once running: `http://localhost:8000/docs` (Swagger UI)

## License

MIT - see [LICENSE](LICENSE)
