# Plan: Time Slice UI & Fast-Lane Gating

## Overview

Add a gating mechanism for fast-lane API triggers and display time slice state in the frontend.

## Current Behavior

- **Web/Cron ON/OFF**: Directly controls device power
- **Fast-lane API**: External triggers that also control device power
- **Protection service**: Checks budget/cooldown before allowing ON
- Both sources can trigger devices anytime

## Proposed Changes

### 1. New Field: `accepting_triggers` on Artworks Table

```sql
ALTER TABLE artworks ADD COLUMN accepting_triggers BOOLEAN NOT NULL DEFAULT FALSE;
```

**Behavior:**
- Set to `true` when artwork/exhibition/all is turned ON via web/cron
- Set to `false` when artwork/exhibition/all is turned OFF via web/cron
- Device-level ON/OFF does NOT change this flag (maintenance mode)

### 2. Fast-Lane Gating

Modify `/api/fast/device/{device_id}/{command}` to:
1. Look up device's artwork
2. Check `artwork.accepting_triggers`
3. If `false`, return error: `{"error": "Artwork not accepting triggers", "blocked": true}`
4. If `true`, proceed with existing logic (budget checks, etc.)

### 3. Maintenance Mode

| Action | accepting_triggers | Time slices |
|--------|-------------------|-------------|
| Device ON | unchanged | **bypassed** |
| Artwork ON | `true` | **enforced** |
| Exhibition ON | `true` (all artworks) | **enforced** |
| All ON | `true` (all artworks) | **enforced** |

Device-level control = maintenance mode (bypass protection, don't change gate)

### 4. Frontend Changes

#### 4a. Badge Indicator (List View)

Add icon to device/artwork badge when `accepting_triggers = true`:
- Small lightning bolt (⚡) or antenna icon
- Tooltip: "Accepting external triggers"

#### 4b. Accordion Details (Expanded View)

Show all protection info in device accordion:

**Protection Status Section:**
```
┌─────────────────────────────────────────────────┐
│ Protection Status                               │
├─────────────────────────────────────────────────┤
│ Accepting Triggers: ✓ Yes / ✗ No               │
│ Can Start: ✓ Yes / ✗ No (reason if blocked)    │
│                                                 │
│ Time Slice Budgets:                             │
│   15-min window: ████████░░ 5m / 7m (resets 14:30) │
│   60-min window: ██████████████░░ 18m / 20m (resets 15:00) │
│                                                 │
│ Current Session:                                │
│   Running: Yes, 45s elapsed                     │
│   Max runtime: 150s                             │
│                                                 │
│ Cooldown:                                       │
│   Status: Inactive / Active (90s remaining)    │
│                                                 │
│ Config:                                         │
│   Force completion: No                          │
│   Min budget to start: 60s                      │
└─────────────────────────────────────────────────┘
```

### 5. API Changes

#### New endpoint: `GET /api/artwork/{id}/protection-status`

Returns:
```json
{
  "accepting_triggers": true,
  "protected": true,
  "config": {
    "time_slices": [
      {"window": 15, "max": 7},
      {"window": 60, "max": 20}
    ],
    "max_runtime": 150,
    "cooldown": 120,
    "force_completion": false,
    "min_budget_to_start": 60
  },
  "state": {
    "is_running": true,
    "runtime_seconds": 45,
    "cooldown_active": false,
    "cooldown_remaining": 0,
    "time_slices": [
      {"window": 15, "used": 120, "max": 420, "remaining": 300, "resets_at": "2026-01-25T14:30:00Z"},
      {"window": 60, "used": 120, "max": 1200, "remaining": 1080, "resets_at": "2026-01-25T15:00:00Z"}
    ],
    "can_start": true,
    "block_reason": null
  }
}
```

### 6. SSE Updates

Broadcast protection status changes via existing SSE:
- When `accepting_triggers` changes
- When budget is consumed
- When cooldown starts/ends

### 7. Database Migration

```python
# 016_artwork_accepting_triggers.py
def upgrade():
    op.add_column('artworks', sa.Column('accepting_triggers', sa.Boolean(), nullable=False, server_default='false'))

def downgrade():
    op.drop_column('artworks', 'accepting_triggers')
```

## Implementation Order

1. Database migration (add `accepting_triggers`)
2. Backend: Update orchestrator to set `accepting_triggers` on web/cron commands
3. Backend: Update fast-lane to check `accepting_triggers`
4. Backend: Add/update protection status endpoint
5. Frontend: Add badge indicator
6. Frontend: Add accordion protection section
7. SSE: Broadcast protection status updates

## Clarifications

- **Per-artwork, not per-device** - `accepting_triggers` lives on artwork table
- **Fast-lane is artwork-level only** - `/api/fast/artwork/{id}/{command}`, not device-level
- **Race conditions unlikely** - timing between gate changes and triggers is not critical in practice
- **Default `false`** - safe default, requires explicit action to open gate

## Resolved Edge Cases

- Artwork ON → device OFF → fast-lane trigger: N/A, fast-lane only triggers artwork level
- Device-level fast-lane: Not supported, removed from API
