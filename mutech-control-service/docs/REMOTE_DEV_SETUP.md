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

# 2. Create curl wrapper (routes curl through proxy with remote DNS)
mkdir -p ~/.local/bin
cat > ~/.local/bin/curl << 'EOF'
#!/bin/bash
exec /usr/bin/curl --proxy socks5h://localhost:1080 "$@"
EOF
chmod +x ~/.local/bin/curl

# 3. Start local PostgreSQL (if not running)
docker run -d --name mutech-postgres \
  -e POSTGRES_USER=mutech \
  -e POSTGRES_PASSWORD=mutech_password \
  -e POSTGRES_DB=mutech \
  -p 5432:5432 \
  postgres:16-alpine

# 4. Run migrations
export DATABASE_URL="postgresql+asyncpg://mutech:mutech_password@172.17.0.1:5432/mutech"
poetry run alembic upgrade head

# 5. Seed database (optional - for fresh setup)
docker exec -i mutech-postgres psql -U mutech -d mutech < /workspace/seed.sql

# 6. Start backend with curl wrapper in PATH
export PATH="$HOME/.local/bin:$PATH"
export DATABASE_URL="postgresql+asyncpg://mutech:mutech_password@172.17.0.1:5432/mutech"
export ENVIRONMENT="development"

poetry run uvicorn mutech_control.main:app --host 0.0.0.0 --port 8000 --reload
```

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│ Your Machine (Remote)                                               │
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
│  │ Shell Devices   │  │ DNS Server      │  │ Other Services  │    │
│  │ *.zkm.de        │  │ (resolves       │  │                 │    │
│  │ (via curl)      │  │  *.zkm.de)      │  │                 │    │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PATH` | Must include curl wrapper directory first | `$HOME/.local/bin:$PATH` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://mutech:mutech_password@172.17.0.1:5432/mutech` |
| `ENVIRONMENT` | Config environment (loads `config/{env}.yaml`) | `development` |

## Device Communication

The core application does **not** have built-in SOCKS proxy support. This is intentional to keep the production code simple.

### Shell Devices (curl-based)

Shell devices use `curl` commands. A wrapper script intercepts curl calls and routes them through the SOCKS proxy:

```bash
~/.local/bin/curl  # Wrapper that adds --proxy socks5h://localhost:1080
```

The `socks5h://` protocol is critical:
- `socks5://` = resolve DNS locally, then connect through proxy (won't work for *.zkm.de)
- `socks5h://` = resolve DNS at the proxy server (works for ZKM internal hostnames)

When the backend spawns subprocess commands like:
```bash
curl http://sammlung-frequencies.zkm.de:5000/state
```
The wrapper intercepts it and resolves `sammlung-frequencies.zkm.de` through the SSH tunnel's DNS.

### Other Device Types

These device types require direct network access and **do not work** through the SOCKS tunnel in remote dev:

- **PJLink devices** (projectors): Direct TCP connections on port 4352
- **NETIO devices** (power strips): Direct HTTP requests
- **ANEL devices**: UDP protocol (SOCKS doesn't support UDP)

For full device access, run the backend on a machine with direct ZKM network access.

## Troubleshooting

### Check SOCKS proxy is running
```bash
ps aux | grep "ssh.*-D" | grep -v grep
```

### Test curl wrapper directly
```bash
~/.local/bin/curl -s http://sammlung-frequencies.zkm.de:5000/state
# Should return: {"running":false,"state":"off","status":"success"}
```

### Test DNS resolution through proxy
```bash
# This should return JSON if the proxy and DNS are working
~/.local/bin/curl -s --connect-timeout 5 http://sonoff-08.zkm.de/switch/sonoff-08-relay
```

### Verify wrapper is being used
```bash
which curl  # Should show ~/.local/bin/curl when PATH is set correctly
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

# Restart backend (with curl wrapper in PATH)
export PATH="$HOME/.local/bin:$PATH"
poetry run uvicorn mutech_control.main:app --host 0.0.0.0 --port 8000 --reload
```

## Limitations

Remote development through SSH tunnel only supports **shell devices** that use curl. For testing PJLink, NETIO, or ANEL devices, you need direct network access to ZKM.

Consider using:
- VPN to ZKM network
- Running the backend directly on a ZKM server
- SSH port forwarding for specific device IPs (tedious but possible)
