# MuTech Control System - Deployment Guide

**Date:** 2026-01-12
**Status:** Deployment Architecture Documentation

---

## Network Architecture Overview

The MuTech Control System uses a **two-subnet architecture** for security and network isolation:

```
┌─────────────────────────────────────────────────┐
│  Subnet A: Main Application Network            │
│  192.168.1.0/24                                 │
│                                                 │
│  - Main Control Service (Steuerung)            │
│  - PostgreSQL Database                          │
│  - Frontend Web UI                              │
│                                                 │
│  IP Range: 192.168.1.1 - 192.168.1.254         │
└─────────────────────────────────────────────────┘
                      │
                      │ HTTP REST API
                      │ (routed between subnets)
                      ↓
┌─────────────────────────────────────────────────┐
│  Subnet B: Control Network (ANEL)              │
│  192.168.50.0/24                                │
│                                                 │
│  - ANEL Runner Container                        │
│  - ANEL Power Control Devices                   │
│                                                 │
│  IP Range: 192.168.50.1 - 192.168.50.254       │
└─────────────────────────────────────────────────┘
```

---

## Why Two Subnets?

### Security Isolation
- **Power control devices separated** from main application network
- Reduces attack surface
- Limits blast radius of potential security breaches

### Network Segmentation
- **Different VLANs** or physical networks
- Control network can have stricter access policies
- Easier to implement network-level security controls

### UDP Broadcast Domain
- **ANEL broadcasts stay contained** within control network
- No broadcast traffic in main application network
- Cleaner network architecture

### Access Control
- **Only ANEL runner** has access to control devices
- Main service cannot directly access ANEL devices
- One-way communication pattern (main → runner)

---

## Deployment Scenarios

### Scenario 1: Two Physical Hosts (Recommended)

**Host 1 - Main Application Server:**
- Network: 192.168.1.0/24
- IP: 192.168.1.10
- Runs: Main service, PostgreSQL, Frontend

**Host 2 - Control Network Server:**
- Network: 192.168.50.0/24
- IP: 192.168.50.2
- Runs: ANEL runner only

**Advantages:**
- Complete physical separation
- Independent hardware for control network
- Easy to secure control network with separate switch/firewall
- No shared resources between application and control

**Network Configuration:**
```bash
# Host 1 (192.168.1.10)
Interface: eth0
IP: 192.168.1.10/24
Gateway: 192.168.1.1
Route to control network: 192.168.50.0/24 via 192.168.1.1

# Host 2 (192.168.50.2)
Interface: eth0
IP: 192.168.50.2/24
Gateway: 192.168.50.1
No route to main network needed (one-way communication)
```

---

### Scenario 2: Single Host with Two NICs

**Single Host with Multiple Network Interfaces:**
- NIC 1 (eth0): 192.168.1.10/24 - Main application network
- NIC 2 (eth1): 192.168.50.2/24 - Control network

**Runs:**
- Main service, PostgreSQL, Frontend (on eth0)
- ANEL runner (on eth1 with `network_mode: host`)

**Advantages:**
- Single physical server
- Lower hardware cost
- Simpler deployment

**Disadvantages:**
- Shared CPU/memory resources
- Less security isolation
- Control network still accessible from same host

**Network Configuration:**
```bash
# Single host with two interfaces
# eth0: Main network
ip addr add 192.168.1.10/24 dev eth0
ip route add default via 192.168.1.1 dev eth0

# eth1: Control network
ip addr add 192.168.50.2/24 dev eth1
# No default route on eth1 - control network is isolated

# Verify routing
ip route show
# 192.168.1.0/24 dev eth0
# 192.168.50.0/24 dev eth1
```

---

### Scenario 3: VLAN Separation

**Single Physical Network with VLANs:**
- VLAN 10 (192.168.1.0/24): Main application
- VLAN 50 (192.168.50.0/24): Control network

**Network Configuration:**
```bash
# Create VLAN interfaces
ip link add link eth0 name eth0.10 type vlan id 10
ip link add link eth0 name eth0.50 type vlan id 50

# Assign IPs
ip addr add 192.168.1.10/24 dev eth0.10
ip addr add 192.168.50.2/24 dev eth0.50

# Bring up interfaces
ip link set eth0.10 up
ip link set eth0.50 up

# Configure switch for VLAN trunking
# Managed switch must support 802.1Q VLAN tagging
```

---

## Docker Deployment

### Main Service Stack (Subnet A)

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: mutech-postgres
    environment:
      POSTGRES_DB: mutech
      POSTGRES_USER: mutech
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      app-network:
        ipv4_address: 172.20.0.2
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mutech"]
      interval: 10s
      timeout: 5s
      retries: 5

  main-service:
    build: ./mutech-control-service
    container_name: mutech-main
    environment:
      DATABASE_URL: postgresql://mutech:${DB_PASSWORD}@postgres:5432/mutech
      ANEL_API_KEY: ${ANEL_API_KEY}
      # ANEL runner on different subnet - use IP address
      ANEL_RUNNER_URL: http://192.168.50.2:8001
    volumes:
      - ./mutech-control-service/config:/app/config
      - ./logs:/app/logs
    ports:
      - "192.168.1.10:8000:8000"  # Bind to main network IP only
    networks:
      app-network:
        ipv4_address: 172.20.0.3
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

  frontend:
    build: ./mutech-control-frontend
    container_name: mutech-frontend
    environment:
      VITE_API_URL: http://192.168.1.10:8000
    ports:
      - "192.168.1.10:80:80"  # Bind to main network IP only
    networks:
      app-network:
        ipv4_address: 172.20.0.4
    depends_on:
      - main-service
    restart: unless-stopped

