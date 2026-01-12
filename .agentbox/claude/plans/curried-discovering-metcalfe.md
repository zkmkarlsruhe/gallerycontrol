# MuTech Control System - Python Refactor Implementation Plan

## Executive Summary

Refactor the existing Node.js microservices architecture into a modern Python monolith with FastAPI, eliminating Socket.IO overhead while maintaining only the ANEL runner as a separate service due to network segmentation requirements.

**Key Changes:**
- **5 Node.js services → 2 Python services** (main + ANEL runner)
- **Socket.IO → REST API** with polling for frontend
- **React → Modern React + TypeScript** with better UI/UX
- **SQLite → PostgreSQL** for better scalability
- **Complex queue → Simple stagger + verify** pattern
- **Hot-reloadable YAML config** for operational flexibility

---

## Phase 1: Project Setup & Infrastructure

### 1.1 Main Service (Poetry Project)

**Location:** `/workspace/mutech-control-service/`

```
mutech-control-service/
├── pyproject.toml                 # Poetry dependencies
├── config/
│   ├── default.yaml              # Default configuration
│   ├── development.yaml          # Dev overrides
│   └── production.yaml           # Prod overrides
├── mutech_control/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entry
│   ├── config.py                 # Config loader with hot-reload
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py             # SQLAlchemy models
│   │   ├── connection.py         # Database connection
│   │   └── migrations/           # Alembic migrations
│   ├── api/
│   │   ├── __init__.py
│   │   ├── control.py            # Control endpoints
│   │   ├── fast.py               # Fast lane endpoints
│   │   ├── state.py              # State query endpoints
│   │   └── admin.py              # Admin CRUD endpoints
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── command_orchestrator.py  # Main command logic
│   │   ├── state_verifier.py       # OFF verification
│   │   └── cooldown_manager.py     # Per-device cooldowns
│   ├── devices/
│   │   ├── __init__.py
│   │   ├── base.py               # Base device interface
│   │   ├── pjlink_manager.py    # PJLink devices
│   │   ├── netio_manager.py     # NETIO devices
│   │   ├── shell_manager.py     # Shell commands
│   │   └── anel_client.py       # ANEL runner REST client
│   └── utils/
│       ├── __init__.py
│       ├── logging.py            # Structured logging
│       └── exceptions.py         # Custom exceptions
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
└── Dockerfile
```

**Dependencies (pyproject.toml):**
```toml
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.109.0"
uvicorn = {extras = ["standard"], version = "^0.27.0"}
sqlalchemy = "^2.0.25"
asyncpg = "^0.29.0"
alembic = "^1.13.0"
pydantic = "^2.5.0"
pydantic-settings = "^2.1.0"
httpx = "^0.26.0"
pyyaml = "^6.0"
pypwrctrl = "^0.1.0"           # ANEL library
pypjlink = "^1.1.1"             # PJLink library
netio = "^1.0.15"               # NETIO library
python-dotenv = "^1.0.0"
watchdog = "^3.0.0"             # Config file watching
```

### 1.2 ANEL Runner (Separate Service)

**Location:** `/workspace/anel-runner-service/`

```
anel-runner-service/
├── pyproject.toml
├── config.yaml
├── anel_runner/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app
│   ├── anel_manager.py           # pypwrctrl wrapper
│   └── auth.py                   # API key authentication
└── Dockerfile
```

**API Endpoints:**
```
GET  /health
GET  /devices/{ip}/state?port={port}
POST /devices/{ip}/on?port={port}
POST /devices/{ip}/off?port={port}
GET  /devices/{ip}/info
```

**Authentication:** Bearer token in `Authorization` header

---

## Phase 2: Database Design & Migration

### 2.1 PostgreSQL Schema

