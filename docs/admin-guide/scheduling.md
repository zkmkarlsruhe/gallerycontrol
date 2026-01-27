# Scheduling System

## Cron Expressions

Standard cron format: `minute hour day month weekday`

**Examples:**

| Expression | Description |
|------------|-------------|
| `0 9 * * 1-5` | 9:00 AM weekdays |
| `0 18 * * *` | 6:00 PM daily |
| `*/15 * * * *` | Every 15 minutes |
| `0 0 1 * *` | Midnight on 1st of month |
| `30 8 * * 1-5` | 8:30 AM weekdays |
| `0 9,18 * * *` | 9 AM and 6 PM daily |

---

## Job Types

### Device Jobs

Target: exhibition, artwork, or device

**Actions:**
- `on` - Turn on
- `off` - Turn off
- `action` - Execute shell action (device only)

### System Jobs

| Task | Description | Default Schedule |
|------|-------------|------------------|
| `asset_linker` | Link devices to assets by hostname | Every 10 minutes |
| `log_cleanup` | Remove old operation logs | Daily at 3 AM |
| `device_info_cache` | Cache projector extended info | Every 30 minutes |
| `lamp_hours_check` | Record all projector lamp hours | Daily at 4 AM |
| `memory_cleanup` | Clear stale in-memory caches | Every hour |

---

## Circuit Breaker

Jobs automatically pause after 5 consecutive failures:

```
Job runs → SUCCESS → fail_count = 0
Job runs → FAILURE → fail_count = 1, backoff = 1 min
Job runs → FAILURE → fail_count = 2, backoff = 2 min
...
Job runs → FAILURE → fail_count = 5 → CIRCUIT OPEN
```

When circuit is open:
- Job is disabled
- Manual reset required via Admin panel
- Prevents log flooding from broken jobs

---

## One-Shot Jobs

Schedule a single execution at a specific time:

```python
await scheduler.schedule_once(
    name="Turn off Gallery A",
    job_type="device",
    run_at=datetime(2024, 12, 31, 18, 0),
    target_type="exhibition",
    target_id="uuid-here",
    action_type="off"
)
```

One-shot jobs:
- Execute once at `run_at` time
- Are disabled after execution
- Can be cancelled before execution

---

## Admin Panel - Task Scheduler

The Admin Panel (accessible via Edit Mode > Admin button) provides monitoring and control.

### Satellites Section

At the top of the Admin Panel:
- **Pending Approval** - Satellites waiting for approval (enter name, approve/reject)
- **Approved Satellites** - List of authorized satellites with connection status

### Quick Actions Section

| Button | Description |
|--------|-------------|
| **Run All Scheduled Tasks Now** | Immediately triggers all scheduled system tasks |

### Task Scheduler Status

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

### Task Lifecycle

```
Task Created → Enabled → Running → Complete → Wait → Running...
                                     ↓ (failure)
                             Fail Count +1
                                     ↓ (5 failures)
                             Circuit Open → Manual Reset Required
```

---

## Schedules Enabled Flag

Artworks and exhibitions have a `schedules_enabled` flag:

- When `false`, scheduled jobs targeting that entity are skipped
- Allows temporarily disabling schedules without deleting jobs
- Useful during maintenance or special events
