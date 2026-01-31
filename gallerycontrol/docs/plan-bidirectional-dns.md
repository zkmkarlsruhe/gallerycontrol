# Plan: Device Import Fix (Revised v3)

## Overview
Fix device naming and import from SQLite:
- `name` = from SQLite `args.name` or `hostname` field
- `host` = connection target (IP or hostname)
- `port` = outlet/channel number (NETIO/ANEL) - **must be in device.port, not config**
- `resolved` = automatic lookup (already works in state_monitor)

## Key Findings from Review

### DNS Resolution - NO CHANGES NEEDED
`state_monitor.py:618-698` already has:
- Both forward (hostname→IP) and reverse (IP→hostname) lookups
- Executor offloading with 3s timeouts
- Per-device backoff via `resolved_at`
- `_should_resolve_dns()` gates on `resolved_at`, not host shape

**Action:** Verify with test, no code changes.

### Port Handling Bug - MUST FIX
Current broken flow:
- Import stores outlet in `config["outlet"]`
- Managers read from `device.port` or `device.config.get("port")`
- Result: all outlets treated as port 1/0, control fails

**Fix:** Import must set `device.port = int(args["port"])` for NETIO/ANEL.

---

## Changes

### 1. DNS Resolution
**Action:** Add integration test to verify both directions work.
**No code changes** to state_monitor.py.

### 2. Import Scripts (Per Device Type)

**Common Pattern:**
```python
# Name priority: args.name > hostname > host
name = args.get('name', '').strip() or row['hostname'] or row['host']
```

**File:** `scripts/import_pjlink_devices.py`
```python
# SQLite: unit_type='projector'
device = {
    "name": args.get('name') or row['hostname'] or row['host'],
    "host": row['host'],
    "port": int(args.get('port') or 4352),
    "device_type": "pjlink",
    "config": {
        "credential_id": lookup_credential_id(args.get('password'))
    }
}
```

**File:** `scripts/import_netio_devices.py`
```python
# SQLite: unit_type='netio'
# CRITICAL: port must be in device.port, not config
device = {
    "name": args.get('name') or row['hostname'] or row['host'],
    "host": row['host'],
    "port": int(args.get('port', 1)),  # Outlet number in device.port
    "device_type": "netio",
    "config": {}  # No outlet in config
}
```

**File:** `scripts/import_anel_devices.py`
```python
# SQLite: unit_type='anel'
# CRITICAL: port must be in device.port, not config
device = {
    "name": args.get('name') or row['hostname'] or row['host'],
    "host": row['host'],
    "port": int(args.get('port', 0)),  # Channel number in device.port
    "device_type": "anel",
    "config": {}  # No channel in config
}
```

**File:** `scripts/import_shell_devices.py`
Already exists. Update name extraction to use:
```python
name = args.get('name') or row.get('hostname') or '#nohost'
```

### 3. Safe Migration Flow

**Step 0: Pause Monitor**
```bash
# Stop polling to avoid races
curl -X POST http://localhost:8000/api/admin/monitoring/pause
# Or restart service with monitoring.enabled=false
```

**Step 1: Full Backup**
```bash
# Export everything (devices, artworks, exhibitions, credentials)
curl -s http://localhost:8000/api/admin/devices > backup_devices.json
curl -s http://localhost:8000/api/admin/artworks > backup_artworks.json
curl -s http://localhost:8000/api/admin/exhibitions > backup_exhibitions.json
curl -s http://localhost:8000/api/admin/credentials > backup_credentials.json

# Also dump the database
pg_dump -U mutech mutech > backup_full.sql
```

**Step 2: Delete Devices**
```bash
for type in shell pjlink netio anel; do
  for id in $(curl -s "http://localhost:8000/api/admin/devices?device_type=$type" | jq -r '.[].id'); do
    curl -s -X DELETE "http://localhost:8000/api/admin/devices/$id"
  done
done
```

**Step 3: Import**
```bash
python3 scripts/import_pjlink_devices.py
python3 scripts/import_netio_devices.py
python3 scripts/import_anel_devices.py
python3 scripts/import_shell_devices.py
```

**Step 4: Verify**
```bash
# Compare counts
sqlite3 /workspace/mutech.db "SELECT unit_type, COUNT(*) FROM units GROUP BY unit_type"
curl -s http://localhost:8000/api/admin/devices | jq 'group_by(.device_type) | map({type: .[0].device_type, count: length})'

# Spot check port values for NETIO/ANEL
curl -s "http://localhost:8000/api/admin/devices?device_type=netio" | jq '.[0:3] | .[] | {name, host, port}'
```

**Step 5: Resume Monitor**
```bash
curl -X POST http://localhost:8000/api/admin/monitoring/resume
# Or restart service with monitoring.enabled=true
```

---

## File Changes Summary

| File | Change |
|------|--------|
| `state_monitor.py` | **None** - just verify with test |
| `scripts/import_pjlink_devices.py` | New |
| `scripts/import_netio_devices.py` | New - **sets device.port correctly** |
| `scripts/import_anel_devices.py` | New - **sets device.port correctly** |
| `scripts/import_shell_devices.py` | Update name extraction |

## Rollback Plan

```bash
# If import fails, restore from backup
psql -U mutech mutech < backup_full.sql
# Resume monitoring
curl -X POST http://localhost:8000/api/admin/monitoring/resume
```

---

## Verification Checklist

- [ ] DNS: Create device with hostname, verify `resolved` shows IP
- [ ] DNS: Create device with IP, verify `resolved` shows hostname
- [ ] Import count: SQLite vs API device counts match
- [ ] Names: Devices have friendly names (not all IPs)
- [ ] NETIO: `device.port` contains outlet number, control works
- [ ] ANEL: `device.port` contains channel number, control works
