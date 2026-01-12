# MuTech Control System - Production Deployment Checklist

Complete checklist for deploying to production.

## Pre-Deployment

### 1. Environment Preparation

- [ ] Production server meets minimum requirements:
  - [ ] Docker Engine 20.10+
  - [ ] Docker Compose 2.0+
  - [ ] 4GB+ RAM
  - [ ] 20GB+ disk space
  - [ ] Network access to all device types

- [ ] DNS/domain configured (if applicable)
- [ ] SSL certificates obtained (if using HTTPS)
- [ ] Firewall rules configured
- [ ] Backup strategy defined

### 2. Configuration

- [ ] Create production `.env` file:
  ```bash
  cp .env.example .env
  nano .env
  ```

- [ ] Set secure credentials in `.env`:
  - [ ] `DB_PASSWORD` - Strong database password (20+ chars)
  - [ ] `ANEL_API_KEY` - Secure API key (UUID or 32+ char random)
  - [ ] `ENVIRONMENT=production`
  - [ ] `LOG_LEVEL=INFO` (or `WARNING` for less verbose)

- [ ] Review `config/default.yaml`:
  - [ ] Adjust cooldown timings for your devices
  - [ ] Set appropriate stagger delays
  - [ ] Configure OFF verification intervals
  - [ ] Set CORS origins (if using frontend)

- [ ] Create production config override (optional):
  ```yaml
  # config/production.yaml
  server:
    reload: false

  logging:
    level: "WARNING"

  orchestrator:
    on_stagger_delay_seconds: 1.0
    max_concurrent_on_commands: 10
  ```

### 3. Security Hardening

- [ ] Change default passwords in `.env`
- [ ] Restrict CORS origins in `config/default.yaml`:
  ```yaml
  api:
    cors_origins:
      - "https://your-frontend-domain.com"
  ```

- [ ] Set up reverse proxy (nginx/traefik) for HTTPS
- [ ] Configure firewall:
  ```bash
  # Allow only necessary ports
  ufw allow 80/tcp    # HTTP (if using)
  ufw allow 443/tcp   # HTTPS
  ufw allow 22/tcp    # SSH
  ufw enable
  ```

- [ ] Enable Docker security features:
  ```yaml
  # docker-compose.yml
  services:
    main-service:
      security_opt:
        - no-new-privileges:true
      read_only: true
      tmpfs:
        - /tmp
  ```

- [ ] Consider encrypting device credentials in database
- [ ] Set up log rotation

### 4. Data Migration

If migrating from existing system:

- [ ] Backup old database:
  ```bash
  cp /path/to/old/mutech.db /backup/mutech_$(date +%Y%m%d).db
  ```

- [ ] Copy old database to server
- [ ] Test migration on staging first:
  ```bash
  docker-compose up -d postgres
  docker-compose exec main-service python scripts/migrate_sqlite_to_postgres.py /path/to/mutech.db
  ```

- [ ] Verify migrated data:
  ```bash
  docker-compose exec postgres psql -U mutech -d mutech -c "
  SELECT
    (SELECT COUNT(*) FROM exhibitions) as exhibitions,
    (SELECT COUNT(*) FROM artworks) as artworks,
    (SELECT COUNT(*) FROM devices) as devices;
  "
  ```

If starting fresh:

- [ ] Plan exhibition/artwork/device hierarchy
- [ ] Prepare device configuration data
- [ ] Create bulk import script if needed

## Deployment

### 1. Initial Deployment

- [ ] Clone repository to production server:
  ```bash
  git clone <repository-url> /opt/mutech-control
  cd /opt/mutech-control
  ```

- [ ] Copy environment files:
  ```bash
  cp .env.example .env
  # Edit .env with production values
  ```

- [ ] Pull/build images:
  ```bash
  docker-compose pull  # If using pre-built images
  # OR
  docker-compose build --no-cache  # If building locally
  ```

- [ ] Start services:
  ```bash
  docker-compose up -d
  ```

- [ ] Check services are running:
  ```bash
  docker-compose ps
  docker-compose logs -f
  ```

- [ ] Wait for migrations to complete:
  ```bash
  docker-compose logs main-service | grep "migration"
  ```

- [ ] Verify health:
  ```bash
  curl http://localhost:8000/health
  curl http://localhost:8000/info
  ```

### 2. Load Data

Option A - Migrate from old system:
```bash
docker-compose exec main-service python scripts/migrate_sqlite_to_postgres.py /app/old_mutech.db
```

Option B - Create via API:
```bash
# Use API_REFERENCE.md for examples
./scripts/create_devices.sh  # Your custom script
```

### 3. Verification

- [ ] Run test suite:
  ```bash
  ./scripts/test_system.sh
  ```

- [ ] Test each device type:
  - [ ] PJLink projector ON/OFF
  - [ ] NETIO outlet ON/OFF
  - [ ] ANEL outlet ON/OFF (check network segment)
  - [ ] Shell command execution

