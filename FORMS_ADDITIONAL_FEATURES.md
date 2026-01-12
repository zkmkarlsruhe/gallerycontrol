# MuTech Control - Additional Form Features

**Date:** 2026-01-12
**Features:** Clone/Duplicate, Move Device, Shell Command Library

---

## Feature 1: Clone/Duplicate Device

### Use Case
- User has multiple identical devices (e.g., 10 projectors with same password)
- Instead of re-entering all settings, clone and change only host/port
- Saves time, reduces errors

### UI/UX Design

#### Option A: Clone Button in Device Badge

```
Exhibition: Main Gallery
  Artwork: Interactive Display
    ████░░ 🎬 1.100 / Main Projector [×][⎘]
                                      ↑ Clone button
```

**On click:**
1. Opens device modal
2. Pre-fills ALL fields from original device
3. Clears: `host`, `port` (must be unique)
4. Pre-fills: `name` with " (Copy)" suffix
5. Title: "Clone Device: Main Projector"

#### Option B: Clone in Edit Mode Context Menu

```
████░░ 🎬 1.100 / Main Projector [⋮]
                                  ↑ Menu

Menu dropdown:
┌─────────────────┐
│ Edit            │
│ Clone           │
│ Move to...      │
│ Delete          │
└─────────────────┘
```

#### Option C: Clone as Submit Option

When editing existing device:
```
Modal footer:
[Clone]  [Update]  [Cancel]
  ↑ New button
```

**Recommended: Option A + Option B**
- Option A for quick access (icon button visible)
- Option B for organized menu in edit mode

### Modal Behavior

```
┌────────────────────────────────────────────┐
│ Clone Device: Main Projector               │
├────────────────────────────────────────────┤
│ 🎬 PJLink Projector                        │
├────────────────────────────────────────────┤
│ ▼ Basic Information                        │
│ ┌────────────────────────────────────────┐ │
│ │ Host/IP: [______________________]     │ │ ← CLEARED
│ │ Port: [____]                          │ │ ← CLEARED
│ │ Name: [Main Projector (Copy)______]  │ │ ← Auto-suffix
│ └────────────────────────────────────────┘ │
├────────────────────────────────────────────┤
│ ▼ Configuration                            │
│ ┌────────────────────────────────────────┐ │
│ │ Password: [••••••••]                  │ │ ← COPIED
│ └────────────────────────────────────────┘ │
├────────────────────────────────────────────┤
│ ▼ Control Settings                         │
│ ┌────────────────────────────────────────┐ │
│ │ ☑ Enabled                              │ │ ← COPIED
│ │ ☑ Automation Enabled                  │ │ ← COPIED
│ │ ☐ Exclude from bulk ON/OFF           │ │ ← COPIED
│ └────────────────────────────────────────┘ │
├────────────────────────────────────────────┤
│ ℹ️ Cloning from: Main Projector            │
│ Artwork: Interactive Display               │
│                                            │
│        [Submit & Add new]                  │
│        [Submit & Close]                    │
└────────────────────────────────────────────┘
```

### Clone Behavior by Field

| Field | Behavior | Reason |
|-------|----------|--------|
| `device_type` | ✅ Copy | Must be same type |
| `host` | ❌ Clear | Must be unique |
| `port` | ❌ Clear (or copy) | Might be same device, different port |
| `name` | ✅ Copy + " (Copy)" | User can edit |
| `config` (all) | ✅ Copy | Passwords, patterns, etc. |
| `enabled` | ✅ Copy | Usually want same state |
| `automation_enabled` | ✅ Copy | Usually want same behavior |
| `exclude_from_auto_onoff` | ✅ Copy | Usually want same behavior |
| `artwork_id` | ✅ Copy | Clone to same artwork by default |

**Port handling decision:**
- **For outlets (NETIO/ANEL):** Different port on same host is common → Copy host, clear port
- **For projectors:** Different host is common → Clear both
- **Solution:** Clear both by default, let user fill in

### API Endpoint

