# MuTech Control - CRUD Forms Design

**Date:** 2026-01-12
**Phase:** Design - Forms & CRUD Operations
**Status:** Design documentation

---

## Current Pattern Analysis

### Pattern 1: Inline Forms (Exhibitions & Artworks)

**Location:** Table header row
**Use case:** Quick batch creation
**UX:** Simple, fast, minimal clicks

```
┌─────────────────────────────────────────────────────┐
│ Add Exhibition: [________________] [Submit]         │ ← Inline form
├─────────────────────────────────────────────────────┤
│ Main Gallery                            [Edit][Del] │
│   └─ Add Artwork: [___________] [Submit]            │ ← Inline form
│       └─ Interactive Display                        │
│           └─ Devices...                             │
└─────────────────────────────────────────────────────┘
```

**Features:**
- Comma-separated batch input: `"Gallery 1, Gallery 2, Gallery 3"`
- Creates multiple items in one submit
- Appears only in edit mode
- Resets input after submit

**Current Implementation (React):**
```jsx
<FormAddObject socket={socket} type="exhibit" />
<FormAddObject socket={socket} type="work" parentId={exhibit.id} />
```

**Input processing:**
```javascript
const objectNames = input.split(',').map(s => s.trim());
objectNames.forEach(name => {
  if (name.length > 0) {
    socket.emit('command', { cmd: 'add', data: { name, type, parentId } });
  }
});
```

---

### Pattern 2: Modal Forms (Devices)

**Location:** Modal dialog
**Use case:** Complex configuration with multiple fields
**UX:** Two-step process - type selection, then form

#### Step 1: Device Type Selection

```
┌─────────────────────────────────────────┐
│ New Unit for "Interactive Display"     │
├─────────────────────────────────────────┤
│ [🎬 Projector] [🔌 NetIO] [🔌 Anel] [💻 Shell] │ ← Toggle buttons
│                                         │
│ (Form appears based on selection)      │
│                                         │
│             [Submit & Add new]          │
│             [Submit & Close]            │
└─────────────────────────────────────────┘
```

**Device types:**
- 🎬 Projector (PJLink)
- 🔌 NetIO (NETIO outlet)
- 🔌 Anel (ANEL outlet)
- 💻 Shell (Shell commands)

#### Step 2: Type-Specific Forms

Forms change based on device type selection (toggle buttons).

---

## New System - Form Fields

### Exhibition Form (Inline)

**Fields:**
```typescript
interface ExhibitionFormData {
  name: string;           // Required, comma-separated for batch
}
```

**API:**
```
POST /api/admin/exhibitions
{ "name": "Main Gallery" }
```

**Batch creation:**
```javascript
// Input: "Gallery 1, Gallery 2, Gallery 3"
names.forEach(name => {
  api.post('/api/admin/exhibitions', { name });
});
```

---

### Artwork Form (Inline)

**Fields:**
```typescript
interface ArtworkFormData {
  name: string;           // Required, comma-separated for batch
  exhibition_id: string;  // Parent exhibition UUID
}
```

**API:**
```
POST /api/admin/artworks
{ "name": "Interactive Display", "exhibition_id": "uuid..." }
```

---

### Device Forms (Modal)

All device forms share common fields, plus type-specific configuration.

#### Common Fields (All Device Types)

```typescript
interface BaseDeviceFormData {
  // Required
  device_type: 'pjlink' | 'netio' | 'anel' | 'shell';
  host: string;                           // IP or DNS
  artwork_id: string;                     // Parent artwork UUID

  // Optional
  port?: number;                          // Device-specific default if empty

  // Control flags
  enabled: boolean;                       // Default: true
  automation_enabled: boolean;            // Default: true
  exclude_from_auto_onoff: boolean;       // Default: false (true for shell)

  // Type-specific config (goes into JSONB config field)
  config: Record<string, any>;
}
```

---

#### Form 1: PJLink Projector

**Fields:**
```
┌─────────────────────────────────────────┐
│ Host/IP: [________________] Port: [___] │
│ Password: [__________________________] │
│ Name: [________________________________] │
│                                         │
│ ☑ Automation Enabled                   │
│ ☐ Exclude from bulk ON/OFF            │
│                                         │
│ [Submit & Add new] [Submit & Close]    │
└─────────────────────────────────────────┘
```

**TypeScript Interface:**
```typescript
interface PJLinkFormData extends BaseDeviceFormData {
  device_type: 'pjlink';
  host: string;                    // IP or DNS
  port?: number;                   // Default: 4352
  config: {
    password?: string;             // Optional
    name?: string;                 // Display name
  };
}
```

