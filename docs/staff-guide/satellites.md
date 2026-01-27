# Satellite Relay System

The satellite relay system allows MuTech Control to manage devices on remote or isolated networks.

## Overview

Satellites are small daemons that run on remote networks and relay device commands from the central MuTech Control server. This is useful when:

- Devices are on a separate VLAN or network segment
- Devices are behind NAT or firewall
- Network segmentation prevents direct access from the server
- Exhibitions are in remote locations with intermittent connectivity

## How Satellites Work

```
┌─────────────────────────────┐     ┌──────────────────────────────┐
│   MuTech Control Server     │     │   Remote Network             │
│                             │     │                              │
│  ┌───────────────────────┐  │     │  ┌────────────────────────┐  │
│  │ Control Interface     │  │     │  │  Satellite Daemon      │  │
│  └──────────┬────────────┘  │     │  │                        │  │
│             │               │     │  │  - Receives commands   │  │
│  ┌──────────▼────────────┐  │     │  │  - Executes locally    │  │
│  │ Orchestrator          │◄─┼─────┼──┤  - Reports results     │  │
│  │ (routes to satellite) │  │ SSE │  │                        │  │
│  └───────────────────────┘  │     │  └───────────┬────────────┘  │
│                             │     │              │               │
└─────────────────────────────┘     │  ┌───────────▼────────────┐  │
                                    │  │   Local Devices        │  │
                                    │  │   (Projectors, PDUs)   │  │
                                    │  └────────────────────────┘  │
                                    └──────────────────────────────┘
```

**Connection Flow:**
1. Satellite connects to the MuTech Control server via Server-Sent Events (SSE)
2. Satellite appears in Admin panel as "Pending Approval"
3. Administrator approves the satellite with a friendly name
4. Commands for assigned exhibitions are routed through the satellite
5. Satellite executes commands locally and reports results

## Managing Satellites

### Accessing Satellite Management

1. Enable **Edit Mode**
2. Click **Admin** in the header
3. View the **Satellites** section at the top

### Approving a New Satellite

When a satellite connects for the first time, it appears in the "Pending Approval" section:

1. Enter a descriptive name for the satellite (e.g., "Gallery-Wing-B", "Remote-Building")
2. Click the **checkmark** button to approve
3. The satellite moves to "Approved Satellites"

**Information shown for pending satellites:**
- Hostname (from the satellite machine)
- Version number
- Connection time

### Rejecting a Satellite

If you don't recognize a satellite connection:

1. Click the **X** button to reject
2. The satellite is removed from the pending list
3. It can try connecting again (and will reappear as pending)

### Revoking an Approved Satellite

If a satellite is no longer needed or compromised:

1. Find the satellite in "Approved Satellites"
2. Click the **trash icon** to revoke
3. Confirm the action
4. The satellite is disconnected and removed
5. If it reconnects, it will need to be re-approved

### Satellite Status

| Badge | Meaning |
|-------|---------|
| **Connected** (green) | Satellite is online and ready |
| **Offline** (gray) | Satellite is not connected |
| **Pending** (yellow) | Awaiting approval |

## Assigning Satellites to Exhibitions

Once a satellite is approved, you can assign it to exhibitions:

1. In Edit Mode, click the **pencil icon** on an exhibition
2. Find the **Satellite Relay** dropdown
3. Select the satellite to use for this exhibition
4. Click **Save Changes**

**Options:**
- **No satellite (direct connection)** - Commands sent directly from server
- **[Satellite name] (online/offline)** - Commands routed through this satellite

**Warning:** If you select an offline satellite, commands will fail until it reconnects.

## Best Practices

### Naming Conventions

Use descriptive names that identify the location or network:
- `Gallery-West-Wing`
- `Building-B-Floor2`
- `Warehouse-Exhibition`
- `Remote-Site-Munich`

### Network Configuration

For the satellite to work, ensure:
- Outbound HTTPS connection from satellite to MuTech server
- Local network access from satellite to devices
- Firewall allows SSE connections (long-lived HTTP)

### Redundancy

Consider running multiple satellites for critical exhibitions:
- Deploy on different machines
- Only one needs to be connected at a time
- Switch exhibitions between satellites if needed

### Monitoring

Regularly check satellite status:
- Admin panel shows "Last seen" time for each satellite
- Set up alerts for satellites going offline
- Monitor satellite logs for connection issues

## Troubleshooting

### Satellite Shows "Pending" Repeatedly

**Causes:**
- Satellite was rejected but keeps reconnecting
- API key mismatch
- Multiple satellites with same hostname

**Solutions:**
1. Verify satellite configuration
2. Check API key matches server expectation
3. Approve the satellite to stop re-attempts

### Commands Failing for Exhibition

**Causes:**
- Assigned satellite is offline
- Satellite can't reach devices locally
- Network timeout between satellite and server

**Solutions:**
1. Check satellite status in Admin panel
2. Verify satellite can ping devices locally
3. Check satellite logs for errors
4. Remove satellite assignment to test direct connection

### Satellite Disconnects Frequently

**Causes:**
- Network instability
- SSE connection timeout
- Server resource limits

**Solutions:**
1. Check network connectivity
2. Review server logs for connection drops
3. Increase SSE timeout settings if needed

## API Reference

### List Approved Satellites

```
GET /api/admin/satellites
```

### List Pending Satellites

```
GET /api/admin/satellites/pending
```

### Approve Satellite

```
POST /api/admin/satellites/approve
{
  "api_key_hash": "hash",
  "name": "Friendly Name"
}
```

### Reject Satellite

```
POST /api/admin/satellites/reject
{
  "api_key_hash": "hash"
}
```

### Revoke Satellite

```
DELETE /api/admin/satellites/{id}
```

## Satellite Daemon Setup

For instructions on deploying the satellite daemon, see the [Admin Guide](../admin-guide/README.md#satellite-deployment).
