# GalleryControl

**One switch to open your museum.**

> **Production-ready** — Daily driver at [ZKM | Center for Art and Media Karlsruhe](https://zkm.de) since 2025. Battle-tested with 50+ devices across multiple exhibitions.

GalleryControl is a centralized control system for museums and galleries. It replaces hours of walking around with remotes or juggling browser tabs with a single, unified interface to manage all your exhibition devices.

## What it does

- **Turn exhibitions on/off** with a single click
- **Schedule opening hours** - devices turn on/off automatically
- **Monitor device health** - see what's online, offline, or needs attention
- **Protect artwork** - automated shutdown when sensors detect issues
- **Control any device** - projectors, power outlets, computers, custom hardware

## Supported Devices

| Protocol | Devices | Examples |
|----------|---------|----------|
| **PJLink** | Projectors, displays | Epson, Panasonic, NEC, Sony |
| **NETIO** | Smart power outlets | NETIO PowerPDU, 4All |
| **ANEL** | Power distribution | ANEL NET-PwrCtrl |
| **Shell** | Any SSH-accessible device | Linux PCs, Raspberry Pi, Mac |

## Quick Start

```bash
# Clone the repository
git clone https://github.com/zkmkarlsruhe/gallerycontrol.git
cd gallerycontrol

# Create environment file
cp .env.example .env
# Edit .env and set a secure DB_PASSWORD

# Start services
docker compose up -d

# Open the UI
open http://localhost:8000
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    GalleryControl                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   Web UI    │  │  REST API   │  │  Scheduler  │      │
│  │   (React)   │  │  (FastAPI)  │  │   (cron)    │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
│         │                │                │              │
│  ┌──────┴────────────────┴────────────────┴──────┐      │
│  │              Device Managers                   │      │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │      │
│  │  │ PJLink │ │ NETIO  │ │  ANEL  │ │ Shell  │  │      │
│  └──┴────────┴─┴────────┴─┴────────┴─┴────────┴──┘      │
│                          │                               │
│  ┌───────────────────────┴───────────────────────┐      │
│  │              PostgreSQL Database               │      │
│  └────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │ Projector│    │  Power   │    │   PC     │
    │ (PJLink) │    │ (NETIO)  │    │ (Shell)  │
    └──────────┘    └──────────┘    └──────────┘
```

## Features

### Device Control
- Turn individual devices on/off
- Group devices by artwork and exhibition
- Staggered startup to prevent power surges
- Verification that devices actually turned off

### Scheduling
- Define opening hours per exhibition
- Automatic on/off at scheduled times
- One-shot tasks for special events
- Per-device schedule overrides

### Monitoring
- Real-time device state polling
- Projector lamp hours tracking
- Connection health monitoring
- Email alerts for failures

### Protection
- Sensor integration (temperature, humidity)
- Automatic shutdown when thresholds exceeded
- Configurable protection rules per artwork

## Configuration

Configuration is managed via YAML files in `gallerycontrol/config/`:

```yaml
# config/default.yaml (excerpt)
server:
  host: 0.0.0.0
  port: 8000

monitoring:
  poll_interval_seconds: 60        # Normal device-state polling
  fast_poll_interval_seconds: 30   # During command verification

email:
  smtp_host: "${SMTP_HOST}"
  recipients: []                   # leave empty to disable status emails
```

`production.yaml` overrides `default.yaml` when `ENVIRONMENT=production`. See [the configuration guide](docs/admin-guide/configuration.md) for the full reference.

## API

Once running, visit http://localhost:8000/docs for interactive API documentation.

### Key Endpoints

```bash
# Turn on an exhibition
POST /api/control/exhibition/{id}/on

# Turn off an exhibition (with verification)
POST /api/control/exhibition/{id}/off

# Get exhibition state
GET /api/state/exhibition/{id}

# Fast lane - external triggers (artwork-level, GET or POST)
POST /external/fast/artwork/{id}/on
POST /external/fast/artwork/{id}/off
```

## Development

```bash
cd gallerycontrol
poetry install
poetry run uvicorn gallerycontrol.main:app --reload
```

### Running Tests

```bash
poetry run pytest
poetry run pytest --cov=gallerycontrol
```

## Deployment

See [examples/zkm-deployment/](examples/zkm-deployment/) for a production deployment example with Traefik reverse proxy.

### ANEL Runner

ANEL devices require UDP broadcast access. For network-isolated deployments, run the ANEL Runner as a separate service (built from `gallerycontrol/Dockerfile.anel-runner`, listens on `:8001`) on a host that can reach the ANEL devices, then point the main service at it:

```bash
# On the host with UDP access to the ANEL devices
docker build -f gallerycontrol/Dockerfile.anel-runner -t gallerycontrol-anel-runner ./gallerycontrol
docker run -d -p 8001:8001 --name anel-runner gallerycontrol-anel-runner

# Then set on the main service:
#   ANEL_RUNNER_URL=http://<runner-host>:8001
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Authors

Created by Marc Schütze @ [ZKM | Center for Art and Media Karlsruhe](https://zkm.de)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
