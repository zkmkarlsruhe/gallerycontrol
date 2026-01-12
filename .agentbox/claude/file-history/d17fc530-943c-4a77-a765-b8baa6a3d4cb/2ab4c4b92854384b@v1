# MuTech Control - Form Layout Design Variations

**Date:** 2026-01-12
**Goal:** Universal form layout that works for all device types
**Focus:** Shell commands with automation enabled/disabled modes

---

## Key Design Challenges

### 1. Device Type Complexity Varies
- **Simple:** PJLink (3-4 fields)
- **Medium:** NETIO, ANEL (2-3 fields + port selector)
- **Complex:** Shell commands (4+ command definitions)

### 2. Shell Command Modes

**Automation Enabled (polling):**
- Needs: `Reachable`, `Status` (with ON/OFF patterns), `ON`, `OFF`
- System polls Status command to detect state
- Patterns required for state detection

**Automation Disabled (manual only):**
- No polling, no state detection
- Just manual action buttons
- Any number of custom commands: "Restart", "Update", "Backup"
- No need for Status command or patterns

### 3. Mobile vs Desktop
- Desktop: More horizontal space, can use columns
- Mobile: Vertical scrolling, full-width inputs

---

## Layout Variation 1: Vertical Sections (Recommended)

**Best for:** Mobile-first, progressive disclosure
**Layout:** Stacked sections, collapsible for complex types

```
┌────────────────────────────────────────────┐
│ New Device for "Interactive Display"      │
├────────────────────────────────────────────┤
│ Device Type:                               │
│ [🎬 Projector][🔌 NETIO][🔌 ANEL][💻 Shell]│
├────────────────────────────────────────────┤
│ ▼ Basic Information                        │
│ ┌────────────────────────────────────────┐ │
│ │ Host/IP: [______________________]     │ │
│ │ Port: [____] (optional, default: 4352)│ │
│ │ Name: [______________________]        │ │
│ └────────────────────────────────────────┘ │
├────────────────────────────────────────────┤
│ ▼ Configuration                            │
│ ┌────────────────────────────────────────┐ │
│ │ (Type-specific fields appear here)    │ │
│ │                                        │ │
│ │ PJLink: Password field                │ │
│ │ NETIO/ANEL: Port selector buttons     │ │
│ │ Shell: Command definitions            │ │
│ └────────────────────────────────────────┘ │
├────────────────────────────────────────────┤
│ ▼ Control Settings                         │
│ ┌────────────────────────────────────────┐ │
│ │ ☑ Enabled                              │ │
│ │ ☑ Automation Enabled                  │ │
│ │ ☐ Exclude from bulk ON/OFF           │ │
│ └────────────────────────────────────────┘ │
├────────────────────────────────────────────┤
│        [Submit & Add new]                  │
│        [Submit & Close]                    │
└────────────────────────────────────────────┘
```

**Pros:**
- Clean, scannable
- Works great on mobile
- Collapsible sections save space
- Logical grouping

**Cons:**
- More vertical scrolling
- Sections might be overlooked if collapsed

---

## Layout Variation 2: Two-Column Split

**Best for:** Desktop use, side-by-side comparison
**Layout:** Left = common, Right = type-specific

```
┌──────────────────────────────────────────────────────────┐
│ New Device for "Interactive Display"                    │
├──────────────────────────────────────────────────────────┤
│ [🎬 Projector][🔌 NETIO][🔌 ANEL][💻 Shell]              │
├──────────────────────────────────────────────────────────┤
│ Common Settings    │ Type-Specific Configuration        │
│ ┌────────────────┐ │ ┌────────────────────────────────┐│
│ │ Host/IP:       │ │ │ PJLink:                        ││
│ │ [___________]  │ │ │ Password: [_________________] ││
│ │                │ │ │                                ││
│ │ Port:          │ │ │ NETIO/ANEL:                    ││
│ │ [___]          │ │ │ [Port 1][Port 2][Port 3]      ││
│ │                │ │ │                                ││
│ │ Name:          │ │ │ Shell:                         ││
│ │ [___________]  │ │ │ (Commands panel)               ││
│ │                │ │ │                                ││
│ │ ☑ Enabled      │ │ │                                ││
│ │ ☑ Automation   │ │ │                                ││
│ │ ☐ Exclude bulk │ │ │                                ││
│ └────────────────┘ │ └────────────────────────────────┘│
├────────────────────┴───────────────────────────────────┤
│              [Submit & Add new]  [Submit & Close]       │
└──────────────────────────────────────────────────────────┘
```

**Responsive:**
```css
@media (max-width: 768px) {
  /* Stack columns on mobile */
  .two-column-form {
    flex-direction: column;
  }
}
```

**Pros:**
- Efficient use of space on desktop
- All settings visible at once
- Clear separation of concerns

