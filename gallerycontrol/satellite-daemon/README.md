# Satellite Daemon

A relay daemon for GalleryControl that allows controlling devices on NATed or isolated networks.

## Overview

The satellite daemon runs on a Raspberry Pi (or similar device) within the target network and:
1. Connects to the main GalleryControl server via WebSocket
2. Receives device commands from the server
3. Executes commands on local devices (ANEL, NETIO, PJLink, Shell)
4. Reports results back to the server

This enables control of devices that aren't directly accessible from the main server.

## Installation

### From Source

```bash
cd satellite-daemon
pip install .
```

### Create Service User

```bash
sudo useradd -r -s /bin/false satellite
sudo mkdir -p /etc/satellite-daemon /var/lib/satellite-daemon
sudo chown satellite:satellite /var/lib/satellite-daemon
```

### Configure

```bash
sudo cp config.yaml.example /etc/satellite-daemon/config.yaml
sudo nano /etc/satellite-daemon/config.yaml
# Set server_url to your GalleryControl server
```

### Install Systemd Service

```bash
sudo cp satellite-daemon.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable satellite-daemon
sudo systemctl start satellite-daemon
```

## Configuration

### `/etc/satellite-daemon/config.yaml`

```yaml
# Required: Server WebSocket URL
server_url: wss://steuerung.example.com

# Optional settings
reconnect_delay: 5.0        # Seconds to wait before reconnecting
heartbeat_interval: 30.0    # Seconds between heartbeats
command_timeout: 30.0       # Seconds to wait for command completion
```

### State File

The daemon automatically creates `/var/lib/satellite-daemon/state.yaml` to store:
- API key (auto-generated on first run)
- Satellite ID (assigned after approval)
- Satellite name (assigned after approval)

## Onboarding Flow

1. Start the daemon - it will connect to the server's onboarding endpoint
2. In the GalleryControl web UI, go to Admin > Satellites
3. You'll see the pending satellite listed with its hostname
4. Enter a name and click "Approve"
5. The daemon will automatically reconnect to the main endpoint

## Supported Device Types

- **ANEL**: UDP control on ports 9975/9977
- **NETIO**: HTTP JSON API with Basic Auth
- **PJLink**: TCP on port 4352 with optional MD5 auth
- **Shell**: Custom shell commands

## Logs

```bash
# View logs
sudo journalctl -u satellite-daemon -f

# View last 100 lines
sudo journalctl -u satellite-daemon -n 100
```

## Troubleshooting

### Connection Failed

1. Check `server_url` in config - must be reachable from satellite
2. Ensure firewall allows outbound WebSocket connections
3. Check server is running and accepting satellite connections

### Command Timeout

1. Increase `command_timeout` in config
2. Check device is reachable from satellite network
3. Verify device credentials in GalleryControl

### Authentication Errors

1. Delete `/var/lib/satellite-daemon/state.yaml`
2. Restart daemon to re-onboard
3. Re-approve in web UI
