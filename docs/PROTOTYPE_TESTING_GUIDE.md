# MuTech Control - Prototype Testing Guide

**Date:** 2026-01-12
**Status:** Ready for Testing

---

## Overview

Three interactive HTML prototypes have been created to test and validate all design decisions before implementation:

1. **Design Variations Prototype** - UI layout and visual design
2. **Forms Complete Prototype** - CRUD operations and advanced features
3. Combined testing approach

---

## Prototype Files

### 1. prototype-design-variations.html

**Focus:** Visual design and layout testing

**Sections:**
- **Exhibition Overview Cards** (3 variations)
  - Stacked layout (most compact for mobile)
  - Inline compact
  - Single line (risk of mobile bloat)

- **Device Badges with Cooldown Progress**
  - Top border progress bar (drains from 100% to 0%)
  - Animated countdown visualization
  - Different cooldown states

- **Automation Disabled Patterns** (4 variations)
  - Indent + striped badge + inline buttons
  - Indent + buttons below
  - Light card wrapper
  - Left border bar only

- **Full Context Example**
  - Realistic exhibition with multiple artworks
  - Mix of automation enabled/disabled devices
  - Different states (on/off/error/cooling)

**Testing Focus:**
- Mobile space optimization
- Visual clarity for quick glance
- Touch target sizing
- Progress indicator usefulness

**Open:** `firefox /workspace/prototype-design-variations.html`

---

### 2. prototype-forms-complete.html

**Focus:** CRUD operations and advanced features

**Section 1: Form Layout Variations**

**Variation 1: Vertical Sections** (Recommended)
- Collapsible accordions (Basic Info, Configuration, Settings)
- Mobile-first approach
- All device types fit same structure
- Example: PJLink with password field

**Variation 2: Two-Column Split**
- Desktop optimized layout
- Common settings left, type-specific right
- Responsive: stacks on mobile
- Example: NETIO with port selector

**Variation 3: Tabbed Interface**
- Organized with tabs: Basic Info, Configuration, Settings
- Reduces clutter
- May hide information
- Example: ANEL with 8 port options

**Variation 4: Shell Commands - Automation Modes**
- **Toggle determines structure:**
  - ☑ Automation ON: Fixed commands (Reachable, Status with patterns, ON, OFF)
  - ☐ Automation OFF: Flexible custom commands with labels
- Live mode switching demonstration
- Command testing with simulated output

**Section 2: Clone & Move Features**

**Clone Device:**
- Context menu trigger
- Modal pre-fills all settings
- Clears host/port (must be unique)
- Auto-adds " (Copy)" to name
- Shows copied settings in collapsible section

**Move Device:**
- Simple modal with cascading dropdowns
- Exhibition selection → Artwork list updates
- Current location clearly displayed

**Section 3: Shell Command Library**

**Template Cards:**
- Automation/Manual badges
- Category organization
- Command count display
- Click to view details

**Built-in Templates:**
- Systemd Service Control (automation)
- Docker Container Control (automation)
- Server Maintenance (manual)
- VLC Media Player (automation)

**Template Details:**
- Variable substitution: `{{SERVICE_NAME}}`, `{{HOST}}`
- Input fields with placeholders
- Command preview with variables
- Apply template button

**Custom Templates:**
- User-created templates shown separately
- Edit/Delete actions available

**Interactive Features:**
- Live command testing
- Variable input validation
- Preview generated commands

**Open:** `firefox /workspace/prototype-forms-complete.html`

---

## Testing Checklist

### Visual Design Testing

**Exhibition Overview Cards:**
- [ ] Which layout works best on mobile?
- [ ] Are state indicators clear at a glance?
- [ ] Can you quickly identify errors?
- [ ] Are buttons easy to tap on mobile?
- [ ] Does stacked vs inline make a difference?

**Device Badges:**
- [ ] Is the progress bar helpful or distracting?
- [ ] Can you tell the difference between cooldown states?
- [ ] Is the countdown direction intuitive (100% → 0%)?
- [ ] Are state colors distinguishable?
- [ ] Is device info readable on small screens?

**Automation Disabled:**
- [ ] Which visual pattern provides clearest separation?
- [ ] Is indent alone sufficient?
- [ ] Do you prefer striped pattern or card wrapper?
- [ ] Are buttons cramped on single line?
- [ ] Would two lines be better for manual devices?

### Form Layout Testing

**Overall:**
- [ ] Which layout variation feels most intuitive?
- [ ] Can you find all fields easily?
- [ ] Is anything hidden that shouldn't be?
- [ ] Do collapsible sections help or hinder?
- [ ] Does tabbed interface add too many clicks?

**PJLink Form:**
- [ ] Is host/port/password layout clear?
- [ ] Are placeholders helpful?
- [ ] Is default port info useful?

**NETIO/ANEL Form:**
- [ ] Are port toggle buttons easy to use?
- [ ] Is visual port selection better than dropdown?
- [ ] Can you tell which port is selected?
- [ ] ANEL: Are 8 ports too many in one row?

**Shell Commands (Automation ON):**
- [ ] Is the fixed structure clear?
- [ ] Are ON/OFF pattern fields understandable?
- [ ] Is Status command requirement obvious?
- [ ] Can you distinguish required vs optional commands?

