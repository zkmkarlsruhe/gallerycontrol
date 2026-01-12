# MuTech Control System - Quick Reference Card

## Essential Commands

### Starting the System

```bash
# First time setup
cp .env.example .env
nano .env  # Edit DB_PASSWORD and ANEL_API_KEY

# Start services
docker-compose up --build -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f main-service
```

### Stopping the System

```bash
# Stop services
docker-compose stop

# Stop and remove containers (keeps data)
docker-compose down

# Stop and remove everything (DELETES ALL DATA)
docker-compose down -v
```

### Health Checks

```bash
# Check main service
curl http://localhost:8000/health

# Check system info
curl http://localhost:8000/info

# Check ANEL runner
curl http://localhost:8001/health
```

### Common Operations

```bash
# Turn on exhibition
curl -X POST http://localhost:8000/api/control/exhibition/{ID}/on

# Turn off exhibition
curl -X POST http://localhost:8000/api/control/exhibition/{ID}/off

# Get device state
curl http://localhost:8000/api/state/device/{ID}

# Fast lane control (no verification)
curl -X POST http://localhost:8000/api/fast/device/{ID}/on
```

### Database Access

```bash
# Connect to database
docker-compose exec postgres psql -U mutech -d mutech

# Check device count
docker-compose exec postgres psql -U mutech -d mutech -c "SELECT COUNT(*) FROM devices;"

# View recent commands
docker-compose exec postgres psql -U mutech -d mutech -c "
SELECT d.name, cl.command, cl.success, cl.timestamp
FROM command_log cl
JOIN devices d ON d.id = cl.device_id
ORDER BY cl.timestamp DESC LIMIT 10;"
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Main service only
docker-compose logs -f main-service

# Last 100 lines
docker-compose logs --tail=100 main-service

# Errors only
docker-compose logs main-service | grep ERROR

# Verification tasks
docker-compose logs main-service | grep verification
```

### Configuration

```bash
# Edit configuration
nano mutech-control-service/config/default.yaml

# Reload configuration (hot-reload)
curl -X POST http://localhost:8000/api/admin/config/reload

# Or restart service
docker-compose restart main-service
```

### Troubleshooting

```bash
# Check Docker status
docker-compose ps

# Check container logs
docker-compose logs main-service

# Check disk space
df -h
docker system df

# Clean up Docker
docker system prune -af

# Restart everything
docker-compose restart

# Rebuild from scratch
docker-compose down
docker-compose up --build
```

### Backup & Restore

```bash
# Backup database
docker-compose exec postgres pg_dump -U mutech mutech > backup_$(date +%Y%m%d).sql

# Restore database
docker-compose exec -T postgres psql -U mutech mutech < backup_20240112.sql

# Backup volumes
docker run --rm -v workspace_postgres_data:/data -v $(pwd):/backup ubuntu tar czf /backup/postgres_backup.tar.gz /data
```

### Testing

```bash
# Run test suite
./scripts/test_system.sh

# Test specific endpoint
curl http://localhost:8000/health

# Test with real device
curl -X POST http://localhost:8000/api/control/device/{ID}/on
```

## Common Issues

| Issue | Solution |
|-------|----------|
| Service won't start | Check logs: `docker-compose logs main-service` |
| Can't connect to database | Wait for healthcheck: `docker-compose ps postgres` |
| Device not responding | Check cooldown: `SELECT next_check_allowed_at FROM devices WHERE id='...'` |
| Config changes not applied | Reload: `curl -X POST localhost:8000/api/admin/config/reload` |
| ANEL runner not accessible | It uses host network mode - access via localhost:8001 |

## State Values

| Value | Meaning |
|-------|---------|
| -1 | Error |
| 0 | Off |
| 1 | On |
| 2 | Cooling (projector) |
| 3 | Warming (projector) |

## Device Types

| Type | Description | Port |
|------|-------------|------|
| `pjlink` | PJLink projectors | Usually 4352 |
| `netio` | NETIO power outlets | Usually 80 |
| `anel` | ANEL power outlets | Usually 75 |
| `shell` | Shell command execution | N/A |

## API Endpoints

### Control (Web UI - with verification)
- `POST /api/control/exhibition/{id}/on`
- `POST /api/control/exhibition/{id}/off`
- `POST /api/control/artwork/{id}/on`
- `POST /api/control/artwork/{id}/off`
- `POST /api/control/device/{id}/on`
- `POST /api/control/device/{id}/off`

### Fast Lane (External triggers - no verification)
- `POST /api/fast/device/{id}/on`
- `POST /api/fast/device/{id}/off`
- `GET /api/fast/device/{id}/state`

### State Queries
- `GET /api/state/exhibitions`
- `GET /api/state/exhibition/{id}`
- `GET /api/state/device/{id}`

### Admin CRUD
- `GET|POST|PUT|DELETE /api/admin/exhibitions`
- `GET|POST|PUT|DELETE /api/admin/artworks`
- `GET|POST|PUT|DELETE /api/admin/devices`
- `POST /api/admin/config/reload`

## File Locations

| File | Purpose |
|------|---------|
| `/workspace/.env` | Environment variables |
| `/workspace/docker-compose.yml` | Service orchestration |
| `/workspace/mutech-control-service/config/default.yaml` | Main configuration |
| `/workspace/scripts/test_system.sh` | Test suite |
| `/workspace/scripts/migrate_sqlite_to_postgres.py` | Data migration |

## Documentation

- `README.md` - Project overview
- `GETTING_STARTED.md` - Setup guide
- `API_REFERENCE.md` - API documentation
- `TROUBLESHOOTING.md` - Common issues
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- `PRODUCTION_DEPLOYMENT.md` - Deployment checklist

## Interactive API Documentation

- http://localhost:8000/docs - Swagger UI
- http://localhost:8000/redoc - ReDoc

## Monitoring

```bash
# Watch for errors
docker-compose logs -f main-service | grep -E "(ERROR|WARNING)"

# Monitor verification
docker-compose logs -f main-service | grep verification

# Check command success rate
docker-compose exec postgres psql -U mutech -d mutech -c "
SELECT
  source,
  COUNT(*) as total,
  SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
  ROUND(100.0 * SUM(CASE WHEN success THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM command_log
WHERE timestamp > NOW() - INTERVAL '1 hour'
GROUP BY source;"
```

## Emergency Contacts

- System Administrator: __________
- On-call Engineer: __________
- Escalation: __________

## Version Info

- Current Version: 1.0.0
- Last Updated: 2024-01-12
- Documentation: http://localhost:8000/docs

---

**For detailed documentation, see the full guides in `/workspace/`**
