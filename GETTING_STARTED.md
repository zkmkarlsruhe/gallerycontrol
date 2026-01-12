# MuTech Control System - Getting Started Guide

This guide will help you get the MuTech Control System up and running in Docker.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- At least 2GB free RAM
- Network access to your devices (PJLink projectors, NETIO outlets, ANEL outlets)

## Quick Start

### 1. Clone and Setup

```bash
# Navigate to the project directory
cd /workspace

# Copy the example environment file
cp .env.example .env

# Edit the .env file with your values
nano .env
```

### 2. Configure Environment Variables

Edit `.env` and set:

```bash
# REQUIRED: Set a secure database password
DB_PASSWORD=your_secure_password_here

# REQUIRED: Set a secure API key for ANEL runner
ANEL_API_KEY=your_secure_api_key_here

# OPTIONAL: Adjust log level if needed
LOG_LEVEL=INFO

# OPTIONAL: Set environment
ENVIRONMENT=production
```

### 3. Start the Services

```bash
# Build and start all services
docker-compose up --build

# Or run in detached mode (background)
docker-compose up --build -d
```

### 4. Verify Services Are Running

```bash
# Check service status
docker-compose ps

# Check main service health
curl http://localhost:8000/health

# Check main service info
curl http://localhost:8000/info

# Check ANEL runner health (if you can access host network)
curl http://localhost:8001/health
```

### 5. Access the API Documentation

Open your browser and navigate to:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Initial Setup

### Option 1: Migrate from Existing SQLite Database

If you have an existing SQLite database from the old Node.js system:

```bash
# Copy your old mutech.db file to the workspace
cp /path/to/old/mutech.db /workspace/

# Run the migration script
docker-compose exec main-service python scripts/migrate_sqlite_to_postgres.py /app/mutech.db
```

### Option 2: Create New Data via Admin API

Use the admin API to create your exhibitions, artworks, and devices:

```bash
# Create an exhibition
curl -X POST http://localhost:8000/api/admin/exhibitions \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Main Exhibition",
    "enabled": true
  }'

# Create an artwork (use the exhibition ID from above)
curl -X POST http://localhost:8000/api/admin/artworks \
  -H "Content-Type: application/json" \
  -d '{
    "exhibition_id": "EXHIBITION_ID_HERE",
    "name": "Interactive Display",
    "enabled": true
  }'

# Create a device (use the artwork ID from above)
curl -X POST http://localhost:8000/api/admin/devices \
  -H "Content-Type: application/json" \
  -d '{
    "artwork_id": "ARTWORK_ID_HERE",
    "name": "Projector 1",
    "device_type": "pjlink",
    "host": "192.168.1.100",
    "port": 4352,
    "enabled": true,
    "automation_enabled": true,
    "exclude_from_auto_onoff": false,
    "config": {
      "password": "projector_password"
    }
  }'
```

## Device Configuration Examples

### PJLink Projector

```json
{
  "artwork_id": "ARTWORK_ID",
  "name": "Main Projector",
  "device_type": "pjlink",
  "host": "192.168.1.100",
  "port": 4352,
  "enabled": true,
  "automation_enabled": true,
  "exclude_from_auto_onoff": false,
  "config": {
    "password": "pjlink_password"
  }
}
```

### NETIO Power Outlet

```json
{
  "artwork_id": "ARTWORK_ID",
  "name": "Power Strip 1",
  "device_type": "netio",
  "host": "192.168.1.101",
  "port": 80,
  "enabled": true,
  "automation_enabled": true,
  "exclude_from_auto_onoff": false,
  "config": {
    "username": "admin",
    "password": "netio_password",
    "port_number": 1
  }
}
```

### ANEL Power Outlet

```json
{
  "artwork_id": "ARTWORK_ID",
  "name": "ANEL Outlet 1",
  "device_type": "anel",
  "host": "192.168.2.100",
  "port": 75,
  "enabled": true,
  "automation_enabled": true,
  "exclude_from_auto_onoff": false,
  "config": {
    "username": "admin",
    "password": "anel_password",
    "port_number": 1
  }
}
```

