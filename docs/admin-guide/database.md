# Database Management

## Migrations

```bash
# Create a new migration
poetry run alembic revision --autogenerate -m "Description"

# Apply migrations
poetry run alembic upgrade head

# Rollback one migration
poetry run alembic downgrade -1
```

## Database Schema

### Core Tables

| Table | Description |
|-------|-------------|
| `exhibitions` | Exhibition containers |
| `artworks` | Artworks within exhibitions |
| `devices` | Controllable devices |
| `credentials` | Password store |
| `shell_templates` | Reusable shell commands |

### Logging Tables

| Table | Description |
|-------|-------------|
| `command_log` | Command executions (issued by the orchestrator) |
| `state_change_logs` | Device state transitions |
| `device_operation_logs` | Detailed operation logs |
| `scheduled_job_logs` | Schedule execution history |

### Scheduling Tables

| Table | Description |
|-------|-------------|
| `scheduled_jobs` | Cron and one-shot jobs |

### Asset Tables

| Table | Description |
|-------|-------------|
| `assets` | Projector asset records |
| `lamp_hours_logs` | Lamp usage history |

### Satellite Tables

| Table | Description |
|-------|-------------|
| `satellites` | Approved satellite relays |

### Protection Tables

| Table | Description |
|-------|-------------|
| `artwork_protection_states` | Runtime tracking for protected artworks |

## Backup

```bash
# Backup database
pg_dump -h localhost -U mutech mutech > backup.sql

# Restore database
psql -h localhost -U mutech mutech < backup.sql
```

## Connection Pool

The database connection pool is configured in `config/default.yaml`:

```yaml
database:
  pool_size: 20        # Base connections
  pool_pre_ping: true  # Verify connections before use
```

Monitor pool usage via application logs. If you see "pool exhausted" errors, increase `pool_size`.
