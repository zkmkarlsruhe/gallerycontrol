# Monitoring & Logging

## State Monitoring

The State Monitor polls all enabled devices:

| Parameter | Default | Description |
|-----------|---------|-------------|
| Normal interval | 60 seconds | Standard polling frequency |
| Fast interval | 30 seconds | During verification |
| Batch size | 30 | Devices per parallel batch |
| Device timeout | 5 seconds | Per-device query timeout |

Devices are polled in parallel batches to minimize total polling time.

---

## SSE Events

Server-Sent Events provide real-time updates to connected frontends.

### Connecting

```javascript
const eventSource = new EventSource('/api/state/stream');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle event based on data.type
};
```

### Event Types

| Type | Description |
|------|-------------|
| `connected` | Initial connection with config |
| `poll_complete` | Device state updated |
| `verification_start` | Enforcement started for device |
| `verification_end` | Enforcement ended for device |
| `config_change` | Configuration hot-reloaded |
| `protection_status` | Protection budget updated |
| `protection_forced_off` | Artwork auto-stopped |
| `accepting_triggers_change` | Gate flag changed |
| `satellite_status` | Satellite connected/disconnected |
| `satellite_pending_count` | Pending satellites count changed |
| `heartbeat` | Keep-alive (every 30s) |

---

## Service Health

External services are monitored for availability:

```yaml
services:
  anel_runner:
    name: "ANEL Runner"
    description: "UDP relay for ANEL power strips"
    url: "${ANEL_RUNNER_URL}"
    health_endpoint: "/health"
    check_interval_seconds: 30
    timeout_seconds: 5
    affects_device_types: ["anel"]
```

When a service is unhealthy, a banner appears in the UI showing affected device types.

---

## Log Retention

The `log_cleanup` task removes old logs:

```yaml
scheduler:
  tasks:
    log_cleanup:
      cron: "0 3 * * *"  # 3 AM daily
      retention_hours: 24
```

Cleaned tables:
- `device_operation_logs`
- `scheduled_job_logs`

State change logs are retained longer for timeline visualization.

---

## Health Check

```bash
curl http://localhost:8000/health
# {"status": "healthy"}
```

---

## Log Levels

Configure via environment or config:

```yaml
logging:
  level: "INFO"   # DEBUG, INFO, WARNING, ERROR
  format: "json"  # json or text
```

**Recommended levels:**

| Environment | Level |
|-------------|-------|
| Development | DEBUG |
| Production | INFO |
| Troubleshooting | DEBUG |

---

## Structured Logging

Logs use structured JSON format with fields:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "logger": "mutech_control.orchestrator",
  "message": "Device command sent",
  "device": "Projector-1",
  "command": "on",
  "duration_ms": 125
}
```

Use `jq` to filter logs:

```bash
# All errors
cat logs.json | jq 'select(.level == "ERROR")'

# Specific device
cat logs.json | jq 'select(.device == "Projector-1")'
```