networks:
  app-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16

volumes:
  postgres_data:
```

**Deployment:**
```bash
# On Host 1 (192.168.1.10)
cd /opt/mutech-control
docker-compose up -d

# Verify services
docker-compose ps
curl http://192.168.1.10:8000/health
```

---

### ANEL Runner (Subnet B)

**docker-compose-anel.yml:**
```yaml
version: '3.8'

services:
  anel-runner:
    build: ./anel-runner-service
    container_name: anel-runner
    environment:
      API_KEY: ${ANEL_API_KEY}
      # Bind to control network interface
      BIND_ADDRESS: 192.168.50.2
      BIND_PORT: 8001
      # UDP configuration for ANEL devices
      UDP_SEND_PORT: 9975
      UDP_RECEIVE_PORT: 9977
      # Logging
      LOG_LEVEL: INFO
    # Use host network to access control network and receive UDP broadcasts
    network_mode: host
    restart: unless-stopped
```

**Deployment:**
```bash
# On Host 2 (192.168.50.2) OR same host with eth1
cd /opt/mutech-control
docker-compose -f docker-compose-anel.yml up -d

# Verify service
docker ps | grep anel-runner
curl http://192.168.50.2:8001/health

# Test UDP listening (from another terminal on same subnet)
nc -u 192.168.50.2 9977
```

---

## Firewall Configuration

### Host 1 Firewall (Main Service)

```bash
# Allow inbound HTTP to main service (from frontend/users)
iptables -A INPUT -p tcp --dport 8000 -s 192.168.1.0/24 -j ACCEPT

# Allow outbound HTTP to ANEL runner (subnet B)
iptables -A OUTPUT -p tcp --dport 8001 -d 192.168.50.2 -j ACCEPT

# Allow PostgreSQL within docker network only
iptables -A INPUT -p tcp --dport 5432 -s 172.20.0.0/16 -j ACCEPT
iptables -A INPUT -p tcp --dport 5432 -j DROP
```

### Host 2 Firewall (ANEL Runner)

```bash
# Allow inbound HTTP from main service only
iptables -A INPUT -p tcp --dport 8001 -s 192.168.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 8001 -j DROP

# Allow UDP for ANEL communication within control network
iptables -A INPUT -p udp --dport 9977 -s 192.168.50.0/24 -j ACCEPT
iptables -A OUTPUT -p udp --dport 9975 -d 192.168.50.0/24 -j ACCEPT

# Block all other traffic from control network to main network
iptables -A OUTPUT -d 192.168.1.0/24 -j DROP
```

### Router/Gateway Configuration

```bash
# On network gateway/router (192.168.1.1 and 192.168.50.1)

# Allow routing between subnets for specific ports only
iptables -A FORWARD -s 192.168.1.0/24 -d 192.168.50.2 -p tcp --dport 8001 -j ACCEPT

# Block all other traffic between subnets
iptables -A FORWARD -s 192.168.1.0/24 -d 192.168.50.0/24 -j DROP
iptables -A FORWARD -s 192.168.50.0/24 -d 192.168.1.0/24 -j DROP
```

---

## Environment Configuration

### .env (Main Service)

```bash
# Database
DB_PASSWORD=your_secure_password_here

# ANEL Runner
ANEL_API_KEY=your_api_key_here
ANEL_RUNNER_URL=http://192.168.50.2:8001

# Service Config
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### .env (ANEL Runner)

```bash
# API Authentication
API_KEY=your_api_key_here

# Network Binding
BIND_ADDRESS=192.168.50.2
BIND_PORT=8001

# UDP Configuration
UDP_SEND_PORT=9975
UDP_RECEIVE_PORT=9977

# Logging
LOG_LEVEL=INFO
```

---

## Verification & Testing

### 1. Network Connectivity Test

```bash
# From Host 1 (main service)
# Test reachability to ANEL runner
ping 192.168.50.2
curl http://192.168.50.2:8001/health

# Should return: {"status": "ok", "listening": true}
```

### 2. ANEL Runner UDP Test

```bash
# On Host 2 (ANEL runner)
# Check if UDP port is listening
netstat -uln | grep 9977

# Should show:
# udp  0.0.0.0:9977  0.0.0.0:*

# Test UDP broadcast reception (requires ANEL device)
# Turn on/off ANEL device manually
# Check runner logs for broadcast reception
docker logs -f anel-runner
# Should see: "Status broadcast: 192.168.50.10:1 = 1"
```