```sql
-- Exhibitions table
CREATE TABLE exhibitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Artworks table
CREATE TABLE artworks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exhibition_id UUID NOT NULL REFERENCES exhibitions(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Devices table (formerly "units")
CREATE TABLE devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artwork_id UUID NOT NULL REFERENCES artworks(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    device_type VARCHAR(50) NOT NULL,  -- 'pjlink', 'netio', 'anel', 'shell'
    host VARCHAR(255) NOT NULL,
    port INTEGER,

    -- Control flags
    enabled BOOLEAN DEFAULT TRUE,                    -- Master on/off
    automation_enabled BOOLEAN DEFAULT TRUE,         -- Allow in automation
    exclude_from_auto_onoff BOOLEAN DEFAULT FALSE,   -- Exclude from "turn all on/off"

    -- Configuration (JSON)
    config JSONB DEFAULT '{}',  -- device-specific: password, timeout, commands, etc.

    -- State management
    state INTEGER DEFAULT -1,  -- -1=error, 0=off, 1=on, 2=cooling, 3=warming
    last_checked_at TIMESTAMP,
    next_check_allowed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_device UNIQUE (host, port, device_type)
);

CREATE INDEX idx_artworks_exhibition ON artworks(exhibition_id);
CREATE INDEX idx_devices_artwork ON devices(artwork_id);
CREATE INDEX idx_devices_enabled ON devices(enabled);
CREATE INDEX idx_devices_type ON devices(device_type);

-- Command log table
CREATE TABLE command_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id UUID REFERENCES devices(id) ON DELETE SET NULL,
    command VARCHAR(50) NOT NULL,  -- 'on', 'off', 'state'
    source VARCHAR(50) NOT NULL,   -- 'web', 'fast', 'admin', 'verification'
    success BOOLEAN NOT NULL,
    error_message TEXT,
    duration_ms INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_command_log_device ON command_log(device_id);
CREATE INDEX idx_command_log_timestamp ON command_log(timestamp);
```

**Key Design Notes:**
- `exclude_from_auto_onoff`: NEW flag for shell/reboot commands that should not participate in bulk ON/OFF
- `automation_enabled`: Determines if device is polled automatically
- `enabled`: Master switch - disabled devices are ignored completely
- `config` JSONB: Flexible storage for device-specific settings (passwords, commands, etc.)

### 2.2 Migration Strategy

**Step 1: Export from SQLite**
```python
# Read existing mutech.db
# Extract exhibits, works, units
# Map to new schema with field conversions
```

**Step 2: Import to PostgreSQL**
```python
# Create new database
# Run Alembic migrations
# Insert data with UUID generation
# Set exclude_from_auto_onoff=true for shell devices with reboot commands
```

**Migration Script:** `/workspace/scripts/migrate_sqlite_to_postgres.py`

---

## Phase 3: Core Service Implementation

### 3.1 Configuration System (YAML Hot-Reload)

**config/default.yaml:**
```yaml
server:
  host: "0.0.0.0"
  port: 8000
  reload: false  # Set true for development

database:
  url: "postgresql://mutech:password@localhost:5432/mutech"
  pool_size: 20
  echo: false  # SQL query logging

device_types:
  pjlink:
    cooldown_seconds: 30
    request_timeout: 10
    off_verify:
      interval_seconds: 30
      max_duration_seconds: 300  # 5 minutes
      retry_on_states: [1, -1]  # retry if on or error
      success_states: [0, 2]    # off or cooling = success

  netio:
    cooldown_seconds: 5
    request_timeout: 5
    off_verify:
      interval_seconds: 30
      max_duration_seconds: 180
      retry_on_states: [1, -1]
      success_states: [0]

  anel:
    cooldown_seconds: 5
    request_timeout: 5
    runner_url: "http://anel-runner:8001"
    runner_api_key: "${ANEL_API_KEY}"  # From environment
    off_verify:
      interval_seconds: 30
      max_duration_seconds: 180
      retry_on_states: [1, -1]
      success_states: [0]

  shell:
    cooldown_seconds: 2
    request_timeout: 30
    # No off_verify for shell commands

orchestrator:
  on_stagger_delay_seconds: 1.0      # 1 second between ON commands
  max_concurrent_on_commands: 10      # Max parallel ON operations
  max_concurrent_off_commands: 50     # OFF can be broadcast
  enable_off_verification: true
  off_verification_task_interval: 10  # Check verification tasks every 10s

logging:
  level: "INFO"
  format: "json"  # or "text"
  file: null      # null = stdout only

api:
  cors_origins:
    - "http://localhost:3000"
    - "http://localhost:8080"
  rate_limit:
    enabled: true
    requests_per_minute: 60
```

