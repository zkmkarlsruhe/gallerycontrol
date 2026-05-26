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
4. In Edit Exhibition → **Satellite Relays**, check the satellites the exhibition can use (one exhibition can have multiple)
5. In each device's edit/add modal, pick a satellite from the dropdown — or leave on "Direct connection"

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
4. Once approved, the satellite becomes selectable in any exhibition's Satellite Relays checklist

---

## Routing Model

Two-level: exhibitions *enable* satellites, devices *pick* one.

- `exhibition_satellites` (M:N): the set of satellites a given exhibition's devices may use
- `devices.satellite_id` (nullable FK): the device's specific choice from that set

Routing decision per device:
- `satellite_id` NULL → direct connection
- `satellite_id` set → route via that satellite

The admin API validates that a device's `satellite_id` is in its exhibition's enabled set. Removing a satellite from an exhibition clears `satellite_id` on every device in that exhibition that was using it.

This supports any topology: an exhibition spanning multiple isolated networks (assign multiple satellites; pick one per device), a single device on a satellite while siblings stay direct, etc.

---

## Troubleshooting

### Satellite shows "Pending" repeatedly

- Satellite was rejected but keeps reconnecting
- API key mismatch
- Approve the satellite to stop re-attempts

### Commands failing for a device

1. Check the device's selected satellite (Edit Device → Satellite Relay)
2. Check satellite status in Admin panel (online?)
3. Verify satellite can reach the device locally
4. Check satellite logs for errors
5. Switch the device's satellite to "Direct connection" to test the direct path

### Satellite disconnects frequently

1. Check network connectivity
2. Review server logs for connection drops
3. Satellite daemon auto-reconnects with backoff
