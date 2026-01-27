# MuTech Control - Admin Guide

This guide covers system administration, configuration, and maintenance of the MuTech Control System.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Database Management](#database-management)
5. [Device Protocols](#device-protocols)
6. [Artwork Protection](#artwork-protection)
7. [Scheduling System](#scheduling-system)
8. [Satellite Relays](#satellite-relays)
9. [Asset Tracking](#asset-tracking)
10. [Monitoring & Logging](#monitoring--logging)
11. [API Reference](#api-reference)
12. [Troubleshooting](#troubleshooting)
13. [Configuration Reference](#configuration-reference)
14. [System Internals](#system-internals)

---

## System Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                 MuTech Control Service                       │
│                    (FastAPI + React)                         │
│                     Port: 8000                               │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  PostgreSQL   │  │  ANEL Runner  │  │   Satellite   │
│  Port: 5432   │  │  Port: 8001   │  │    Daemons    │
└───────────────┘  └───────────────┘  └───────────────┘
```

### Service Descriptions

| Service | Purpose | Port |
|---------|---------|------|
| **Main Service** | Web interface, API, device control | 8000 |
| **PostgreSQL** | Data storage | 5432 |
| **ANEL Runner** | UDP control for ANEL devices | 8001 |
| **Satellite Daemon** | WebSocket relay for remote networks | varies |

---

## Installation

### Docker Deployment (Recommended)

```bash
# Clone repository
git clone <repository-url>
cd mutech-control

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start services
docker-compose up -d
```

### Manual Installation

```bash
# Install Python dependencies
cd mutech-control-service
poetry install

# Set up database
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/mutech"
poetry run alembic upgrade head

# Build frontend
cd frontend
npm install
npm run build
cd ..

# Start service
poetry run uvicorn mutech_control.main:app --host 0.0.0.0 --port 8000
```

---

## Configuration

### Configuration Files

| File | Purpose |
|------|---------|
| `config/default.yaml` | Base configuration |
| `config/production.yaml` | Production overrides |
| `.env` | Environment variables |

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/mutech

# ANEL Runner (optional)
ANEL_RUNNER_URL=http://localhost:8001
ANEL_API_KEY=your-api-key

# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### Key Configuration Options

```yaml
# config/default.yaml

server:
  host: "0.0.0.0"
  port: 8000

database:
  pool_size: 10
  max_overflow: 20

device_types:
  pjlink:
    timeout: 5.0
    verify_enabled: true
    verify_max_attempts: 10
    verify_interval: 3.0
    cooldown_on: 5
    cooldown_off: 30
  netio:
    timeout: 5.0
    verify_enabled: true
  anel:
    timeout: 3.0
  shell:
    timeout: 30.0

orchestrator:
  stagger_delay: 1.0          # Seconds between device ON commands
  max_concurrent_on: 5        # Max parallel ON operations
  max_concurrent_off: 10      # Max parallel OFF operations
  verification_enabled: true

monitoring:
  poll_interval: 60           # Normal polling interval (seconds)
  fast_poll_interval: 30      # Fast polling during verification
  batch_size: 30              # Devices per poll batch

scheduler:
  check_interval: 10          # Seconds between schedule checks
```

### Hot Reload

Configuration changes are detected automatically and broadcast to connected clients. No restart required for most settings.

---

## Database Management

### Migrations

```bash
# Create a new migration
poetry run alembic revision --autogenerate -m "Description"

# Apply migrations
poetry run alembic upgrade head

# Rollback one migration
poetry run alembic downgrade -1
```

### Database Schema

**Core Tables:**
- `exhibitions` - Exhibition containers
- `artworks` - Artworks within exhibitions
- `devices` - Controllable devices
- `credentials` - Password store
- `shell_templates` - Reusable shell commands

**Logging Tables:**
- `state_change_logs` - Device state transitions
- `device_operation_logs` - Detailed operation logs
- `scheduled_job_logs` - Schedule execution history

**Scheduling Tables:**
- `scheduled_jobs` - Cron and one-shot jobs

**Asset Tables:**
- `assets` - Projector asset records
- `lamp_hours_logs` - Lamp usage history

### Backup

```bash
# Backup database
pg_dump -h localhost -U mutech mutech > backup.sql

# Restore database
psql -h localhost -U mutech mutech < backup.sql
```

---

## Device Protocols

### PJLink

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
    timeout: 5.0
    verify_enabled: true
    verify_max_attempts: 10
    verify_interval: 3.0
    cooldown_on: 5      # Wait after ON before state is reliable
    cooldown_off: 30    # Wait after OFF for cooling
```

### NETIO

HTTP JSON API for smart power strips.

**Features:**
- Per-outlet control
- Basic authentication
- State monitoring

**Supported Models:**
- NETIO 4, NETIO 4All
- NETIO PowerPDU 4C/8QS

### ANEL

UDP-based control for ANEL power distribution units.

**Architecture:**
```
MuTech Control ──HTTP──► ANEL Runner ──UDP──► ANEL Device
```

The ANEL Runner service handles UDP communication and exposes an HTTP API.

**Starting ANEL Runner:**
```bash
cd anel-runner-service
poetry run python -m anel_runner
```

### Shell

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

---

## Artwork Protection

Protect sensitive equipment from overuse.

### Time-Slice Protection

Limit runtime within rolling time windows.

```json
{
  "time_slices": [
    {"window": 15, "max": 7}
  ]
}
```
*Max 7 minutes of ON time within any 15-minute window.*

### Runtime + Cooldown

Limit continuous runtime with mandatory rest periods.

```json
{
  "max_runtime": 180,
  "cooldown": 60,
  "min_budget_to_start": 30
}
```
- Max 3 minutes continuous runtime
- 1 minute cooldown before restart allowed
- Don't start if less than 30 seconds of budget remaining

### Force Completion

Prevent interruption of protected artworks.

```json
{
  "force_completion": true,
  "max_runtime": 150
}
```
OFF commands are blocked until max_runtime is reached.

### API Triggers

The `accepting_triggers` flag on artworks controls whether the Fast-Lane API can trigger the artwork.

```
POST /api/fast/artwork/{id}/on
POST /api/fast/artwork/{id}/off
```

---

## Scheduling System

### Cron Expressions

Standard cron format: `minute hour day month weekday`

**Examples:**
| Expression | Description |
|------------|-------------|
| `0 9 * * 1-5` | 9:00 AM weekdays |
| `0 18 * * *` | 6:00 PM daily |
| `*/15 * * * *` | Every 15 minutes |
| `0 0 1 * *` | Midnight on 1st of month |

### Job Types

**Device Jobs:**
- Target: exhibition, artwork, or device
- Actions: on, off, or custom action

**System Jobs:**
- `asset_linker` - Link devices to assets
- `log_cleanup` - Remove old logs
- `lamp_hours_check` - Record projector lamp hours
- `memory_cleanup` - Clear stale caches

### Circuit Breaker

Jobs automatically pause after 5 consecutive failures:
- `fail_count` tracks failures
- `backoff_until` sets retry delay
- Manual reset required via Admin panel

### Admin Panel - Task Scheduler

The Admin Panel (accessible via Edit Mode > Admin button) provides monitoring and control of the task scheduler.

#### Satellites Section

At the top of the Admin Panel:
- **Pending Approval** - Satellites waiting for approval (enter name, approve/reject)
- **Approved Satellites** - List of authorized satellites with connection status

#### Quick Actions Section

| Button | Description |
|--------|-------------|
| **Run All Scheduled Tasks Now** | Immediately triggers all scheduled system tasks |

This runs asset linking, log cleanup, and other periodic tasks without waiting for their scheduled times.

#### Task Scheduler Status

Shows the overall scheduler status and individual task states:

**Scheduler Info:**
- **Running/Stopped** badge - Overall scheduler state
- **Check interval** - How often the scheduler checks for due jobs

**Task Cards:**

Each system task shows:
| Field | Description |
|-------|-------------|
| **Name** | Task identifier (e.g., `asset_linker`, `log_cleanup`) |
| **Running** | Blue badge if currently executing |
| **Circuit Open** | Red badge if paused due to failures |
| **Last run** | When the task last executed |
| **Next run** | When it will run next |
| **Interval** | How often it runs |
| **Failures** | Count of consecutive failures |
| **Last error** | Error message if last run failed |
| **Last result** | JSON result from successful runs |

**Task Actions:**

| Button | When | Action |
|--------|------|--------|
| **Run** | Circuit closed | Manually trigger this specific task |
| **Reset** | Circuit open | Clear failure count and re-enable task |

#### Task Lifecycle

```
Task Created → Enabled → Running → Complete → Wait → Running...
                                     ↓ (failure)
                             Fail Count +1
                                     ↓ (5 failures)
                             Circuit Open → Manual Reset Required
```

---

## Satellite Relays

For controlling devices on NATed or isolated networks.

### Architecture

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

### Setup

1. Deploy satellite daemon on the remote network
2. Configure satellite to connect to main server
3. Approve satellite in Admin panel
4. Assign exhibition to satellite
5. Enable `use_satellite` on devices

### Satellite Daemon Deployment {#satellite-deployment}

#### Requirements

- Python 3.11+
- Network access to MuTech Control server (HTTPS/WSS)
- Local network access to devices

#### Installation

```bash
cd satellite-daemon
poetry install
```

#### Configuration

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

#### Running

```bash
poetry run python -m satellite_daemon --config config.yaml
```

#### Systemd Service

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

#### First Connection

1. Start the satellite daemon
2. It will connect to MuTech Control and appear as "Pending"
3. An administrator must approve the satellite in the Admin panel
4. Once approved, assign exhibitions to use this satellite

---

## Asset Tracking

Track projector usage for maintenance planning.

### Automatic Linking

Devices are linked to assets by hostname pattern:

```yaml
asset_tracking:
  hostname_pattern: "^(?P<asset>\\d{6})-"
```

Hostname `123456-projector.local` → Asset `123456`

### Lamp Hours Recording

Lamp hours are recorded:
- On device power-off (after warmup)
- Periodically via scheduled task
- Manually via Assets view

### Asset Browser

The Assets view (`#assets`) shows:
- All tracked projector assets
- Current lamp hours
- Usage history
- Linked devices

---

## Monitoring & Logging

### State Monitoring

The State Monitor polls all enabled devices:
- Normal interval: 60 seconds
- Fast interval: 30 seconds (during verification)
- Batch size: 30 devices per batch

### SSE Events

Server-Sent Events provide real-time updates:

```javascript
const eventSource = new EventSource('/api/state/events');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle: state_change, protection_update, config_change
};
```

### Log Retention

Configure log cleanup in scheduled jobs:

```yaml
scheduler:
  tasks:
    log_cleanup:
      cron: "0 3 * * *"  # 3 AM daily
      retention_days: 30
```

### Health Check

```bash
curl http://localhost:8000/health
# {"status": "healthy"}
```

---

## API Reference

### Control Endpoints

```
POST /api/control/exhibition/{id}/on
POST /api/control/exhibition/{id}/off
POST /api/control/artwork/{id}/on
POST /api/control/artwork/{id}/off
POST /api/control/device/{id}/on
POST /api/control/device/{id}/off
POST /api/control/device/{id}/action/{name}
```

### Fast-Lane API

External trigger endpoints (requires `accepting_triggers=true`):

```
POST /api/fast/artwork/{id}/on
POST /api/fast/artwork/{id}/off
GET  /api/fast/artwork/{id}/state
```

### State Queries

```
GET /api/state/exhibitions
GET /api/state/exhibition/{id}
GET /api/state/artwork/{id}
GET /api/state/device/{id}
GET /api/state/events  # SSE stream
```

### Admin CRUD

```
GET/POST        /api/admin/exhibitions
GET/PATCH/DELETE /api/admin/exhibitions/{id}
# Same pattern for: artworks, devices, credentials, shell_templates, schedules
```

### Interactive Documentation

- Swagger UI: `/docs`
- ReDoc: `/redoc`

---

## Troubleshooting

### Device Not Responding

1. Check network connectivity: `ping <device-ip>`
2. Verify port is open: `nc -zv <device-ip> <port>`
3. Check device logs in Logs view
4. Try direct API query: `GET /api/debug/device/{id}/info`

### State Not Updating

1. Check SSE connection in browser DevTools
2. Verify device is enabled
3. Check State Monitor logs
4. Force refresh: Clear browser cache

### Schedule Not Running

1. Check job status in Admin panel
2. Verify cron expression
3. Check `schedules_enabled` on target
4. Look for circuit breaker (fail_count > 5)

### Database Connection Issues

```bash
# Test connection
psql -h localhost -U mutech -d mutech -c "SELECT 1"

# Check connection pool
curl http://localhost:8000/health
```

### ANEL Devices Not Working

1. Verify ANEL Runner is running
2. Check ANEL_RUNNER_URL environment variable
3. Test directly: `curl http://localhost:8001/health`
4. Check UDP connectivity to ANEL device

### Performance Issues

1. Check database connection pool usage
2. Monitor memory usage (memory_cleanup task)
3. Review concurrent operation limits
4. Check polling batch size

---

## Configuration Reference

MuTech Control uses YAML configuration files in the `config/` directory.

### File Structure

```
config/
├── default.yaml      # Base configuration
├── development.yaml  # Development overrides
└── production.yaml   # Production overrides
```

Environment-specific files override `default.yaml`. The active environment is set via `ENVIRONMENT` env var.

### Environment Variable Substitution

Use `${VAR_NAME}` syntax in YAML to reference environment variables:

```yaml
database:
  url: "${DATABASE_URL}"
```

### Complete Configuration Schema

```yaml
# ======================
# SERVER
# ======================
server:
  host: "0.0.0.0"          # Bind address
  port: 8000               # HTTP port
  reload: false            # Auto-reload on code changes (dev only)

# ======================
# DATABASE
# ======================
database:
  url: "${DATABASE_URL}"   # PostgreSQL connection string
  pool_size: 20            # Connection pool size
  pool_pre_ping: true      # Test connections before use
  echo: false              # Log SQL queries (debug)

# ======================
# DEVICE TYPES
# ======================
device_types:
  pjlink:
    cooldown_seconds: 30       # Min time between requests to same device
    request_timeout: 10        # TCP connection timeout
    verify:
      enabled: true            # Enable verification after commands
      interval_seconds: 30     # Polling interval during verification
      initial_timeout_seconds: 300  # Max wait for initial state
      stable_duration_seconds: 300  # Enforcement period duration
      max_retries: 3           # Retries for stability failures
      on:
        success_states: [1, 3] # 1=ON, 3=WARMING
      off:
        success_states: [0, 2] # 0=OFF, 2=COOLING

  netio:
    cooldown_seconds: 5
    request_timeout: 5
    verify:
      enabled: true
      interval_seconds: 30
      initial_timeout_seconds: 180
      stable_duration_seconds: 300
      max_retries: 3
      on:
        success_states: [1]
      off:
        success_states: [0]

  anel:
    cooldown_seconds: 5
    request_timeout: 5
    runner_url: "${ANEL_RUNNER_URL}"    # ANEL Runner HTTP endpoint
    runner_api_key: "${ANEL_API_KEY}"   # API key for runner
    verify:
      enabled: true
      interval_seconds: 30
      initial_timeout_seconds: 180
      stable_duration_seconds: 300
      max_retries: 3
      on:
        success_states: [1]
      off:
        success_states: [0]

  shell:
    cooldown_seconds: 2
    request_timeout: 30
    verify:
      enabled: false           # Shell commands don't have verifiable state

# ======================
# ORCHESTRATOR
# ======================
orchestrator:
  on_stagger_delay_seconds: 1.0        # Delay between sequential ON commands
  max_concurrent_on_commands: 10       # Max parallel ON commands (with stagger)
  max_concurrent_off_commands: 20      # Max parallel OFF commands
  max_concurrent_fast_commands: 20     # Max parallel fast-lane commands
  max_concurrent_verification_polls: 10 # Max parallel verification queries
  enable_verification: true            # Enable post-command verification

# ======================
# MONITORING
# ======================
monitoring:
  enabled: true
  poll_interval_seconds: 60        # Normal polling interval
  fast_poll_interval_seconds: 30   # Polling during verification
  batch_size: 30                   # Devices per parallel batch
  batch_delay_seconds: 0           # Delay between batches (0 = parallel)
  device_timeout_seconds: 5        # Per-device query timeout

# ======================
# SCHEDULER
# ======================
scheduler:
  enabled: true
  check_interval_seconds: 60       # How often to check for due jobs

# ======================
# EXTERNAL SERVICES
# ======================
services:
  anel_runner:
    name: "ANEL Runner"
    description: "UDP relay for ANEL power strips"
    url: "${ANEL_RUNNER_URL}"
    health_endpoint: "/health"
    check_interval_seconds: 30
    timeout_seconds: 5
    affects_device_types: ["anel"]

# ======================
# LOGGING
# ======================
logging:
  level: "INFO"                # DEBUG, INFO, WARNING, ERROR
  format: "json"               # json or text
  file: null                   # Log file path (null = stdout only)

# ======================
# API
# ======================
api:
  cors_origins:
    - "*"                      # Allowed origins for CORS
  rate_limit:
    enabled: true
    requests_per_minute: 60    # Per-client rate limit

# ======================
# EMAIL
# ======================
email:
  smtp_host: "${SMTP_HOST}"
  smtp_port: 587
  smtp_user: "${SMTP_USER}"
  smtp_password: "${SMTP_PASSWORD}"
  smtp_use_tls: true
  from_address: "${EMAIL_FROM}"
  subject: "MuTech Device Inventory"
  recipients:
    - "technik@zkm.de"
```

### Tuning Guidelines

| Scenario | Adjustment |
|----------|------------|
| **Large installation (200+ devices)** | Increase `poll_interval_seconds` to 90-120 |
| **Network congestion** | Decrease `batch_size` to 10-15 |
| **Slow devices** | Increase `request_timeout` |
| **Fast local network** | Decrease cooldown values |
| **Heavy projector use** | Increase verification `stable_duration_seconds` |
| **Resource constraints** | Reduce `pool_size` and concurrent limits |

### Hot-Reloadable Settings

Changes to these settings take effect without restart:
- `monitoring.*` (poll intervals, batch size, timeouts)
- Device type timeouts and cooldowns
- Verification settings

Settings requiring restart:
- `server.*` (port, host)
- `database.*` (connection string, pool size)
- `api.cors_origins`

---

## System Internals

This section explains the internal design decisions and algorithms used by MuTech Control.

### Why ON Commands Are Staggered

When turning ON multiple devices (exhibition or artwork), commands are sent **sequentially with a delay** (default 1 second):

```
Device 1 ON → wait 1s → Device 2 ON → wait 1s → Device 3 ON
```

**Reasons:**

1. **Power Surge Prevention** - Projectors draw significant current during lamp ignition. Starting 10 projectors simultaneously could trip breakers or cause voltage dips.

2. **Network Flooding Prevention** - PJLink connections are TCP with handshake/auth. Simultaneous connections could overwhelm switches or the control server.

3. **Projector Response Time** - Some projectors need time to process power commands before accepting new connections.

**Configuration:**
```yaml
orchestrator:
  on_stagger_delay_seconds: 1.0
  max_concurrent_on_commands: 10
```

### Why OFF Commands Are Parallel

OFF commands are sent **in parallel with concurrency limits** (default 20 concurrent):

```
Device 1 OFF ─┬─ (parallel) → All sent within ~1s
Device 2 OFF ─┤
Device 3 OFF ─┘
```

**Reasons:**

1. **Lower Power Impact** - Turning off doesn't cause power surges.

2. **User Experience** - When closing an exhibition, staff expect quick shutdown.

3. **Projector Safety** - Starting cooling sooner is better for lamp life.

**Configuration:**
```yaml
orchestrator:
  max_concurrent_off_commands: 20
```

### Device State Machine

All devices follow this state model:

```
          ┌────────────┐
          │   ERROR    │ ← Connection failed
          │   (-1)     │
          └─────┬──────┘
                │ recovery
          ┌─────▼──────┐     ON command     ┌────────────┐
          │    OFF     │ ──────────────────►│  WARMING   │
          │    (0)     │                    │    (3)     │
          └─────▲──────┘                    └─────┬──────┘
                │                                 │ lamp ready
                │ lamp cooled                     │
          ┌─────┴──────┐                    ┌─────▼──────┐
          │  COOLING   │◄───────────────────│    ON      │
          │    (2)     │    OFF command     │    (1)     │
          └────────────┘                    └────────────┘
```

**Important:** Commands sent during WARMING or COOLING states are **queued**, not rejected. The command will execute once the device reaches a stable state.

### The Verification/Enforcement System

After sending a command, the system **actively enforces** the expected state:

```
1. Send ON command to projector
2. Start enforcement period (default 5 minutes)
3. Enable fast polling (every 30s instead of 60s)
4. On each poll:
   - If state = ON → Good, keep monitoring
   - If state = OFF → Send ON again (correction)
   - If device offline → Skip, wait for next poll
5. After enforcement period ends:
   - Final state correct → SUCCESS
   - Final state wrong → Mark ERROR
```

**Why This Exists:**

- Projectors can ignore commands if overheating
- Network glitches may drop packets
- Some devices need multiple attempts
- Ensures museum opens reliably

**Configuration:**
```yaml
device_types:
  pjlink:
    verify:
      enabled: true
      stable_duration_seconds: 300  # 5 min enforcement
      on:
        success_states: [1, 3]  # ON or WARMING
      off:
        success_states: [0, 2]  # OFF or COOLING
```

### The Fast Lane API

External triggers (motion sensors, buttons) use the **Fast Lane API**:

```
POST /api/fast/artwork/{id}/on
POST /api/fast/artwork/{id}/off
```

**Differences from Web/Scheduler commands:**

| Feature | Web/Scheduler | Fast Lane |
|---------|---------------|-----------|
| Verification | Yes (5 min) | No |
| Stagger delay | Yes | No |
| accepting_triggers gate | Updates it | Checks it |
| Protection check | Yes | Yes |

**Why:** Fast triggers need immediate response. A motion sensor can't wait 1 second per device.

### The accepting_triggers Gate

This flag prevents external triggers from interfering with staff control:

```
Staff clicks "Turn OFF Exhibition"
    ↓
Sets accepting_triggers = FALSE for all artworks
    ↓
Motion sensor triggers → REJECTED (403)
    ↓
Staff clicks "Turn ON Exhibition"
    ↓
Sets accepting_triggers = TRUE
    ↓
Motion sensor triggers → ALLOWED
```

**Logic:**
- Web/scheduler ON → sets `accepting_triggers = true`
- Web/scheduler OFF → sets `accepting_triggers = false`
- Device-level commands don't change it (maintenance mode)
- Fast Lane checks the flag before executing

### Protection Budget Calculation

Protection uses **rolling time windows**, not fixed periods:

```
Time Slice: max 7 minutes per 15-minute window

Example timeline (runtime marked as ███):

10:00 ─────────────────────────────────────────────► Time
      │ 7 min ON │
      ████████████
                 │ budget empty, blocked │
                                         │ budget refills as old usage slides out │
                                                     │ 7 min ON │
                                                     ████████████
```

**How it works:**

1. System tracks all ON periods with timestamps
2. When checking budget, sums runtime in last N minutes
3. Budget refills gradually as old usage "slides out" of the window
4. Multiple windows can stack (e.g., 7/15min AND 20/60min)

**Runtime + Cooldown:**

```
Artwork turns ON
    ↓
Timer starts
    ↓
After max_runtime (e.g., 150s) reached
    ↓
System sends automatic OFF command
    ↓
Cooldown starts (e.g., 120s)
    ↓
During cooldown: ON commands BLOCKED
    ↓
Cooldown ends: ON commands ALLOWED
```

### State Polling Architecture

The StateMonitor polls all devices periodically:

```
┌──────────────────────────────────────────────────────────┐
│                    StateMonitor Loop                      │
│                                                          │
│  Every 5 seconds:                                        │
│  1. Get all enabled devices                              │
│  2. Filter to devices due for polling:                   │
│     - Normal devices: last poll > 60s ago                │
│     - Fast poll devices: last poll > 30s ago             │
│  3. Split into batches of 30                             │
│  4. Poll all batches IN PARALLEL                         │
│  5. Update database with new states                      │
│  6. Broadcast via SSE to connected frontends             │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

**Why parallel batches?** With 100 devices at 5s timeout each, sequential polling would take 500 seconds. Parallel batches complete in ~5-10 seconds.

**Configuration:**
```yaml
monitoring:
  poll_interval_seconds: 60
  fast_poll_interval_seconds: 30
  batch_size: 30
  device_timeout_seconds: 5
```

### Hot-Reload Configuration

The system watches `config/*.yaml` files and reloads on change:

```
1. File change detected (watchdog)
    ↓
2. Reload YAML configuration
    ↓
3. Update StateMonitor intervals in-memory
    ↓
4. Broadcast config_change event via SSE
    ↓
5. Frontend receives new poll intervals
    ↓
6. Progress bars update to reflect new timing
```

**What can be changed without restart:**
- Poll intervals
- Batch sizes
- Timeouts
- Device-specific settings

**What requires restart:**
- Database connection
- API port
- New device types

### Circuit Breaker Pattern

Scheduled jobs use a circuit breaker to prevent failure storms:

```
Job runs → SUCCESS → fail_count = 0
Job runs → FAILURE → fail_count = 1, backoff = 1 min
Job runs → FAILURE → fail_count = 2, backoff = 2 min
Job runs → FAILURE → fail_count = 3, backoff = 4 min
Job runs → FAILURE → fail_count = 4, backoff = 8 min
Job runs → FAILURE → fail_count = 5 → CIRCUIT OPEN
    ↓
Job disabled until manual reset
```

**Why:** A broken job shouldn't fill logs with errors forever. After 5 failures, human intervention is required.

**Reset via Admin Panel:**
1. Fix the underlying issue
2. Click "Reset" on the failed job
3. Job resumes with fail_count = 0

### Lamp Hours Recording

PJLink projectors report lamp usage. The system records this:

```
Projector powers OFF
    ↓
Schedule one-shot task: "Record lamp hours in 7 minutes"
    ↓
(Projector cools down, becomes queryable)
    ↓
Task runs: Query lamp hours via PJLink LAMP command
    ↓
Store in lamp_hours_log with event_type = "power_off"
    ↓
Asset browser shows usage history
```

**Why 7 minutes?** Projectors in COOLING state may not respond to queries. Waiting ensures reliable readings.

### Satellite Command Routing

When a device has `use_satellite = true`:

```
Command to Device
    ↓
Check: use_satellite && exhibition.satellite_id
    ↓
YES → Route through satellite:
    1. Find connected WebSocket for satellite
    2. Send command payload
    3. Satellite executes locally
    4. Return result
    ↓
NO → Direct execution:
    1. Connect to device directly
    2. Send protocol command
    3. Return result
```

**Why satellites?** Devices on isolated networks can't be reached directly. The satellite runs on that network and relays commands.

### Memory Management

Long-running services accumulate stale data. The memory_cleanup task runs hourly:

```
1. Get all valid device IDs from database
2. Remove stale entries from:
   - _last_polled dict (StateMonitor)
   - _fast_poll_devices dict (StateMonitor)
   - _cooldowns dict (each DeviceManager)
3. Force Python garbage collection
```

**Why:** Deleted devices leave orphan entries in in-memory caches. This prevents slow memory growth.

### Transaction Isolation Handling

Database operations use careful transaction management:

```python
# WRONG: Read-then-update in separate transactions
async with db.session() as s1:
    obj = await s1.get(Model, id)  # Read in tx1

async with db.session() as s2:
    obj.value = new_value  # Object is detached!
    # Error: object not in session

# CORRECT: Read-then-update in same transaction
async with db.session() as session:
    obj = await session.get(Model, id)
    obj.value = new_value
    # Commit happens on context exit
```

**Why:** Each `session()` is a new transaction. Objects from one transaction can't be modified in another.

### SSE Event Flow

The frontend receives real-time updates via Server-Sent Events:

```
Browser connects to /api/state/events
    ↓
SSEBroadcaster adds client queue
    ↓
Events broadcast to all queues:
- poll_complete: Device state updated
- verification_start/end: Enforcement status
- config_change: Poll intervals changed
- protection_status: Budget updated
- protection_forced_off: Auto-stopped
- accepting_triggers_change: Gate changed
- satellite_status: Connection changed
- heartbeat: Keep-alive (every 30s)
    ↓
Frontend updates UI without refresh
```

---

## Support

For technical assistance, contact the ZKM technical team.

**Logs Location:**
- Application logs: stdout/stderr
- Database logs: PostgreSQL logs
- Frontend errors: Browser console