**Hot Reload Implementation:**
- Use `watchdog` library to monitor `config/*.yaml`
- On file change, reload config without restart
- Emit warning if reload fails (keep old config)
- Log config changes to audit trail

### 3.2 Device Managers

**Base Interface (devices/base.py):**
```python
from abc import ABC, abstractmethod
from typing import Literal

DeviceState = Literal[-1, 0, 1, 2, 3]  # error, off, on, cooling, warming

class DeviceManager(ABC):
    @abstractmethod
    async def get_state(self, device: Device) -> tuple[bool, DeviceState, str | None]:
        """Returns (success, state, error_message)"""
        pass

    @abstractmethod
    async def set_power(self, device: Device, on: bool) -> tuple[bool, DeviceState, str | None]:
        """Returns (success, new_state, error_message)"""
        pass

    @abstractmethod
    async def test_connection(self, device: Device) -> tuple[bool, str | None]:
        """Returns (success, error_message)"""
        pass
```

**PJLink Manager (devices/pjlink_manager.py):**
```python
class PJLinkManager(DeviceManager):
    def __init__(self, config: dict):
        self.config = config
        self.cooldown_manager = CooldownManager()
        # Connection pool per device IP
        self._connections = {}

    async def get_state(self, device: Device) -> tuple[bool, DeviceState, str | None]:
        # Check cooldown
        if not self.cooldown_manager.is_allowed(device.id):
            next_time = self.cooldown_manager.next_allowed(device.id)
            return False, device.state, f"Cooldown active until {next_time}"

        try:
            async with timeout(self.config['request_timeout']):
                # Use pypjlink library
                projector = await self._get_projector(device)
                power_state = await projector.get_power()

                # Map PJLink states to our states
                state = self._map_pjlink_state(power_state)

                # Record successful check
                self.cooldown_manager.record_success(device.id, self.config['cooldown_seconds'])

                return True, state, None
        except asyncio.TimeoutError:
            return False, -1, "Request timeout"
        except Exception as e:
            return False, -1, str(e)

    async def set_power(self, device: Device, on: bool) -> tuple[bool, DeviceState, str | None]:
        # Similar pattern with cooldown checking
        pass
```

**NETIO Manager (devices/netio_manager.py):**
```python
class NETIOManager(DeviceManager):
    def __init__(self, config: dict):
        self.config = config
        self.cooldown_manager = CooldownManager()
        # Shared httpx AsyncClient for connection pooling
        self.http_client = httpx.AsyncClient()

    async def get_state(self, device: Device) -> tuple[bool, DeviceState, str | None]:
        # Use Netio library via httpx
        # Check specific port on device
        pass
```

**ANEL Client (devices/anel_client.py):**
```python
class ANELClient(DeviceManager):
    def __init__(self, config: dict):
        self.runner_url = config['runner_url']
        self.api_key = config['runner_api_key']
        self.http_client = httpx.AsyncClient()
        self.cooldown_manager = CooldownManager()

    async def get_state(self, device: Device) -> tuple[bool, DeviceState, str | None]:
        # REST call to ANEL runner
        url = f"{self.runner_url}/devices/{device.host}/state"
        params = {"port": device.port}
        headers = {"Authorization": f"Bearer {self.api_key}"}

        response = await self.http_client.get(url, params=params, headers=headers)
        # Parse response and map to state
        pass
```

**Shell Manager (devices/shell_manager.py):**
```python
class ShellManager(DeviceManager):
    async def get_state(self, device: Device) -> tuple[bool, DeviceState, str | None]:
        # Execute status command from device.config['commands']['status']
        # Parse output using onPattern/offPattern regex
        cmd = device.config['commands']['status']['cmd']
        on_pattern = device.config['commands']['status'].get('onPattern')
        off_pattern = device.config['commands']['status'].get('offPattern')

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config['request_timeout']
            )

            output = stdout.decode()

            # Pattern matching
            if on_pattern and re.search(on_pattern, output):
                return True, 1, None
            elif off_pattern and re.search(off_pattern, output):
                return True, 0, None
            else:
                return True, -1, "Could not determine state from output"
        except asyncio.TimeoutError:
            return False, -1, "Command timeout"
```

### 3.3 Command Orchestrator