```typescript
// Option 1: Client-side clone (just pre-fill form)
// No special API needed, just GET device and populate form

// Option 2: Server-side clone
POST /api/admin/devices/:id/clone
Body: {
  host: "192.168.1.101",
  port: 4352,
  name: "Main Projector 2"
}
Response: { id: "new-uuid", ...device }
```

**Recommendation:** Client-side clone (simpler, no special endpoint needed)

---

## Feature 2: Move Device to Different Artwork

### Use Case
- Device was added to wrong artwork
- Reorganizing artworks
- Moving device between exhibitions/artworks

### UI/UX Design

#### Option A: Dropdown Selector in Edit

```
Modal when editing device:
┌────────────────────────────────────────────┐
│ Edit Device: Main Projector                │
├────────────────────────────────────────────┤
│ Current Location:                          │
│ Exhibition: Main Gallery                   │
│ Artwork: Interactive Display               │
│                                            │
│ Move to Artwork:                           │
│ ┌────────────────────────────────────────┐ │
│ │ [Interactive Display ▼]                │ │
│ └────────────────────────────────────────┘ │
│                                            │
│ (Rest of form...)                          │
└────────────────────────────────────────────┘
```

Dropdown shows hierarchical list:
```
Interactive Display (current)
Video Wall
Sound Installation
───────────────────
Other Exhibitions:
  Entrance Hall → Lobby Display
  Entrance Hall → Welcome Screen
```

#### Option B: Dedicated "Move" Action

Context menu or button:
```
[Edit] [Clone] [Move] [Delete]
                 ↑
```

Opens simple dialog:
```
┌────────────────────────────────────────────┐
│ Move Device: Main Projector                │
├────────────────────────────────────────────┤
│ Current: Main Gallery → Interactive Display│
│                                            │
│ Move to:                                   │
│ ┌────────────────────────────────────────┐ │
│ │ Exhibition: [Main Gallery ▼]          │ │
│ │ Artwork:    [Video Wall ▼]            │ │
│ └────────────────────────────────────────┘ │
│                                            │
│             [Move]  [Cancel]               │
└────────────────────────────────────────────┘
```

**Recommended: Option B** - Clearer intent, separate action

### Cascading Dropdowns

```typescript
const MoveDeviceDialog = ({ device }) => {
  const [selectedExhibition, setSelectedExhibition] = useState(device.exhibition_id);
  const [selectedArtwork, setSelectedArtwork] = useState(device.artwork_id);

  // Filter artworks by selected exhibition
  const filteredArtworks = artworks.filter(
    a => a.exhibition_id === selectedExhibition
  );

  return (
    <>
      <Form.Select
        value={selectedExhibition}
        onChange={(e) => {
          setSelectedExhibition(e.target.value);
          setSelectedArtwork(null); // Reset artwork selection
        }}
      >
        {exhibitions.map(ex => (
          <option value={ex.id}>{ex.name}</option>
        ))}
      </Form.Select>

      <Form.Select
        value={selectedArtwork}
        onChange={(e) => setSelectedArtwork(e.target.value)}
        disabled={!selectedExhibition}
      >
        {filteredArtworks.map(art => (
          <option value={art.id}>{art.name}</option>
        ))}
      </Form.Select>
    </>
  );
};
```

### API Endpoint

```typescript
PATCH /api/admin/devices/:id/move
Body: {
  artwork_id: "new-artwork-uuid"
}
Response: { id: "device-uuid", artwork_id: "new-artwork-uuid", ... }
```

Or use existing update endpoint:
```typescript
PUT /api/admin/devices/:id
Body: {
  artwork_id: "new-artwork-uuid"
  // ... other fields unchanged
}
```

### Bulk Move Option

Select multiple devices and move at once:
```
┌────────────────────────────────────────────┐
│ ☑ 🎬 1.100 / Main Projector               │
│ ☑ 🎬 1.101 / Left Projector               │
│ ☐ 🔌 N-01 Port 2 / Power Strip            │
│                                            │
│ Selected: 2 devices                        │
│ [Move Selected] [Delete Selected]          │
└────────────────────────────────────────────┘
```

