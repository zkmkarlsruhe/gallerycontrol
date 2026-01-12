# Backend API - Gap Analysis for Frontend Features

**Date:** 2026-01-12
**Status:** Identifying what's needed for designed frontend

---

## Current Backend Status

### ✅ Implemented - Core CRUD

**Exhibitions:**
- ✅ `GET /api/admin/exhibitions` - List all
- ✅ `POST /api/admin/exhibitions` - Create
- ✅ `PUT /api/admin/exhibitions/{id}` - Update
- ✅ `DELETE /api/admin/exhibitions/{id}` - Delete (cascades)

**Artworks:**
- ✅ `GET /api/admin/artworks` - List all (optional filter by exhibition)
- ✅ `POST /api/admin/artworks` - Create
- ✅ `PUT /api/admin/artworks/{id}` - Update (includes moving to different exhibition)
- ✅ `DELETE /api/admin/artworks/{id}` - Delete (cascades)

**Devices:**
- ✅ `GET /api/admin/devices` - List all (optional filters by artwork/type)
- ✅ `POST /api/admin/devices` - Create
- ✅ `PUT /api/admin/devices/{id}` - Update (includes moving to different artwork)
- ✅ `DELETE /api/admin/devices/{id}` - Delete

**Config:**
- ✅ `POST /api/admin/config/reload` - Reload config

### ✅ Implemented - Device Model Fields

All required fields exist:
- ✅ `id`, `artwork_id`, `name`, `device_type`
- ✅ `host`, `port`
- ✅ `enabled`, `automation_enabled`, `exclude_from_auto_onoff`
- ✅ `config` (JSONB - stores device-specific settings)
- ✅ `state`, `last_checked_at`, `next_check_allowed_at`
- ✅ `created_at`, `updated_at`

---

## ❌ Missing Features for Designed Frontend

### 1. IP/DNS Resolution Fields

**Issue:** Frontend design assumes separate `ip_address` and `dns_name` fields.

**Current:** Only single `host` field exists.

**Frontend Design:**
- User enters IP or DNS in form
- Backend resolves DNS → IP for device communication
- Display uses what user entered
- Communication uses resolved IP

**What's Needed:**
```sql
ALTER TABLE devices
ADD COLUMN ip_address VARCHAR(45),     -- Resolved IP for communication
ADD COLUMN dns_name VARCHAR(255);      -- Optional DNS name
```

**Backend Logic Needed:**
```python
# On device create/update:
if is_ip(device.host):
    device.ip_address = device.host
    device.dns_name = reverse_dns_lookup(device.host)  # Optional
else:
    device.dns_name = device.host
    device.ip_address = resolve_dns(device.host)

# Device managers use ip_address for communication
# Frontend displays host (whatever user entered)
```

**Priority:** Medium
**Workaround:** Use `host` for both display and communication (current behavior)

---

### 2. Single Device Endpoint

**Issue:** No endpoint to get a single device by ID.

**Current:** Only `GET /api/admin/devices` (list all with filters)

**Frontend Needs:** When editing device, need to fetch current data.

**What's Needed:**
```python
@router.get("/devices/{device_id}")
async def get_device(device_id: str, session=Depends(get_session)):
    """Get a single device by ID."""
    stmt = select(Device).where(Device.id == UUID(device_id))
    result = await session.execute(stmt)
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return {
        "id": str(device.id),
        "name": device.name,
        # ... all fields
    }
```

**Priority:** High
**Workaround:** Filter list endpoint by ID, or cache devices client-side

---

### 3. Clone Device Feature

**Issue:** No dedicated clone endpoint.

**Current:** Must GET device then POST with new data.

**Frontend Design:** Clone button pre-fills all settings except host/port.

**What's Needed (Option A - Client-side):**
```javascript
// Frontend handles cloning:
1. GET /api/admin/devices/{id}
2. Modify host/port, add "(Copy)" to name
3. POST /api/admin/devices with modified data
```