**orchestrator/command_orchestrator.py:**
```python
class CommandOrchestrator:
    def __init__(self, db, device_managers, config):
        self.db = db
        self.device_managers = device_managers
        self.config = config
        self.state_verifier = StateVerifier(db, device_managers, config)
        self._on_semaphore = asyncio.Semaphore(config['max_concurrent_on_commands'])

    async def execute_control_command(
        self,
        target_type: Literal['exhibition', 'artwork', 'device'],
        target_id: str,
        command: Literal['on', 'off'],
        source: Literal['web', 'fast']
    ) -> dict:
        """Main entry point for control commands"""

        # 1. Resolve target to list of devices
        devices = await self._resolve_target(target_type, target_id)

        # 2. Filter devices
        devices = self._filter_devices(devices, command)

        # 3. Execute command
        if source == 'web':
            if command == 'on':
                results = await self._execute_on_staggered(devices)
            else:
                results = await self._execute_off_with_verification(devices)
        else:  # fast lane
            results = await self._execute_fast(devices, command)

        return {
            "success": True,
            "devices_targeted": len(devices),
            "results": results
        }

    def _filter_devices(self, devices: list[Device], command: str) -> list[Device]:
        """Filter based on enabled flags"""
        filtered = []
        for device in devices:
            if not device.enabled:
                continue
            if device.exclude_from_auto_onoff and command in ['on', 'off']:
                continue
            filtered.append(device)
        return filtered

    async def _execute_on_staggered(self, devices: list[Device]) -> list[dict]:
        """ON commands: 1 second stagger, limited concurrency"""
        results = []

        for device in devices:
            async with self._on_semaphore:  # Limit concurrent operations
                result = await self._execute_single_device(device, 'on', 'web')
                results.append(result)

                # Stagger delay
                await asyncio.sleep(self.config['on_stagger_delay_seconds'])

        return results

    async def _execute_off_with_verification(self, devices: list[Device]) -> list[dict]:
        """OFF commands: Broadcast, then verify"""
        # 1. Send OFF to all devices in parallel
        tasks = [
            self._execute_single_device(device, 'off', 'web')
            for device in devices
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 2. Start verification tasks for devices that need it
        devices_to_verify = [
            device for device, result in zip(devices, results)
            if result.get('success') and device.device_type != 'shell'
        ]

        if self.config['enable_off_verification'] and devices_to_verify:
            asyncio.create_task(
                self.state_verifier.verify_devices_off(devices_to_verify)
            )

        return results

    async def _execute_fast(self, devices: list[Device], command: str) -> list[dict]:
        """Fast lane: Fire once, no verification"""
        tasks = [
            self._execute_single_device(device, command, 'fast')
            for device in devices
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_single_device(self, device: Device, command: str, source: str) -> dict:
        """Execute command on single device"""
        manager = self.device_managers[device.device_type]

        start_time = time.time()
        success, new_state, error = await manager.set_power(device, command == 'on')
        duration = int((time.time() - start_time) * 1000)

        # Update database
        if success:
            await self.db.update_device_state(device.id, new_state)

        # Log command
        await self.db.log_command(
            device_id=device.id,
            command=command,
            source=source,
            success=success,
            error_message=error,
            duration_ms=duration
        )

        return {
            "device_id": device.id,
            "success": success,
            "state": new_state,
            "error": error,
            "duration_ms": duration
        }
```

