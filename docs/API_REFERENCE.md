# MuTech Control System - API Reference

Quick reference for all API endpoints.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently no authentication is required. For production, implement API keys or OAuth2.

## Response Format

All responses follow this general structure:

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

Error responses:

```json
{
  "detail": "Error message here"
}
```

---

## Control API

### Turn On Exhibition

```http
POST /api/control/exhibition/{exhibition_id}/on
```

**Behavior:**
- Staggers ON commands by 1 second between devices
- Limits concurrent operations (default: 10)
- Respects per-device cooldowns
- Skips devices with `exclude_from_auto_onoff=true`
- Skips devices with `enabled=false`

**Response:**
```json
{
  "success": true,
  "devices_targeted": 5,
  "results": [
    {
      "device_id": "uuid",
      "success": true,
      "state": 1,
      "error": null,
      "duration_ms": 250
    }
  ]
}
```

### Turn Off Exhibition

```http
POST /api/control/exhibition/{exhibition_id}/off
```

**Behavior:**
- Broadcasts OFF commands to all devices immediately
- Starts verification tasks for non-shell devices
- Checks every 30 seconds for up to 5 minutes
- Retries OFF command if device reports on/error
- Treats "cooling" state (2) as success

**Response:**
```json
{
  "success": true,
  "devices_targeted": 5,
  "results": [...]
}
```

### Turn On Artwork

```http
POST /api/control/artwork/{artwork_id}/on
```

Same behavior as exhibition ON, but only for devices in the artwork.

### Turn Off Artwork

```http
POST /api/control/artwork/{artwork_id}/off
```

Same behavior as exhibition OFF, but only for devices in the artwork.

### Turn On Device

```http
POST /api/control/device/{device_id}/on
```

Turns on a single device with verification.

### Turn Off Device

```http
POST /api/control/device/{device_id}/off
```

Turns off a single device with verification task.

---

## Fast Lane API

For external triggers (e.g., NETIO HTTP action). No verification, fire once.

### Fast ON

```http
POST /api/fast/device/{device_id}/on
```

**Behavior:**
- Sends ON command once
- No retry
- No verification
- Immediate response

### Fast OFF

```http
POST /api/fast/device/{device_id}/off
```

**Behavior:**
- Sends OFF command once
- No retry
- No verification
- Immediate response

### Fast State Query

```http
GET /api/fast/device/{device_id}/state
```

**Response:**
```json
{
  "device_id": "uuid",
  "state": 1,
  "last_checked_at": "2024-01-12T10:30:00Z"
}
```

---

## State API

### List All Exhibitions

```http
GET /api/state/exhibitions
```

Returns complete state tree (exhibitions → artworks → devices).

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Main Exhibition",
    "enabled": true,
    "artworks": [
      {
        "id": "uuid",
        "name": "Interactive Display",
        "enabled": true,
        "devices": [
          {
            "id": "uuid",
            "name": "Projector 1",
            "device_type": "pjlink",
            "host": "192.168.1.100",
            "port": 4352,
            "state": 1,
            "enabled": true,
            "automation_enabled": true,
            "exclude_from_auto_onoff": false,
            "last_checked_at": "2024-01-12T10:30:00Z",
            "next_check_allowed_at": "2024-01-12T10:30:30Z"
          }
        ]
      }
    ]
  }
]
```

### Get Exhibition State

```http
GET /api/state/exhibition/{exhibition_id}
```

Returns state for specific exhibition with all artworks and devices.

### Get Device State

```http
GET /api/state/device/{device_id}
```

Returns state for a single device.

**Response:**
```json
{
  "id": "uuid",
  "name": "Projector 1",
  "device_type": "pjlink",
  "host": "192.168.1.100",
  "port": 4352,
  "state": 1,
  "enabled": true,
  "automation_enabled": true,
  "exclude_from_auto_onoff": false,
  "last_checked_at": "2024-01-12T10:30:00Z",
  "next_check_allowed_at": "2024-01-12T10:30:30Z"
}
```

---

## Admin API - Exhibitions

### List Exhibitions

```http
GET /api/admin/exhibitions
```

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Main Exhibition",
    "enabled": true,
    "created_at": "2024-01-12T10:00:00Z",
    "updated_at": "2024-01-12T10:00:00Z"
  }
]
```

### Create Exhibition

```http
POST /api/admin/exhibitions
Content-Type: application/json

{
  "name": "New Exhibition",
  "enabled": true
}
```

### Update Exhibition

```http
PUT /api/admin/exhibitions/{exhibition_id}
Content-Type: application/json

{
  "name": "Updated Name",
  "enabled": false
}
```

### Delete Exhibition

```http
DELETE /api/admin/exhibitions/{exhibition_id}
```

**Note:** Cascades to artworks and devices!

---

## Admin API - Artworks

### List Artworks

```http
GET /api/admin/artworks
GET /api/admin/artworks?exhibition_id={exhibition_id}
```

### Create Artwork

```http
POST /api/admin/artworks
Content-Type: application/json

{
  "exhibition_id": "uuid",
  "name": "New Artwork",
  "enabled": true
}
```

### Update Artwork

```http
PUT /api/admin/artworks/{artwork_id}
Content-Type: application/json

{
  "name": "Updated Name",
  "enabled": false,
  "exhibition_id": "new_uuid"
}
```