**Field Details:**
- **Host/IP**: Accepts IP (192.168.1.100) or DNS (projector-main.zkm.de)
- **Port**: Default 4352, leave blank for default
- **Password**: Optional, defaults by manufacturer (NEC: none, Panasonic: "panasonic")
- **Name**: Display name (shows in badge)
- **Automation Enabled**: Include in polling loop
- **Exclude from bulk ON/OFF**: Never checked for projectors

**Input sanitization:**
```typescript
host: host.toLowerCase().trim().replace(/^https?:\/\//, '')
```

**Validation:**
```typescript
- host.length >= 3
- port: empty OR 1-65535
```

---

#### Form 2: NETIO Outlet

**Fields:**
```
┌─────────────────────────────────────────┐
│ Host/DNS: [__________________________] │
│ Name: [________________________________] │
│                                         │
│ Port Selection:                         │
│ [ Port 1 ] [ Port 2 ] [ Port 3 ]       │ ← Toggle buttons
│                                         │
│ ☑ Automation Enabled                   │
│ ☐ Exclude from bulk ON/OFF            │
│                                         │
│ [Submit & Add new] [Submit & Close]    │
└─────────────────────────────────────────┘
```

**TypeScript Interface:**
```typescript
interface NETIOFormData extends BaseDeviceFormData {
  device_type: 'netio';
  host: string;
  port: number;                    // 0, 1, or 2 (device port index)
  config: {
    name?: string;                 // Display name
  };
}
```

**Field Details:**
- **Host/DNS**: NETIO device hostname or IP
- **Name**: Optional display name
- **Port Selection**: Visual toggle buttons (0-2), NOT dropdown
  - Display: "Port 1", "Port 2", "Port 3"
  - Value: 0, 1, 2 (zero-indexed)
- **Automation Enabled**: Default true
- **Exclude from bulk ON/OFF**: Default false

**Port Selection UI:**
```jsx
<ButtonGroup>
  {[0, 1, 2].map(portIndex => (
    <ToggleButton
      key={portIndex}
      value={portIndex}
      checked={selectedPort === portIndex}
      onChange={() => setSelectedPort(portIndex)}
    >
      Port {portIndex + 1}
    </ToggleButton>
  ))}
</ButtonGroup>
```

---

#### Form 3: ANEL Outlet

**Fields:**
```
┌─────────────────────────────────────────┐
│ Host/IP: [____________________________] │
│ Name: [________________________________] │
│                                         │
│ Port Selection:                         │
│ [Port 1][Port 2][Port 3][Port 4]...    │ ← Toggle buttons (8 ports)
│                                         │
│ ☑ Automation Enabled                   │
│ ☐ Exclude from bulk ON/OFF            │
│                                         │
│ [Submit & Add new] [Submit & Close]    │
└─────────────────────────────────────────┘
```

**TypeScript Interface:**
```typescript
interface ANELFormData extends BaseDeviceFormData {
  device_type: 'anel';
  host: string;                    // IP address (ANEL uses UDP)
  port: number;                    // 0-7 (ANEL has 8 ports)
  config: {
    name?: string;                 // Display name
  };
}
```

**Field Details:**
- **Host/IP**: IP address only (ANEL uses UDP broadcast)
- **Name**: Optional display name
- **Port Selection**: 8 toggle buttons (0-7)
  - Display: "Port 1" through "Port 8"
  - Value: 0-7 (zero-indexed)
- **Automation Enabled**: Default true
- **Exclude from bulk ON/OFF**: Default false

---

#### Form 4: Shell Commands

**Fields:**
```
┌──────────────────────────────────────────────────────┐
│ Name: [_________________________________________]    │
│                                                      │
│ Commands:                                            │
│ ┌──────────────────────────────────────────────────┐│
│ │ Reachable:                                       ││
│ │ Command: [ping -c 1 server___________________]  ││
│ │                                        [Test]    ││
│ ├──────────────────────────────────────────────────┤│
│ │ Status:                                          ││
│ │ Command: [systemctl status app_______________]  ││
│ │ ON Pattern: [active \(running\)______________]  ││
│ │ OFF Pattern: [inactive_______________________]  ││
│ │                                        [Test]    ││
│ ├──────────────────────────────────────────────────┤│
│ │ ON:                                              ││
│ │ Command: [systemctl start app________________]  ││
│ │                                        [Test]    ││
│ ├──────────────────────────────────────────────────┤│
│ │ OFF:                                             ││
│ │ Command: [systemctl stop app_________________]  ││
│ │                                        [Test]    ││
│ ├──────────────────────────────────────────────────┤│
│ │ [+ Add Custom Command]                           ││
│ └──────────────────────────────────────────────────┘│
│                                                      │
│ ☐ Automation Enabled                                │
│ ☑ Exclude from bulk ON/OFF (recommended)           │
│                                                      │
│ [Submit & Add new] [Submit & Close]                 │
└──────────────────────────────────────────────────────┘
```

