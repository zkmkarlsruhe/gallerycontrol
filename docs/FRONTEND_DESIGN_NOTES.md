# MuTech Control System - Frontend Design Notes

**Date:** 2026-01-12
**Phase:** Design & Prototyping
**Status:** Testing design variations before implementation

---

## Design Principles

### Mobile-First Philosophy
- **Primary use case:** Quick glance on mobile devices
- **Desktop:** Same layout, more breathing room
- **Optimization goal:** Minimize vertical space, maximize information density
- **Interaction:** Scroll over click (no accordions for main content)

### Quick Glance Requirements
1. See all exhibition states at once
2. Identify errors immediately
3. Access controls with minimal taps
4. No hidden information requiring clicks to reveal

---

## Page Structure

### Two-Section Layout

```
┌─────────────────────────────────────┐
│ STICKY HEADER                       │
│ MuTech Control    [ALL ON][ALL OFF]│
├─────────────────────────────────────┤
│ EXHIBITION OVERVIEW (NEW)           │
│ - Floating cards                    │
│ - Quick status indicators           │
│ - Per-exhibition controls           │
│ - Click to jump to detail           │
├─────────────────────────────────────┤
│ TABLE VIEW (CURRENT, OPTIMIZED)     │
│ - Full hierarchy                    │
│ - Exhibition → Artwork → Device     │
│ - All expanded, scroll to navigate  │
│ - Device cooldown indicators        │
└─────────────────────────────────────┘
```

---

## Section 1: Exhibition Overview

### Purpose
- Quick status check across all exhibitions
- Fast navigation to detailed view
- Bulk control per exhibition

### Design Decisions

#### Card Layout
- **Format:** Floating cards, responsive grid
- **Mobile:** Single column or 2-up
- **Tablet/Desktop:** 2-3 cards per row
- **Min width:** 280px per card

#### State Indicators
**Show all three states:**
- ● Green count = ON devices
- ● Gray count = OFF devices
- ⚠ Red count = ERROR devices

**Card background color:**
- Green = majority ON
- Dark = majority OFF
- Red = many errors (>30%)
- Yellow = mixed state

#### Layout Options to Test

**Option A: Stacked (most compact)**
```
╭──────────────────╮
│ Main Gallery     │
│ ●10 ●2 ⚠2       │
│ [ON] [OFF]      │
╰──────────────────╯
```

**Option B: Inline compact**
```
╭────────────────────────────╮
│ Main Gallery  ●10 ●2 ⚠2   │
│               [ON] [OFF]   │
╰────────────────────────────╯
```

**Option C: Single line (risk of mobile bloat)**
```
╭──────────────────────────────────╮
│ Main Gallery  ●10 ●2 ⚠2 [ON][OFF]│
╰──────────────────────────────────╯
```

**Decision:** Defer to prototype testing

---

## Section 2: Table View (Detailed)

### Structure
```
Exhibition Header              [ON] [OFF]
  Artwork Name                 [ON] [OFF]
    ████░░ 🎬 1.100 / Projector [×]     ← automation enabled
    ███░░░ 🔌 N-01 Port 2 [×]           ← automation enabled
        ▓▓▓░░ 💻 Reboot [×] [ON][OFF]   ← automation disabled (indented)
```

### Device Display Components

#### 1. Cooldown Progress Indicator
**Location:** Top border of badge
**Behavior:** Countdown (drains from 100% to 0%)

```
████████████████ (100%) - Just checked
████████░░░░░░░░ (50%)  - Halfway through cooldown
░░░░░░░░░░░░░░░░ (0%)   - Ready to check
```

**Implementation:**
- 3-4px colored bar on top of badge
- Fills left-to-right, empties as cooldown expires
- Color: `rgba(255,255,255,0.7)` with opacity based on progress
- Smooth 1s transition animation