### Delete Artwork

```http
DELETE /api/admin/artworks/{artwork_id}
```

**Note:** Cascades to devices!

---

## Admin API - Devices

### List Devices

```http
GET /api/admin/devices
GET /api/admin/devices?artwork_id={artwork_id}
GET /api/admin/devices?device_type=pjlink
```

### Create Device

```http
POST /api/admin/devices
Content-Type: application/json

{
  "artwork_id": "uuid",
  "name": "Projector 1",
  "device_type": "pjlink",
  "host": "192.168.1.100",
  "port": 4352,
  "enabled": true,
  "automation_enabled": true,
  "exclude_from_auto_onoff": false,
  "config": {
    "password": "projector_password"
  }
}
```

**Device Types:**
- `pjlink` - PJLink projectors
- `netio` - NETIO power outlets
- `anel` - ANEL power outlets
- `shell` - Shell command execution

### Update Device

```http
PUT /api/admin/devices/{device_id}
Content-Type: application/json

{
  "name": "Updated Name",
  "enabled": false,
  "config": {
    "password": "new_password"
  }
}
```

### Delete Device

```http
DELETE /api/admin/devices/{device_id}
```

---

## Admin API - Configuration

### Reload Configuration

```http
POST /api/admin/config/reload
```

Manually triggers configuration hot-reload.

---

## System Endpoints

### Root

```http
GET /
```

**Response:**
```json
{
  "service": "MuTech Control Service",
  "version": "1.0.0",
  "status": "running"
}
```

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy"
}
```

### System Info

```http
GET /info
```

**Response:**
```json
{
  "version": "1.0.0",
  "device_types_supported": ["pjlink", "netio", "anel", "shell"],
  "features": {
    "on_stagger": true,
    "off_verification": true,
    "fast_lane": true,
    "hot_reload_config": true
  },
  "orchestrator": {
    "on_stagger_delay": 1.0,
    "max_concurrent_on": 10,
    "off_verification_enabled": true
  }
}
```

---

## Device Configuration Schemas

### PJLink Device Config

```json
{
  "config": {
    "password": "string (optional)",
    "timeout": 10
  }
}
```

### NETIO Device Config

```json
{
  "config": {
    "username": "admin",
    "password": "string",
    "port_number": 1
  }
}
```

### ANEL Device Config

```json
{
  "config": {
    "username": "admin",
    "password": "string",
    "port_number": 1
  }
}
```

### Shell Device Config

```json
{
  "config": {
    "commands": {
      "on": {
        "cmd": "systemctl start service",
        "timeout": 30
      },
      "off": {
        "cmd": "systemctl stop service",
        "timeout": 30
      },
      "status": {
        "cmd": "systemctl status service",
        "timeout": 10,
        "onPattern": "active \\(running\\)",
        "offPattern": "inactive|failed"
      }
    }
  }
}
```

---

## State Values

| Value | Description |
|-------|-------------|
| -1 | Error state |
| 0 | Off |
| 1 | On |
| 2 | Cooling (projectors) - treated as OFF success |
| 3 | Warming (projectors) |

---

## Rate Limiting

Not yet implemented. For production, consider implementing:
- Per-IP rate limiting
- API key-based quotas
- Exponential backoff for repeated failures

---

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 204 | No Content (successful delete) |
| 400 | Bad Request |
| 404 | Not Found |
| 500 | Internal Server Error |

---

## Examples with curl

### Complete Exhibition Control Flow

```bash
# 1. Create exhibition
EXHIBITION_ID=$(curl -s -X POST http://localhost:8000/api/admin/exhibitions \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Exhibition", "enabled": true}' \
  | jq -r '.id')

# 2. Create artwork
ARTWORK_ID=$(curl -s -X POST http://localhost:8000/api/admin/artworks \
  -H "Content-Type: application/json" \
  -d "{\"exhibition_id\": \"$EXHIBITION_ID\", \"name\": \"Test Artwork\", \"enabled\": true}" \
  | jq -r '.id')

# 3. Create device
DEVICE_ID=$(curl -s -X POST http://localhost:8000/api/admin/devices \
  -H "Content-Type: application/json" \
  -d "{
    \"artwork_id\": \"$ARTWORK_ID\",
    \"name\": \"Test Projector\",
    \"device_type\": \"pjlink\",
    \"host\": \"192.168.1.100\",
    \"port\": 4352,
    \"enabled\": true,
    \"config\": {\"password\": \"test\"}
  }" \
  | jq -r '.id')

# 4. Turn on exhibition
curl -X POST http://localhost:8000/api/control/exhibition/$EXHIBITION_ID/on

# 5. Check state
curl http://localhost:8000/api/state/exhibition/$EXHIBITION_ID | jq

# 6. Turn off exhibition
curl -X POST http://localhost:8000/api/control/exhibition/$EXHIBITION_ID/off

# 7. Monitor verification
docker-compose logs -f main-service | grep verification
```

---

For more details, see:
- `/docs` - Interactive Swagger UI
- `/redoc` - ReDoc API documentation
- `GETTING_STARTED.md` - Setup guide
- `IMPLEMENTATION_SUMMARY.md` - Technical details
