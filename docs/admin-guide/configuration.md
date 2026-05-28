# Configuration

## Configuration Files

| File | Purpose |
|------|---------|
| `config/default.yaml` | Base configuration |
| `config/production.yaml` | Production overrides |
| `.env` | Environment variables |

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/gallerycontrol

# ANEL Runner (optional)
ANEL_RUNNER_URL=http://localhost:8001
ANEL_API_KEY=your-api-key

# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO
```

## Hot Reload

Configuration changes are detected automatically and broadcast to connected clients. No restart required for most settings.

---

## Configuration Reference

GalleryControl uses YAML configuration files in the `config/` directory.

### File Structure

```
config/
├── default.yaml      # Base configuration
└── production.yaml   # Production overrides (loaded when ENVIRONMENT=production)
```

`production.yaml` overrides `default.yaml` when the `ENVIRONMENT` env var is set to `production`.

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
      "on":
        success_states: [1, 3] # 1=ON, 3=WARMING
      "off":
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
      "on":
        success_states: [1]
      "off":
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
      "on":
        success_states: [1]
      "off":
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
  tasks:                           # Built-in maintenance jobs (seeded on startup)
    asset_linker:
      enabled: true
      interval_minutes: 10         # Link devices to asset records
      batch_size: 20
    log_cleanup:
      enabled: true
      interval_minutes: 60
      retention_hours: 24          # Keep 24h of operation logs
    device_info_cache:
      enabled: true
      interval_minutes: 30
      max_concurrent: 5
      timeout_seconds: 10

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
  subject: "GalleryControl Device Inventory"
  recipients:
    - "admin@example.com"        # empty list ([]) disables status emails

# ======================
# HOSTNAME TEMPLATES (device-form quick-generate buttons)
# ======================
hostname_templates:
  netio: ""    # e.g. "netio-{num:03d}.example.com" ({num:03d} = zero-padded); "" disables
  anel: ""     # e.g. "anel-{num}.example.com"

# ======================
# DISPLAY (kiosk protection-status screens)
# ======================
display:
  enabled: true
  config_cache_ttl: 5            # Cache TTL for per-artwork config.yaml (enables hot-reload)
  default_template: "mack-style"
  default_chart_type: "donut"
```

## Tuning Guidelines

| Scenario | Adjustment |
|----------|------------|
| **Large installation (200+ devices)** | Increase `poll_interval_seconds` to 90-120 |
| **Network congestion** | Decrease `batch_size` to 10-15 |
| **Slow devices** | Increase `request_timeout` |
| **Fast local network** | Decrease cooldown values |
| **Heavy projector use** | Increase verification `stable_duration_seconds` |
| **Resource constraints** | Reduce `pool_size` and concurrent limits |

## Hot-Reloadable Settings

Changes to these settings take effect without restart:
- `monitoring.*` (poll intervals, batch size, timeouts)
- Device type timeouts and cooldowns
- Verification settings

Settings requiring restart:
- `server.*` (port, host)
- `database.*` (connection string, pool size)
- `api.cors_origins`
