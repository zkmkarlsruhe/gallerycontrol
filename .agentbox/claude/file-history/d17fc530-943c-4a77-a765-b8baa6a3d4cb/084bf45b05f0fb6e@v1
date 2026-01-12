# MuTech Control System - Python Refactor

Modern Python-based museum device control system with FastAPI, PostgreSQL, and Docker.

## Architecture

- **Main Service**: FastAPI monolith handling PJLink, NETIO, Shell, and ANEL client
- **ANEL Runner**: Separate service for ANEL devices (network segment isolation)
- **PostgreSQL**: Database for exhibitions, artworks, and devices
- **React Frontend**: Modern TypeScript UI (to be implemented)

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### Setup

1. Clone and navigate to the project:
```bash
cd /workspace
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env and set secure passwords/keys
```

3. Build and start services:
```bash
docker-compose up --build
```

4. Access services:
- Main API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- ANEL Runner: http://localhost:8001 (host network mode)
- PostgreSQL: localhost:5432

### Development

To run services locally without Docker:

**Main Service:**
```bash
cd mutech-control-service
poetry install
poetry run uvicorn mutech_control.main:app --reload
```

**ANEL Runner:**
```bash
cd anel-runner-service
poetry install
poetry run uvicorn anel_runner.main:app --port 8001
```

## Project Structure

```
/workspace/
├── mutech-control-service/      # Main FastAPI service
│   ├── mutech_control/
│   │   ├── api/                 # REST endpoints
│   │   ├── database/            # Models & migrations
│   │   ├── devices/             # Device managers
│   │   ├── orchestrator/        # Command coordination
│   │   └── utils/
│   ├── config/                  # YAML configuration
│   └── tests/
│
├── anel-runner-service/         # ANEL isolated service
│   └── anel_runner/
│
├── docker-compose.yml           # Docker orchestration
└── README.md
```

## Configuration

Configuration is managed via YAML files in `mutech-control-service/config/`:

- `default.yaml`: Base configuration
- `development.yaml`: Dev overrides (optional)
- `production.yaml`: Production settings (optional)

Hot-reload is enabled - changes to config files are picked up automatically.

## Database Migrations

```bash
# Create new migration
docker-compose exec main-service poetry run alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec main-service poetry run alembic upgrade head

# Rollback
docker-compose exec main-service poetry run alembic downgrade -1
```

## API Documentation

Once running, visit http://localhost:8000/docs for interactive API documentation.

### Key Endpoints

**Control:**
- `POST /api/control/exhibition/{id}/on` - Turn on exhibition
- `POST /api/control/exhibition/{id}/off` - Turn off exhibition (with verification)
- `POST /api/control/artwork/{id}/on` - Turn on artwork
- `POST /api/control/device/{id}/on` - Turn on device

**Fast Lane:**
- `POST /api/fast/device/{id}/on` - Fast lane (no verification)
- `POST /api/fast/device/{id}/off` - Fast lane off

**State:**
- `GET /api/state/exhibition/{id}` - Get exhibition state
- `GET /api/state/device/{id}` - Get device state

**Admin:**
- `GET /api/admin/exhibitions` - List exhibitions
- `POST /api/admin/exhibitions` - Create exhibition
- (CRUD endpoints for artworks and devices)

## Features

### Implemented

✅ FastAPI REST API framework
✅ PostgreSQL database with SQLAlchemy
✅ Alembic migrations
✅ YAML configuration with hot-reload
✅ Docker deployment with docker-compose
✅ ANEL runner service with API key auth
✅ Health check endpoints

### In Progress

🚧 Device managers (PJLink, NETIO, Shell, ANEL client)
🚧 Command orchestrator with ON stagger (1s)
🚧 OFF verification with retry logic
🚧 Per-device cooldown management
🚧 REST API endpoints
🚧 SQLite to PostgreSQL migration script
🚧 Frontend React + TypeScript

## Testing

```bash
# Run tests
docker-compose exec main-service poetry run pytest

# With coverage
docker-compose exec main-service poetry run pytest --cov=mutech_control
```

## Monitoring

```bash
# View logs
docker-compose logs -f main-service
docker-compose logs -f anel-runner

# Database logs
docker-compose logs -f postgres
```

## Troubleshooting

**Database connection issues:**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check connection
docker-compose exec postgres psql -U mutech -d mutech -c "\dt"
```

**ANEL runner network issues:**
- ANEL runner uses `network_mode: host` to access UDP broadcasts
- Ensure ANEL devices are on the same network segment
- Check ports 9975 (send) and 9977 (receive) are accessible

## License

GPL-3.0

## Authors

ZKM | Center for Art and Media Karlsruhe
