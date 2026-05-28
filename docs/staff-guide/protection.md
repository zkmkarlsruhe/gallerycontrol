# Artwork Protection System

The protection system prevents equipment damage and manages visitor interaction with sensitive artworks.

## Overview

Protection applies at the **artwork level** and affects all devices within that artwork. When protection rules are violated, ON commands are blocked.

## Protection Types

### 1. Time-Slice Windows

Limit how long an artwork can be ON within a rolling time window.

**Use Case:** Prevent projector overuse by limiting runtime to 7 minutes per 15-minute window.

**Configuration:**
```json
{
  "time_slices": [
    {"window": 15, "max": 7}
  ]
}
```

**How it works:**
- System tracks ON time over last 15 minutes
- If artwork was ON for 7+ minutes, new ON commands are blocked
- Budget refills as old time slides out of window

**Multiple Windows:**
```json
{
  "time_slices": [
    {"window": 15, "max": 7},
    {"window": 60, "max": 20}
  ]
}
```
*Max 7 min per 15 min AND max 20 min per hour.*

### 2. Runtime + Cooldown

Limit continuous runtime with mandatory rest periods.

**Use Case:** Equipment needs periodic cooling breaks.

**Configuration:**
```json
{
  "max_runtime": 180,
  "cooldown": 60
}
```

**How it works:**
- Artwork can run for max 3 minutes (180 seconds)
- After reaching limit, artwork turns OFF automatically
- 1-minute (60 second) cooldown before restart allowed

### 3. Minimum Budget to Start

Prevent starting an artwork if insufficient time remains.

**Use Case:** Don't start a 2-minute experience if only 30 seconds of budget remain.

**Configuration:**
```json
{
  "time_slices": [{"window": 15, "max": 7}],
  "min_budget_to_start": 120
}
```

**How it works:**
- ON command blocked if remaining budget < 2 minutes
- Prevents frustrating partial activations

### 4. Force Completion

Prevent interruption of a running artwork.

**Use Case:** Artwork has a complete cycle that shouldn't be interrupted.

**Configuration:**
```json
{
  "force_completion": true,
  "max_runtime": 150
}
```

**How it works:**
- Once artwork starts, OFF commands are ignored
- Artwork runs for full 2.5 minutes (150 seconds)
- After max_runtime, artwork turns OFF automatically

## Configuring Protection

### Prerequisites

Protection must be enabled at the artwork level before you can configure rules:

1. Enable Edit Mode
2. Click the **pencil icon** on an artwork
3. Check **Enable Time Slice Protection**
4. Save the artwork
5. The **shield icon** now appears on the artwork

### Via UI

1. Enable Edit Mode
2. Click the **shield icon** on an artwork (only visible if protection is enabled)
3. The Protection Config modal opens
4. Configure protection rules
5. Click **Save**

### Protection Config Modal

The Protection Config modal has the following sections:

#### Time Slices Section

Add multiple time windows with runtime limits:

1. Click **+ Add Slice** to add a new time window
2. Configure each slice:
   - **Max** - Maximum minutes the artwork can be ON
   - **per** - Time window in minutes
3. Click the **trash icon** to remove a slice

**Example:** "Max 0.5 min per 1 min window" means max 30 seconds per minute.

#### Max Runtime

- Enter seconds for maximum continuous ON time
- Leave empty for no limit
- When reached, artwork automatically turns OFF

#### Cooldown

- Enter seconds of mandatory rest after max runtime
- Leave empty for no cooldown
- During cooldown, ON commands are blocked

#### Min Budget to Start

- Enter minimum seconds of budget required to turn ON
- Prevents starting if there's not enough time left
- Leave empty (or 0) to allow starting anytime

#### Force Completion

- Toggle ON to prevent OFF commands until max_runtime
- Once artwork starts, it must complete its full cycle
- Use with max_runtime to define the cycle length

#### Footer Actions

| Button | Description |
|--------|-------------|
| **Clear All** | Remove all protection settings from this artwork |
| **Cancel** | Close without saving |
| **Save** | Apply the protection configuration |

### Protection Settings Summary

| Setting | Description | Field Type |
|---------|-------------|------------|
| **Time Slices** | List of time windows with max runtime | Multiple rows |
| **Max Runtime** | Maximum continuous ON time (seconds) | Number input |
| **Cooldown** | Wait time after OFF before allowing ON (seconds) | Number input |
| **Min Budget to Start** | Minimum remaining budget to turn ON (seconds) | Number input |
| **Force Completion** | Block OFF until max_runtime reached | Toggle switch |

## External Triggers (Fast-Lane API)

### Accepting Triggers

The `accepting_triggers` flag controls whether external systems can trigger the artwork:

```
POST /external/fast/artwork/{id}/on
POST /external/fast/artwork/{id}/off
```

**When enabled:**
- External sensors can trigger artwork
- Motion detectors, door sensors, etc.
- Protection rules still apply

**When disabled:**
- Fast-lane API returns 403 Forbidden
- Only manual/scheduled control works

### Typical Integration

```
Motion Sensor → API Gateway → POST /external/fast/artwork/123/on
                                      ↓
                              Protection Check
                                      ↓
                              ✓ Budget OK → Turn ON
                              ✗ Budget Low → Reject (429)
```

## Protection Status Display

### In Control Mode

Protected artworks show:
- Current budget remaining
- Time until budget refills
- Protection status (active/inactive)

### Status Colors

| Color | Meaning |
|-------|---------|
| Green | Sufficient budget |
| Yellow | Low budget (< min_budget_to_start) |
| Red | No budget / cooling down |

## Examples

### Interactive Installation

Visitors can activate artwork via button, but limit use:

```json
{
  "time_slices": [{"window": 10, "max": 5}],
  "min_budget_to_start": 60,
  "force_completion": true,
  "max_runtime": 180
}
```

- Max 5 minutes per 10-minute window
- Won't start unless 1+ minute budget available
- Once started, runs full 3-minute cycle
- Then OFF, even if triggered again

### Projector Protection

Limit projector runtime to extend lamp life:

```json
{
  "time_slices": [
    {"window": 60, "max": 45}
  ]
}
```

- Max 45 minutes per hour
- 15-minute mandatory rest per hour

### Sensitive Equipment

Equipment that needs cooling breaks:

```json
{
  "max_runtime": 300,
  "cooldown": 120
}
```

- Max 5 minutes continuous runtime
- 2-minute cooldown before restart

## API Reference

### Get Protection Status

```
GET /api/state/protection/{artwork_id}
```

Response:
```json
{
  "artwork_id": "uuid",
  "protection_enabled": true,
  "remaining_budget_seconds": 180,
  "cooldown_remaining_seconds": 0,
  "can_turn_on": true,
  "reason": null
}
```

### Protection Rejection

When ON is blocked, API returns:
```json
{
  "error": "protection_blocked",
  "reason": "Insufficient budget (30s remaining, 60s required)",
  "remaining_budget": 30,
  "cooldown_remaining": 0
}
```

## Best Practices

1. **Start Conservative:** Begin with generous limits, tighten as needed
2. **Test Thoroughly:** Verify protection works before public opening
3. **Monitor Usage:** Review timeline to understand actual usage patterns
4. **Communicate:** Post signage explaining any activation limits
5. **Emergency Override:** Know how to disable protection if needed (Edit Mode)