### Shell Command

```json
{
  "artwork_id": "ARTWORK_ID",
  "name": "Media Player Control",
  "device_type": "shell",
  "host": "localhost",
  "port": null,
  "enabled": true,
  "automation_enabled": true,
  "exclude_from_auto_onoff": false,
  "config": {
    "commands": {
      "on": {
        "cmd": "systemctl start mediaplayer",
        "timeout": 30
      },
      "off": {
        "cmd": "systemctl stop mediaplayer",
        "timeout": 30
      },
      "status": {
        "cmd": "systemctl status mediaplayer",
        "timeout": 10,
        "onPattern": "active \\(running\\)",
        "offPattern": "inactive|failed"
      }
    }
  }
}
```

### Shell Reboot Command (Excluded from Bulk Operations)

```json
{
  "artwork_id": "ARTWORK_ID",
  "name": "Server Reboot",
  "device_type": "shell",
  "host": "192.168.1.200",
  "port": null,
  "enabled": true,
  "automation_enabled": true,
  "exclude_from_auto_onoff": true,
  "config": {
    "commands": {
      "on": {
        "cmd": "ssh admin@192.168.1.200 'sudo reboot'",
        "timeout": 60
      }
    }
  }
}
```

## Controlling Devices

### Turn On an Exhibition

```bash
curl -X POST http://localhost:8000/api/control/exhibition/EXHIBITION_ID/on
```

This will:
- Send ON commands to all enabled devices
- Stagger commands by 1 second between devices
- Respect device cooldowns
- Skip devices with `exclude_from_auto_onoff=true`

### Turn Off an Exhibition

```bash
curl -X POST http://localhost:8000/api/control/exhibition/EXHIBITION_ID/off
```

This will:
- Broadcast OFF commands to all enabled devices immediately
- Start verification tasks for non-shell devices
- Check every 30 seconds for up to 5 minutes
- Retry OFF command if device reports on/error
- Accept "cooling" state as success for projectors

### Fast Lane Control (No Verification)

```bash
# Fast ON (fire once, no retry)
curl -X POST http://localhost:8000/api/fast/device/DEVICE_ID/on

# Fast OFF (fire once, no verification)
curl -X POST http://localhost:8000/api/fast/device/DEVICE_ID/off

# Fast state query
curl http://localhost:8000/api/fast/device/DEVICE_ID/state
```

### Query Device State

```bash
# Get all exhibitions with full state tree
curl http://localhost:8000/api/state/exhibitions

# Get specific exhibition state
curl http://localhost:8000/api/state/exhibition/EXHIBITION_ID

# Get specific device state
curl http://localhost:8000/api/state/device/DEVICE_ID
```

## Configuration Hot-Reload

The system monitors `config/default.yaml` for changes and reloads automatically.

```bash
# Edit configuration
nano mutech-control-service/config/default.yaml

# Changes are picked up automatically (check logs)
docker-compose logs -f main-service | grep "Configuration changed"
```

You can also manually trigger a reload:

```bash
curl -X POST http://localhost:8000/api/admin/config/reload
```

## Monitoring and Logs

### View Logs

```bash
# All services
docker-compose logs -f

# Main service only
docker-compose logs -f main-service

# ANEL runner only
docker-compose logs -f anel-runner

# PostgreSQL only
docker-compose logs -f postgres

# Last 100 lines
docker-compose logs --tail=100 main-service
```

### Monitor OFF Verification

```bash
# Watch for verification tasks
docker-compose logs -f main-service | grep "verification"

# Watch for cooldown rejections
docker-compose logs -f main-service | grep "Cooldown active"

# Watch for errors
docker-compose logs -f main-service | grep -E "(ERROR|WARNING)"
```

### Database Queries

Connect to PostgreSQL:

```bash
docker-compose exec postgres psql -U mutech -d mutech
```

