# MuTech Control Service - Quick Start Guide

Get up and running with the MuTech Control Service in minutes.

## Prerequisites

- Python 3.11+
- Poetry (Python package manager)
- Optional: PostgreSQL for production (SQLite used for development)

## Installation

1. **Clone and Navigate**
   ```bash
   cd mutech-control-service
   ```

2. **Install Dependencies**
   ```bash
   poetry install
   ```

3. **Set Up Environment**
   ```bash
   # .env file already created for development with SQLite
   # Edit .env if you need to change database or other settings
   cat .env
   ```

4. **Run Database Migrations**
   ```bash
   poetry run alembic upgrade head
   ```

5. **Create Sample Data** (Optional but recommended for testing)
   ```bash
   poetry run python scripts/create_sample_data.py
   ```

## Running the Service

### Start the Server

```bash
poetry run uvicorn mutech_control.main:app --host 0.0.0.0 --port 8000 --reload
```

The service will start on `http://localhost:8000`

You should see:
```
INFO - Starting MuTech Control Service...
INFO - Database initialized
INFO - Initialized device managers: ['pjlink', 'netio', 'anel', 'shell']
INFO - Command orchestrator initialized
INFO - State monitor initialized
INFO - State monitoring started
INFO - API documentation available at /docs
```

### Access the API Documentation

Open your browser to:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Using the CLI Tool

The CLI tool provides a convenient way to interact with the service:

### Check Service Health

```bash
poetry run python scripts/cli.py health
```

### List Resources

```bash
# List all exhibitions
poetry run python scripts/cli.py list-exhibitions

# List all devices
poetry run python scripts/cli.py list-devices
```

### Control Devices

```bash
# Turn on a specific device
poetry run python scripts/cli.py device DEVICE_ID on

# Turn off a specific device
poetry run python scripts/cli.py device DEVICE_ID off
```

### Control Artworks

```bash
# Turn on all devices in an artwork
poetry run python scripts/cli.py artwork ARTWORK_ID on

# Turn off all devices in an artwork
poetry run python scripts/cli.py artwork ARTWORK_ID off
```

### Control Exhibitions

```bash
# Turn on entire exhibition
poetry run python scripts/cli.py exhibition EXHIBITION_ID on

# Turn off entire exhibition
poetry run python scripts/cli.py exhibition EXHIBITION_ID off
```

## Using the REST API

### Get Health Status

```bash
curl http://localhost:8000/health
```

### List Exhibitions

```bash
curl http://localhost:8000/api/admin/exhibitions
```

### List Devices

```bash
curl http://localhost:8000/api/admin/devices
```

### Control a Device

```bash
# Turn device on
curl -X POST http://localhost:8000/api/control/device/DEVICE_ID/on

# Turn device off
curl -X POST http://localhost:8000/api/control/device/DEVICE_ID/off
```

### Control an Artwork

```bash
# Turn artwork on (all devices)
curl -X POST http://localhost:8000/api/control/artwork/ARTWORK_ID/on

# Turn artwork off
curl -X POST http://localhost:8000/api/control/artwork/ARTWORK_ID/off
```

### Control an Exhibition

```bash
# Turn exhibition on (all artworks and devices)
curl -X POST http://localhost:8000/api/control/exhibition/EXHIBITION_ID/on

# Turn exhibition off with verification
curl -X POST http://localhost:8000/api/control/exhibition/EXHIBITION_ID/off
```

### Fast Lane (No Verification)

For immediate control without verification:

```bash
curl -X POST http://localhost:8000/api/fast/device/DEVICE_ID/off
```

## Understanding the System

### Device States

- `-1`: Error/offline/unknown
- `0`: Off
- `1`: On
- `2`: Cooling (projectors)
- `3`: Warming (projectors)

### Device Types

- **pjlink**: Projectors using PJLink protocol (TCP port 4352)
- **netio**: NETIO power strips (HTTP API)
- **anel**: ANEL power strips (UDP protocol)
- **shell**: Custom shell commands (SSH, local scripts)

### Control Behavior

**ON Commands:**
- Staggered execution (1 second delay between devices)
- Limited concurrency (10 devices at a time)
- Prevents power surges

