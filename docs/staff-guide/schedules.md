# Scheduling System

Automate device control with scheduled ON/OFF operations.

## Overview

Schedules allow you to:
- Automatically turn on exhibitions at opening time
- Turn off all devices at closing time
- Run periodic maintenance tasks
- Automate repetitive daily operations

## Prerequisites

### Enable Schedules

Schedules must be enabled at each level:

1. **Exhibition Level:** Enable "Enable Schedules" in exhibition settings
2. **Artwork Level:** Enable "Enable Schedules" in artwork settings
3. **Device Level:** Enable "Enable Schedules" in device settings

Only targets with schedules enabled will show the schedule button.

## Creating a Schedule

### Via UI

1. Enable Edit Mode
2. Click the **calendar icon** on the target (exhibition, artwork, or device)
3. The Schedule Manager modal opens
4. Configure the schedule in the "Add New Schedule" section
5. Click **Add Schedule**

### Schedule Manager Modal

The Schedule Manager shows:

**Existing Schedules Section:**
- List of all configured schedules for this target
- Recurring schedules show a repeat icon and cron expression
- One-time schedules show a calendar icon and execution time
- Toggle button to enable/disable each schedule
- Edit button to modify recurring schedules
- Delete button to remove schedules

**Add New Schedule Section:**
| Field | Description |
|-------|-------------|
| **Name** | Optional descriptive name (auto-generated if blank) |
| **Type** | Recurring (cron-based) or One-time |
| **Action** | ON, OFF, or custom action (devices only) |
| **Cron Expression** | For recurring: when to run (see below) |
| **Date & Time** | For one-time: specific execution time |

### Schedule Types

**Recurring Schedules:**
- Run repeatedly based on cron expression
- Shows "Next runs:" preview of upcoming executions
- Can be edited, enabled/disabled, or deleted
- Best for daily/weekly routines

**One-time Schedules:**
- Run once at a specific date and time
- Shows "Scheduled:" time before execution
- Shows "Executed:" time after running
- Useful for one-off tasks or delayed actions
- Cannot be edited after creation

### Schedule Cards

Each schedule displays:
- **Name** - Descriptive title
- **Icon** - Repeat icon for recurring, calendar for one-time
- **Status** - Enabled/disabled state
- **Next/Executed** - When it will run or when it ran
- **Cron** - Human-readable format + raw expression

### Managing Existing Schedules

**Enable/Disable:** Click the pause/play button to toggle
**Edit:** Click the pencil icon (recurring only)
**Delete:** Click the trash icon and confirm

## Cron Expressions

Cron expressions define when schedules run.

### Format

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, Sun=0)
│ │ │ │ │
* * * * *
```

### Examples

| Expression | Description |
|------------|-------------|
| `0 9 * * *` | Every day at 9:00 AM |
| `0 18 * * *` | Every day at 6:00 PM |
| `0 9 * * 1-5` | Weekdays at 9:00 AM |
| `0 10 * * 6,0` | Weekends at 10:00 AM |
| `30 8 * * 1-5` | Weekdays at 8:30 AM |
| `0 9,12,15 * * *` | Daily at 9 AM, 12 PM, 3 PM |
| `*/15 * * * *` | Every 15 minutes |
| `0 0 1 * *` | First of every month at midnight |

### Common Patterns

**Museum Hours (Tue-Sun, 10 AM - 6 PM):**
```
Turn ON:  0 10 * * 2-0
Turn OFF: 0 18 * * 2-0
```

**Weekday Schedule (Mon-Fri, 9 AM - 5 PM):**
```
Turn ON:  0 9 * * 1-5
Turn OFF: 0 17 * * 1-5
```

**Extended Weekend Hours (Sat-Sun, 10 AM - 8 PM):**
```
Turn ON:  0 10 * * 6,0
Turn OFF: 0 20 * * 6,0
```

## Schedule Levels

### Exhibition Schedules

Controls all artworks and devices in the exhibition:
- Turn on entire gallery at opening
- Turn off everything at closing

**Best for:** Daily open/close operations

### Artwork Schedules

Controls all devices in a single artwork:
- Specific artwork timing different from exhibition
- Independent operation hours

**Best for:** Artworks with different schedules

### Device Schedules

Controls individual devices:
- Staggered startup (prevent power surge)
- Devices that need pre-warming

**Best for:** Fine-grained control

## Schedule Execution

### How It Works

1. Scheduler checks for due jobs every 10 seconds
2. Due jobs are executed in order
3. Results are logged
4. Next run time is calculated

### Execution Order

When a schedule triggers:
1. Protection rules are checked first
2. If allowed, command is sent
3. State verification runs
4. Result is logged

### Staggered Startup

When turning on multiple devices, the system automatically staggers:
- 1-second delay between ON commands
- Prevents network flooding
- Reduces power surge

## Monitoring Schedules

### Schedule Status

In the Admin panel, view:
- Last run time
- Last result (success/failure)
- Next scheduled run
- Fail count

### Execution Logs

View schedule execution history:
1. Open Admin panel
2. Click on a schedule
3. View execution logs

### Circuit Breaker

If a schedule fails 5 times in a row:
- Schedule is automatically paused
- `backoff_until` is set
- Manual intervention required

**To Resume:**
1. Fix the underlying issue
2. Open Admin panel
3. Reset the fail count

## Best Practices

### Startup Sequence

For exhibitions with many devices:
1. Create exhibition-level ON schedule (e.g., 8:55 AM)
2. This turns on critical infrastructure first
3. Individual artworks activate within their protection budgets

### Shutdown Sequence

Reverse order for clean shutdown:
1. Artwork schedules turn OFF at 5:55 PM
2. Exhibition schedule turns OFF at 6:00 PM
3. Catches any missed devices

### Avoid Conflicts

- Don't schedule same target at same time with different actions
- Leave buffer between ON and OFF schedules
- Consider warmup/cooldown times

### Holiday Handling

For days the museum is closed:
1. Create a "disable" schedule that keeps things OFF
2. Or manually disable schedules via Edit Mode
3. Re-enable when museum reopens

## Troubleshooting

### Schedule Not Running

1. **Check Enable Flags:** Schedule, artwork, device all need schedules_enabled
2. **Check Cron Expression:** Use a cron validator
3. **Check Time Zone:** Server uses UTC or local time?
4. **Check Circuit Breaker:** Fail count may have triggered pause

### Schedule Runs But Nothing Happens

1. **Check Device State:** Already in desired state?
2. **Check Protection:** Artwork may be protected
3. **Check Device Enabled:** Device may be disabled
4. **Check Logs:** View execution details

### Wrong Time Execution

1. **Server Time Zone:** Verify server system time
2. **Cron Expression:** Double-check day of week (0=Sunday)
3. **DST Changes:** Some issues around daylight saving transitions

## API Reference

### List Schedules

```
GET /api/admin/schedules
```

### Create Schedule

```
POST /api/admin/schedules
{
  "name": "Morning Startup",
  "job_type": "device",
  "target_type": "exhibition",
  "target_id": "uuid",
  "action_type": "on",
  "cron_expression": "0 9 * * 1-5",
  "enabled": true
}
```

### Update Schedule

```
PATCH /api/admin/schedules/{id}
{
  "enabled": false
}
```

### Delete Schedule

```
DELETE /api/admin/schedules/{id}
```

### Run Schedule Now

```
POST /api/admin/schedules/{id}/run
```