**Cons:**
- Cramped on mobile/tablet
- Right column varies in height

---

## Layout Variation 3: Tabbed Interface

**Best for:** Complex forms, organized navigation
**Layout:** Tabs separate basic info from advanced config

```
┌────────────────────────────────────────────┐
│ New Device for "Interactive Display"      │
├────────────────────────────────────────────┤
│ [🎬 Projector][🔌 NETIO][🔌 ANEL][💻 Shell]│
├────────────────────────────────────────────┤
│ [Basic Info] [Configuration] [Settings]   │ ← Tabs
├────────────────────────────────────────────┤
│ Tab 1: Basic Info                          │
│ ┌────────────────────────────────────────┐ │
│ │ Host/IP: [______________________]     │ │
│ │ Port: [____]                          │ │
│ │ Name: [______________________]        │ │
│ └────────────────────────────────────────┘ │
│                                            │
│ Tab 2: Configuration (type-specific)       │
│ ┌────────────────────────────────────────┐ │
│ │ (Appears when tab selected)            │ │
│ └────────────────────────────────────────┘ │
│                                            │
│ Tab 3: Settings                            │
│ ┌────────────────────────────────────────┐ │
│ │ ☑ Enabled                              │ │
│ │ ☑ Automation Enabled                  │ │
│ │ ☐ Exclude from bulk ON/OFF           │ │
│ └────────────────────────────────────────┘ │
├────────────────────────────────────────────┤
│        [Submit & Add new]                  │
│        [Submit & Close]                    │
└────────────────────────────────────────────┘
```

**Pros:**
- Very organized
- Reduces visual clutter
- Easy to add more settings later

**Cons:**
- Adds clicks (tab switching)
- Can't see all settings at once
- Users might miss tabs

---

## Layout Variation 4: Progressive Disclosure (Wizard-like)

**Best for:** Guided setup, reducing complexity
**Layout:** Show only relevant fields based on selections

```
┌────────────────────────────────────────────┐
│ Add Device - Step 1 of 3                   │
├────────────────────────────────────────────┤
│ Select Device Type:                        │
│ [🎬 Projector][🔌 NETIO][🔌 ANEL][💻 Shell]│
│                                  [Next →]  │
└────────────────────────────────────────────┘

              ↓ After selection

┌────────────────────────────────────────────┐
│ Add Device - Step 2 of 3                   │
├────────────────────────────────────────────┤
│ PJLink Projector Configuration:            │
│ ┌────────────────────────────────────────┐ │
│ │ Host/IP: [______________________]     │ │
│ │ Port: [____]                          │ │
│ │ Password: [______________________]    │ │
│ │ Name: [______________________]        │ │
│ └────────────────────────────────────────┘ │
│                      [← Back]  [Next →]   │
└────────────────────────────────────────────┘

              ↓ After configuration

┌────────────────────────────────────────────┐
│ Add Device - Step 3 of 3                   │
├────────────────────────────────────────────┤
│ Control Settings:                          │
│ ┌────────────────────────────────────────┐ │
│ │ ☑ Enabled                              │ │
│ │ ☑ Automation Enabled                  │ │
│ │ ☐ Exclude from bulk ON/OFF           │ │
│ └────────────────────────────────────────┘ │
│      [← Back]  [Submit & Add]  [Submit]   │
└────────────────────────────────────────────┘
```

**Pros:**
- Very beginner-friendly
- Reduces cognitive load
- Clear progression

**Cons:**
- More clicks to complete
- Slower for experienced users
- Back/forth navigation annoying

---

## Shell Commands: Automation Modes Design

### Mode 1: Automation Enabled (Polling)

**Requirements:**
- 4 predefined commands: Reachable, Status, ON, OFF
- Status command MUST have ON/OFF patterns
- Optional custom commands

```
┌────────────────────────────────────────────────┐
│ Shell Commands Configuration                   │
│                                                 │
│ ☑ Automation Enabled                           │
│   → System will poll Status command for state  │
├────────────────────────────────────────────────┤
│ Required Commands:                              │
│                                                 │
│ ┌─ Reachable (Optional) ────────────────────┐  │
│ │ Command: [ping -c 1 $HOST___________] [Test]│
│ └────────────────────────────────────────────┘  │
│                                                 │
│ ┌─ Status (Required for automation) ────────┐  │
│ │ Command: [systemctl status app_______] [Test]│
│ │                                            │  │
│ │ State Detection:                           │  │
│ │ ON Pattern:  [active.*running_________]   │  │
│ │ OFF Pattern: [inactive________________]   │  │
│ └────────────────────────────────────────────┘  │
│                                                 │
│ ┌─ ON Command ────────────────────────────────┐│
│ │ Command: [systemctl start app________] [Test]│
│ └────────────────────────────────────────────┘  │
│                                                 │
│ ┌─ OFF Command ───────────────────────────────┐│
│ │ Command: [systemctl stop app_________] [Test]│
│ └────────────────────────────────────────────┘  │
│                                                 │
│ ▼ Custom Commands (Optional)                   │
│ ┌────────────────────────────────────────────┐  │
│ │ [+ Add Custom Command]                     │  │
│ └────────────────────────────────────────────┘  │
└────────────────────────────────────────────────┘
```

