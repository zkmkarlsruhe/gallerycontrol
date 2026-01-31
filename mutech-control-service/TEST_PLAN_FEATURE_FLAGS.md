# Test Plan: Feature Enable/Disable Flags

## Overview
Test the `timeslice_enabled` and `schedules_enabled` feature flags for artworks and exhibitions.

---

## 1. API Response Tests

### 1.1 State API returns new fields
- [ ] GET `/api/state/exhibitions` returns `schedules_enabled` for exhibitions
- [ ] GET `/api/state/exhibitions` returns `timeslice_enabled` and `schedules_enabled` for artworks
- [ ] Fields have correct boolean values (not null/undefined)

### 1.2 Admin API update endpoints
- [ ] PATCH `/api/admin/artworks/{id}` accepts `timeslice_enabled`
- [ ] PATCH `/api/admin/artworks/{id}` accepts `schedules_enabled`
- [ ] PATCH `/api/admin/exhibitions/{id}` accepts `schedules_enabled`
- [ ] Updates persist to database and reflect in subsequent GET requests

---

## 2. UI Visibility Tests

### 2.1 Artwork Row (Edit Mode)
- [ ] Shield button (protection config) HIDDEN when `timeslice_enabled = false`
- [ ] Shield button VISIBLE when `timeslice_enabled = true`
- [ ] Calendar button (schedules) HIDDEN when `schedules_enabled = false`
- [ ] Calendar button VISIBLE when `schedules_enabled = true`

### 2.2 Exhibition Header (Edit Mode)
- [ ] Calendar button HIDDEN when `schedules_enabled = false`
- [ ] Calendar button VISIBLE when `schedules_enabled = true`

### 2.3 Edit Artwork Modal
- [ ] Shows "Enable Time Slice Protection" checkbox
- [ ] Shows "Enable Schedules" checkbox
- [ ] Checkboxes reflect current state when opening modal
- [ ] Saving updates the flags correctly

### 2.4 Edit Exhibition Modal
- [ ] Shows "Enable Schedules" checkbox
- [ ] Checkbox reflects current state when opening modal
- [ ] Saving updates the flag correctly

---

## 3. Backend Logic Tests

### 3.1 Protection Service (Time Slice)
- [ ] `check_can_start()` returns `(True, None)` when `timeslice_enabled = false`
- [ ] `check_can_start()` enforces limits when `timeslice_enabled = true`
- [ ] `_check_all_runtimes()` skips artworks with `timeslice_enabled = false`
- [ ] Toggling `timeslice_enabled` on/off updates `_enabled_artworks` set

### 3.2 Cron Scheduler
- [ ] Scheduled jobs for artwork targets skip when `artwork.schedules_enabled = false`
- [ ] Scheduled jobs for exhibition targets skip when `exhibition.schedules_enabled = false`
- [ ] Skipped jobs don't count as failures (no backoff/circuit breaker)
- [ ] Jobs execute normally when flags are `true`

---

## 4. Data Preservation Tests

### 4.1 Protection Config Preserved
- [ ] Disabling `timeslice_enabled` does NOT delete `protection_config`
- [ ] Re-enabling `timeslice_enabled` restores access to existing config
- [ ] Config can still be edited via API even when disabled

### 4.2 Scheduled Jobs Preserved
- [ ] Disabling `schedules_enabled` does NOT delete scheduled jobs
- [ ] Re-enabling `schedules_enabled` allows jobs to execute again
- [ ] Job list still visible in API (just not executed)

---

## 5. Edge Cases

### 5.1 State Transitions
- [ ] Enable -> Disable -> Enable cycle works correctly
- [ ] Multiple rapid toggles don't corrupt state
- [ ] SSE broadcasts flag changes to connected clients

### 5.2 Migration Correctness
- [ ] Artworks WITH `protection_config` have `timeslice_enabled = true`
- [ ] Artworks WITHOUT `protection_config` have `timeslice_enabled = false`
- [ ] Artworks/exhibitions WITH scheduled jobs have `schedules_enabled = true`
- [ ] Artworks/exhibitions WITHOUT scheduled jobs have `schedules_enabled = false`

### 5.3 Mixed States
- [ ] Artwork with `timeslice_enabled=true` but no config shows empty shield button
- [ ] Artwork with `timeslice_enabled=false` but HAS config - config preserved, button hidden

---

## Test Execution Commands

```bash
# 1. Check API response for exhibitions
curl -s http://localhost:8000/api/state/exhibitions | jq '.[0] | {name, schedules_enabled, artworks: [.artworks[] | {name, timeslice_enabled, schedules_enabled}]}'

# 2. Update artwork flags
curl -X PATCH http://localhost:8000/api/admin/artworks/{ARTWORK_ID} \
  -H "Content-Type: application/json" \
  -d '{"timeslice_enabled": false, "schedules_enabled": true}'

# 3. Update exhibition flags
curl -X PATCH http://localhost:8000/api/admin/exhibitions/{EXHIBITION_ID} \
  -H "Content-Type: application/json" \
  -d '{"schedules_enabled": true}'

# 4. Check protection service behavior (via control API)
curl -X POST http://localhost:8000/api/control/artwork/{ARTWORK_ID}/on

# 5. Check scheduler status
curl -s http://localhost:8000/api/admin/scheduler/status | jq '.jobs[] | {name, target_type, target_id, enabled}'
```