---

## Feature 3: Shell Command Library

### Use Case
- Many shell commands are reusable (systemd, docker, nginx)
- Pre-built templates save time and reduce errors
- Share common patterns across team

### Library Structure

```typescript
interface ShellCommandTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  automation_enabled: boolean;
  commands: {
    reachable?: ShellCommand;
    status?: ShellCommand;
    on?: ShellCommand;
    off?: ShellCommand;
    [custom: string]: ShellCommand;
  };
  variables?: {
    name: string;
    placeholder: string;
    description: string;
  }[];
}
```

### Built-in Library Templates

#### 1. Systemd Service Control (Automation)

```json
{
  "id": "systemd-service-auto",
  "name": "Systemd Service (with automation)",
  "description": "Control a systemd service with state monitoring",
  "category": "System",
  "automation_enabled": true,
  "variables": [
    { "name": "SERVICE_NAME", "placeholder": "myapp", "description": "Service name" },
    { "name": "HOST", "placeholder": "server.local", "description": "Server hostname/IP" }
  ],
  "commands": {
    "reachable": {
      "name": "Reachable",
      "cmd": "ping -c 1 {{HOST}}"
    },
    "status": {
      "name": "Status",
      "cmd": "systemctl status {{SERVICE_NAME}}",
      "onPattern": "Active: active \\(running\\)",
      "offPattern": "Active: inactive"
    },
    "on": {
      "name": "ON",
      "cmd": "systemctl start {{SERVICE_NAME}}"
    },
    "off": {
      "name": "OFF",
      "cmd": "systemctl stop {{SERVICE_NAME}}"
    }
  }
}
```

#### 2. Docker Container Control (Automation)

```json
{
  "id": "docker-container-auto",
  "name": "Docker Container (with automation)",
  "description": "Start/stop Docker container with state monitoring",
  "category": "Docker",
  "automation_enabled": true,
  "variables": [
    { "name": "CONTAINER_NAME", "placeholder": "nginx", "description": "Container name" }
  ],
  "commands": {
    "status": {
      "name": "Status",
      "cmd": "docker ps -a --filter name={{CONTAINER_NAME}} --format '{{.Status}}'",
      "onPattern": "Up",
      "offPattern": "Exited"
    },
    "on": {
      "name": "ON",
      "cmd": "docker start {{CONTAINER_NAME}}"
    },
    "off": {
      "name": "OFF",
      "cmd": "docker stop {{CONTAINER_NAME}}"
    }
  }
}
```

#### 3. Server Maintenance (Manual Actions)

```json
{
  "id": "server-maintenance",
  "name": "Server Maintenance Actions",
  "description": "Common server maintenance commands",
  "category": "System",
  "automation_enabled": false,
  "variables": [
    { "name": "HOST", "placeholder": "server.local", "description": "Server hostname/IP" }
  ],
  "commands": {
    "restart": {
      "name": "Restart",
      "cmd": "ssh {{HOST}} 'sudo reboot'"
    },
    "update": {
      "name": "Update",
      "cmd": "ssh {{HOST}} 'sudo apt update && sudo apt upgrade -y'"
    },
    "cleanup": {
      "name": "Cleanup",
      "cmd": "ssh {{HOST}} 'sudo apt autoremove -y && sudo apt clean'"
    },
    "diskspace": {
      "name": "Disk Space",
      "cmd": "ssh {{HOST}} 'df -h'"
    }
  }
}
```

#### 4. Media Player Control (Automation)

