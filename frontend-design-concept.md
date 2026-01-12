# MuTech Control Frontend - Design Concept

## Device Badge Component Design

### Visual Elements

```
┌─────────────────────────────────────┐
│ ████████░░░░░░░░ (progress bar)     │  ← Time until next check
├─────────────────────────────────────┤
│ 🎬 192.168.1.100 / Main Projector   │  ← Badge content
│    [state icon] [device info]       │
└─────────────────────────────────────┘
     ↑ Badge background color changes based on state
```

### State Colors

| State | Color | Bootstrap Variant | Meaning |
|-------|-------|-------------------|---------|
| `-1` | Red | `danger` | Error |
| `0` | Dark Gray | `dark` | Off |
| `1` | Green | `success` | On |
| `2` | Yellow | `warning` | Cooling (projector) |
| `3` | Orange | `warning` | Warming (projector) |

### Progress Indicator Options

#### Option 1: Top Border with Animation
```jsx
<div style={{
  borderTop: `3px solid rgba(255,255,255,0.5)`,
  borderImage: `linear-gradient(to right,
    rgba(255,255,255,0.8) ${progress}%,
    rgba(255,255,255,0.2) ${progress}%) 1`,
  transition: 'border-image 1s linear'
}}>
  <Badge bg={stateColor}>...</Badge>
</div>
```

#### Option 2: Thin Progress Bar Above Badge
```jsx
<div className="device-wrapper">
  <div className="progress-bar-thin" style={{ width: '100%', height: '2px' }}>
    <div
      style={{
        width: `${progress}%`,
        height: '100%',
        backgroundColor: 'rgba(255,255,255,0.7)',
        transition: 'width 1s linear'
      }}
    />
  </div>
  <Badge bg={stateColor}>...</Badge>
</div>
```

#### Option 3: Animated Border Glow (Recommended)
```jsx
<Badge
  bg={stateColor}
  style={{
    boxShadow: `0 0 0 ${2 - (progress/50)}px rgba(255,255,255,${progress/100})`,
    transition: 'box-shadow 1s ease-out'
  }}
>
  ...
</Badge>
```

### Automation Disabled Visual

**Current Pattern (Keep):**
```jsx
// automation_enabled: false
<Card className="p-0 py-1 ps-1 my-1 ms-5" bg="light">
  <Card.Body className="p-0 m-0">
    <Badge bg={stateColor} className="me-1 mb-1 m-0 p-1">
      <DeviceIcon /> Device Info
    </Badge>
    <ButtonDelete />
    <ButtonsOnOff /> {/* or ButtonsShell */}
  </Card.Body>
</Card>

// automation_enabled: true
<Badge bg={stateColor} className="me-1 m-1 mb-1">
  <DeviceIcon /> Device Info
  <ButtonDelete />
</Badge>
```

**Additional Visual Indicator:**
- Gray `Card` background with left indent (ms-5) ✓ Already exists
- Could add: Striped badge pattern or dashed border for extra visibility
- Could add: 🔇 icon or "Manual" label

### Device Info Display Pattern

**PJLink:**
```
🎬 192.168.1.100 / Main Projector
   ↑ Icon  ↑ Host  ↑ Name
```

**NETIO:**
```
🔌 N-netio-01 Port 2 / Power Strip A
   ↑ Icon ↑ Host ↑ Port ↑ Name
```

**ANEL:**
```
🔌 A-anel-03 Port 1 / Light Controller
   ↑ Icon ↑ Host ↑ Port ↑ Name
```

**Shell:**
```
💻 Reboot Server
   ↑ Icon ↑ Name
```

### Cooldown Timer Display

When device is in cooldown period (`next_check_allowed_at` in future):

```jsx
<OverlayTrigger overlay={<Tooltip>Next check: {relativeTime}</Tooltip>}>
  <div className="cooldown-indicator">
    <Badge bg={stateColor} style={{ opacity: 0.7 }}>
      <DeviceIcon /> Device Info
      <small className="ms-2">⏱ {countdown}</small>
    </Badge>
  </div>
</OverlayTrigger>
```

**Progress Calculation:**
```javascript
const calculateProgress = (device) => {
  const now = Date.now();
  const nextCheck = new Date(device.next_check_allowed_at).getTime();
  const lastCheck = new Date(device.last_checked_at).getTime();

  if (now >= nextCheck) return 100; // Ready to check

  const total = nextCheck - lastCheck;
  const elapsed = now - lastCheck;
  const progress = (elapsed / total) * 100;

  return Math.max(0, Math.min(100, progress));
};

// Update every second
useEffect(() => {
  const interval = setInterval(() => {
    setProgress(calculateProgress(device));
  }, 1000);
  return () => clearInterval(interval);
}, [device]);
```

## Component Structure

```
DeviceCard
├── ProgressIndicator (if automation_enabled)
├── Badge (colored by state)
│   ├── DeviceIcon (type-specific)
│   ├── DeviceInfo (formatted)
│   ├── CooldownTimer (if in cooldown)
│   └── DeleteButton (if editMode)
└── ControlButtons (if !automation_enabled)
    ├── ButtonsOnOff (pjlink, netio, anel)
    └── ButtonsShell (shell)
```

## CSS Animations

```css
/* Smooth progress animation */
.device-progress {
  transition: width 1s linear;
}

/* Pulse animation when ready to check */
@keyframes pulse-ready {
  0%, 100% { box-shadow: 0 0 0 0 rgba(255,255,255,0.7); }
  50% { box-shadow: 0 0 0 4px rgba(255,255,255,0.3); }
}

.device-ready {
  animation: pulse-ready 2s ease-in-out infinite;
}

/* Automation disabled badge pattern */
.automation-disabled .badge {
  background-image: repeating-linear-gradient(
    45deg,
    transparent,
    transparent 10px,
    rgba(255,255,255,0.1) 10px,
    rgba(255,255,255,0.1) 20px
  );
}
```

## State Polling Integration

```javascript
// Frontend polling every 5 seconds
useEffect(() => {
  const fetchState = async () => {
    const response = await api.state.getAllExhibitions();
    setDevices(response.data);
  };

  fetchState(); // Initial
  const interval = setInterval(fetchState, 5000);
  return () => clearInterval(interval);
}, []);
```

## Accessibility

- Use aria-label for device type icons
- Show tooltip with full device info on hover
- Color + icon combination (not just color) for state
- Keyboard navigation support for control buttons

## Responsive Design

- Desktop: Inline badges, multiple per row
- Tablet: 2-3 badges per row
- Mobile: Full-width cards, stacked

## Example Layout

```
Exhibition: Main Gallery
┌─────────────────────────────────────────────────────────────┐
│ Artwork: Interactive Display                    [ON] [OFF]  │
├─────────────────────────────────────────────────────────────┤
│ ████████████░░░░ 🎬 192.168.1.100 / Projector 1 [×]        │ ← automation_enabled
│ ████████████████ 🔌 N-01 Port 2 / Power Strip [×]          │ ← automation_enabled
│                                                              │
│   ╭──────────────────────────────────────────────────╮      │
│   │ 💻 Reboot Server     [×]  [On] [Off] [Restart]  │      │ ← automation_disabled
│   ╰──────────────────────────────────────────────────╯      │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Priority

1. ✅ Basic badge with state colors
2. ✅ Device type icons
3. ✅ Automation disabled Card wrapper
4. 🔄 Progress indicator for next check
5. 🔄 Cooldown timer display
6. 🔄 Real-time state polling
7. 🔄 Smooth animations