### 3. End-to-End Test

```bash
# From Host 1, test ANEL control via runner
curl -X POST \
  -H "Authorization: Bearer ${ANEL_API_KEY}" \
  http://192.168.50.2:8001/devices/192.168.50.10/on?port=1

# Should return:
# {"success": true, "state": 1, "timestamp": 1234567890}

# Verify state query
curl -H "Authorization: Bearer ${ANEL_API_KEY}" \
  http://192.168.50.2:8001/devices/192.168.50.10/state?port=1

# Should return current state from broadcast cache
```

### 4. Main Service Integration Test

```bash
# Test through main service API
curl -X POST http://192.168.1.10:8000/api/control/device/{device_id}/on

# Check main service logs
docker logs -f mutech-main

# Should see ANEL runner communication logs
```

---

## Troubleshooting

### ANEL Runner Cannot Receive Broadcasts

**Symptom:** ANEL runner logs show no broadcasts received

**Checks:**
```bash
# 1. Verify network interface
ip addr show
# Ensure 192.168.50.2 is present

# 2. Verify UDP port binding
netstat -uln | grep 9977

# 3. Test broadcast reception manually
tcpdump -i eth1 udp port 9977

# 4. Check firewall rules
iptables -L -n -v | grep 9977

# 5. Verify ANEL devices are broadcasting
# Check device config - some need broadcast enabled
```

**Solution:**
- Ensure `network_mode: host` in docker-compose
- Verify host has interface on 192.168.50.0/24
- Check ANEL device broadcast settings
- Verify no firewall blocking UDP 9977

### Main Service Cannot Reach ANEL Runner

**Symptom:** Timeout errors when main service calls ANEL runner

**Checks:**
```bash
# 1. From main service container
docker exec -it mutech-main ping 192.168.50.2

# 2. Test HTTP connectivity
docker exec -it mutech-main curl http://192.168.50.2:8001/health

# 3. Check routing
docker exec -it mutech-main ip route

# 4. Verify runner is listening
curl http://192.168.50.2:8001/health  # From host
```

**Solution:**
- Add route on Host 1: `ip route add 192.168.50.0/24 via <gateway>`
- Verify router forwards traffic between subnets
- Check firewall rules allow TCP 8001 from 192.168.1.0/24
- Ensure ANEL runner container is running: `docker ps`

### Docker Network Issues

**Symptom:** Containers cannot communicate

**Checks:**
```bash
# 1. Verify Docker networks
docker network ls
docker network inspect mutech_app-network

# 2. Check container IPs
docker inspect mutech-main | grep IPAddress
docker inspect mutech-postgres | grep IPAddress

# 3. Test internal connectivity
docker exec -it mutech-main ping postgres
```

**Solution:**
- Restart Docker daemon: `systemctl restart docker`
- Recreate networks: `docker-compose down && docker-compose up -d`
- Check Docker network driver: `docker network inspect mutech_app-network`

---

## Security Best Practices

### 1. API Key Rotation
```bash
# Generate strong API key
openssl rand -base64 32

# Update .env files on both hosts
# Restart services
docker-compose restart
```

### 2. Network Isolation
- Use separate physical switches for each subnet
- Configure VLAN ACLs to prevent cross-VLAN communication
- Implement firewall rules at router level

### 3. Access Control
- Restrict SSH access to specific IPs
- Use VPN for remote administration
- Implement fail2ban for brute force protection

### 4. Monitoring
- Log all ANEL runner API calls
- Alert on failed authentication attempts
- Monitor UDP broadcast traffic for anomalies

---

## Production Checklist

- [ ] **Network configured** with two subnets (192.168.1.0/24, 192.168.50.0/24)
- [ ] **Routing configured** between subnets
- [ ] **Firewall rules** implemented and tested
- [ ] **Docker installed** on both hosts
- [ ] **Environment files** created with secure credentials
- [ ] **SSL/TLS certificates** obtained (if exposing to internet)
- [ ] **Database backups** configured
- [ ] **Monitoring** set up (Prometheus/Grafana)
- [ ] **Logging** aggregation configured (ELK stack)
- [ ] **ANEL devices** configured with correct IP addresses
- [ ] **ANEL broadcast** verified working
- [ ] **End-to-end tests** passed
- [ ] **Documentation** updated with actual IPs and config

---

## Maintenance

### Updating Services

```bash
# Main service update (Host 1)
cd /opt/mutech-control
git pull
docker-compose build
docker-compose up -d

# ANEL runner update (Host 2)
cd /opt/mutech-control
git pull
docker-compose -f docker-compose-anel.yml build
docker-compose -f docker-compose-anel.yml up -d
```

### Backup & Restore

```bash
# Database backup
docker exec mutech-postgres pg_dump -U mutech mutech > backup.sql

# Config backup
tar -czf config-backup.tar.gz mutech-control-service/config

# Restore database
docker exec -i mutech-postgres psql -U mutech mutech < backup.sql
```

---

**Last Updated:** 2026-01-12
**Status:** Deployment Architecture Complete
**Contact:** System Administrator
