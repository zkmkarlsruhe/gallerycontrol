# MuTech Control System - Troubleshooting Guide

Common issues and their solutions.

## Table of Contents

1. [Service Won't Start](#service-wont-start)
2. [Database Issues](#database-issues)
3. [Device Control Problems](#device-control-problems)
4. [ANEL Runner Issues](#anel-runner-issues)
5. [Configuration Problems](#configuration-problems)
6. [Performance Issues](#performance-issues)
7. [OFF Verification Issues](#off-verification-issues)
8. [Docker Issues](#docker-issues)

---

## Service Won't Start

### Symptom: Main service container exits immediately

**Check logs:**
```bash
docker-compose logs main-service
```

**Common causes:**

1. **Database not ready**
   - Wait for PostgreSQL healthcheck to pass
   - Check: `docker-compose ps postgres`
   - Solution: Increase startup wait time in `entrypoint.sh`

2. **Migration failure**
   ```
   Error: Could not connect to database
   ```
   - Check DATABASE_URL in docker-compose.yml
   - Verify PostgreSQL is running: `docker-compose ps postgres`
   - Manually run migration: `docker-compose exec main-service alembic upgrade head`

3. **Missing dependencies**
   ```
   ModuleNotFoundError: No module named 'X'
   ```
   - Rebuild containers: `docker-compose up --build`
   - Check pyproject.toml has all dependencies
   - Clear poetry cache: `docker-compose exec main-service poetry cache clear --all pypi`

4. **Port already in use**
   ```
   Error: Address already in use
   ```
   - Check what's using port 8000: `lsof -i :8000`
   - Stop conflicting service or change port in docker-compose.yml

### Symptom: Service starts but returns 500 errors

**Check application logs:**
```bash
docker-compose logs -f main-service | grep ERROR
```

**Common causes:**

1. **Config file errors**
   - Check `config/default.yaml` syntax
   - Ensure all required environment variables are set
   - Validate YAML: `docker-compose exec main-service python -c "import yaml; yaml.safe_load(open('config/default.yaml'))"`

2. **Database connection issues**
   - Test connection: `docker-compose exec main-service nc -z postgres 5432`
   - Check credentials in .env file
   - Verify PostgreSQL is accepting connections

---

## Database Issues

### Symptom: Migration fails with "relation already exists"

```bash
# Check current migration status
docker-compose exec main-service alembic current

# Mark migrations as applied without running
docker-compose exec main-service alembic stamp head

# Or reset database (DELETES ALL DATA)
docker-compose down -v
docker-compose up --build
```

### Symptom: Cannot connect to PostgreSQL

**From main service:**
```bash
# Test connection
docker-compose exec main-service pg_isready -h postgres -U mutech

# Try manual connection
docker-compose exec postgres psql -U mutech -d mutech

# Check if PostgreSQL is running
docker-compose ps postgres
```

**If PostgreSQL container is failing:**
```bash
# Check logs
docker-compose logs postgres

# Common issues:
# 1. Permission issues on volume
# 2. Corrupted data directory
# 3. Port already in use

# Solution: Reset database (DELETES ALL DATA)
docker-compose down -v
docker-compose up --build
```

### Symptom: Database queries are slow

```sql
-- Connect to database
docker-compose exec postgres psql -U mutech -d mutech

-- Check for missing indexes
SELECT schemaname, tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public';

-- Check table sizes
SELECT
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;

-- Analyze tables
ANALYZE;
```

### Symptom: Database is filling up disk space

```bash
# Check database size
docker-compose exec postgres psql -U mutech -d mutech -c "\l+"

# Check command_log table size
docker-compose exec postgres psql -U mutech -d mutech -c "
SELECT pg_size_pretty(pg_total_relation_size('command_log'));
"

# Clean old command logs (older than 30 days)
docker-compose exec postgres psql -U mutech -d mutech -c "
DELETE FROM command_log WHERE timestamp < NOW() - INTERVAL '30 days';
"

# Vacuum database
docker-compose exec postgres psql -U mutech -d mutech -c "VACUUM ANALYZE;"
```

---

## Device Control Problems

### Symptom: Device not responding to commands

**1. Check device is enabled:**
```bash
docker-compose exec postgres psql -U mutech -d mutech -c "
SELECT id, name, device_type, enabled, exclude_from_auto_onoff
FROM devices WHERE name LIKE '%device_name%';
"
```

**2. Check cooldown status:**
```bash
docker-compose exec postgres psql -U mutech -d mutech -c "
SELECT id, name, last_checked_at, next_check_allowed_at
FROM devices WHERE name LIKE '%device_name%'
  AND next_check_allowed_at > NOW();
"
```

If `next_check_allowed_at` is in the future, the device is in cooldown.

**3. Check command log for errors:**
```bash
docker-compose exec postgres psql -U mutech -d mutech -c "
SELECT timestamp, command, source, success, error_message
FROM command_log
WHERE device_id = 'DEVICE_ID'
ORDER BY timestamp DESC LIMIT 10;
"
```

**4. Test device connectivity:**

For PJLink:
```bash
docker-compose exec main-service telnet DEVICE_IP 4352
```

For NETIO:
```bash
docker-compose exec main-service curl http://DEVICE_IP
```

For Shell:
```bash
docker-compose exec main-service bash -c "SHELL_COMMAND"
```

### Symptom: PJLink projector reports "blocked" or timeouts

**Cause:** PJLink protocol is brittle and blocks after too many rapid requests.

**Solution:**

1. **Increase cooldown:**
   Edit `config/default.yaml`:
   ```yaml
   device_types:
     pjlink:
       cooldown_seconds: 60  # Increase from 30
       request_timeout: 15   # Increase from 10
   ```

2. **Reload config:**
   ```bash
   curl -X POST http://localhost:8000/api/admin/config/reload
   ```

3. **Power cycle the projector** (sometimes the only solution)

4. **Check projector logs** if accessible

### Symptom: Shell commands failing

**1. Check command syntax:**
```bash
docker-compose exec main-service bash -c "EXACT_COMMAND_FROM_CONFIG"
```

**2. Check command permissions:**
- Does the container have permission to execute?
- Does SSH key authentication work?
- Are sudo permissions configured?

**3. Common shell command issues:**

```yaml
# BAD: Uses single quotes (variables won't expand)
"cmd": "echo 'Device state: $STATE'"

# GOOD: Uses double quotes
"cmd": "echo \"Device state: $STATE\""

# BAD: Complex command without proper escaping
"cmd": "ssh user@host 'systemctl status service | grep running'"

# GOOD: Escaped properly
"cmd": "ssh user@host 'systemctl status service | grep running'"
```

### Symptom: NETIO device not responding

**1. Check device is reachable:**
```bash
docker-compose exec main-service ping NETIO_IP
docker-compose exec main-service curl http://NETIO_IP
```

**2. Check credentials:**
```bash
# Get device config from database
docker-compose exec postgres psql -U mutech -d mutech -c "
SELECT config FROM devices WHERE host = 'NETIO_IP';
"
```

**3. Check port number:**
- NETIO devices have multiple outlets (usually 1-4)
- Ensure `config.port_number` matches the physical outlet

### Symptom: Device excluded from bulk ON/OFF but shouldn't be

**Check exclusion flag:**
```bash
docker-compose exec postgres psql -U mutech -d mutech -c "
SELECT id, name, device_type, exclude_from_auto_onoff
FROM devices WHERE name LIKE '%device_name%';
"
```

**Update flag:**
```bash
curl -X PUT http://localhost:8000/api/admin/devices/DEVICE_ID \
  -H "Content-Type: application/json" \
  -d '{"exclude_from_auto_onoff": false}'
```

---

## ANEL Runner Issues

### Symptom: Cannot reach ANEL runner

**ANEL runner uses host network mode**, so it's not accessible via Docker network.

**1. Check ANEL runner is running:**
```bash
docker-compose ps anel-runner
```

**2. Check from host machine:**
```bash
curl http://localhost:8001/health
```

**3. Check from main service:**
```bash
# This will FAIL because host network mode
docker-compose exec main-service curl http://anel-runner:8001/health

# Use host IP or localhost instead (if on same machine)
docker-compose exec main-service curl http://host.docker.internal:8001/health
```

**4. Fix in docker-compose.yml:**
```yaml
services:
  main-service:
    environment:
      ANEL_RUNNER_URL: http://host.docker.internal:8001  # or http://HOST_IP:8001
```

### Symptom: ANEL runner cannot reach devices

**1. ANEL uses UDP broadcast** - must be on same network segment

**2. Check network configuration:**
```bash
# From ANEL runner container
docker-compose exec anel-runner ip addr
docker-compose exec anel-runner ip route
```

**3. Test ANEL device reachability:**
```bash
docker-compose exec anel-runner ping ANEL_DEVICE_IP
```

**4. Check firewall rules:**
- UDP port 75 must be open
- Broadcast packets must be allowed

### Symptom: ANEL runner authentication failures

**1. Check API key is set:**
```bash
# In .env file
cat .env | grep ANEL_API_KEY
```

**2. Test authentication:**
```bash
# Should fail (401)
curl http://localhost:8001/health

# Should succeed (200)
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8001/health
```

**3. Verify main service has correct key:**
```bash
docker-compose exec main-service env | grep ANEL_API_KEY
```

---

## Configuration Problems

### Symptom: Config changes not taking effect

**1. Check config file syntax:**
```bash
docker-compose exec main-service python -c "
import yaml
with open('config/default.yaml') as f:
    config = yaml.safe_load(f)
    print('Config loaded successfully')
"
```

**2. Check file watcher is running:**
```bash
docker-compose logs main-service | grep "Configuration hot-reload enabled"
```

**3. Manually trigger reload:**
```bash
curl -X POST http://localhost:8000/api/admin/config/reload
```

**4. Check logs for reload:**
```bash
docker-compose logs -f main-service | grep "Configuration changed"
```

**5. If hot-reload not working, restart service:**
```bash
docker-compose restart main-service
```

### Symptom: Environment variables not substituted

**Config file:**
```yaml
database:
  password: ${DB_PASSWORD}  # Correct
  # password: $DB_PASSWORD   # Wrong - missing braces
```

**Check substitution:**
```bash
docker-compose exec main-service python -c "
from mutech_control.config import get_config
config = get_config()
print('DB Password:', config.get('database.password'))
"
```

---

## Performance Issues

### Symptom: Slow API responses

**1. Check database query performance:**
```sql
-- Enable query logging
ALTER DATABASE mutech SET log_statement = 'all';
ALTER DATABASE mutech SET log_duration = on;

-- Check slow queries in logs
docker-compose logs postgres | grep "duration:"
```

**2. Check for missing indexes:**
```sql
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname = 'public'
  AND tablename IN ('devices', 'artworks', 'exhibitions')
ORDER BY abs(correlation) DESC;
```

**3. Check connection pool:**
```yaml
# In config/default.yaml
database:
  pool_size: 20  # Increase if needed
  max_overflow: 10
```

**4. Check for verification tasks:**
```bash
# Too many verification tasks can slow things down
docker-compose logs main-service | grep "verification" | wc -l
```

### Symptom: High memory usage

**1. Check for memory leaks:**
```bash
# Monitor memory usage
docker stats main-service

# Check for growing process memory
docker-compose exec main-service ps aux
```

**2. Common causes:**
- Too many active verification tasks
- Connection pool not being cleaned up
- Large command_log table

**3. Solutions:**
```bash
# Clean old command logs
docker-compose exec postgres psql -U mutech -d mutech -c "
DELETE FROM command_log WHERE timestamp < NOW() - INTERVAL '7 days';
"

# Restart service to clear memory
docker-compose restart main-service
```

### Symptom: Device stagger too slow for large exhibitions

**Current:** 1 second × 500 devices = 8.3 minutes to turn on

**Solution 1: Reduce stagger delay**
```yaml
# In config/default.yaml
orchestrator:
  on_stagger_delay_seconds: 0.5  # Reduce from 1.0
```

**Solution 2: Increase concurrency**
```yaml
orchestrator:
  max_concurrent_on_commands: 20  # Increase from 10
```

**Trade-offs:**
- Faster = higher power spike risk
- More concurrent = more network load

---

## OFF Verification Issues

### Symptom: Devices not verifying OFF

**1. Check verification is enabled:**
```yaml
# In config/default.yaml
orchestrator:
  enable_off_verification: true
```

**2. Check verification tasks in logs:**
```bash
docker-compose logs -f main-service | grep "verification"
```

**3. Check device-specific verification config:**
```yaml
device_types:
  pjlink:
    off_verify:
      interval_seconds: 30
      max_duration_seconds: 300  # 5 minutes
      retry_on_states: [1, -1]   # on or error
      success_states: [0, 2]      # off or cooling
```

**4. Check command log for verification attempts:**
```sql
SELECT timestamp, command, source, success, error_message
FROM command_log
WHERE device_id = 'DEVICE_ID' AND source = 'verification'
ORDER BY timestamp DESC;
```

### Symptom: Verification tasks never complete

**1. Device may be stuck in error state:**
```sql
SELECT id, name, state, last_checked_at
FROM devices
WHERE state = -1;  -- Error state
```

**2. Manually reset device state:**
```sql
UPDATE devices SET state = 0 WHERE id = 'DEVICE_ID';
```

**3. Check max duration:**
```yaml
device_types:
  pjlink:
    off_verify:
      max_duration_seconds: 300  # Increase if needed
```

### Symptom: Projector stuck in "cooling" state

**This is normal!** Projectors take time to cool down.

**Configuration:**
```yaml
device_types:
  pjlink:
    off_verify:
      success_states: [0, 2]  # 2 = cooling (treated as success)
```

**Check it's working:**
```bash
docker-compose logs main-service | grep "verified OFF"
```

---

## Docker Issues

### Symptom: "No space left on device"

**1. Clean Docker:**
```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove unused containers
docker container prune

# Nuclear option (removes EVERYTHING not running)
docker system prune -a --volumes
```

**2. Check disk usage:**
```bash
docker system df
df -h
```

### Symptom: "Cannot remove container" or similar errors

**1. Stop all services:**
```bash
docker-compose down

# Force remove if needed
docker-compose down -v --remove-orphans
```

**2. Remove stuck containers:**
```bash
docker ps -a | grep mutech
docker rm -f CONTAINER_ID
```

### Symptom: Changes to code not reflected

**1. Rebuild without cache:**
```bash
docker-compose build --no-cache
docker-compose up
```

**2. Check volumes aren't mounted:**
```yaml
# In docker-compose.yml, remove volume mounts for code:
# volumes:
#   - ./mutech-control-service/mutech_control:/app/mutech_control  # Remove this
```

---

## Getting Help

If none of these solutions work:

1. **Collect diagnostic information:**
```bash
# System info
docker-compose version
docker version

# Service status
docker-compose ps

# Recent logs
docker-compose logs --tail=100 > logs.txt

# Database schema
docker-compose exec postgres pg_dump -U mutech -s mutech > schema.sql
```

2. **Check documentation:**
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- `API_REFERENCE.md` - API documentation
- `GETTING_STARTED.md` - Setup guide

3. **Enable debug logging:**
```yaml
# In config/default.yaml
logging:
  level: "DEBUG"
```

```bash
docker-compose restart main-service
docker-compose logs -f main-service
```

4. **Test with test script:**
```bash
./scripts/test_system.sh
```

---

## Common Error Messages

### "Cooldown active until..."

**Cause:** Device was recently queried/controlled
**Solution:** Wait for cooldown period or disable cooldown in config

### "Device not found"

**Cause:** Device ID invalid or device deleted
**Solution:** Check device exists: `GET /api/admin/devices`

### "Connection refused"

**Cause:** Device network unreachable
**Solution:** Check device IP, firewall, network segmentation

### "Authentication failed"

**Cause:** Wrong credentials in device config
**Solution:** Update device config with correct credentials

### "Command timeout"

**Cause:** Device not responding or command takes too long
**Solution:** Increase timeout in device config or check device health

---

## Prevention Best Practices

1. **Regular database cleanup:**
   ```bash
   # Add to cron
   0 0 * * 0 docker-compose exec postgres psql -U mutech -d mutech -c "DELETE FROM command_log WHERE timestamp < NOW() - INTERVAL '30 days';"
   ```

2. **Monitor disk space:**
   ```bash
   df -h
   docker system df
   ```

3. **Regular backups:**
   ```bash
   docker-compose exec postgres pg_dump -U mutech mutech > backup_$(date +%Y%m%d).sql
   ```

4. **Test configuration changes in dev first:**
   ```yaml
   # Use different environment
   ENVIRONMENT=development docker-compose up
   ```

5. **Monitor logs regularly:**
   ```bash
   docker-compose logs -f main-service | grep -E "(ERROR|WARNING)"
   ```