**What's Needed (Option B - Server-side):**
```python
@router.post("/devices/{device_id}/clone")
async def clone_device(
    device_id: str,
    clone_data: DeviceClone,  # host, port, name
    session=Depends(get_session)
):
    """Clone a device with new host/port."""
    # Get original device
    original = await get_device(device_id)

    # Create new device with copied settings
    new_device = Device(
        artwork_id=original.artwork_id,
        device_type=original.device_type,
        enabled=original.enabled,
        automation_enabled=original.automation_enabled,
        exclude_from_auto_onoff=original.exclude_from_auto_onoff,
        config=original.config.copy(),
        # Override with new values
        host=clone_data.host,
        port=clone_data.port,
        name=clone_data.name or f"{original.name} (Copy)"
    )

    session.add(new_device)
    await session.flush()
    return {...}
```

**Priority:** Low (client-side works fine)
**Workaround:** Client-side cloning (recommended)

---

### 4. Shell Command Testing

**Issue:** No endpoint to test shell commands.

**Frontend Design:** "Test" button next to each command input, shows output.

**What's Needed:**
```python
@router.post("/shell/test")
async def test_shell_command(command: ShellCommandTest):
    """Execute a shell command and return output (for testing)."""
    try:
        import subprocess

        result = subprocess.run(
            command.cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30  # Safety timeout
        )

        return {
            "success": True,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Command timed out (30s limit)"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

**Security Considerations:**
- ⚠️ Command injection risk - validate/sanitize input
- ⚠️ Limit to authenticated admin users only
- ⚠️ Consider whitelist of allowed commands
- ⚠️ Timeout to prevent hanging
- ⚠️ Resource limits (CPU, memory)

**Priority:** High (important for shell device setup)
**Workaround:** Users test commands manually via SSH

---

### 5. Shell Command Templates

**Issue:** No storage or endpoints for command templates.

**Frontend Design:** Pre-built templates (Systemd, Docker, etc.) with variable substitution.

**Database Schema Needed:**
```sql
CREATE TABLE shell_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    automation_enabled BOOLEAN NOT NULL,
    commands JSONB NOT NULL,
    variables JSONB,
    is_builtin BOOLEAN DEFAULT FALSE,
    created_by UUID,  -- Optional: user tracking
    is_shared BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**API Endpoints Needed:**
```python
GET    /api/admin/shell-templates         # List all templates
GET    /api/admin/shell-templates/{id}    # Get single template
POST   /api/admin/shell-templates         # Create custom template
PUT    /api/admin/shell-templates/{id}    # Update custom template
DELETE /api/admin/shell-templates/{id}    # Delete custom template

# Built-in templates seeded on first run
```

**Built-in Templates to Seed:**
```python
BUILTIN_TEMPLATES = [
    {
        "name": "Systemd Service Control",
        "description": "Control systemd service with state monitoring",
        "category": "System",
        "automation_enabled": True,
        "is_builtin": True,
        "variables": [
            {"name": "SERVICE_NAME", "placeholder": "myapp"},
            {"name": "HOST", "placeholder": "server.local"}
        ],
        "commands": {
            "reachable": {"name": "Reachable", "cmd": "ping -c 1 {{HOST}}"},
            "status": {
                "name": "Status",
                "cmd": "systemctl status {{SERVICE_NAME}}",
                "onPattern": "Active: active \\(running\\)",
                "offPattern": "Active: inactive"
            },
            "on": {"name": "ON", "cmd": "systemctl start {{SERVICE_NAME}}"},
            "off": {"name": "OFF", "cmd": "systemctl stop {{SERVICE_NAME}}"}
        }
    },
    # ... more templates
]
```

**Priority:** Medium (nice-to-have, can start with client-side templates)
**Workaround:** Hard-code templates in frontend, store in localStorage

---

### 6. Batch Create Operations

**Issue:** No bulk create endpoints.

