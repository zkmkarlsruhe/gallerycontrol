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

### 2. State Change Protocol ✅ COMPLETED

**Status:** Implemented

**Problem:** Current logging only tracks command execution, not when devices actually changed state. No history of ON/OFF transitions.

**Solution:** Created a state change log that records only actual transitions.

**Implementation:**
- New `StateChangeLog` model with CASCADE delete (device deleted → logs deleted)
- Centralized `update_device_state_with_log()` helper in `database/state_logger.py`
- Only logs when state actually changes (previous_state != new_state)
- Tracks trigger source: polling, command, or verification

**API Endpoints:**
- `GET /api/state/changes` - List state changes with filters (device_id, artwork_id, exhibition_id, from_date, to_date, new_state, limit, offset)
- `GET /api/state/changes/export` - Export as CSV
- `POST /api/admin/state-changes/cleanup` - Manual cleanup with configurable retention (default 90 days)

**What Gets Logged:**
- Which device changed
- Previous state → New state (values: -1=error, 0=off, 1=on, 2=cooling, 3=warming)
- When it changed (timestamp)
- What triggered the change (polling, command, verification)

**Use Cases:**
- "When did this projector last turn off?"
- "How many errors occurred today?"
- "Show me all state changes for Gallery 1"

---

### 3. Shell Command Library ✅ COMPLETED

**Status:** Implemented (Jan 2026)

**Problem:** Shell devices require complex configuration (SSH commands, status patterns, ON/OFF commands). When setting up similar devices, users must re-enter everything manually.

**Solution:** Allow copying existing shell devices into a reusable library.

**Implementation:**
- Shell Templates modal accessible via "Shell Library" button in header (edit mode)
- Templates support both ON/OFF mode and Custom Actions mode
- Full CRUD: create, edit, delete templates
- "Save to Library" button in Edit Device modal for shell devices
- Template selector dropdown in Add Device form (Shell type)
- Test buttons for each command in template editor

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

### 4. Credentials Library ✅ COMPLETED

**Status:** Implemented

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

### 6. Touch-Safe Controls ✅ COMPLETED

**Status:** Implemented (Jan 2026)

**Problem:** Accidental button presses on touch devices can turn devices on/off unintentionally.

**Solution:** Multiple safety layers.

**Implementation:**
- `TouchSafeButton` component with responsive behavior
- Mobile (< 900px): Double-tap required - first tap shows "ON?"/"OFF?", second tap executes
- Desktop (> 900px): Single click works normally
- Applied to all ON/OFF buttons in non-edit mode (exhibitions, artworks, devices)
- Mobile compact CSS reduces whitespace for better touch targets

**Layer 2: Double-tap confirmation**
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

**Future testing:**
- PWA with gesture controls (double-tap, long-press, swipe)
- Test what feels natural on actual devices

---

### 7. State Timeline Visualization (Gantt View) ✅ COMPLETED

**Status:** Implemented (Jan 2026)

**Problem:** When debugging device issues, staff need to see *when* state changes happened across multiple devices. A text log is hard to scan - you can't easily see patterns like "all projectors failed at 9:15" or "this device keeps cycling on/off".

**Solution:** Gantt-style timeline visualization accessible via "Timeline" button in header.

**Visual Design:**
```
Time:     08:00   09:00   10:00   11:00   12:00   13:00
          ├───────┼───────┼───────┼───────┼───────┤
Projector 1  ████████████████░░░░░░░░░████████████
Projector 2  ████████████████████████████░░░░░░░░░
NETIO Port 1 ████████████████████████████████████████
Computer 1   ░░░░░░░░████████████████████████████████
             └─ gray=off, green=on, red=error, yellow=warming/cooling
```

**Features:**
- Each device is a row
- Time is X-axis (scrollable, zoomable)
- Colored segments show state:
  - Green = ON
  - Gray = OFF
  - Red = ERROR
  - Yellow = WARMING/COOLING
- Hover shows exact timestamp + trigger source
- Click segment to see state change details
- Filter by exhibition/artwork
- Time range selector (last hour, today, custom)

**Data source:** `StateChangeLog` table (already exists)
- Query: `GET /api/state/changes?from_date=...&to_date=...`
- Returns: device_id, previous_state, new_state, timestamp, trigger

**Implementation:** D3.js for the timeline visualization (horizontal bar segments)

**Use Cases:**
- "When did devices start failing this morning?"
- "Is this device cycling on/off repeatedly?"
- "Did all projectors turn off at the same time?"
- "How long was this device in error state?"

---

### 8. Frontend Error Notifications

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

### 9. PWA (Progressive Web App) ✅ COMPLETED

**Status:** Implemented (Jan 2026)

**Problem:** Staff need quick access from phones without opening browser and typing URL.

**Solution:** Make the web app installable as PWA.

**Implementation:**
- manifest.json with 8 icon sizes (72px-512px) + maskable icons
- Service worker with cache-first for static assets, network-only for API
- iOS meta tags (apple-mobile-web-app-capable, apple-touch-icon)
- Backend routes serve PWA files from root for proper SW scope

**Features:**
- Add to home screen (iOS + Android)
- Full screen mode (no browser chrome)
- Offline capability (cached interface)
- Fast loading
- App icon on home screen (power symbol with control dots)

---

### 10. Shell Devices: Combined ON/OFF + Actions

**Priority:** Low (idea for future)
**Status:** Idea - needs testing in feature branch

**Problem:** Currently shell devices have two modes:
- **ON/OFF Mode**: status/on/off commands for automation
- **Custom Mode**: only custom actions (no automation)

You can't have both. For devices like Ghost Commander Windows clients, you might want:
- ON/OFF for automation (turn artwork on/off)
- PLUS extra actions like Reboot, Restart App

**Current Workaround:** Create two shell devices:
1. One for automation (ON/OFF mode)
2. One for actions (Custom mode)

**Potential Solution:** Allow actions in ON/OFF mode too. Show actions section regardless of mode.

**Implementation Notes:**
- Backend already supports this (actions stored separately from on/off commands)
- Only frontend form needs updating
- Add "Additional Actions" section when onoff_mode=true

**Testing:** Create feature branch `feature/shell-combined-mode` to test UX.

---

### 11. Additional Features (Lower Priority)

**Single Entity Endpoints** ✅ COMPLETED
- GET /api/admin/exhibitions/{id}
- GET /api/admin/artworks/{id}
- GET /api/admin/devices/{id}

**ANEL UDP Implementation** ✅ COMPLETED
- ANEL runner service with broadcast listener
- GET /devices/broadcast/cache - all cached device states
- GET /devices/{host}/cached - single device cached state

---

**Last Updated:** 2026-01-17