**TypeScript Interface:**
```typescript
interface ShellCommand {
  name: string;                    // "Reachable", "Status", "ON", "OFF", etc.
  cmd: string;                     // Shell command to execute
  onPattern?: string;              // Regex for ON state (Status command only)
  offPattern?: string;             // Regex for OFF state (Status command only)
}

interface ShellFormData extends BaseDeviceFormData {
  device_type: 'shell';
  host: 'shell-command';           // Fixed value (no actual host)
  config: {
    name: string;                  // Required display name
    commands: {
      reachable?: ShellCommand;    // Optional
      status?: ShellCommand;       // Optional
      on?: ShellCommand;           // Optional
      off?: ShellCommand;          // Optional
      [key: string]: ShellCommand; // Custom commands
    };
  };
  exclude_from_auto_onoff: true;   // Usually true for shell commands
}
```

**Field Details:**
- **Name**: Required (e.g., "Reboot Media Server")
- **Commands**: 4 default + custom
  - **Reachable**: Test if device is reachable
  - **Status**: Get current state (needs ON/OFF patterns)
  - **ON**: Turn on command
  - **OFF**: Turn off command
  - **Custom**: User can add more (e.g., "Restart", "Update")
- **Pattern Matching** (Status command):
  - ON Pattern: Regex to detect ON state (e.g., `active \(running\)`)
  - OFF Pattern: Regex to detect OFF state (e.g., `inactive`)
