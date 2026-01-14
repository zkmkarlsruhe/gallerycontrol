# MuTech Control System - Planned Features

**Created:** 2026-01-14
**Status:** Planning Document

---

## Overview

This document tracks current features and planned enhancements for the MuTech Control System.

---

## Core Principles

**Everything is editable.** All entities (exhibitions, artworks, devices, templates) support full CRUD:
- Add
- Edit (all fields)
- Delete
- Copy (shell templates only)

No read-only items. No locked fields. Staff can change anything at any time.

**Touch safety - double tap to confirm:**
1. First tap: Button shows `ON?` / `OFF?` (confirm state)
2. Second tap: Command sent
3. Timeout: Resets after few seconds if not confirmed
4. Any other button pressed: All pending confirmations reset

Prevents accidental button presses on touch devices.

**Control mode interactions:**
- Tap device → toggle state (with double-tap safety)
- Small link icon → open device web interface (http://host)
- Artwork: ON/OFF buttons → control all devices in artwork
- Exhibition: ON/OFF buttons → control all devices in exhibition

**Credentials library:**

Central store for passwords/users. Devices reference credentials by name.

| Device Type | Credentials |
|-------------|-------------|
| PJLink | Password only (select from library) |
| NETIO | User + Password (select from library) |
| ANEL | User + Password (select from library) |
| Shell/SSH | Use placeholder `{{PASSWORD:name}}` in commands |

**Example credential entry:**
- Name: `museumstechnik`
- User: `museumstechnik`
- Password: `(stored)`

**Usage in shell command:**
```
sshpass -p {{PASSWORD:museumstechnik}} ssh {{USER:museumstechnik}}@host
```

System replaces placeholders at runtime. Change password once → all devices update.

---

## Current Features

### Core System
- REST API for device control
- PostgreSQL/SQLite database
- Docker deployment
- Hot-reload configuration
- Basic web interface

### Device Support
- PJLink projectors
- NETIO power strips
- Shell commands (SSH/local scripts)
- ANEL power strips (partially implemented)

### Control Features
- Hierarchy: Exhibition > Artwork > Device
- ON command stagger (1-second delay between devices)
- OFF verification with retry
- Fast lane API for external triggers
- Per-device cooldown
- Automatic state polling

### Enable/Disable (Current)
Each level has an `enabled` flag:
- Exhibition enabled/disabled
- Artwork enabled/disabled
- Device enabled/disabled

**Behavior:**
- Enabled devices are always polled (no per-device automation toggle)
- Manual ON/OFF always works, regardless of polling
- Global "Maintenance Mode" to pause all automation temporarily

**Limitation:** Flags are currently independent. Disabling an exhibition does NOT automatically affect its artworks and devices.

### Logging (Current)
- Command execution log (which commands were sent)
- Request ID tracing
- Duration tracking

**Limitation:** Only logs commands, not actual state changes.

---

## Planned Features

### 1. Enable/Disable with Inheritance ✅ COMPLETED

**Status:** Implemented (commit 814cf60)

**Problem:** Currently, disabling an exhibition does not affect its children. Operators must manually disable each artwork and device.

**Solution:** Implemented inheritance where children inherit the disabled state from parents via `effective_enabled` computed property.

**Implementation:**
- Command orchestrator checks parent chain before executing commands
- State monitor query joins parent tables to filter disabled devices from polling
- API returns both `enabled` (individual flag) and `effective_enabled` (computed)
- Frontend has Control/Show All toggle:
  - Control mode: Hides disabled items completely
  - Show All mode: Shows disabled items with DISABLED/PARENT DISABLED badges

**Behavior:**
- Exhibition disabled → All artworks and devices effectively disabled
- Artwork disabled → All devices in that artwork effectively disabled
- Device disabled → Only that device disabled

**Important:** Disabling a parent does NOT change children's own enabled state. We check the parent chain to determine effective state. Children keep their individual settings.

**Benefits:**
- One click to disable entire exhibition
- Re-enabling parent restores previous child states automatically
- Clean control interface without disabled clutter

---

### 2. State Change Protocol

**Priority:** High

**Problem:** Current logging only tracks command execution, not when devices actually changed state. No history of ON/OFF transitions.

**Solution:** Create a state change log that records only actual transitions.

**What Gets Logged:**
- Which device changed
- Previous state → New state
- When it changed
- What triggered the change (command, polling, etc.)

**Key Principles:**
- Only log when state actually changes (not every poll)
- Lightweight storage
- Useful for troubleshooting and statistics

**Data Cleanup:**
- When a device is deleted, all its state history is automatically removed
- Configurable retention period (e.g., 90 days)

**Export:**
- Export state change history (CSV or plain text)
- Filter by date range, exhibition, artwork, or device

**Use Cases:**
- "When did this projector last turn off?"
- "How many errors occurred today?"
- "Show me all state changes for Gallery 1"

---

### 3. Shell Command Library

**Priority:** High

**Problem:** Shell devices require complex configuration (SSH commands, status patterns, ON/OFF commands). When setting up similar devices, users must re-enter everything manually.

**Solution:** Allow copying existing shell devices into a reusable library.

**How It Works:**
1. Create and configure a shell device manually
2. Save working device config to library (as template)
3. When creating new device, select from library
4. Adjust host/name as needed

**Library entries are fully editable** (add/edit/delete). No pre-built templates - library is built from real devices.

**Command Testing:**
- Test button to verify commands work before saving
- Shows command output and success/failure

---

### 4. Credentials Library

**Priority:** High

**Problem:** Passwords are scattered across device configs. Same password entered multiple times. Changing a shared password requires editing every device.

**Solution:** Central credentials store. Devices reference credentials by name.

**Credential entry fields:**
- Name (identifier, e.g., `museumstechnik`, `projector-default`)
- User (optional, for NETIO/ANEL/SSH)
- Password

**Usage per device type:**

| Device | How credentials are used |
|--------|--------------------------|
| PJLink | Dropdown: select credential (password only) |
| NETIO | Dropdown: select credential (user + password) |
| ANEL | Dropdown: select credential (user + password) |
| Shell | Placeholders in command text |

**Shell command placeholders:**
```
{{USER:name}}      → replaced with username
{{PASSWORD:name}}  → replaced with password
```

**Example:**
```
sshpass -p {{PASSWORD:museumstechnik}} ssh {{USER:museumstechnik}}@server.zkm.de
```

**Benefits:**
- Change password once → all devices using it update automatically
- No duplicate password entry
- UI shows credential name, not actual password
- Credentials list fully editable (add/edit/delete)

---

### 5. Email Inventory Export

**Priority:** Medium

**Problem:** If the control system (Steuerung) breaks, staff need to know what devices exist and how to connect to them manually.

**Solution:** Send complete device inventory via email for maintenance/backup purposes.

**Format:**
```
### LH 1/2 GamePlay
## Bubbles
* Projektor: http://192.168.232.69

## Room Racers
* Projektor: http://192.168.232.149
* Steckdose: http://netzwerksteckdose-netio-011.zkm.de Port: 1

## PacaPong
* Shell: sshpass -f /root/.ssh/museumstechnik.txt ssh museumstechnik@gameplay-pacapong.zkm.de
```

**Features:**
- Hierarchical: Exhibition → Artwork → Device
- Shows device type (Projektor, Steckdose, Shell)
- Direct connection URL or command
- Port number for power strips
- Trigger manually when needed
- Plain text format (works in any email client)

---

### 6. Touch-Safe Controls

**Priority:** High

**Problem:** Accidental button presses on touch devices can turn devices on/off unintentionally.

**Solution:** Double-tap confirmation for all control actions.

**Device controls:**
- Tap device → shows confirm state (e.g., device highlight or `?`)
- Tap again → command sent
- Timeout (few seconds) → resets to normal
- Tap any other button → all pending confirmations reset

**Artwork / Exhibition controls:**
- ON/OFF buttons for bulk control
- Same double-tap safety applies

**Additional:**
- Small link icon on device → opens device web interface (http://host)
- Works on both touch and mouse

---

### 7. Frontend Error Notifications

**Priority:** Medium

**Problem:** Staff don't know when something goes wrong unless they're actively watching the interface. A projector might fail to turn on and nobody notices.

**Solution:** Show error notifications in the frontend when devices fail.

**What triggers a notification:**
- Device fails to change state (command sent but state didn't change)
- Device becomes unreachable
- Command timeout or error response

**Display options:**
- Toast/popup notification
- Error badge/counter in header
- Error log panel (expandable)
- Visual indicator on affected device

**Behavior:**
- Notifications appear automatically
- Can be dismissed
- Recent errors visible in a log view
- Clear indication which device/artwork/exhibition has problems

---

### 8. Additional Features (Lower Priority)

**Single Entity Endpoints** ✅ COMPLETED
- GET /api/admin/exhibitions/{id}
- GET /api/admin/artworks/{id}
- GET /api/admin/devices/{id}

**ANEL UDP Implementation** ✅ COMPLETED
- ANEL runner service with broadcast listener
- GET /devices/broadcast/cache - all cached device states
- GET /devices/{host}/cached - single device cached state

---

**Last Updated:** 2026-01-14