### Mode 2: Automation Disabled (Manual Only)

**Requirements:**
- No polling, no state detection
- Just action buttons - any number of commands
- No need for Status command or patterns

```
┌────────────────────────────────────────────────┐
│ Shell Commands Configuration                   │
│                                                 │
│ ☐ Automation Disabled                          │
│   → Manual control only, no state polling      │
├────────────────────────────────────────────────┤
│ Action Commands:                                │
│                                                 │
│ ┌─ Command 1 ─────────────────────────────────┐│
│ │ Label: [Restart_________________]      [×] │  │
│ │ Command: [systemctl restart app____] [Test]│  │
│ └────────────────────────────────────────────┘  │
│                                                 │
│ ┌─ Command 2 ─────────────────────────────────┐│
│ │ Label: [Update__________________]      [×] │  │
│ │ Command: [apt update && apt upgrade_] [Test]│  │
│ └────────────────────────────────────────────┘  │
│                                                 │
│ ┌─ Command 3 ─────────────────────────────────┐│
│ │ Label: [Backup__________________]      [×] │  │
│ │ Command: [./backup.sh_______________] [Test]│  │
│ └────────────────────────────────────────────┘  │
│                                                 │
│ [+ Add Another Command]                        │
│                                                 │
│ Note: These buttons will appear in the device  │
│ card for manual triggering.                    │
└────────────────────────────────────────────────┘
```

**Key Differences:**

| Feature | Automation ON | Automation OFF |
|---------|--------------|----------------|
| **Polling** | Yes | No |
| **Status Command** | Required | Not needed |
| **ON/OFF Patterns** | Required | Not needed |
| **Command Structure** | Fixed (4 types) | Flexible (any number) |
| **Button Labels** | ON/OFF | Custom labels |
| **Use Case** | Monitor + Control | Just trigger actions |

---

## Unified Form Component Approach

**Strategy:** One form component that adapts based on device type and automation mode

```typescript
interface FormConfig {
  deviceType: 'pjlink' | 'netio' | 'anel' | 'shell';
  automationEnabled: boolean;
  sections: {
    basic: FieldConfig[];      // Host, Port, Name
    specific: FieldConfig[];   // Type-specific config
    settings: FieldConfig[];   // Flags
  };
}

// Field definitions change based on type + automation
const getFormConfig = (type: DeviceType, automation: boolean): FormConfig => {
  switch(type) {
    case 'shell':
      return automation
        ? shellAutomationForm    // Fixed commands + patterns
        : shellManualForm;       // Flexible custom commands
    // ... other types
  }
};
```

---

## Recommended Design: Hybrid Approach

**Combination of Variation 1 + 4:**
- **Simple types (PJLink, NETIO, ANEL)**: Vertical sections (Variation 1)
- **Shell commands**: Progressive disclosure within modal (Variation 4)

**Workflow:**

### For PJLink/NETIO/ANEL:
```
1. Click "Add Device"
2. Select type (toggle buttons)
3. All fields appear in vertical sections
4. Fill and submit
```

### For Shell:
```
1. Click "Add Device"
2. Select Shell type
3. See: "Automation Enabled?" toggle
   → If YES: Show fixed command structure
   → If NO: Show flexible command builder
4. Fill commands
5. Test commands (optional but recommended)
6. Submit
```

---

## Visual Design Elements

### Collapsible Sections
```jsx
<Accordion defaultActiveKey="0">
  <Accordion.Item eventKey="0">
    <Accordion.Header>Basic Information</Accordion.Header>
    <Accordion.Body>
      {/* Host, Port, Name fields */}
    </Accordion.Body>
  </Accordion.Item>

  <Accordion.Item eventKey="1">
    <Accordion.Header>Configuration</Accordion.Header>
    <Accordion.Body>
      {/* Type-specific fields */}
    </Accordion.Body>
  </Accordion.Item>
</Accordion>
```

### Command Testing UI
```
┌────────────────────────────────────────┐
│ Command: [systemctl status app___] [Test] │ ← Input + button
└────────────────────────────────────────┘
         ↓ Click Test
┌────────────────────────────────────────┐
│ Testing... ⏳                          │
└────────────────────────────────────────┘
         ↓ After execution
┌────────────────────────────────────────┐
│ ✓ Exit code: 0                         │
│ Output:                                 │
│ ┌────────────────────────────────────┐ │
│ │ app.service - Application Service  │ │
│ │    Loaded: loaded                  │ │
│ │    Active: active (running)        │ │
│ └────────────────────────────────────┘ │
│                           [Collapse ▲] │
└────────────────────────────────────────┘
```

