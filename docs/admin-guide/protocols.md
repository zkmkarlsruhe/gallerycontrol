# Device Protocols

## PJLink

Industry-standard projector control protocol.

**Features:**
- TCP connection on port 4352
- MD5 authentication
- State polling (power, lamp hours, errors)
- Warmup/cooldown detection

**Configuration:**
```yaml
device_types:
  pjlink:
    cooldown_seconds: 30       # Min time between requests to same device
    request_timeout: 10        # TCP connection timeout
    verify:
      enabled: true
      interval_seconds: 30           # Poll interval during verification
      initial_timeout_seconds: 300   # Give up if state never reached
      stable_duration_seconds: 300   # Hold-stable window after state reached
      max_retries: 3
```

**PJLink States:**

| State | Code | Description |
|-------|------|-------------|
| OFF | 0 | Projector off |
| ON | 1 | Projector on |
| COOLING | 2 | Cooling down after OFF |
| WARMING | 3 | Warming up after ON |
| ERROR | -1 | Communication error |

**Extended Info Queries:**

The system queries additional projector information:
- `INF1` - Manufacturer
- `INF2` - Product name
- `LAMP` - Lamp hours and status
- `ERST` - Error status (fan, lamp, temp, cover, filter)

---

## NETIO

HTTP JSON API for smart power strips.

**Features:**
- Per-outlet control
- Basic authentication
- State monitoring

**Supported Models:**
- NETIO 4, NETIO 4All
- NETIO PowerPDU 4C/8QS

**API Endpoints:**
```
GET  http://device/netio.json         # Get state
POST http://device/netio.json         # Set state
```

**Configuration:**
```yaml
device_types:
  netio:
    cooldown_seconds: 5
    request_timeout: 5
```

---

## ANEL

UDP-based control for ANEL power distribution units.

**Architecture:**
```
GalleryControl ──HTTP──► ANEL Runner ──UDP──► ANEL Device
```

The ANEL Runner service handles UDP communication and exposes an HTTP API. This is necessary because:
1. UDP doesn't work well in containerized environments
2. ANEL devices require specific timing/retry logic
3. Centralizes UDP handling for multiple GalleryControl instances

**Starting ANEL Runner** (on a host with UDP access to the ANEL devices; listens on `:8001`):
```bash
# Container (recommended)
docker build -f gallerycontrol/Dockerfile.anel-runner -t gallerycontrol-anel-runner ./gallerycontrol
docker run -d -p 8001:8001 gallerycontrol-anel-runner

# Or run the module directly
cd gallerycontrol && python -m anel_runner.main
```

**Configuration:**
```yaml
device_types:
  anel:
    cooldown_seconds: 5
    request_timeout: 5
    runner_url: "${ANEL_RUNNER_URL}"
    runner_api_key: "${ANEL_API_KEY}"
```

---

## Shell

Execute arbitrary commands for custom device control.

**Use Cases:**
- Wake-on-LAN
- SSH commands
- HTTP API calls
- Local scripts

**Placeholders:**

| Placeholder | Replaced With |
|-------------|---------------|
| `{{HOST}}` | Device hostname |
| `{{USERNAME}}` | Credential username |
| `{{PASSWORD}}` | Credential password |
| `{{CREDENTIAL:name}}` | Specific credential by name |

**Example Commands:**

Wake-on-LAN:
```bash
wakeonlan {{HOST}}
```

SSH command:
```bash
sshpass -p '{{PASSWORD}}' ssh {{USERNAME}}@{{HOST}} 'power on'
```

HTTP API:
```bash
curl -X POST http://{{HOST}}/api/power -d '{"state":"on"}'
```

**Configuration:**
```yaml
device_types:
  shell:
    cooldown_seconds: 2
    request_timeout: 30
    verify:
      enabled: false  # Shell commands don't have verifiable state
```

**Shell Templates:**

Reusable command templates can be stored in the Shell Library and applied when creating devices.