Useful queries:

```sql
-- Check device states
SELECT name, device_type, state, last_checked_at
FROM devices
WHERE enabled = true
ORDER BY last_checked_at DESC;

-- Check recent commands
SELECT d.name, cl.command, cl.source, cl.success, cl.timestamp
FROM command_log cl
JOIN devices d ON d.id = cl.device_id
ORDER BY cl.timestamp DESC
LIMIT 20;

-- Find devices in error state
SELECT name, device_type, host, state
FROM devices
WHERE state = -1 AND enabled = true;

-- Check excluded devices
SELECT name, device_type, host, exclude_from_auto_onoff
FROM devices
WHERE exclude_from_auto_onoff = true;
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs for errors
docker-compose logs main-service

# Ensure PostgreSQL is healthy
docker-compose ps postgres

# Try rebuilding
docker-compose down
docker-compose up --build
```

### Database Migration Fails

```bash
# Check PostgreSQL connection
docker-compose exec main-service nc -z postgres 5432

# Manually run migration
docker-compose exec main-service alembic upgrade head

# Check migration status
docker-compose exec main-service alembic current
```

### Device Not Responding

1. Check device is enabled: `SELECT * FROM devices WHERE id = 'DEVICE_ID';`
2. Check cooldown: Look for `next_check_allowed_at` timestamp
3. Check command log: `SELECT * FROM command_log WHERE device_id = 'DEVICE_ID' ORDER BY timestamp DESC LIMIT 10;`
4. Test connectivity: `docker-compose exec main-service ping DEVICE_HOST`
5. Check device type configuration in `config/default.yaml`

### ANEL Runner Connection Issues

```bash
# Check ANEL runner is running
docker-compose ps anel-runner

# Check if it can reach ANEL devices (it uses host network)
docker-compose exec anel-runner ping ANEL_DEVICE_IP

# Verify API key is correct
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8001/health
```

### OFF Verification Stuck

Check logs:

```bash
docker-compose logs -f main-service | grep "Device.*verification"
```

If a device fails to verify OFF after 5 minutes:
1. It will be marked as state=-1 (error)
2. Check device connectivity
3. Try manual OFF command via fast lane
4. Check device-specific OFF verification config in `config/default.yaml`

## Stopping the Services

```bash
# Stop services
docker-compose stop

# Stop and remove containers (keeps data)
docker-compose down

# Stop and remove everything including volumes (DELETES ALL DATA)
docker-compose down -v
```

## Backup and Restore

### Backup Database

```bash
# Create backup
docker-compose exec postgres pg_dump -U mutech mutech > backup_$(date +%Y%m%d_%H%M%S).sql

# Or use Docker volume backup
docker run --rm -v workspace_postgres_data:/data -v $(pwd):/backup ubuntu tar czf /backup/postgres_backup.tar.gz /data
```

### Restore Database

```bash
# From SQL dump
docker-compose exec -T postgres psql -U mutech mutech < backup_20240112_120000.sql

# From volume backup
docker run --rm -v workspace_postgres_data:/data -v $(pwd):/backup ubuntu tar xzf /backup/postgres_backup.tar.gz -C /
```

## Next Steps

1. **Build Frontend**: Create React + TypeScript frontend with REST polling
2. **Add Monitoring**: Integrate Prometheus metrics and Grafana dashboards
3. **Add Authentication**: Implement API key or OAuth2 authentication
4. **Production Deployment**: Configure nginx reverse proxy with HTTPS
5. **Add Tests**: Write unit and integration tests

## Support

For issues and questions, refer to:
- `README.md` - Project overview
- `IMPLEMENTATION_SUMMARY.md` - Technical implementation details
- `config/default.yaml` - Configuration options
- API docs at http://localhost:8000/docs

## State Values

Devices can have the following states:
- `-1` - Error state
- `0` - Off
- `1` - On
- `2` - Cooling (projectors only, treated as OFF success)
- `3` - Warming (projectors only)