**Frontend Design:** Comma-separated input creates multiple items at once.

**Current:** Must POST multiple times (one per item).

**What's Needed:**
```python
class ExhibitionBatchCreate(BaseModel):
    names: List[str]  # List of exhibition names

@router.post("/exhibitions/batch", status_code=201)
async def create_exhibitions_batch(
    batch: ExhibitionBatchCreate,
    session=Depends(get_session)
):
    """Create multiple exhibitions at once."""
    created = []

    for name in batch.names:
        exhibition = Exhibition(name=name.strip())
        session.add(exhibition)
        created.append(exhibition)

    await session.flush()

    return [
        {
            "id": str(ex.id),
            "name": ex.name,
            "enabled": ex.enabled
        }
        for ex in created
    ]

# Similar for artworks batch create
```

**Priority:** Low (client-side can loop and POST)
**Workaround:** Client splits comma-separated input and POSTs individually

---

### 7. Get Single Exhibition/Artwork

**Issue:** No endpoints to get single exhibition or artwork by ID.

**Current:** Only list endpoints exist.

**What's Needed:**
```python
@router.get("/exhibitions/{exhibition_id}")
async def get_exhibition(exhibition_id: str, session=Depends(get_session)):
    """Get a single exhibition by ID."""
    # Implementation similar to get_device

@router.get("/artworks/{artwork_id}")
async def get_artwork(artwork_id: str, session=Depends(get_session)):
    """Get a single artwork by ID."""
    # Implementation similar to get_device
```

**Priority:** Medium
**Workaround:** Use list endpoints with filters, cache client-side

---

### 8. Bulk Operations

**Issue:** No bulk update/delete endpoints.

**Frontend Design:** Select multiple devices → Move all or Delete all.

**What's Needed:**
```python
class BulkUpdate(BaseModel):
    device_ids: List[str]
    artwork_id: str  # New artwork to move to

@router.patch("/devices/bulk/move")
async def bulk_move_devices(bulk: BulkUpdate, session=Depends(get_session)):
    """Move multiple devices to a different artwork."""
    stmt = (
        update(Device)
        .where(Device.id.in_([UUID(id) for id in bulk.device_ids]))
        .values(artwork_id=UUID(bulk.artwork_id))
    )
    result = await session.execute(stmt)
    return {"updated": result.rowcount}

@router.delete("/devices/bulk")
async def bulk_delete_devices(device_ids: List[str], session=Depends(get_session)):
    """Delete multiple devices at once."""
    stmt = delete(Device).where(Device.id.in_([UUID(id) for id in device_ids]))
    result = await session.execute(stmt)
    return {"deleted": result.rowcount}
```

**Priority:** Low (nice-to-have)
**Workaround:** Client loops and calls individual endpoints

---

## Summary Table

| Feature | Status | Priority | Workaround Available |
|---------|--------|----------|---------------------|
| **Core CRUD** | ✅ Complete | - | - |
| **IP/DNS Fields** | ❌ Missing | Medium | Use single host field |
| **Get Single Device** | ❌ Missing | High | Use list + filter |
| **Get Single Exhibition/Artwork** | ❌ Missing | Medium | Use list + filter |
| **Clone Device** | ❌ Missing | Low | Client-side clone |
| **Shell Command Test** | ❌ Missing | **High** | Manual SSH testing |
| **Shell Templates DB** | ❌ Missing | Medium | Frontend localStorage |
| **Batch Create** | ❌ Missing | Low | Client loops POST |
| **Bulk Operations** | ❌ Missing | Low | Client loops |

---

## Recommended Implementation Order

### Phase 1: Essential (Block frontend development)
1. **GET single device endpoint** - Frontend needs this for edit forms
2. **Shell command test endpoint** - Critical for shell device setup

### Phase 2: Important (Improve UX)
3. **GET single exhibition/artwork** - Better than filtering lists
4. **IP/DNS resolution fields** - Better architecture for future