**Shell Commands (Automation OFF):**
- [ ] Is the flexible structure intuitive?
- [ ] Can you add custom commands easily?
- [ ] Is button label field clear?
- [ ] Do you understand no state polling?

### Feature Testing

**Clone Device:**
- [ ] Is the clone intent clear?
- [ ] Do you understand what's copied vs cleared?
- [ ] Is the " (Copy)" suffix helpful?
- [ ] Can you see what settings were copied?
- [ ] Is it obvious you need to change host/port?

**Move Device:**
- [ ] Is the cascading dropdown pattern clear?
- [ ] Can you easily select exhibition then artwork?
- [ ] Is current location obvious?
- [ ] Would you prefer a different UI for this?

**Shell Command Library:**
- [ ] Can you find relevant templates?
- [ ] Is automation vs manual distinction clear?
- [ ] Are template descriptions helpful?
- [ ] Is variable substitution understandable?
- [ ] Would you use the template system?
- [ ] Can you tell custom from built-in templates?

### Mobile-Specific Testing

**Critical Tests:**
- [ ] Open on actual mobile device (not just browser resize)
- [ ] Test touch targets (minimum 44px recommended)
- [ ] Test modal scrolling on small screens
- [ ] Verify text is readable without zooming
- [ ] Check button spacing for fat fingers
- [ ] Test landscape vs portrait orientation

**Specific Checks:**
- [ ] Can you tap small buttons accurately?
- [ ] Do modals become full-screen properly?
- [ ] Is scrolling smooth?
- [ ] Are dropdowns usable?
- [ ] Do toggle buttons work well?

---

## How to Test

### Desktop Testing

```bash
# Open in browser
firefox /workspace/prototype-design-variations.html
firefox /workspace/prototype-forms-complete.html

# Or use local server for better testing
cd /workspace
python3 -m http.server 8080
# Then open:
# http://localhost:8080/prototype-design-variations.html
# http://localhost:8080/prototype-forms-complete.html
```

### Mobile Testing

**Option 1: Browser Dev Tools**
```
1. Open in Firefox/Chrome
2. F12 → Toggle device toolbar
3. Test different device sizes
4. Note: Touch simulation != real touch
```

**Option 2: Real Device** (Recommended)
```
1. Start local server: python3 -m http.server 8080
2. Find computer IP: ip addr show
3. On mobile browser: http://YOUR_IP:8080/prototype-design-variations.html
4. Test with real touches
```

### Interactive Testing

**All Prototypes:**
- Click all buttons
- Toggle all switches
- Test all dropdowns
- Resize browser window
- Scroll through content

**Design Variations:**
- Watch progress bar animations
- Click device badges
- Test exhibition cards
- Compare variations side-by-side

**Forms Complete:**
- Toggle shell automation mode
- Test command execution simulation
- Open context menus
- Fill out forms
- Use template library
- Test clone/move modals

---

## Decision Points

After testing, decide on:

### 1. Exhibition Overview Layout
**Options:** Stacked / Inline Compact / Single Line
**Criteria:** Mobile space, clarity, touch targets
**Decision:** __________________

### 2. Device Badge Progress Indicator
**Options:** Top border / Glow effect / None
**Criteria:** Usefulness vs distraction
**Decision:** __________________

### 3. Automation Disabled Visual
**Options:** Indent + striped / Card wrapper / Border only
**Criteria:** Clear separation, space efficiency
**Decision:** __________________

### 4. Form Layout
**Options:** Vertical Sections / Two-Column / Tabs / Wizard
**Criteria:** Usability, mobile-friendly, all device types
**Decision:** __________________

### 5. Shell Automation Modes
**Options:** Same form with toggle / Different forms / Wizard
**Criteria:** Clear distinction, ease of use
**Decision:** __________________

### 6. Port Selection
**Options:** Toggle buttons / Dropdown / Radio buttons
**Criteria:** Touch-friendly, visual clarity
**Decision:** __________________

### 7. Template Library
**Options:** Modal / Sidebar / Inline selector
**Criteria:** Discoverability, ease of use
**Decision:** __________________

---

## Feedback Collection

### What Works Well

- _______________________________________________
- _______________________________________________
- _______________________________________________

### What Needs Improvement

- _______________________________________________
- _______________________________________________
- _______________________________________________

### Unexpected Issues

- _______________________________________________
- _______________________________________________
- _______________________________________________

### Must-Have Features

- _______________________________________________
- _______________________________________________
- _______________________________________________

### Nice-to-Have Features

- _______________________________________________
- _______________________________________________
- _______________________________________________

---

## Next Steps After Testing

1. **Consolidate feedback** from all testers
2. **Make final design decisions** based on testing results
3. **Update design docs** with chosen approaches
4. **Create final design spec** for implementation
5. **Begin React component development**
6. **Implement API integration**
7. **User acceptance testing**

---

## Notes

- Prototypes use Bootstrap 5 for quick development
- Final implementation will use same or similar framework
- Animations in prototype may differ from final implementation
- Focus on UX patterns, not pixel-perfect design
- Mobile testing on real devices is critical

---

**Last Updated:** 2026-01-12
**Status:** Ready for testing and feedback