**OFF Commands:**
- Broadcast to all devices simultaneously
- Verification loop for 5 minutes (configurable)
- Automatic retry if device doesn't turn off
- Fast lane option to skip verification

### State Monitoring

The service automatically polls all enabled devices every 60 seconds (configurable in `config/default.yaml`):

```yaml
monitoring:
  enabled: true
  poll_interval_seconds: 60
  batch_size: 10
  batch_delay_seconds: 1.0
```

## Configuration

Edit `config/default.yaml` to customize:

- Database connection
- Device manager settings (cooldowns, timeouts)
- OFF verification parameters
- State monitoring intervals
- Orchestrator behavior
- Logging levels

The configuration supports hot-reload - changes are detected automatically (when watching is enabled).

## Logging

### View Logs

Logs are output to stdout with structured context:

```
[req:a1b2c3d4] [command=ON, device=Projector1, host=192.168.1.100] Getting device state
```

### Filter Logs by Request ID

```bash
# If logs are saved to a file
grep "req:a1b2c3d4" app.log
```

### Filter by Device

```bash
grep "device=Projector1" app.log
```

## Troubleshooting

### Service Won't Start

1. Check database connection:
   ```bash
   # Verify DATABASE_URL in .env
   cat .env | grep DATABASE_URL
   ```

2. Run migrations:
   ```bash
   poetry run alembic upgrade head
   ```

3. Check for port conflicts:
   ```bash
   lsof -i :8000
   ```

### Device Control Fails

1. Check device state:
   ```bash
   poetry run python scripts/cli.py list-devices
   ```

2. Check device configuration in database
3. Verify network connectivity to device
4. Check device-specific credentials in device config

### OFF Verification Not Working

1. Check configuration in `config/default.yaml`:
   ```yaml
   device_types:
     pjlink:
       off_verify:
         enabled: true
         interval_seconds: 30
         max_duration_seconds: 300
   ```

2. Watch verification logs:
   ```bash
   grep "verification" app.log
   ```

3. Adjust retry intervals and timeouts as needed

## Development Tips

### Run Tests

```bash
# All unit tests
poetry run pytest tests/unit/ -v

# Specific test file
poetry run pytest tests/unit/test_state_verifier.py -v

# With coverage
poetry run pytest --cov=mutech_control --cov-report=html
```

### Create New Migration

```bash
# After modifying models
poetry run alembic revision --autogenerate -m "Description of changes"

# Review the generated migration in mutech_control/database/migrations/versions/
# Then apply it
poetry run alembic upgrade head
```

### Reset Database

```bash
# SQLite (development)
rm mutech_dev.db
poetry run alembic upgrade head
poetry run python scripts/create_sample_data.py

# PostgreSQL (production)
poetry run alembic downgrade base
poetry run alembic upgrade head
```

## Next Steps

- **Production Deployment**: Set up PostgreSQL, configure environment variables
- **Add Your Devices**: Use the admin API to add exhibitions, artworks, and devices
- **Frontend Integration**: Use the REST API from your frontend application
- **Monitoring**: Integrate with your monitoring system using the /health endpoint

## Getting Help

- **API Documentation**: http://localhost:8000/docs
- **Phase 2 Changes**: See `PHASE2_CHANGES.md` for recent improvements
- **Architecture**: See plan file for system architecture details

## Example Workflow

Here's a complete workflow from setup to control:

```bash
# 1. Install and setup
poetry install
poetry run alembic upgrade head
poetry run python scripts/create_sample_data.py

# 2. Start service (in one terminal)
poetry run uvicorn mutech_control.main:app --reload

# 3. In another terminal, test it
poetry run python scripts/cli.py health
poetry run python scripts/cli.py list-exhibitions
poetry run python scripts/cli.py list-devices

# 4. Get exhibition ID from list
EXHIBITION_ID=$(curl -s http://localhost:8000/api/admin/exhibitions | jq -r '.[0].id')

# 5. Control the exhibition
poetry run python scripts/cli.py exhibition $EXHIBITION_ID on
# Wait a few seconds...
poetry run python scripts/cli.py exhibition $EXHIBITION_ID off

# 6. Watch the logs
# Observe structured logging with request IDs, device context, and verification
```

Happy controlling! 🎮