- **Test Button**: Execute command and show output in debug panel
- **Automation Enabled**: Usually false for shell commands
- **Exclude from bulk ON/OFF**: Usually true (don't trigger on bulk operations)

**Test Command Feature:**
```tsx
const testCommand = async (cmd: string) => {
  setTesting(true);
  const response = await api.post('/api/admin/shell/test', { command: cmd });
  setDebugOutput(response.data.output);
  setShowDebugPanel(true);
  setTesting(false);
};
```

**Debug Panel (Off-canvas):**
```
┌─────────────────────────────────────┐
│ Command Test Output                 │
├─────────────────────────────────────┤
│ $ ping -c 1 server                  │
│                                     │
│ PING server (192.168.1.50):        │
│ 64 bytes from 192.168.1.50: icmp_seq=0 ttl=64 time=1.234 ms
│                                     │
│ Exit code: 0                        │
│                                     │
│            [Close]                  │
└─────────────────────────────────────┘
```

---

## Form Behavior & UX

### Submit Buttons

**Two options:**

1. **Submit & Add new**
   - Creates device
   - Keeps modal open
   - Resets form to initial state
   - User can immediately add another device
   - Good for batch setup

2. **Submit & Close**
   - Creates device
   - Closes modal
   - Returns to table view
   - Good for single additions

**Implementation:**
```typescript
const handleSubmit = async (e: FormEvent, closeModal: boolean) => {
  e.preventDefault();

  const device = buildDeviceData(formState);
  await api.post('/api/admin/devices', device);

  if (closeModal) {
    handleModalClose();
  } else {
    resetForm();
    toast.success('Device added! Add another?');
  }
};
```

### Input Sanitization

**Host field:**
```typescript
const sanitizeHost = (input: string) => {
  return input
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, '')  // Remove protocol
    .replace(/\/.*$/, '');         // Remove path
};
```

**All text fields:**
```typescript
onChange={(e) => setField(e.target.value.trim())}
```

### Validation

**Client-side:**
```typescript
interface ValidationErrors {
  host?: string;
  port?: string;
  name?: string;
  commands?: string;
}

const validate = (formData: DeviceFormData): ValidationErrors => {
  const errors: ValidationErrors = {};

  // Host required (except shell)
  if (formData.device_type !== 'shell' && formData.host.length < 3) {
    errors.host = 'Host must be at least 3 characters';
  }

  // Port range
  if (formData.port && (formData.port < 1 || formData.port > 65535)) {
    errors.port = 'Port must be between 1-65535';
  }

  // Shell: name required
  if (formData.device_type === 'shell' && !formData.config.name) {
    errors.name = 'Name is required for shell commands';
  }

  return errors;
};
```

**Server-side validation happens in API** - client should show errors.

---

## Edit Mode

### Toggle Edit Mode

**Location:** Header or navigation
**UI:** Simple toggle switch

```
┌─────────────────────────────────────┐
│ MuTech Control    ☐ Edit Mode      │
└─────────────────────────────────────┘
```

**When enabled:**
- Inline forms appear (exhibitions, artworks)
- Edit/Delete buttons visible on all items
- "Add Unit" buttons visible
- Delete confirmations required

**When disabled:**
- Forms hidden
- Only ON/OFF control buttons visible
- Clean viewing interface

### Edit Actions

**Exhibition/Artwork:**
- **Edit**: Inline edit (click name → editable input)
- **Delete**: Confirmation dialog with cascade warning

**Device:**
- **Edit**: Opens same modal with pre-filled form
- **Delete**: X button with confirmation

**Delete Confirmation:**
```
┌─────────────────────────────────────────┐
│ Delete "Main Gallery"?                  │
├─────────────────────────────────────────┤
│ This will also delete:                  │
│ • 3 artworks                            │
│ • 12 devices                            │
│                                         │
│ This action cannot be undone.           │
│                                         │
│        [Cancel]  [Delete]               │
└─────────────────────────────────────────┘
```

---

## Component Structure (React + TypeScript)

```
components/
├── forms/
│   ├── ExhibitionForm.tsx           # Inline form
│   ├── ArtworkForm.tsx              # Inline form
│   ├── DeviceModal.tsx              # Modal wrapper
│   ├── DeviceTypeSelector.tsx      # Toggle buttons
│   └── devices/
│       ├── PJLinkForm.tsx
│       ├── NETIOForm.tsx
│       ├── ANELForm.tsx
│       └── ShellForm.tsx
├── common/
│   ├── FormInput.tsx                # Reusable input with label
│   ├── FormToggleButton.tsx         # Port selector
│   ├── SubmitButtons.tsx            # Submit & Add new / Close
│   └── ValidationError.tsx          # Error display
└── debug/
    └── ShellDebugPanel.tsx          # Command test output
```

---

## API Endpoints

### CRUD Operations

**Exhibitions:**
```
GET    /api/admin/exhibitions
POST   /api/admin/exhibitions
PUT    /api/admin/exhibitions/:id
DELETE /api/admin/exhibitions/:id
```

**Artworks:**
```
GET    /api/admin/artworks
POST   /api/admin/artworks
PUT    /api/admin/artworks/:id
DELETE /api/admin/artworks/:id
```

**Devices:**
```
GET    /api/admin/devices
POST   /api/admin/devices
PUT    /api/admin/devices/:id
DELETE /api/admin/devices/:id
```

**Shell Command Testing:**
```
POST   /api/admin/shell/test
Body: { "command": "ping -c 1 server" }
Response: { "output": "...", "exitCode": 0 }
```

---

## Mobile Considerations

### Modal Forms on Mobile

**Challenge:** Large forms in modals on small screens

**Solutions:**
1. **Full-screen modal on mobile**
```css
@media (max-width: 575px) {
  .device-modal {
    width: 100vw;
    height: 100vh;
    margin: 0;
  }
}
```

2. **Collapsible sections** for shell commands
3. **Sticky submit buttons** at bottom
4. **Larger touch targets** for toggle buttons

### Inline Forms on Mobile

**No issues** - single input field works well on all screen sizes.

---

## Accessibility

- **Labels**: All inputs have associated labels
- **ARIA**: Proper ARIA labels for toggle buttons
- **Keyboard**: Tab navigation, Enter to submit
- **Focus**: Auto-focus first field when modal opens
- **Validation**: Error messages announced to screen readers

---

## State Management

**Form state:**
```typescript
const [formData, setFormData] = useState<DeviceFormData>(initialState);
const [errors, setErrors] = useState<ValidationErrors>({});
const [isSubmitting, setIsSubmitting] = useState(false);
```

**Modal state:**
```typescript
const [showModal, setShowModal] = useState(false);
const [editingDevice, setEditingDevice] = useState<Device | null>(null);
```

**Device type selection:**
```typescript
const [selectedType, setSelectedType] = useState<DeviceType>('pjlink');
```

---

## Open Questions

1. **DNS Resolution**: Should frontend validate DNS or let backend handle?
2. **Port Defaults**: Show default in placeholder or pre-fill?
3. **Shell Commands**: Limit number of custom commands?
4. **Edit Inline**: Allow inline editing for exhibitions/artworks or always modal?
5. **Bulk Delete**: Support selecting multiple items for deletion?

---

## Next Steps

1. ✅ Design documentation complete
2. ⏳ Create form prototypes (HTML/mockups)
3. ⏳ Implement React components
4. ⏳ Add form validation
5. ⏳ Wire up API calls
6. ⏳ Test on mobile devices
7. ⏳ User acceptance testing

---

**Last Updated:** 2026-01-12
**Status:** Design phase - ready for prototyping
