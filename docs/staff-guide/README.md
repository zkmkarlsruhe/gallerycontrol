# MuTech Control - Staff Guide

This guide covers how to use the MuTech Control interface to manage museum exhibition devices.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Interface Overview](#interface-overview)
3. [Control Mode](#control-mode)
4. [Edit Mode](#edit-mode)
5. [Managing Exhibitions](#managing-exhibitions)
6. [Managing Artworks](#managing-artworks)
7. [Managing Devices](#managing-devices)
8. [Device Types](#device-types)
9. [Credentials](#credentials)
10. [Shell Library](#shell-library)
11. [Views](#views)
12. [Mobile Access](#mobile-access)

## Additional Documentation

- [Device Types - Detailed Guide](devices.md) - Complete device configuration reference
- [Asset Management (Projectors)](assets.md) - Lamp hours tracking and projector management
- [Artwork Protection](protection.md) - Time-slice windows and runtime limits
- [Scheduling System](schedules.md) - Automated ON/OFF scheduling
- [Satellite Relay System](satellites.md) - Managing devices on remote networks

---

## Getting Started

### Accessing the System

Open your web browser and navigate to the MuTech Control URL provided by your administrator (typically `http://your-server:8000`).

### First Time Setup

When you first access the system with no data, you'll see the empty state:


To start adding content, enable **Edit Mode** using the checkbox in the top-right corner:


---

## Interface Overview

### Header Navigation

The header provides quick access to different views and tools:

| Button | Description |
|--------|-------------|
| **Timeline** | View device state history over time |
| **Projectors** | Browse projector assets and lamp hours (Edit Mode only) |
| **Logs** | View real-time operation logs |
| **Library** | Manage shell command templates (Edit Mode only) |
| **Credentials** | Manage device passwords (Edit Mode only) |
| **Mail** | Send inventory reports (Edit Mode only) |
| **Admin** | System administration tools (Edit Mode only) |
| **Edit Mode** | Toggle between control and edit modes |

### Main Area

The main area displays exhibitions in a hierarchical structure:
- **Exhibitions** - Top-level containers (e.g., "Gallery Floor 1")
- **Artworks** - Art installations within exhibitions
- **Devices** - Individual controllable devices within artworks

---

## Control Mode

Control Mode is the default view for day-to-day operations.

### Service Health Banner

When backend services are offline or unavailable, a warning banner appears at the top of the page:

- Shows which service is affected and its description
- Lists device types that may not work
- Displays error message if available
- Click **×** to dismiss temporarily

**Example:** If the ANEL Runner service is down, you'll see "ANEL Runner - UDP relay service for ANEL power devices" with affected device types listed.

### Global Controls

At the top of the main view, you'll see global control buttons:

- **Turn All ON** - Powers on all devices in all exhibitions
- **Turn All OFF** - Powers off all devices in all exhibitions

**Note:** These require double-click/tap to confirm (prevents accidental activation).

### Controlling Exhibitions

Each exhibition shows:
- **ON/OFF buttons** - Control all devices in the exhibition
- **Device counts** - Shows number of devices by state (e.g., "2 on / 1 off")
- **Auto/Manual split** - Shows "3 auto / 1 manual" indicating automation vs manual-only devices
- Expandable artwork list


### Controlling Artworks

Click on an artwork to expand it and see its devices. Each artwork has:
- **ON/OFF buttons** - Control all devices in the artwork
- Device status indicators
- **Time Slice indicator** - Lightning bolt icon when artwork has active time windows (see [Artwork Protection](protection.md))
- **Accepting triggers** - When time slice is active and device commands are allowed

**Device Separation:**
- **Automation devices** - Included in bulk ON/OFF operations (shown first)
- **Manual devices** - Must be controlled individually (shown with hand icon)

### Controlling Devices

Individual devices show their current state with color indicators:
- **Green** - Device is ON
- **Gray** - Device is OFF
- **Blue** - Device is warming up
- **Orange** - Device is cooling down
- **Red** - Device error or unreachable

**Device Badges:**
- **Poll progress bar** - Shows time until next state poll
- **Hand icon** - Device is manual-only (not included in automation)
- **Type icon** - Projector, terminal, plug, or lightning based on device type

### Expanded Device Information

Click on a device to expand and see detailed information:

**Extended Info Panel** (for PJLink projectors):
- Manufacturer and model
- Lamp hours
- MAC address
- Voltage, power, temperature readings

**Protection Status Panel** (when protection is configured):
- Current budget bars showing usage limits
- Runtime limit progress
- Cooldown status

**Host Link:**
- Shows device hostname/IP
- Click copy button to copy to clipboard

**Device Logs:**
- Click "Logs" button to view recent operations for this device

---

## Edit Mode

Enable Edit Mode to add, modify, or delete exhibitions, artworks, and devices.

### Enabling Edit Mode

Click the **Edit Mode** checkbox in the top-right corner. Additional controls will appear:

- **+ Artwork** button on exhibitions
- **Edit** (pencil) and **Delete** (trash) buttons
- Header tools (Library, Credentials, Admin)

---

## Managing Exhibitions

### Creating an Exhibition

1. Enable Edit Mode
2. Enter the exhibition name in the input field
3. Click **+ Add**


The exhibition is created:


### Editing an Exhibition

Click the **pencil icon** on an exhibition to edit:


**Settings:**
- **Exhibition Name** - Display name
- **Enabled** - When disabled, the exhibition is hidden in Control Mode
- **Enable Schedules** - Show schedule button for automated ON/OFF
- **Satellite Relay** - Route commands through a satellite daemon (for remote networks)

### Deleting an Exhibition

Click the **trash icon** and confirm. This deletes all artworks and devices within.

---

## Managing Artworks

### Creating an Artwork

1. Click **+ Artwork** on an exhibition
2. Enter the artwork name(s)
3. Click **Add Artwork**


**Tip:** Create multiple artworks at once by separating names with commas:
```
Room 1, Room 2, Room 3
```


### Artwork Created


---

## Managing Devices

### Adding a Device

1. Click **+ Device** on an artwork
2. Select the device type
3. Fill in the configuration
4. Click **Save** (button enables when host is reachable)


### Device Forms

Each device type has specific configuration options. See [Device Types](#device-types) below.

---

## Device Types

### PJLink (Projectors)

PJLink is the standard protocol for projector control.


**Configuration:**
| Field | Description |
|-------|-------------|
| Device Name | Display name (e.g., "Main Projector") |
| Host / IP Address | Projector's network address |
| Port | PJLink port (default: 4352) |
| Credentials | Password for protected projectors |
| Device Enabled | Include in state polling |
| Include in Automation | Include in bulk ON/OFF operations |

**Features:**
- Automatic warmup/cooldown detection
- Lamp hours tracking (with asset linking)
- State verification after commands

### NETIO (Smart Power Strips)

NETIO devices provide per-outlet power control via HTTP API.


**Configuration:**
| Field | Description |
|-------|-------------|
| Device Name | Display name |
| Host / IP Address | NETIO device address |
| Port/Outlet | Which outlet to control (1-8) |
| Credentials | Username/password for the device |

### ANEL (Power Distribution Units)

ANEL devices use UDP for control (via the ANEL Runner service).


**Configuration:**
| Field | Description |
|-------|-------------|
| Device Name | Display name |
| Host / IP Address | ANEL device address |
| Port/Outlet | Which outlet to control |
| Credentials | Device password |

### Shell (Custom Commands)

Shell devices execute custom commands for devices that don't support standard protocols.


**Configuration:**
| Section | Description |
|---------|-------------|
| Device Name | Display name |
| Credentials | Optional SSH credentials (use `{{PASSWORD}}` placeholder) |
| Status Detection | Command and regex patterns to detect ON/OFF state |
| ON/OFF Control | Commands to turn device on and off |
| Custom Actions | Additional buttons for special operations |

**Placeholders:**
- `{{HOST}}` - Device hostname
- `{{PASSWORD}}` - Password from selected credential
- `{{USERNAME}}` - Username from selected credential

---

## Credentials

The Credentials Store manages passwords used by devices.


### Adding a Credential

1. Click **Credentials** in the header
2. Click **+ Add**
3. Enter name, username, and password
4. Click **Save**

### Using Credentials

When configuring a device, select the credential from the dropdown. The device will use the stored password for authentication.

**Benefits:**
- Change a password in one place, all devices update
- Passwords not exposed in device configuration
- Easy credential rotation

---

## Email Inventory

The Email Inventory feature sends device reports via email.

### Accessing Email Inventory

1. Enable **Edit Mode**
2. Click **Mail** in the header

### Configuration

**Prerequisites:** SMTP must be configured by the administrator. If not configured, you'll see a warning message.

**Options:**
| Field | Description |
|-------|-------------|
| **Exhibition** | Select which exhibition to include, or "All Exhibitions" |
| **Include disabled** | Include disabled devices in the report |

### Sending Reports

1. Click **Preview** to see what will be sent
2. Review the inventory list
3. Click **Send Email** to send to configured recipients

**Report includes:**
- Exhibition and artwork names
- Device names and types
- Host addresses
- Current state
- Configuration details

---

## Shell Library

The Shell Library stores reusable command templates for Shell devices.


### Creating a Template

1. Click **Library** in the header
2. Click **+ Add Template**
3. Configure the template:
   - Name and description
   - Status command and patterns
   - ON/OFF commands
   - Custom actions

### Using Templates

When adding a Shell device, select a template to pre-fill the configuration.

### Save to Library (from Device)

You can save an existing Shell device's configuration as a template:

1. Open the device's edit modal (pencil icon)
2. Click **Save to Library** button
3. Enter a template name
4. Click **Save**

This is useful when you've configured a working Shell device and want to reuse the configuration for similar devices.

---

## Views

### Timeline View

The Timeline shows device state changes over time using an interactive visualization.


**Time Range Selector:**
| Option | Description |
|--------|-------------|
| **1h** | Last hour |
| **4h** | Last 4 hours |
| **12h** | Last 12 hours |
| **24h** | Last 24 hours |
| **Today** | Since midnight |
| **7d** | Last 7 days |
| **30d** | Last 30 days |
| **Custom** | Pick specific date range |

**Filtering:**
- **Exhibition dropdown** - Filter devices by exhibition
- Shows only devices with state changes in the selected period

**Interactive Controls:**
| Action | Effect |
|--------|--------|
| **Ctrl + Scroll** | Zoom in/out on timeline |
| **Drag** | Pan left/right |
| **Click device** | View device details |

**Visual Indicators:**
- **Green bars** - Device ON periods
- **Gray bars** - Device OFF periods
- **Red bars** - Error/unreachable periods
- **Blue bars** - Warming up
- **Orange bars** - Cooling down
- **"NOW" line** - Current time indicator (red vertical line)

### Logs View

The Logs view shows real-time operation logs with powerful filtering.


**Information shown:**
- Timestamp
- Device name (click to filter by device)
- Operation type
- Success/failure status
- Error messages

**Controls:**

| Control | Description |
|---------|-------------|
| **Device dropdown** | Filter logs to specific device |
| **Errors Only** | Show only failed operations |
| **Pause/Resume** | Stop/start auto-refresh |
| **Auto-scroll** | Automatically scroll to newest |
| **Advanced** | Toggle advanced view |

**Advanced View:**
When enabled, shows additional panel:
- **Task Scheduler Status** - View scheduled jobs and their next run time
- Click any log line to filter by that device

### Assets View (Projectors)

The Assets view tracks projector lamp hours.


**Features:**
- View all projector assets
- Track lamp hours over time
- Manual lamp hours entry
- Link devices to asset records

---

## Admin Tools

The Admin panel provides system management functions.


**Available tools:**
- Run system tasks manually
- View scheduled job status
- Check service health
- Manage satellites

---

## API Documentation

For integration and automation, the system provides interactive API documentation.

### Swagger UI


Access at `/docs` - Interactive API testing interface.

### ReDoc


Access at `/redoc` - Readable API reference documentation.

---

## Mobile Access

The interface is fully responsive and works on mobile devices.

### Mobile Control View


### Mobile Edit View


### Tablet View


**Mobile features:**
- Touch-safe buttons (double-tap for destructive actions)
- Responsive layout
- PWA support (add to home screen)

---

## Quick Reference

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Escape` | Close modal dialogs |

### State Colors

| Color | Meaning |
|-------|---------|
| Green | Device ON |
| Gray | Device OFF |
| Blue | Warming up |
| Orange | Cooling down |
| Red | Error/Unreachable |
| Yellow | Pending operation |

### URL Hash Navigation

| URL | View |
|-----|------|
| `#` or `/` | Control Mode |
| `#edit` | Edit Mode |
| `#timeline` | Timeline View |
| `#assets` | Assets View |
| `#logs` | Logs View |

---

## Getting Help

For technical support, contact your system administrator.

For API integration, see the [API Documentation](/docs).