**orchestrator/state_verifier.py:**
```python
class StateVerifier:
    """Handles OFF command verification with retries"""

    def __init__(self, db, device_managers, config):
        self.db = db
        self.device_managers = device_managers
        self.config = config
        self._active_verifications = {}  # device_id -> task

    async def verify_devices_off(self, devices: list[Device]):
        """Start verification task for multiple devices"""
        for device in devices:
            if device.id not in self._active_verifications:
                task = asyncio.create_task(self._verify_single_device(device))
                self._active_verifications[device.id] = task

    async def _verify_single_device(self, device: Device):
        """Verify a single device turned off"""
        device_config = self.config['device_types'][device.device_type]
        verify_config = device_config.get('off_verify')

        if not verify_config:
            return  # No verification for this device type

        interval = verify_config['interval_seconds']
        max_duration = verify_config['max_duration_seconds']
        retry_states = verify_config['retry_on_states']
        success_states = verify_config['success_states']

        manager = self.device_managers[device.device_type]

        start_time = time.time()
        attempts = 0

        try:
            while (time.time() - start_time) < max_duration:
                await asyncio.sleep(interval)
                attempts += 1

                # Check state
                success, state, error = await manager.get_state(device)

                if not success:
                    logger.warning(f"Verification check failed for {device.id}: {error}")
                    continue

                if state in success_states:
                    logger.info(f"Device {device.id} verified OFF after {attempts} checks")
                    await self.db.update_device_state(device.id, state)
                    return

                if state in retry_states:
                    # Still on or error - retry OFF command
                    logger.warning(f"Device {device.id} still in state {state}, resending OFF")
                    await manager.set_power(device, False)
                    await self.db.log_command(
                        device_id=device.id,
                        command='off',
                        source='verification',
                        success=True,
                        error_message=None,
                        duration_ms=0
                    )

            # Max duration exceeded
            logger.error(f"Device {device.id} failed to verify OFF after {max_duration}s")
            await self.db.update_device_state(device.id, -1)  # Mark as error

        finally:
            del self._active_verifications[device.id]
```

### 3.4 REST API Design

**api/control.py:**
```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/control", tags=["control"])

class ControlRequest(BaseModel):
    command: Literal['on', 'off']

@router.post("/exhibition/{exhibition_id}/{command}")
async def control_exhibition(
    exhibition_id: str,
    command: Literal['on', 'off'],
    orchestrator: CommandOrchestrator = Depends(get_orchestrator)
):
    result = await orchestrator.execute_control_command(
        target_type='exhibition',
        target_id=exhibition_id,
        command=command,
        source='web'
    )
    return result

@router.post("/artwork/{artwork_id}/{command}")
async def control_artwork(artwork_id: str, command: str, ...):
    pass

@router.post("/device/{device_id}/{command}")
async def control_device(device_id: str, command: str, ...):
    pass
```

**api/fast.py:**
```python
router = APIRouter(prefix="/api/fast", tags=["fast"])

@router.post("/device/{device_id}/{command}")
async def fast_control(device_id: str, command: str, ...):
    result = await orchestrator.execute_control_command(
        target_type='device',
        target_id=device_id,
        command=command,
        source='fast'
    )
    return result
```

**api/state.py:**
```python
router = APIRouter(prefix="/api/state", tags=["state"])

@router.get("/exhibition/{exhibition_id}")
async def get_exhibition_state(exhibition_id: str, db = Depends(get_db)):
    exhibition = await db.get_exhibition_with_full_state(exhibition_id)
    return exhibition

@router.get("/device/{device_id}")
async def get_device_state(device_id: str, db = Depends(get_db)):
    device = await db.get_device(device_id)
    return device
```

**api/admin.py:**
```python
router = APIRouter(prefix="/api/admin", tags=["admin"])

# CRUD for exhibitions
@router.get("/exhibitions")
async def list_exhibitions(...):
    pass

@router.post("/exhibitions")
async def create_exhibition(...):
    pass

@router.put("/exhibitions/{id}")
async def update_exhibition(...):
    pass

@router.delete("/exhibitions/{id}")
async def delete_exhibition(...):
    pass

# Similar for artworks and devices
# ...

@router.post("/config/reload")
async def reload_config(...):
    """Manually trigger config reload"""
    pass
```

---

## Phase 4: Frontend Rewrite

### 4.1 Technology Stack

**Framework:** React 18 + TypeScript
**UI Library:** Material-UI (MUI) v5 or Ant Design
**State Management:** Zustand (lightweight) or TanStack Query (for API state)
**API Client:** Axios or native fetch with TanStack Query
**Build Tool:** Vite (faster than CRA)

### 4.2 Project Structure

