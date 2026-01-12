# MuTech Control Service

Main control service for the MuTech museum device control system.

## Features

- FastAPI REST API for device control
- Support for multiple device types: PJLink, NETIO, ANEL, Shell
- Intelligent ON command staggering (1s delay)
- OFF command verification with retry logic
- Fast lane API for external triggers
- Hot-reloadable YAML configuration
- PostgreSQL database for 1000+ devices
- Per-device cooldown management

## Installation

```bash
# Install dependencies with Poetry
poetry install

# Setup database
alembic upgrade head

# Run development server
poetry run uvicorn mutech_control.main:app --reload --host 0.0.0.0 --port 8000
```

## Configuration

Configuration is managed via YAML files in the `config/` directory:

- `default.yaml` - Base configuration
- `development.yaml` - Development overrides
- `production.yaml` - Production settings

Environment variables can be used to override config values using `${VAR_NAME}` syntax.

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=mutech_control
```

## License

GPL-3.0
