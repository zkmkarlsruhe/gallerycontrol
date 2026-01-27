# Satellite Relays

For controlling devices on NATed or isolated networks.

## Architecture

```
┌──────────────┐     WebSocket      ┌──────────────┐
│   MuTech     │◄──────────────────►│  Satellite   │
│   Control    │                    │   Daemon     │
└──────────────┘                    └───────┬──────┘
                                            │
                                    ┌───────┴───────┐
                                    │ Local Network │
                                    │   Devices     │
                                    └───────────────┘
```

## Setup

1. Deploy satellite daemon on the remote network
2. Configure satellite to connect to main server
3. Approve satellite in Admin panel
4. Assign exhibition to satellite
5. Enable `use_satellite` on devices

---

## Satellite Daemon Deployment

### Requirements

- Python 3.11+
- Network access to MuTech Control server (HTTPS/WSS)
- Local network access to devices

### Installation

```bash
cd satellite-daemon
poetry install
```

### Configuration

Create `config.yaml`:

```yaml
server:
  url: wss://mutech-control.museum.local/ws/satellite
  api_key: your-unique-api-key

local:
  hostname: gallery-wing-b  # Friendly identifier

protocols:
  pjlink:
    enabled: true
    timeout: 5.0
  netio:
    enabled: true
    timeout: 5.0
  shell:
    enabled: true
    timeout: 30.0
```

### Running

```bash
poetry run python -m satellite_daemon --config config.yaml
```

### Systemd Service

Create `/etc/systemd/system/mutech-satellite.service`:

```ini
[Unit]
Description=MuTech Control Satellite Daemon
After=network.target

[Service]
Type=simple
User=mutech
WorkingDirectory=/opt/satellite-daemon
ExecStart=/opt/satellite-daemon/.venv/bin/python -m satellite_daemon --config config.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable mutech-satellite
sudo systemctl start mutech-satellite
```

---

## First Connection

1. Start the satellite daemon
2. It will connect to MuTech Control and appear as "Pending"
3. An administrator must approve the satellite in the Admin panel
4. Once approved, assign exhibitions to use this satellite

---

## Device-Level Routing

Individual devices can opt-in to satellite routing:

1. Exhibition must have a satellite assigned
2. Device has `use_satellite = true`
3. Commands route through satellite instead of direct connection

This allows mixed setups where some devices are reachable directly and others require the satellite.

---

## Troubleshooting

### Satellite shows "Pending" repeatedly

- Satellite was rejected but keeps reconnecting
- API key mismatch
- Approve the satellite to stop re-attempts

### Commands failing for exhibition

1. Check satellite status in Admin panel
2. Verify satellite can reach devices locally
3. Check satellite logs for errors
4. Remove satellite assignment to test direct connection

### Satellite disconnects frequently

1. Check network connectivity
2. Review server logs for connection drops
3. Satellite daemon auto-reconnects with backoff