### Phase 3: Nice-to-Have (Can defer)
5. **Shell templates database** - Start with frontend-only templates
6. **Batch create** - Client-side works fine
7. **Bulk operations** - Client-side loops work
8. **Dedicated clone endpoint** - Client-side works fine

---

## Client-Side Workarounds Summary

### Works Fine Client-Side:
- **Clone device:** GET + modify + POST
- **Batch create:** Split input + loop POST
- **Bulk move:** Loop PUT for each device
- **Bulk delete:** Loop DELETE for each device
- **Shell templates:** Hard-code in frontend or localStorage

### Needs Server Implementation:
- **Shell command testing:** Security-sensitive, needs server-side execution
- **Get single items:** More efficient than filtering large lists
- **IP/DNS resolution:** Better done server-side with proper DNS libraries

---

## Action Items

### Immediate (Before Frontend Implementation)
- [ ] Add `GET /api/admin/devices/{id}` endpoint
- [ ] Add `POST /api/admin/shell/test` endpoint (with security considerations)
- [ ] Add `GET /api/admin/exhibitions/{id}` endpoint
- [ ] Add `GET /api/admin/artworks/{id}` endpoint

### Short-term (During Frontend Development)
- [ ] Add `ip_address` and `dns_name` columns to Device model
- [ ] Add migration for new columns
- [ ] Update device create/update to resolve DNS
- [ ] Update device managers to use `ip_address` for communication

### Long-term (Future Enhancement)
- [ ] Implement shell templates database and endpoints
- [ ] Add batch create endpoints
- [ ] Add bulk operations endpoints
- [ ] Add dedicated clone endpoint
- [ ] Add template variable validation

---

## Security Considerations

### Shell Command Testing Endpoint

**Risks:**
- Command injection attacks
- Resource exhaustion
- Unauthorized access
- Privilege escalation

**Mitigations:**
```python
from fastapi import Depends, HTTPException
from functools import wraps

# 1. Authentication & Authorization
@router.post("/shell/test")
async def test_shell_command(
    command: ShellCommandTest,
    user: User = Depends(get_current_admin_user)  # Require admin
):
    # 2. Input validation
    if len(command.cmd) > 1000:
        raise HTTPException(status_code=400, detail="Command too long")

    # 3. Forbidden patterns
    FORBIDDEN = [';', '&&', '||', '|', '`', '$', '>', '<', '&']
    if any(char in command.cmd for char in FORBIDDEN):
        raise HTTPException(status_code=400, detail="Invalid characters in command")

    # 4. Timeout limit
    timeout = 30

    # 5. Execute with resource limits
    result = await asyncio.wait_for(
        execute_shell_command(command.cmd),
        timeout=timeout
    )

    # 6. Log all executions
    logger.info(f"Shell test by {user.id}: {command.cmd}")

    return result
```

**Alternative:** Whitelist approach
```python
# Only allow specific command patterns
ALLOWED_PATTERNS = [
    r'^ping -c \d+ [\w\.-]+$',
    r'^systemctl (status|start|stop) [\w-]+$',
    r'^docker (ps|start|stop) [\w-]+$',
]

if not any(re.match(pattern, command.cmd) for pattern in ALLOWED_PATTERNS):
    raise HTTPException(status_code=400, detail="Command not allowed")
```

---

## Conclusion

**Current Status:** ✅ **Backend has core CRUD complete**

**Ready for Frontend?** ⚠️ **Mostly yes, with workarounds**

**Blockers:** Only 2 critical missing endpoints:
1. GET single device (can work around with list filtering)
2. Shell command testing (should implement for security + UX)

**Recommendation:**
- Start frontend development now
- Implement the 4 "Immediate" endpoints in parallel
- Use client-side workarounds for batch/bulk operations
- Defer templates database until needed

---

**Last Updated:** 2026-01-12
**Status:** Gap analysis complete