```
mutech-control-frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   ├── client.ts              # Axios/fetch setup
│   │   ├── control.ts             # Control API calls
│   │   ├── state.ts               # State API calls
│   │   └── admin.ts               # Admin API calls
│   ├── components/
│   │   ├── exhibitions/
│   │   │   ├── ExhibitionList.tsx
│   │   │   ├── ExhibitionCard.tsx
│   │   │   └── ExhibitionControls.tsx
│   │   ├── artworks/
│   │   │   ├── ArtworkList.tsx
│   │   │   └── ArtworkCard.tsx
│   │   ├── devices/
│   │   │   ├── DeviceCard.tsx
│   │   │   ├── DeviceState.tsx
│   │   │   ├── DeviceControls.tsx
│   │   │   └── forms/
│   │   │       ├── PJLinkForm.tsx
│   │   │       ├── NETIOForm.tsx
│   │   │       ├── ANELForm.tsx
│   │   │       └── ShellForm.tsx
│   │   ├── layout/
│   │   │   ├── AppBar.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── ControlPanel.tsx
│   │   └── common/
│   │       ├── LoadingSpinner.tsx
│   │       └── ErrorMessage.tsx
│   ├── store/
│   │   └── useStore.ts            # Zustand store
│   ├── hooks/
│   │   ├── usePolling.ts          # Polling logic
│   │   ├── useDeviceState.ts
│   │   └── useControlCommand.ts
│   ├── types/
│   │   ├── api.ts                 # API response types
│   │   ├── device.ts              # Device types
│   │   └── state.ts               # State types
│   └── utils/
│       ├── formatters.ts
│       └── constants.ts
└── Dockerfile
```

### 4.3 Key Features

**State Polling:**
```typescript
// hooks/usePolling.ts
export function usePolling(interval: number = 5000) {
  const fetchState = async () => {
    const response = await api.state.getAllExhibitions();
    store.setState({ exhibitions: response.data });
  };

  useEffect(() => {
    fetchState(); // Initial fetch
    const timer = setInterval(fetchState, interval);
    return () => clearInterval(timer);
  }, [interval]);
}
```

**Device State Display:**
```typescript
// components/devices/DeviceState.tsx
export function DeviceState({ device }: { device: Device }) {
  const stateColor = {
    '-1': 'error',
    '0': 'default',
    '1': 'success',
    '2': 'warning',  // cooling
    '3': 'warning',  // warming
  }[device.state.toString()] || 'default';

  const stateLabel = {
    '-1': 'Error',
    '0': 'Off',
    '1': 'On',
    '2': 'Cooling',
    '3': 'Warming',
  }[device.state.toString()] || 'Unknown';

  const nextCheckTime = device.next_check_allowed_at
    ? formatRelativeTime(device.next_check_allowed_at)
    : null;

  return (
    <Box>
      <Chip label={stateLabel} color={stateColor} />
      {nextCheckTime && (
        <Typography variant="caption">
          Next check: {nextCheckTime}
        </Typography>
      )}
    </Box>
  );
}
```

**Control Actions:**
```typescript
// hooks/useControlCommand.ts
export function useControlCommand() {
  const [loading, setLoading] = useState(false);

  const sendCommand = async (
    targetType: 'exhibition' | 'artwork' | 'device',
    targetId: string,
    command: 'on' | 'off'
  ) => {
    setLoading(true);
    try {
      await api.control.send(targetType, targetId, command);
      // Success toast
      toast.success(`${command.toUpperCase()} command sent`);
    } catch (error) {
      toast.error('Command failed');
    } finally {
      setLoading(false);
    }
  };

  return { sendCommand, loading };
}
```

**Admin Interface:**
- Full CRUD for exhibitions, artworks, devices
- Form validation with Zod or Yup
- Inline editing for names
- Batch operations (enable/disable multiple)
- Config viewer/editor (if needed)

---

## Phase 5: Deployment & Docker

### 5.1 Docker Compose

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: mutech
      POSTGRES_USER: mutech
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mutech"]
      interval: 10s
      timeout: 5s
      retries: 5

  main-service:
    build:
      context: ./mutech-control-service
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://mutech:${DB_PASSWORD}@postgres:5432/mutech
      ANEL_API_KEY: ${ANEL_API_KEY}
      ANEL_RUNNER_URL: http://anel-runner:8001
    volumes:
      - ./mutech-control-service/config:/app/config
      - ./logs:/app/logs
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

  anel-runner:
    build:
      context: ./anel-runner-service
      dockerfile: Dockerfile
    environment:
      API_KEY: ${ANEL_API_KEY}
    network_mode: host  # Access ANEL network segment
    restart: unless-stopped

  frontend:
    build:
      context: ./mutech-control-frontend
      dockerfile: Dockerfile
    environment:
      VITE_API_URL: http://main-service:8000
    ports:
      - "80:80"
    depends_on:
      - main-service
    restart: unless-stopped

