# Remote Development Setup

Run the mutech-control backend locally while communicating with devices at ZKM through an SSH tunnel.

## Prerequisites

- SSH access to `museumstechnik@docker.mutech.zkm.de`
- SSH key loaded in ssh-agent
- Docker running locally
- Python dependencies installed (`poetry install`)

## Quick Start

```bash
cd /workspace/mutech-control-service

# 1. Start SOCKS proxy (SSH tunnel to ZKM network)
ssh -D 1080 -f -N -o ServerAliveInterval=60 museumstechnik@docker.mutech.zkm.de

# 2. Start local PostgreSQL (if not running)
docker run -d --name mutech-postgres \
  -e POSTGRES_USER=mutech \
  -e POSTGRES_PASSWORD=mutech_password \
  -e POSTGRES_DB=mutech \
  -p 5432:5432 \
  postgres:16-alpine

# 3. Run migrations
export DATABASE_URL="postgresql+asyncpg://mutech:mutech_password@172.17.0.1:5432/mutech"
poetry run alembic upgrade head

# 4. Seed database (optional - for fresh setup)
docker exec -i mutech-postgres psql -U mutech -d mutech < /workspace/seed.sql

# 5. Start backend with SOCKS proxy
export SOCKS_PROXY="socks5://localhost:1080"
export DATABASE_URL="postgresql+asyncpg://mutech:mutech_password@172.17.0.1:5432/mutech"
export ENVIRONMENT="development"

poetry run uvicorn mutech_control.main:app --host 0.0.0.0 --port 8000 --reload
```

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│ Your Machine (Home)                                                 │
│                                                                     │
│  ┌─────────────┐     ┌──────────────┐     ┌───────────────────┐   │
│  │   Backend   │────▶│ SOCKS Proxy  │────▶│   SSH Tunnel      │   │
│  │  :8000      │     │  :1080       │     │                   │   │
│  └─────────────┘     └──────────────┘     └─────────┬─────────┘   │
│         │                                           │             │
│         ▼                                           │             │
│  ┌─────────────┐                                    │             │
│  │  PostgreSQL │                                    │             │
│  │  :5432      │                                    │             │
│  └─────────────┘                                    │             │
└─────────────────────────────────────────────────────┼─────────────┘
                                                      │
                                                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ZKM Network (docker.mutech.zkm.de)                                  │
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐    │
│  │ PJLink Devices  │  │ NETIO Devices   │  │ Other Devices   │    │
│  │ 192.168.232.x   │  │ *.zkm.de:80     │  │                 │    │
│  │ :4352           │  │                 │  │                 │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SOCKS_PROXY` | SOCKS5 proxy URL for device communication | `socks5://localhost:1080` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://mutech:mutech_password@172.17.0.1:5432/mutech` |
| `ENVIRONMENT` | Config environment (loads `config/{env}.yaml`) | `development` |

## Device Communication

When `SOCKS_PROXY` is set:

- **PJLink devices** (projectors): TCP connections on port 4352 go through the SOCKS proxy
- **NETIO devices** (power strips): HTTP requests go through the SOCKS proxy
- **ANEL devices**: Not supported through SOCKS (uses UDP)
- **Shell devices**: Commands run locally (not tunneled)

## Troubleshooting

### Check SOCKS proxy is running
```bash
ps aux | grep "ssh.*-D" | grep -v grep
```

### Test SOCKS connectivity to a device
```bash
python3 -c "
from python_socks.sync import Proxy
proxy = Proxy.from_url('socks5://localhost:1080')
sock = proxy.connect(dest_host='192.168.232.69', dest_port=4352, timeout=5)
print('Connected!')
print(sock.recv(1024).decode())
sock.close()
"
```

### Check backend logs
```bash
tail -f /tmp/backend.log
```

### Database connection issues
If using Docker Desktop, use `host.docker.internal` instead of `172.17.0.1`:
```bash
export DATABASE_URL="postgresql+asyncpg://mutech:mutech_password@host.docker.internal:5432/mutech"
```

### Restart everything
```bash
# Kill existing processes
pkill -f "ssh.*-D.*1080"
pkill -f uvicorn

# Restart SOCKS proxy
ssh -D 1080 -f -N -o ServerAliveInterval=60 museumstechnik@docker.mutech.zkm.de

# Restart backend
poetry run uvicorn mutech_control.main:app --host 0.0.0.0 --port 8000 --reload
```

## Required Python Packages

The SOCKS proxy support requires these packages (included as dev dependencies in pyproject.toml):
- `python-socks[asyncio]` - For PJLink TCP connections
- `httpx-socks` - For NETIO HTTP requests

These are installed automatically with:
```bash
poetry install
```
