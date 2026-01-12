# ANEL Runner Service

Isolated service for controlling ANEL power distribution units via UDP protocol.

## Purpose

This service must run in the same network segment as the ANEL devices due to UDP broadcast requirements. It provides a REST API for the main control service to interact with ANEL devices.

## Features

- UDP-based ANEL device control using pypwrctrl
- REST API with Bearer token authentication
- Device state monitoring
- Power control (on/off)
- Device information retrieval

## Installation

```bash
# Install dependencies
poetry install

# Run service
poetry run uvicorn anel_runner.main:app --host 0.0.0.0 --port 8001
```

## Configuration

Set these environment variables:

```bash
API_KEY=your-secure-api-key-here
PORT=8001
HOST=0.0.0.0
```

## API Endpoints

```
GET  /health                          - Health check
GET  /devices/{ip}/state?port={port} - Get device state
POST /devices/{ip}/on?port={port}    - Turn device on
POST /devices/{ip}/off?port={port}   - Turn device off
GET  /devices/{ip}/info               - Get device information
```

All endpoints (except /health) require Bearer token authentication:

```
Authorization: Bearer YOUR_API_KEY
```

## Network Requirements

- Must be on same network segment as ANEL devices
- UDP ports 9975 (send) and 9977 (receive) must be accessible
- Typically requires `network_mode: host` in Docker

## License

GPL-3.0