volumes:
  postgres_data:
```

### 5.2 Dockerfiles

**Main Service:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy dependencies
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --no-dev

# Copy application
COPY mutech_control ./mutech_control
COPY config ./config

# Expose port
EXPOSE 8000

# Run with Uvicorn
CMD ["uvicorn", "mutech_control.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**ANEL Runner:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install poetry

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false && poetry install --no-dev

COPY anel_runner ./anel_runner
COPY config.yaml ./

EXPOSE 8001

CMD ["uvicorn", "anel_runner.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

**Frontend:**
```dockerfile
# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

---

## Phase 6: Migration & Testing Plan

### 6.1 Migration Steps

1. **Setup new infrastructure** (PostgreSQL, services in dev)
2. **Run data migration** from existing SQLite to PostgreSQL
3. **Deploy services** in parallel with old system (test mode)
4. **Validate functionality:**
   - All devices controllable
   - State polling working
   - OFF verification working
   - Fast lane working
5. **Switch DNS/load balancer** to new system
6. **Monitor for 24 hours**, keep old system on standby
7. **Decommission old system**

### 6.2 Testing Strategy

**Unit Tests:**
- Device manager tests (mocked device responses)
- Orchestrator logic tests
- State verifier tests
- API endpoint tests

**Integration Tests:**
- End-to-end control flow
- Database operations
- Config hot-reload
- OFF verification retry logic

**Manual Testing Checklist:**
- [ ] Turn on single device (PJLink, NETIO, ANEL, Shell)
- [ ] Turn off single device
- [ ] Turn on artwork (multiple devices)
- [ ] Turn off artwork with verification
- [ ] Turn on exhibition (all artworks)
- [ ] Turn off exhibition
- [ ] Test fast lane endpoint
- [ ] Verify cooldown prevents rapid requests
- [ ] Test excluded device (shell reboot) not triggered by bulk ON
- [ ] Test admin CRUD operations
- [ ] Test config hot-reload
- [ ] Monitor OFF verification retries

### 6.3 Performance Targets

- **Fast lane response:** < 1 second
- **Web UI control:** < 5 seconds for individual device
- **Bulk exhibition ON:** 1s per device (staggered)
- **Bulk exhibition OFF:** < 5s to send all commands
- **State polling:** 5-10 second interval (frontend)
- **OFF verification:** Check every 30s for up to 5 minutes

---

## Phase 7: Critical Implementation Order

### Week 1-2: Foundation
1. Setup Poetry projects (main + ANEL runner)
2. Implement configuration system with hot-reload
3. Setup PostgreSQL schema with Alembic
4. Create migration script from SQLite
5. Implement base device manager interface

### Week 3-4: Device Managers
6. Implement PJLink manager (highest priority - most complex)
7. Implement NETIO manager
8. Implement ANEL runner service + client
9. Implement Shell manager
10. Test each manager independently

### Week 5-6: Orchestrator
11. Implement cooldown manager
12. Implement command orchestrator (ON stagger, OFF broadcast)
13. Implement state verifier with retry logic
14. Test orchestrator flows

### Week 7-8: API Layer
15. Implement FastAPI endpoints (control, fast, state, admin)
16. Add API documentation (Swagger/OpenAPI)
17. Integration tests for API
18. Performance testing

### Week 9-10: Frontend
19. Setup Vite + React + TypeScript project
20. Implement state polling hook
21. Build exhibition/artwork/device components
22. Implement control actions
23. Build admin interface

### Week 11-12: Deployment & Migration
24. Setup Docker Compose environment
25. Run data migration
26. Deploy in test environment
27. End-to-end testing
28. Performance tuning
29. Production deployment
30. Monitoring & documentation

---

## Critical Files to Create

### Main Service
- `/workspace/mutech-control-service/pyproject.toml`
- `/workspace/mutech-control-service/config/default.yaml`
- `/workspace/mutech-control-service/mutech_control/main.py`
- `/workspace/mutech-control-service/mutech_control/config.py`
- `/workspace/mutech-control-service/mutech_control/database/models.py`
- `/workspace/mutech-control-service/mutech_control/orchestrator/command_orchestrator.py`
- `/workspace/mutech-control-service/mutech_control/orchestrator/state_verifier.py`
- `/workspace/mutech-control-service/mutech_control/devices/pjlink_manager.py`
- `/workspace/mutech-control-service/mutech_control/api/control.py`