```json
{
  "id": "vlc-control",
  "name": "VLC Media Player Control",
  "description": "Control VLC via HTTP interface",
  "category": "Media",
  "automation_enabled": true,
  "variables": [
    { "name": "HOST", "placeholder": "192.168.1.100", "description": "VLC host" },
    { "name": "PORT", "placeholder": "8080", "description": "VLC HTTP port" },
    { "name": "PASSWORD", "placeholder": "admin", "description": "VLC password" }
  ],
  "commands": {
    "status": {
      "name": "Status",
      "cmd": "curl -u :{{PASSWORD}} http://{{HOST}}:{{PORT}}/requests/status.xml",
      "onPattern": "<state>playing</state>",
      "offPattern": "<state>stopped</state>"
    },
    "on": {
      "name": "ON (Play)",
      "cmd": "curl -u :{{PASSWORD}} http://{{HOST}}:{{PORT}}/requests/status.xml?command=pl_play"
    },
    "off": {
      "name": "OFF (Stop)",
      "cmd": "curl -u :{{PASSWORD}} http://{{HOST}}:{{PORT}}/requests/status.xml?command=pl_stop"
    }
  }
}
```

### UI Design: Library Selector

```
┌────────────────────────────────────────────┐
│ New Shell Device                           │
├────────────────────────────────────────────┤
│ Load from Template:                        │
│ ┌────────────────────────────────────────┐ │
│ │ [Select template... ▼]                │ │
│ │ ┌────────────────────────────────────┐ ││
│ │ │ System                             │ ││
│ │ │   Systemd Service (automation)     │ ││
│ │ │   Server Maintenance (manual)      │ ││
│ │ │ Docker                             │ ││
│ │ │   Docker Container (automation)    │ ││
│ │ │ Media                              │ ││
│ │ │   VLC Media Player                 │ ││
│ │ │ ────────────────                   │ ││
│ │ │ Custom                             │ ││
│ │ │   My Server Restart (saved)        │ ││
│ │ │   Video Wall Control (saved)       │ ││
│ │ └────────────────────────────────────┘ ││
│ └────────────────────────────────────────┘ │
│                                            │
│ Or start from scratch:                     │
│ [+ Blank Shell Device]                     │
└────────────────────────────────────────────┘
```

After selecting template:

```
┌────────────────────────────────────────────┐
│ New Shell Device                           │
│ Template: Systemd Service (automation)     │
├────────────────────────────────────────────┤
│ Configure Template Variables:              │
│ ┌────────────────────────────────────────┐ │
│ │ Service Name:                          │ │
│ │ [myapp___________________]             │ │
│ │ ℹ️ Name of the systemd service         │ │
│ │                                        │ │
│ │ Host:                                  │ │
│ │ [server.local____________]             │ │
│ │ ℹ️ Server hostname or IP                │ │
│ └────────────────────────────────────────┘ │
│                                            │
│ Preview Generated Commands:                │
│ [▼ Expand to review]                       │
│                                            │
│ [Apply Template]  [Customize Further]      │
└────────────────────────────────────────────┘
```

After applying:
- Commands populated with variables replaced
- User can test and modify
- Can save modified version as new template

### Save Custom Template

```
┌────────────────────────────────────────────┐
│ Save as Template                           │
├────────────────────────────────────────────┤
│ Template Name:                             │
│ [Video Wall Control__________________]     │
│                                            │
│ Description:                               │
│ [Start/stop video wall with 4 projectors_]│
│                                            │
│ Category:                                  │
│ [Custom ▼]                                 │
│                                            │
│ ☑ Share with team (visible to all users) │
│                                            │
│             [Save]  [Cancel]               │
└────────────────────────────────────────────┘
```

### Template Management

```
Settings → Shell Command Templates

┌────────────────────────────────────────────┐
│ Shell Command Templates                    │
├────────────────────────────────────────────┤
│ Built-in Templates (4)                     │
│ ┌────────────────────────────────────────┐ │
│ │ Systemd Service (automation)           │ │
│ │ Docker Container (automation)          │ │
│ │ Server Maintenance (manual)            │ │
│ │ VLC Media Player (automation)          │ │
│ └────────────────────────────────────────┘ │
│                                            │
│ Custom Templates (2)                       │
│ ┌────────────────────────────────────────┐ │
│ │ Video Wall Control        [Edit][Del]  │ │
│ │ Exhibition Server Reboot  [Edit][Del]  │ │
│ └────────────────────────────────────────┘ │
│                                            │
│ [+ New Template]                           │
└────────────────────────────────────────────┘
```