**Calculation:**
```javascript
const cooldownRemaining = (device) => {
  const now = Date.now();
  const nextCheck = new Date(device.next_check_allowed_at).getTime();
  const lastCheck = new Date(device.last_checked_at).getTime();

  if (now >= nextCheck) return 0; // Empty = ready

  const totalCooldown = nextCheck - lastCheck;
  const timeRemaining = nextCheck - now;

  return (timeRemaining / totalCooldown) * 100;
};
```

#### 2. State Colors
| State | Color | Bootstrap | Meaning |
|-------|-------|-----------|---------|
| -1 | Red | `danger` | Error |
| 0 | Dark Gray | `dark` | Off |
| 1 | Green | `success` | On |
| 2 | Yellow | `warning` | Cooling |
| 3 | Yellow | `warning` | Warming |

#### 3. Device Type Icons
- 🎬 Projector (PJLink)
- 🔌 Outlet (NETIO)
- 🔌 Plug (ANEL)
- 💻 Terminal (Shell)

#### 4. Host Display
**IP addresses:** Remove first two octets (always 192.168)
- Input: `192.168.1.100` → Display: `1.100`

**DNS names:** Show as-is
- Input: `projector-main-hw12345.zkm.de` → Display: `projector-main-hw12345.zkm.de`

**Toggle behavior:**
- Click badge → Opens `http://{host}` in new tab
- Form field accepts either IP or DNS
- Display shows what user entered
- Backend uses resolved IP for device communication

#### 5. Badge Content Format

**PJLink:**
```
🎬 1.100 / Main Projector
```

**NETIO:**
```
🔌 N-netio-01 Port 2 / Power Strip
```

**ANEL:**
```
🔌 A-anel-03 Port 1 / Light
```

**Shell:**
```
💻 Reboot Server
```

### Automation Disabled Visual Design

**Goal:** Clear visual separation while staying compact

#### Current Pattern (Baseline)
```
Card with:
- Light gray background
- Left indent (ms-5 = ~3rem)
- Full card wrapper
- Buttons on same line or below

Issues:
- Takes too much vertical space on mobile
- Heavy visual weight
```

#### Proposed Pattern
```
Visual indent + striped badge:
    ▓▓▓░░ 💻 Reboot Server [×] [ON][OFF][Restart]
    ↑ Left margin indent
    ↑ Striped/hatched badge pattern
```

**Visual indicators:**
1. Left indent (e.g., 1-2rem margin-left)
2. Striped/hatched badge background
3. All buttons inline (for now)

**Striped pattern CSS:**
```css
.automation-disabled .badge {
  background-image: repeating-linear-gradient(
    45deg,
    transparent,
    transparent 8px,
    rgba(255,255,255,0.15) 8px,
    rgba(255,255,255,0.15) 16px
  );
}
```

#### Options to Test

**A. Single line, all inline**
```
    ▓▓▓░░ 💻 Reboot Server [×] [ON][OFF][Restart][Custom]
```
- Pros: Most compact
- Cons: May overflow on small mobile, text truncation

**B. Badge + buttons below**
```
    ▓▓▓░░ 💻 Reboot Server [×]
    [ON] [OFF] [Restart] [Custom]
```
- Pros: Never cramped
- Cons: Extra vertical space

**C. Light card wrapper, no indent**
```
╭─────────────────────────────────────╮
│ ▓▓▓░░ 💻 Reboot [×] [ON][OFF][RST] │
╰─────────────────────────────────────╯
```
- Pros: Clear separation
- Cons: Still adds space

**D. Left border bar only**
```
│ ▓▓▓░░ 💻 Reboot Server [×] [ON][OFF]
│ ↑ 3px left border
```
- Pros: Minimal visual weight
- Cons: May not stand out enough

**Decision:** Test in prototype with real content

---

## Responsive Breakpoints

```css
/* Mobile first */
.exhibition-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.exhibition-card {
  flex: 1 1 100%; /* Full width on mobile */
  min-width: 280px;
}

/* Tablet */
@media (min-width: 576px) {
  .exhibition-card {
    flex: 1 1 calc(50% - 0.5rem); /* 2 up */
  }
}

/* Desktop */
@media (min-width: 992px) {
  .exhibition-card {
    flex: 1 1 calc(33.333% - 0.5rem); /* 3 up */
  }
}
```