### ANEL Runner
- `/workspace/anel-runner-service/pyproject.toml`
- `/workspace/anel-runner-service/anel_runner/main.py`
- `/workspace/anel-runner-service/anel_runner/anel_manager.py`

### Frontend
- `/workspace/mutech-control-frontend/package.json`
- `/workspace/mutech-control-frontend/tsconfig.json`
- `/workspace/mutech-control-frontend/src/main.tsx`
- `/workspace/mutech-control-frontend/src/api/client.ts`
- `/workspace/mutech-control-frontend/src/hooks/usePolling.ts`

### Infrastructure
- `/workspace/docker-compose.yml`
- `/workspace/scripts/migrate_sqlite_to_postgres.py`
- `/workspace/.env.example`

---

## Verification Steps

After implementation, verify:

1. **Control Flow:**
   - [ ] Web UI ON command staggers devices by 1 second
   - [ ] Web UI OFF command broadcasts and starts verification
   - [ ] Fast lane commands execute once without retry
   - [ ] Shell devices with `exclude_from_auto_onoff=true` not triggered by bulk commands

2. **State Management:**
   - [ ] Device cooldowns prevent rapid polling
   - [ ] PJLink "cooling" state treated as OFF received
   - [ ] Failed OFF verification retries every 30s
   - [ ] After 5 minutes, device marked as error if still not off

3. **Configuration:**
   - [ ] YAML config changes reflected without restart
   - [ ] Per-device-type timeouts and cooldowns working
   - [ ] OFF verification intervals configurable

4. **Frontend:**
   - [ ] State updates via polling every 5 seconds
   - [ ] "Next check at" timestamps displayed correctly
   - [ ] Control buttons show loading state
   - [ ] Admin interface allows full CRUD

5. **Database:**
   - [ ] Command log records all operations
   - [ ] State updates persisted correctly
   - [ ] Cascade deletes working (exhibition → artworks → devices)

6. **Performance:**
   - [ ] 1000 devices polled within reasonable timeframe
   - [ ] PostgreSQL handles concurrent operations
   - [ ] No memory leaks in long-running verification tasks

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| PJLink protocol blocking | Implement aggressive cooldowns (30s+), connection pooling |
| OFF verification failures | Log all retries, alert after max attempts, manual override |
| PostgreSQL migration issues | Backup SQLite, validate data integrity, rollback plan |
| Frontend polling overhead | Adjust interval based on load, implement backoff |
| ANEL network segmentation | Test runner connectivity, document network requirements |
| Config hot-reload race conditions | Lock config during reload, validate before applying |
| Device credential security | Encrypt config JSONB field, use environment variables |

---

## Success Criteria

✅ **Main service runs as single Python monolith**
✅ **ANEL runner separate with REST API**
✅ **No Socket.IO overhead** (REST only)
✅ **ON commands stagger 1 second apart**
✅ **OFF commands broadcast + verify for 5 minutes**
✅ **Fast lane bypasses verification**
✅ **Shell reboot commands excluded from bulk ON/OFF**
✅ **PJLink cooldown prevents blocking**
✅ **Hot-reloadable YAML config**
✅ **Modern React + TypeScript frontend**
✅ **PostgreSQL handles 1000+ devices**
✅ **Full admin interface for device management**

---

## Notes & Considerations

- **State values:** Keep existing -1/0/1/2/3 for compatibility
- **UUIDs:** Generate new UUIDs during migration, not reuse SQLite IDs
- **Credentials:** Consider encrypting device config JSONB in production
- **Monitoring:** Add Prometheus metrics for operation counts, durations, failures
- **Logging:** Structured JSON logging for better observability
- **API versioning:** Consider `/api/v1/...` for future compatibility
- **CORS:** Configure carefully for production deployment
- **Rate limiting:** Implement per-IP rate limits on public endpoints

---

This plan provides a complete roadmap from current Node.js microservices to a modern, maintainable Python monolith with clear separation of concerns, improved operational characteristics, and a much better developer experience.
