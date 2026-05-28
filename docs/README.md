# GalleryControl

**Museum Device Control System** for managing exhibitions, artworks, and connected devices.

Developed by ZKM | Center for Art and Media Karlsruhe.

## Overview

GalleryControl is a web-based system for controlling museum exhibition devices including projectors, power strips, and custom hardware. It provides:

- **Hierarchical Control**: Manage devices at exhibition, artwork, or individual device level
- **Multi-Protocol Support**: PJLink projectors, NETIO power strips, ANEL PDUs, and custom shell commands
- **Artwork Protection**: Time-slice windows and runtime limits to protect sensitive equipment
- **Scheduling**: Automated ON/OFF schedules with cron expressions
- **Real-time Monitoring**: Live device state updates via Server-Sent Events
- **Asset Tracking**: Lamp hours logging for projector maintenance planning
- **Satellite Relay**: Control devices on remote or isolated networks via relay daemons

## Quick Links

- [Staff Guide](staff-guide/README.md) - How to use the control interface
- [Admin Guide](admin-guide/README.md) - System configuration and maintenance
- [API Reference](admin-guide/api.md) - REST API endpoints
- Interactive API docs are served by the running app at `/docs` (Swagger UI) and `/redoc` (ReDoc)

## Features

### Device Control

| Protocol | Device Type | Features |
|----------|-------------|----------|
| **PJLink** | Projectors | ON/OFF, state polling, warmup/cooldown detection, lamp hours |
| **NETIO** | Smart power strips | Per-outlet control, state monitoring |
| **ANEL** | Power distribution units | Multi-outlet control via UDP |
| **Shell** | Custom devices | SSH/local commands, custom actions, regex state detection |

### Hierarchical Management

```
Exhibition
  └── Artwork
        └── Device
```

- Turn ON/OFF an entire exhibition (all artworks and devices)
- Turn ON/OFF a single artwork (all its devices)
- Control individual devices with custom actions

### Artwork Protection

Protect sensitive equipment with configurable limits:

- **Time-slice windows**: Maximum runtime within a time window (e.g., 7 min per 15 min)
- **Runtime + cooldown**: Maximum continuous runtime before mandatory rest
- **Force completion**: Prevent interruption until minimum runtime reached
- **External triggers**: Gate fast-lane API access per artwork

### Scheduling

- **Recurring schedules**: Cron-based automation (e.g., "Turn on at 9 AM weekdays")
- **One-shot tasks**: Delayed actions for lamp hours recording
- **Circuit breaker**: Auto-pause after consecutive failures

### Real-time Updates

- Server-Sent Events (SSE) for live state changes
- Automatic polling with configurable intervals
- Fast-poll mode during verification operations

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│  - Control Interface    - Edit Mode    - Asset Browser       │
│  - Timeline View        - Logs View    - Mobile Support      │
└─────────────────────────────────┬───────────────────────────┘
                                  │ HTTP/SSE
┌─────────────────────────────────┴───────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Control   │  │   Admin     │  │   State/Events      │  │
│  │   API       │  │   API       │  │   API (SSE)         │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         └────────────────┼───────────────────┘              │
│                    ┌─────┴─────┐                             │
│                    │Orchestrator│                            │
│                    └─────┬─────┘                             │
│  ┌──────────────────────┴────────────────────────────┐      │
│  │              Device Managers                       │      │
│  │  PJLink  │  NETIO  │  ANEL  │  Shell  │ Satellite │      │
│  └───────────────────────────────────────────────────┘      │
└─────────────────────────────────┬───────────────────────────┘
                                  │
┌─────────────────────────────────┴───────────────────────────┐
│                      PostgreSQL                              │
│  Exhibitions │ Artworks │ Devices │ Logs │ Schedules │ Assets│
└─────────────────────────────────────────────────────────────┘
```

## Getting Started

### Requirements

- Python 3.11+
- PostgreSQL 14+
- Node.js 18+ (for frontend development)

### Quick Start with Docker

```bash
docker-compose up -d
```

Access the interface at http://localhost:8000

### Development Setup

```bash
# Backend
cd gallerycontrol
poetry install
poetry run uvicorn gallerycontrol.main:app --reload

# Frontend (separate terminal)
cd gallerycontrol/frontend
npm install
npm run dev
```

## Configuration

Configuration is managed via YAML files with hot-reload support:

- `config/default.yaml` - Base configuration
- `config/production.yaml` - Production overrides

Key settings:
- Database connection
- Device polling intervals
- Concurrency limits
- Asset tracking patterns

## Documentation

| Document | Description |
|----------|-------------|
| [Staff Guide](staff-guide/README.md) | Using the control interface |
| [Admin Guide](admin-guide/README.md) | System administration |
| [Device Types](staff-guide/devices.md) | Device configuration details |
| [Asset Management](staff-guide/assets.md) | Projector tracking and lamp hours |
| [Protection System](staff-guide/protection.md) | Artwork protection configuration |
| [Scheduling](staff-guide/schedules.md) | Automated scheduling |
| [Satellite Relays](staff-guide/satellites.md) | Remote network device control |
| [API Reference](admin-guide/api.md) | REST API documentation |

## Support

For issues and feature requests, use the [GitHub issue tracker](https://github.com/zkmkarlsruhe/gallerycontrol/issues).

## License

MIT License - see [LICENSE](../LICENSE) for details.