### Storage

**Client-side:** LocalStorage for user-specific templates
```typescript
localStorage.setItem('shellTemplates', JSON.stringify(templates));
```

**Server-side:** Database table for shared templates
```sql
CREATE TABLE shell_templates (
  id UUID PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  category VARCHAR(50),
  automation_enabled BOOLEAN,
  commands JSONB,
  variables JSONB,
  is_builtin BOOLEAN DEFAULT FALSE,
  created_by UUID REFERENCES users(id),
  is_shared BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW()
);
```

### Template Variable Substitution

```typescript
const applyTemplate = (template: ShellCommandTemplate, variables: Record<string, string>) => {
  const substitute = (str: string) => {
    return str.replace(/\{\{(\w+)\}\}/g, (match, key) => {
      return variables[key] || match;
    });
  };

  const commands = {};
  for (const [key, cmd] of Object.entries(template.commands)) {
    commands[key] = {
      ...cmd,
      cmd: substitute(cmd.cmd),
      onPattern: cmd.onPattern ? substitute(cmd.onPattern) : undefined,
      offPattern: cmd.offPattern ? substitute(cmd.offPattern) : undefined,
    };
  }

  return commands;
};
```

---

## Integration with Main Form

### Updated Modal Flow

```
1. User clicks "Add Device"
2. Modal opens with device type selector
3. If Shell selected:
   ┌─────────────────────────────────────┐
   │ Choose starting point:              │
   │ ● Load from template                │
   │ ○ Start from scratch                │
   └─────────────────────────────────────┘

4a. If template selected:
    → Show template selector
    → Collect variable values
    → Apply and populate form
    → User can test/modify

4b. If from scratch:
    → Show blank shell form
    → User builds commands manually

5. Option to save as new template
6. Submit device
```

### Context Menu Integration

```
Device badge context menu:
┌─────────────────┐
│ Edit            │
│ Clone           │ ← NEW
│ Move to...      │ ← NEW
│ ────────────    │
│ Save as Template│ ← NEW (shell only)
│ ────────────    │
│ Delete          │
└─────────────────┘
```

---

## API Endpoints Summary

### Clone
```
# Client-side implementation (no special endpoint)
GET /api/admin/devices/:id  # Fetch original
POST /api/admin/devices     # Create clone
```

### Move
```
PATCH /api/admin/devices/:id/move
Body: { artwork_id: "uuid" }

# Or use existing update:
PUT /api/admin/devices/:id
Body: { artwork_id: "uuid", ... }
```

### Templates
```
GET    /api/admin/shell-templates
POST   /api/admin/shell-templates
PUT    /api/admin/shell-templates/:id
DELETE /api/admin/shell-templates/:id
```

---

## Mobile Considerations

### Clone Button
- Small icon button might be hard to tap on mobile
- Solution: Context menu (long-press on mobile, click on desktop)

### Move Dialog
- Cascading dropdowns work fine on mobile
- Ensure adequate touch targets

### Template Selector
- Categorized dropdown works on mobile
- Consider drawer/bottom sheet for better UX on small screens

---

## Summary of New Features

| Feature | Benefit | Complexity |
|---------|---------|------------|
| **Clone Device** | Save time setting up similar devices | Low |
| **Move Device** | Easy reorganization | Low |
| **Shell Library** | Reusable templates, reduce errors | Medium |
| **Save Template** | Share knowledge across team | Medium |
| **Bulk Move** | Reorganize multiple devices at once | Medium |

---

## Implementation Priority

1. **Clone Device** (High ROI, low complexity)
2. **Move Device** (Frequently needed, simple)
3. **Basic Shell Library** (4-5 built-in templates)
4. **Save Custom Templates** (Power user feature)
5. **Bulk Operations** (Nice to have)

---

**Next:** Add these features to the interactive prototype for testing

