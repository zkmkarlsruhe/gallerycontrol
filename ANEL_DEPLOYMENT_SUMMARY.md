# ANEL Runner - Deployment Architecture Summary

**Date:** 2026-01-12
**Purpose:** Quick reference for ANEL runner separate subnet deployment

---

## Key Understanding

✅ **One Docker container** for ANEL runner
✅ **Different subnet** from main control service (Steuerung)
✅ **Communication method flexible** (HTTP/REST is fine)
✅ **UDP broadcasts** from ANEL devices stay in control network

---

## Network Topology

```
Main Application Network (192.168.1.0/24)
├── Main Service (Steuerung)
├── PostgreSQL
└── Frontend
        │
        │ HTTP/REST
        │ (routed between subnets)
        ↓
Control Network (192.168.50.0/24)
├── ANEL Runner Container (192.168.50.2)
│   ├── Listens: UDP 9977 (receives broadcasts)
│   ├── Sends: UDP 9975 (sends commands)
│   └── REST API: HTTP 8001
│
└── ANEL Devices (192.168.50.10+)
    └── Broadcast status via UDP
```

---

## Why This Architecture?

### Security Isolation
- Power control devices separated from main application
- Reduces attack surface
- Limits blast radius of security breaches

### Network Segmentation
- Different VLANs or physical networks
- Control network has stricter access policies
- Easier to implement network-level security

### UDP Broadcast Domain
- ANEL broadcasts contained within control network
- No broadcast noise in main application network
- Cleaner network architecture

### Access Control
- Only ANEL runner accesses control devices
- Main service cannot directly reach ANEL devices
- One-way communication (main → runner)

---

## Communication Flow

### Command: User turns device ON
```
1. User clicks "ON" in web UI
2. Frontend → Main Service (192.168.1.10)
3. Main Service → ANEL Runner (HTTP POST to http://192.168.50.2:8001)
4. ANEL Runner → ANEL Device (UDP command on port 9975)
5. ANEL Device changes state
6. ANEL Device broadcasts new state (UDP port 9977)
7. ANEL Runner receives broadcast, caches state
8. ANEL Runner returns state to Main Service (HTTP response)
9. Main Service updates database
10. Frontend sees new state (~500ms total)
```

### Status: ANEL device spontaneously broadcasts
```
1. ANEL Device state changes (manual switch, power event, etc.)
2. Device broadcasts status (UDP port 9977)
3. ANEL Runner receives broadcast immediately
4. Runner caches new state
5. Main Service queries state on next poll
6. OR Runner pushes to Main Service (webhook/SSE)
7. Frontend sees update
```

---

## Docker Deployment

### Main Service (Subnet A)
```yaml
# docker-compose.yml on 192.168.1.x host
services:
  main-service:
    environment:
      ANEL_RUNNER_URL: http://192.168.50.2:8001
    networks:
      - app-network
```

### ANEL Runner (Subnet B)
```yaml
# docker-compose-anel.yml on 192.168.50.x host
services:
  anel-runner:
    network_mode: host  # Access control network interface
    environment:
      BIND_ADDRESS: 192.168.50.2
      UDP_RECEIVE_PORT: 9977
      UDP_SEND_PORT: 9975
```

---

## Deployment Options

### Option 1: Two Physical Hosts (Recommended)
- **Host 1:** 192.168.1.10 (main application)
- **Host 2:** 192.168.50.2 (ANEL runner)
- Complete physical separation
- Best security

### Option 2: One Host, Two NICs
- **eth0:** 192.168.1.10 (main application)
- **eth1:** 192.168.50.2 (ANEL runner with network_mode: host)
- Single server, lower cost
- Still good isolation

### Option 3: VLANs
- **VLAN 10:** 192.168.1.0/24 (main)
- **VLAN 50:** 192.168.50.0/24 (control)
- Single physical network
- VLAN tags for separation

---

## What's Documented

### ANEL_ARCHITECTURE.md
- Complete UDP protocol details
- Why separation is mandatory
- Python implementation with asyncio
- Event-driven architecture
- Communication patterns

### DEPLOYMENT_GUIDE.md (NEW)
- Network configuration examples
- Three deployment scenarios
- Docker Compose configurations
- Firewall rules
- Troubleshooting guides
- Security best practices
- Production checklist

### Updated Files
- Implementation plan (curried-discovering-metcalfe.md)
- PROJECT_STATUS.md
- BACKEND_GAP_ANALYSIS.md

---

## Quick Start

1. **Setup networks:**
   - Main: 192.168.1.0/24
   - Control: 192.168.50.0/24

2. **Deploy main service:**
   ```bash
   # On 192.168.1.10 host
   docker-compose up -d
   ```

3. **Deploy ANEL runner:**
   ```bash
   # On 192.168.50.2 host (or same host with eth1)
   docker-compose -f docker-compose-anel.yml up -d
   ```

4. **Configure firewall:**
   - Allow HTTP from 192.168.1.0/24 to 192.168.50.2:8001
   - Allow UDP 9977 from 192.168.50.0/24 to runner

5. **Test:**
   ```bash
   # From main service host
   curl http://192.168.50.2:8001/health
   ```

---

## Key Takeaways

✅ **ANEL runner is separate** - runs in control network subnet
✅ **Not just command execution** - sophisticated UDP gateway with real-time broadcasts
✅ **Communication is flexible** - HTTP/REST works fine between subnets
✅ **Network isolation is critical** - security boundary between app and control
✅ **One container on control network** - simple deployment with `network_mode: host`

---

**See Full Details:**
- `/workspace/ANEL_ARCHITECTURE.md` - Technical implementation
- `/workspace/DEPLOYMENT_GUIDE.md` - Complete deployment procedures
- `/workspace/PROJECT_STATUS.md` - Overall project status

**Last Updated:** 2026-01-12
