# Asset Tracking

Track projector usage for maintenance planning.

## Automatic Linking

Devices are linked to assets by hostname pattern:

```yaml
asset_tracking:
  hostname_pattern: "^(?P<asset>\\d{6})-"
```

Hostname `123456-projector.local` → Asset `123456`

The `asset_linker` task runs periodically to link new devices to assets.

---

## Lamp Hours Recording

Lamp hours are recorded:

| Event | When |
|-------|------|
| `power_off` | 7 minutes after device powers off |
| `power_on` | When device powers on (delta tracking) |
| `onboard` | When device is linked to asset |
| `offboard` | When device is unlinked |
| `manual` | Manual recording via UI |
| `scheduled` | Daily scheduled check |

### Why 7 Minutes Delay?

Projectors in COOLING state may not respond to lamp hour queries. The system schedules a one-shot task to query lamp hours 7 minutes after power-off, ensuring the projector is queryable.

---

## Asset Browser

The Assets view (`#assets`) shows:
- All tracked projector assets
- Current lamp hours
- Usage history
- Linked devices

### Actions

| Button | Description |
|--------|-------------|
| **Relink** | Re-run device linking for unlinked assets |
| **Backfill** | Create missing assets from existing devices |
| **Lamp Hours** | Record current lamp hours for selected assets |
| **Export** | Download lamp history as CSV |

---

## Maintenance Planning

Use lamp hours data to:

- **Plan replacements** - Most projector lamps last 2000-5000 hours
- **Identify overuse** - Find projectors running more than expected
- **Balance load** - Move projectors between high/low use locations
- **Warranty claims** - Document usage for manufacturer support

---

## API Endpoints

```
GET  /api/assets                    # List all assets
GET  /api/assets/{id}               # Get asset details
GET  /api/assets/{id}/lamp-history  # Get lamp hours history
POST /api/assets/record-lamp-hours  # Record current hours
POST /api/assets/backfill           # Create missing assets
POST /api/assets/lamp-history/csv   # Export as CSV
```