---

## Data Model

### Database Schema (Relevant Fields)

```sql
devices:
  id UUID
  artwork_id UUID
  device_type VARCHAR  -- 'pjlink', 'netio', 'anel', 'shell'
  host VARCHAR         -- What user entered (IP or DNS)
  ip_address VARCHAR   -- Resolved IP (for communication)
  dns_name VARCHAR     -- Resolved DNS (optional)
  port INTEGER

  enabled BOOLEAN                    -- Master switch
  automation_enabled BOOLEAN         -- In automation loop
  exclude_from_auto_onoff BOOLEAN    -- Exclude from bulk ON/OFF

  config JSONB         -- Device-specific settings
  state INTEGER        -- -1=error, 0=off, 1=on, 2=cooling, 3=warming

  last_checked_at TIMESTAMP
  next_check_allowed_at TIMESTAMP
```

### State Polling

**Frontend:**
- Poll every 5 seconds: `GET /api/state/exhibitions`
- Returns full hierarchy with device states
- Update UI without page refresh

**Progress indicator:**
- Update every 1 second (local calculation)
- No server polling needed for progress bar

---

## Open Questions / Decisions Deferred

### Exhibition Overview Cards
- [ ] Exact layout: stacked vs inline vs single-line?
- [ ] Show total count (e.g., "10/12") or just individual counts?
- [ ] Error badge prominent or subtle?

### Automation Disabled Devices
- [ ] Single line vs two lines for buttons?
- [ ] Indent amount (1rem vs 2rem)?
- [ ] Visual separator strength (striped pattern sufficient or need border/card?)

### Mobile Optimization
- [ ] Minimum touch target size (44px recommended)
- [ ] Button text on mobile: full labels or icons/abbreviations?
- [ ] Font sizes for different screen sizes

### Interactions
- [ ] Loading states when sending commands
- [ ] Error feedback display
- [ ] Success confirmation (toast? inline?)
- [ ] Optimistic UI updates vs wait for server

---

## Testing Plan

### Prototype Testing
1. Build HTML prototype with all variations
2. Test on real mobile devices (not just browser resize)
3. Test with realistic data:
   - Exhibition with 3 artworks, 12 devices
   - Mix of automation enabled/disabled
   - Various device name lengths
   - Different states (on/off/error/cooling)
4. Test interactions:
   - Tap targets size
   - Button accessibility
   - Scroll performance
   - Visual clarity at different screen sizes

### User Testing Questions
- Can you quickly identify which exhibitions have errors?
- Can you find and control a specific device?
- Is the automation disabled visual clear enough?
- Are the buttons easy to tap on mobile?
- Is the cooldown indicator helpful or distracting?

---

## Implementation Notes

### Technology Stack (Confirmed)
- React 18 + TypeScript
- Vite (build tool)
- Bootstrap 5 (or keep existing if compatible)
- TanStack Query or Zustand (state management)
- Axios (API client)

### Component Structure (Proposed)
```
App
├── Header (sticky, global controls)
├── ExhibitionOverview
│   └── ExhibitionCard[]
└── TableView
    └── ExhibitionSection[]
        └── ArtworkSection[]
            ├── DeviceBadge[] (automation enabled)
            └── DeviceCard[] (automation disabled)
```

### Reusable Components
- `DeviceBadge` - with progress indicator, state color, icon
- `StateIndicator` - colored dot + count
- `ControlButtons` - ON/OFF/custom buttons
- `CooldownProgress` - top border animation

---

## Next Steps

1. ✅ Design notes documented
2. 🔄 HTML prototype with variations
3. ⏳ Mobile device testing
4. ⏳ Design decision finalization
5. ⏳ React component implementation
6. ⏳ API integration
7. ⏳ User acceptance testing

---

**Last Updated:** 2026-01-12
**Review Date:** After prototype testing
