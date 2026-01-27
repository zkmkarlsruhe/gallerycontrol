# Artwork Protection

Protect sensitive equipment from overuse.

## Time-Slice Protection

Limit runtime within rolling time windows.

```json
{
  "time_slices": [
    {"window": 15, "max": 7}
  ]
}
```
*Max 7 minutes of ON time within any 15-minute window.*

Multiple windows can be combined:
```json
{
  "time_slices": [
    {"window": 15, "max": 7},
    {"window": 60, "max": 20}
  ]
}
```
*Max 7 min per 15-min window AND max 20 min per hour.*

---

## Runtime + Cooldown

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

---

## Force Completion

Prevent interruption of protected artworks.

```json
{
  "force_completion": true,
  "max_runtime": 150
}
```
OFF commands are blocked until max_runtime is reached. Useful for video artworks that must complete playback.

---

## Enabling Protection

Protection requires two things:

1. **Protection Config** on the artwork (JSON configuration)
2. **timeslice_enabled = true** on the artwork (feature flag)

The feature flag allows temporarily disabling protection without deleting the configuration.

---

## API Triggers

The `accepting_triggers` flag on artworks controls whether the Fast-Lane API can trigger the artwork.

```
POST /api/fast/artwork/{id}/on
POST /api/fast/artwork/{id}/off
```

When staff turns an exhibition OFF via web interface, `accepting_triggers` is set to `false` for all artworks, preventing motion sensors from turning things back on.

---

## Protection State

The system maintains protection state in the `artwork_protection_states` table:

| Field | Description |
|-------|-------------|
| `is_running` | Whether artwork is currently ON |
| `started_at` | When current run started |
| `cooldown_until` | When cooldown ends |
| `time_slice_usage` | Runtime per window |
| `last_window_reset` | When each window last reset |

This state is persisted across service restarts.
