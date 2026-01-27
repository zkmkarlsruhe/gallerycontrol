# System Internals

This document explains the internal design decisions and algorithms used by MuTech Control.

---

## Why ON Commands Are Staggered

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

---

## Why OFF Commands Are Parallel

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

---

## Device State Machine

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

---

## The Verification/Enforcement System

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

---

## The Fast Lane API

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

---

## The accepting_triggers Gate

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

---

## Protection Budget Calculation

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

---

## State Polling Architecture

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

---

## Hot-Reload Configuration

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

---

## Circuit Breaker Pattern

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

---

## Lamp Hours Recording

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

---

## Satellite Command Routing

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

---

## Memory Management

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

---

## Transaction Isolation Handling

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

---

## SSE Event Flow

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
