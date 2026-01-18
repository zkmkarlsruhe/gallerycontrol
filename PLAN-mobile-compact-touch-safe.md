# Plan: Mobile Compact View + Double-Tap Safety

## Summary
1. Add CSS media query for screens < 900px to reduce whitespace (keep 44px button height)
2. Create `TouchSafeButton` - uses `(pointer: coarse)` to detect touch devices
3. Apply to ON/OFF buttons that are currently single-click in non-edit mode
4. Keep existing `ConfirmButton` for manual device actions (already has confirmation)

---

## Analyst Feedback (Incorporated)
- Use `(pointer: coarse)` instead of width-based detection for touch devices
- Keep button min-height at 44px for accessibility
- Don't replace existing ConfirmButton usages - those already have safety
- Guard `window` access for SSR safety, clean up listeners

---

## Part 1: Compact Mobile CSS (< 900px)

**File:** `mutech-control-service/frontend/src/App.css`

Add new media query `@media (max-width: 900px)` to reduce spacing only:

| Element | Current | Compact |
|---------|---------|---------|
| Header padding | 0.75rem 1rem | 0.5rem 0.75rem |
| Overview section padding | 1rem | 0.5rem |
| Overview section gap | 0.75rem | 0.5rem |
| Exhibition card padding | 0.75rem | 0.5rem |
| Exhibition card min-width | 200px | 140px |
| Exhibition section margin | 1rem | 0.5rem |
| Exhibition header padding | 0.75rem 1rem | 0.5rem 0.75rem |
| Artwork row padding | 0.75rem 1rem | 0.5rem 0.75rem |
| Artwork inline layout gap | 0.75rem | 0.5rem |
| Device badge padding | 0.3rem 0.5rem | 0.25rem 0.4rem |
| **Button height** | **44px** | **44px (keep!)** |

---

## Part 2: TouchSafeButton Component

**New file:** `mutech-control-service/frontend/src/components/ui/TouchSafeButton.tsx`

```tsx
// Detects touch device via matchMedia('(pointer: coarse)')
// On touch: requires double-tap (delegates to ConfirmButton logic)
// On mouse: single click works normally
// Guards window access in useEffect for SSR safety
// Cleans up matchMedia listener on unmount
```

---

## Part 3: Apply TouchSafeButton to Non-Edit Mode

Only replace buttons that are **currently single-click**:

**1. `ExhibitionCard.tsx`**
- ON/OFF buttons → TouchSafeButton (currently single-click)

**2. `ExhibitionSection.tsx`** (lines 68-81)
- Exhibition header ON/OFF buttons → TouchSafeButton (currently single-click)

**3. `ArtworkRow.tsx`** (non-edit mode sections)
- Artwork ON/OFF buttons (lines 155-158) → TouchSafeButton (currently single-click)

**Keep existing ConfirmButton (already has double-tap everywhere):**
- Manual device ON/OFF buttons (lines 192-196) - already ConfirmButton
- Shell action buttons (lines 189-191) - already ConfirmButton

---

## Verification
1. Run `npm run dev` in frontend directory
2. **Mouse/trackpad device:** Single click works immediately on all buttons
3. **Touch device (or Chrome DevTools touch emulation):**
   - Verify reduced spacing throughout UI
   - Exhibition/artwork ON/OFF: First tap shows "ON?"/"OFF?", second tap executes
   - Manual device actions: Still require confirmation (unchanged)
4. Buttons remain 44px height for accessibility