- [ ] Test bulk operations:
  - [ ] Turn on artwork (multiple devices)
  - [ ] Turn off artwork with verification
  - [ ] Turn on exhibition (all devices)
  - [ ] Turn off exhibition

- [ ] Test exclusion flag:
  - [ ] Verify shell reboot devices excluded from bulk ops
  - [ ] Manual control still works

- [ ] Test cooldowns:
  - [ ] Rapid requests rejected during cooldown
  - [ ] Cooldown timing matches config

- [ ] Test OFF verification:
  - [ ] Verification tasks start after OFF command
  - [ ] Check every 30 seconds (or configured interval)
  - [ ] Retry if device reports on/error
  - [ ] Accept cooling state as success (projectors)
  - [ ] Give up after 5 minutes (or configured max)

- [ ] Test config hot-reload:
  ```bash
  # Edit config/default.yaml
  # Watch logs for reload confirmation
  docker-compose logs -f main-service | grep "Configuration changed"
  ```

### 4. Reverse Proxy Setup (Optional but Recommended)

Example nginx configuration:

```nginx
# /etc/nginx/sites-available/mutech-control
server {
    listen 80;
    server_name mutech.example.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name mutech.example.com;

    ssl_certificate /etc/letsencrypt/live/mutech.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mutech.example.com/privkey.pem;

    # API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Docs
    location /docs {
        proxy_pass http://localhost:8000;
    }

    # Frontend (when implemented)
    location / {
        root /var/www/mutech-frontend/dist;
        try_files $uri $uri/ /index.html;
    }
}
```

Enable and restart:
```bash
ln -s /etc/nginx/sites-available/mutech-control /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

## Post-Deployment

### 1. Monitoring Setup

- [ ] Set up log monitoring:
  ```bash
  # Create log monitoring script
  cat > /usr/local/bin/mutech-monitor.sh << 'EOF'
  #!/bin/bash
  cd /opt/mutech-control
  docker-compose logs --since 5m main-service | grep -E "(ERROR|WARNING)" > /var/log/mutech-errors.log
  EOF

  chmod +x /usr/local/bin/mutech-monitor.sh

  # Add to cron (every 5 minutes)
  echo "*/5 * * * * /usr/local/bin/mutech-monitor.sh" | crontab -
  ```

- [ ] Set up disk space monitoring:
  ```bash
  # Add to cron (daily)
  echo "0 2 * * * df -h > /var/log/disk-usage.log" | crontab -
  ```

- [ ] Set up Docker stats monitoring:
  ```bash
  docker stats --no-stream > /var/log/docker-stats.log
  ```

- [ ] Consider external monitoring (optional):
  - [ ] Prometheus + Grafana
  - [ ] Datadog
  - [ ] New Relic
  - [ ] Custom monitoring solution

### 2. Backup Strategy

- [ ] Set up automated database backups:
  ```bash
  cat > /usr/local/bin/mutech-backup.sh << 'EOF'
  #!/bin/bash
  BACKUP_DIR="/backup/mutech"
  mkdir -p $BACKUP_DIR
  cd /opt/mutech-control
  docker-compose exec -T postgres pg_dump -U mutech mutech | gzip > $BACKUP_DIR/mutech_$(date +%Y%m%d_%H%M%S).sql.gz
  # Keep only last 30 days
  find $BACKUP_DIR -name "mutech_*.sql.gz" -mtime +30 -delete
  EOF

  chmod +x /usr/local/bin/mutech-backup.sh

  # Add to cron (daily at 2 AM)
  echo "0 2 * * * /usr/local/bin/mutech-backup.sh" | crontab -
  ```

- [ ] Test backup restore procedure:
  ```bash
  # On staging/test environment
  gunzip -c backup.sql.gz | docker-compose exec -T postgres psql -U mutech mutech
  ```

- [ ] Document backup location and restore procedure
- [ ] Set up off-site backup replication (optional)

### 3. Maintenance Tasks

- [ ] Set up command log cleanup:
  ```bash
  cat > /usr/local/bin/mutech-cleanup.sh << 'EOF'
  #!/bin/bash
  cd /opt/mutech-control
  docker-compose exec -T postgres psql -U mutech mutech -c "
  DELETE FROM command_log WHERE timestamp < NOW() - INTERVAL '30 days';
  VACUUM ANALYZE command_log;
  "
  EOF

  chmod +x /usr/local/bin/mutech-cleanup.sh

  # Add to cron (weekly on Sunday at 3 AM)
  echo "0 3 * * 0 /usr/local/bin/mutech-cleanup.sh" | crontab -
  ```

- [ ] Set up Docker cleanup:
  ```bash
  # Add to cron (monthly)
  echo "0 4 1 * * docker system prune -af --volumes --filter 'until=720h'" | crontab -
  ```

### 4. Documentation

- [ ] Document deployment architecture
- [ ] Create runbook for common operations
- [ ] Document device IP addresses and credentials (securely!)
- [ ] Create escalation procedures
- [ ] Document backup/restore procedures
- [ ] Create troubleshooting guide for operators

### 5. Access Control

- [ ] Restrict SSH access to production server
- [ ] Set up SSH key authentication (disable password auth)
- [ ] Create separate user for application:
  ```bash
  useradd -m -s /bin/bash mutech
  usermod -aG docker mutech
  chown -R mutech:mutech /opt/mutech-control
  ```

- [ ] Implement API authentication (for future):
  - JWT tokens
  - API keys
  - OAuth2

### 6. Alerting

- [ ] Set up alerts for:
  - [ ] Service down
  - [ ] Database connection failures
  - [ ] Disk space low
  - [ ] High error rates
  - [ ] OFF verification failures

Example with email alerts:
```bash
cat > /usr/local/bin/mutech-alert.sh << 'EOF'
#!/bin/bash
ERROR_COUNT=$(docker-compose logs --since 1h main-service | grep -c ERROR)
if [ $ERROR_COUNT -gt 10 ]; then
  echo "MuTech Control: $ERROR_COUNT errors in last hour" | mail -s "MuTech Alert" admin@example.com