### Toggle Button Visual States
```css
/* Unselected */
.device-type-button {
  background: #f8f9fa;
  border: 2px solid #dee2e6;
}

/* Selected */
.device-type-button.active {
  background: #0d6efd;
  color: white;
  border: 2px solid #0d6efd;
}

/* Hover */
.device-type-button:hover {
  background: #e9ecef;
  transform: translateY(-2px);
}
```

---

## Mobile Optimizations

### Full-Screen Modal on Mobile
```css
@media (max-width: 575px) {
  .device-modal {
    width: 100vw;
    height: 100vh;
    margin: 0;
    border-radius: 0;
  }

  .modal-header {
    position: sticky;
    top: 0;
    background: white;
    z-index: 10;
  }

  .modal-footer {
    position: sticky;
    bottom: 0;
    background: white;
    box-shadow: 0 -2px 8px rgba(0,0,0,0.1);
  }
}
```

### Stacked Device Type Selector
```
Mobile:
┌──────────────┐
│ 🎬 Projector │
│ 🔌 NETIO     │
│ 🔌 ANEL      │
│ 💻 Shell     │
└──────────────┘

Desktop:
[🎬 Projector][🔌 NETIO][🔌 ANEL][💻 Shell]
```

---

## Accessibility Features

1. **Keyboard Navigation**
   - Tab through all fields
   - Enter to submit
   - Escape to close modal

2. **Screen Readers**
   - Proper ARIA labels on all inputs
   - Form validation errors announced
   - Command test results announced

3. **Focus Management**
   - Auto-focus first field on modal open
   - Focus trap within modal
   - Return focus to trigger button on close

4. **Error Handling**
```jsx
<Form.Control
  isInvalid={!!errors.host}
  aria-describedby="host-error"
/>
<Form.Control.Feedback type="invalid" id="host-error">
  {errors.host}
</Form.Control.Feedback>
```

---

## Form Validation Strategy

### Client-Side (Immediate Feedback)
```typescript
const validateField = (field: string, value: any) => {
  switch(field) {
    case 'host':
      if (deviceType !== 'shell' && value.length < 3) {
        return 'Host must be at least 3 characters';
      }
      break;
    case 'port':
      if (value && (value < 1 || value > 65535)) {
        return 'Port must be between 1-65535';
      }
      break;
    // ... more validations
  }
  return null;
};
```

### Server-Side (Final Validation)
```python
# Backend validates:
# - Host format (IP/DNS)
# - Port availability
# - Device connectivity (optional)
# - Command syntax (shell)
# - Unique constraint (host + port + type)
```

---

## Comparison Matrix

| Feature | Variation 1<br/>Vertical | Variation 2<br/>Two-Column | Variation 3<br/>Tabs | Variation 4<br/>Wizard | **Recommended<br/>Hybrid** |
|---------|----------|------------|------|--------|----------------|
| **Mobile-friendly** | ✅ Excellent | ⚠️ Cramped | ✅ Good | ✅ Good | ✅ Excellent |
| **Desktop efficiency** | ⚠️ Lots of scrolling | ✅ Compact | ✅ Compact | ⚠️ Many clicks | ✅ Balanced |
| **Complexity handling** | ✅ Collapsible | ⚠️ Fixed height | ✅ Hidden tabs | ✅ Step-by-step | ✅ Adaptive |
| **Quick entry** | ✅ All visible | ✅ All visible | ⚠️ Need tab switch | ❌ Must navigate | ✅ Context-aware |
| **Beginner-friendly** | ✅ Clear structure | ⚠️ Overwhelming | ✅ Organized | ✅ Guided | ✅ Progressive |
| **Shell automation modes** | ✅ Toggle + show/hide | ✅ Side-by-side | ⚠️ Tab switch | ✅ Different steps | ✅ **Adaptive UI** |

---

## Final Recommendation

**Use Vertical Sections (Variation 1) as base, with:**

1. **Device type selector** at top (toggle buttons)
2. **Three collapsible sections:**
   - Basic Information (always expanded)
   - Configuration (expanded, changes per type)
   - Control Settings (collapsed by default)
3. **Shell commands special handling:**
   - Automation toggle changes command structure
   - "Automation ON" → Fixed commands + patterns
   - "Automation OFF" → Flexible command list
4. **Submit buttons** always visible (sticky on mobile)

**Why this works:**
- ✅ Mobile-first but works great on desktop
- ✅ All device types fit same structure
- ✅ Shell complexity handled with show/hide
- ✅ No extra clicks for simple types
- ✅ Progressive disclosure for complex types
- ✅ Consistent UX across all forms

---

**Next Step:** Create HTML prototype with all variations for testing

