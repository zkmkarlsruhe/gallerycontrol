# API Reference

## Interactive Documentation

- **Swagger UI:** `/docs`
- **ReDoc:** `/redoc`

---

## Control Endpoints

Turn devices on/off at various levels:

```
POST /api/control/exhibition/{id}/on
POST /api/control/exhibition/{id}/off
POST /api/control/artwork/{id}/on
POST /api/control/artwork/{id}/off
POST /api/control/device/{id}/on
POST /api/control/device/{id}/off
POST /api/control/device/{id}/action/{name}
```

**Response:**
```json
{
  "success": true,
  "devices_targeted": 5,
  "devices_successful": 5,
  "results": [...]
}
```

---

## Fast-Lane API

External trigger endpoints for motion sensors, buttons, etc.

```
POST /api/fast/artwork/{id}/on
POST /api/fast/artwork/{id}/off
GET  /api/fast/artwork/{id}/state
```

**Requirements:**
- Artwork must have `accepting_triggers = true`
- Protection rules still apply

**Response (403) when blocked:**
```json
{
  "detail": "Artwork not accepting triggers"
}
```

---

## State Queries

```
GET /api/state/exhibitions          # All exhibitions with state
GET /api/state/exhibition/{id}      # Single exhibition
GET /api/state/artwork/{id}         # Single artwork
GET /api/state/device/{id}          # Single device
GET /api/state/events               # SSE stream
```

---

## Admin CRUD

Standard REST patterns for all entities:

```
GET    /api/admin/exhibitions           # List all
POST   /api/admin/exhibitions           # Create
GET    /api/admin/exhibitions/{id}      # Get one
PATCH  /api/admin/exhibitions/{id}      # Update
DELETE /api/admin/exhibitions/{id}      # Delete
```

Same pattern for:
- `/api/admin/artworks`
- `/api/admin/devices`
- `/api/admin/credentials`
- `/api/admin/shell_templates`
- `/api/admin/schedules`

---

## Satellite Endpoints

```
GET  /api/admin/satellites              # List approved
GET  /api/admin/satellites/pending      # List pending
POST /api/admin/satellites/approve      # Approve pending
POST /api/admin/satellites/reject       # Reject pending
DELETE /api/admin/satellites/{id}       # Revoke approved
```

---

## Asset Endpoints

```
GET  /api/assets                        # List assets
GET  /api/assets/{id}                   # Get asset
PUT  /api/assets/{id}                   # Update asset
DELETE /api/assets/{id}                 # Delete asset
GET  /api/assets/{id}/lamp-history      # Lamp history
POST /api/assets/record-lamp-hours      # Record current
POST /api/assets/backfill               # Create from devices
POST /api/assets/lamp-history/csv       # Export CSV
```

---

## Scheduler Endpoints

```
GET  /api/admin/scheduler/status        # Scheduler status
POST /api/admin/scheduler/trigger/{task}  # Trigger task
POST /api/admin/scheduler/reset/{job_id}  # Reset circuit
```

---

## Debug Endpoints

```
GET /api/debug/device/{id}/info         # Query device info
GET /api/debug/device/{id}/state        # Query current state
GET /health                             # Health check
GET /info                               # System info
```

---

## Authentication

Currently no authentication is required. For production deployments behind a reverse proxy, configure authentication at the proxy level.