fi
EOF

chmod +x /usr/local/bin/mutech-alert.sh
echo "0 * * * * /usr/local/bin/mutech-alert.sh" | crontab -
```

## Performance Tuning

### 1. Database Optimization

- [ ] Tune PostgreSQL for production:
  ```bash
  # Edit PostgreSQL config
  docker-compose exec postgres vi /var/lib/postgresql/data/postgresql.conf
  ```

- [ ] Recommended settings:
  ```
  shared_buffers = 256MB
  effective_cache_size = 1GB
  maintenance_work_mem = 64MB
  checkpoint_completion_target = 0.9
  wal_buffers = 16MB
  default_statistics_target = 100
  random_page_cost = 1.1
  effective_io_concurrency = 200
  work_mem = 2MB
  min_wal_size = 1GB
  max_wal_size = 4GB
  ```

- [ ] Create additional indexes if needed:
  ```sql
  CREATE INDEX CONCURRENTLY idx_command_log_source ON command_log(source);
  CREATE INDEX CONCURRENTLY idx_devices_state ON devices(state);
  ```

### 2. Application Tuning

- [ ] Adjust connection pool size:
  ```yaml
  # config/default.yaml
  database:
    pool_size: 20
    max_overflow: 10
  ```

- [ ] Tune orchestrator settings:
  ```yaml
  orchestrator:
    max_concurrent_on_commands: 20
    max_concurrent_off_commands: 100
  ```

- [ ] Adjust device timeouts:
  ```yaml
  device_types:
    pjlink:
      cooldown_seconds: 30
      request_timeout: 10
  ```

## Rollback Procedure

If deployment fails:

1. **Stop new services:**
   ```bash
   docker-compose down
   ```

2. **Restore database from backup:**
   ```bash
   gunzip -c /backup/mutech/backup.sql.gz | docker-compose exec -T postgres psql -U mutech mutech
   ```

3. **Revert to previous version:**
   ```bash
   git checkout <previous-version-tag>
   docker-compose up -d
   ```

4. **Verify rollback:**
   ```bash
   curl http://localhost:8000/health
   ./scripts/test_system.sh
   ```

## Production Checklist Summary

### Critical (Must Complete)

- [x] Secure credentials set in `.env`
- [x] Database backup strategy implemented
- [x] Health checks passing
- [x] All device types tested
- [x] OFF verification working
- [x] Firewall configured
- [x] Log monitoring in place

### Recommended (Should Complete)

- [ ] HTTPS/SSL configured
- [ ] Reverse proxy set up
- [ ] Automated backups scheduled
- [ ] Log rotation configured
- [ ] Alerting implemented
- [ ] Documentation complete

### Optional (Nice to Have)

- [ ] External monitoring (Prometheus/Grafana)
- [ ] API authentication
- [ ] Rate limiting
- [ ] CDN for frontend
- [ ] Multi-region deployment
- [ ] High availability setup

## Support Contacts

Document your support contacts:

- **System Administrator:** [Name/Email]
- **Database Administrator:** [Name/Email]
- **Network Administrator:** [Name/Email]
- **On-call Engineer:** [Name/Phone]

## Post-Deployment Verification

Run this command 24 hours after deployment:

```bash
# Check for errors
docker-compose logs --since 24h main-service | grep -c ERROR

# Check disk usage
df -h

# Check database size
docker-compose exec postgres psql -U mutech -d mutech -c "\l+"

# Check command success rate
docker-compose exec postgres psql -U mutech -d mutech -c "
SELECT
  source,
  COUNT(*) as total,
  SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
  ROUND(100.0 * SUM(CASE WHEN success THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM command_log
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY source;
"
```

Success criteria:
- Error count < 50 per day
- Success rate > 95%
- All services running
- Disk usage < 80%

## Go-Live Approval

Sign-off required from:

- [ ] Technical Lead: _________________ Date: _______
- [ ] Operations Manager: _____________ Date: _______
- [ ] Security Officer: _______________ Date: _______

---

**Deployment Date:** _____________
**Deployed By:** _____________
**Production URL:** _____________
**Documentation Location:** _____________
