"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from mutech_control.api import admin, assets, control, debug, fast, satellite, state
from mutech_control.config import get_config
from mutech_control.database.connection import get_db_manager
from mutech_control.devices.anel_client import ANELClient
from mutech_control.devices.anel_manager import ANELManager
from mutech_control.devices.netio_manager import NETIOManager
from mutech_control.devices.pjlink_manager import PJLinkManager
from mutech_control.devices.shell_manager import ShellManager, load_credentials
from mutech_control.monitoring.service_health import ServiceHealthMonitor
from mutech_control.monitoring.state_monitor import StateMonitor
from mutech_control.orchestrator.command_orchestrator import CommandOrchestrator
from mutech_control.scheduler import CronScheduler
from mutech_control.scheduler.tasks import (
    run_asset_linker,
    run_device_info_cache,
    run_lamp_hours_check,
    run_lamp_hours_record,
    run_log_cleanup,
    run_memory_cleanup,
)
from mutech_control.devices.satellite_router import SatelliteRouter
from mutech_control.services.asset_service import AssetService
from mutech_control.services.protection_service import ProtectionService
from mutech_control.services.satellite_manager import SatelliteManager
from mutech_control.services.sse_broadcaster import SSEBroadcaster

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting MuTech Control Service...")

    config = get_config()

    # Initialize database
    db_manager = get_db_manager()
    logger.info("Database initialized")

    # Load credentials into cache for shell command placeholder replacement
    async with db_manager.session() as session:
        await load_credentials(session)

    # Initialize device managers
    device_types_config = config.get("device_types", {})

    # Choose ANEL implementation based on config
    anel_config = device_types_config.get("anel", {})
    if anel_config.get("runner_url"):
        anel_manager = ANELClient(anel_config)
        logger.info("Using ANELClient (HTTP to runner)")
    else:
        anel_manager = ANELManager(anel_config)
        logger.info("Using ANELManager (direct UDP)")

    device_managers = {
        "pjlink": PJLinkManager(device_types_config.get("pjlink", {})),
        "netio": NETIOManager(device_types_config.get("netio", {})),
        "anel": anel_manager,
        "shell": ShellManager(device_types_config.get("shell", {})),
    }
    logger.info(f"Initialized device managers: {list(device_managers.keys())}")

    # Initialize command orchestrator
    orchestrator_config = config.get_all()
    orchestrator = CommandOrchestrator(db_manager, device_managers, orchestrator_config)
    logger.info("Command orchestrator initialized")

    # Initialize SSE broadcaster for real-time updates
    sse_broadcaster = SSEBroadcaster()
    await sse_broadcaster.start()
    logger.info("SSE broadcaster initialized")

    # Initialize state monitor with SSE broadcaster
    state_monitor = StateMonitor(
        db_manager, device_managers, orchestrator_config, sse_broadcaster=sse_broadcaster
    )
    logger.info("State monitor initialized")

    # Initialize asset service for lamp hours tracking
    asset_service = AssetService(db_manager, device_managers, orchestrator_config)
    logger.info("Asset service initialized")

    # Initialize protection service for artwork overuse prevention
    protection_service = ProtectionService(
        db_manager, sse_broadcaster=sse_broadcaster, config=orchestrator_config
    )
    logger.info("Protection service initialized")

    # Initialize satellite manager for WebSocket relay connections
    satellite_manager = SatelliteManager(db_manager, sse_broadcaster=sse_broadcaster)
    logger.info("Satellite manager initialized")

    # Initialize satellite router for command routing through satellites
    satellite_router = SatelliteRouter(satellite_manager, device_managers)
    logger.info("Satellite router initialized")

    # Initialize service health monitor for external services (runners, etc.)
    services_config = config.get("services", {})
    service_monitor = ServiceHealthMonitor(services_config)
    logger.info(f"Service health monitor initialized for: {list(services_config.keys())}")

    # Initialize unified cron scheduler
    cron_scheduler = CronScheduler(
        db_manager=db_manager,
        orchestrator=orchestrator,
        device_managers=device_managers,
        asset_service=asset_service,
        config=orchestrator_config,
    )

    # Register system tasks with the cron scheduler
    # These wrap the existing task implementations with proper dependencies
    cron_scheduler.register_system_task(
        "asset_linker",
        lambda **kwargs: run_asset_linker(db_manager, asset_service, **kwargs),
        {"batch_size": 20},
    )
    cron_scheduler.register_system_task(
        "log_cleanup",
        lambda **kwargs: run_log_cleanup(db_manager, **kwargs),
        {"retention_hours": 24},
    )
    cron_scheduler.register_system_task(
        "device_info_cache",
        lambda **kwargs: run_device_info_cache(db_manager, orchestrator, **kwargs),
        {"max_concurrent": 5, "timeout_seconds": 10},
    )
    cron_scheduler.register_system_task(
        "lamp_hours_check",
        lambda **kwargs: run_lamp_hours_check(db_manager, asset_service, **kwargs),
        {"chunk_size": 10, "delay_between_chunks": 2.0},
    )
    # One-shot task for single-device lamp hours recording (used by orchestrator)
    cron_scheduler.register_system_task(
        "lamp_hours_record",
        lambda **kwargs: run_lamp_hours_record(db_manager, asset_service, **kwargs),
        {},  # No default config - all params come from task_config
    )
    # Memory cleanup task to prevent leaks from stale cache entries
    cron_scheduler.register_system_task(
        "memory_cleanup",
        lambda **kwargs: run_memory_cleanup(db_manager, state_monitor, device_managers, **kwargs),
        {},
    )
    logger.info("Cron scheduler initialized with system tasks")

    # Connect orchestrator's verifier to state monitor for unified polling
    orchestrator.set_state_monitor(state_monitor)
    logger.info("Command verifier connected to state monitor")

    # Connect orchestrator to asset service for lamp hours recording
    orchestrator.set_asset_service(asset_service)
    logger.info("Asset service connected to orchestrator")

    # Connect scheduler to orchestrator for one-shot task scheduling (lamp hours)
    orchestrator.set_scheduler(cron_scheduler)
    logger.info("Cron scheduler connected to orchestrator")

    # Connect protection service to orchestrator for protection checks
    orchestrator.set_protection_service(protection_service)
    logger.info("Protection service connected to orchestrator")

    # Connect orchestrator to protection service for auto-OFF on budget/runtime exceeded
    protection_service.set_orchestrator(orchestrator)
    logger.info("Orchestrator connected to protection service")

    # Connect SSE broadcaster to orchestrator for real-time gate updates
    orchestrator.set_sse_broadcaster(sse_broadcaster)
    logger.info("SSE broadcaster connected to orchestrator")

    # Connect satellite router to orchestrator for satellite command routing
    orchestrator.set_satellite_router(satellite_router)
    logger.info("Satellite router connected to orchestrator")

    # Store in app state
    app.state.db_manager = db_manager
    app.state.device_managers = device_managers
    app.state.orchestrator = orchestrator
    app.state.state_monitor = state_monitor
    app.state.sse_broadcaster = sse_broadcaster
    app.state.asset_service = asset_service
    app.state.cron_scheduler = cron_scheduler
    app.state.service_monitor = service_monitor
    app.state.protection_service = protection_service
    app.state.satellite_manager = satellite_manager

    # Start config watching (hot-reload) with SSE broadcast
    def on_config_change(loader):
        """Callback when config changes - broadcast to SSE clients."""
        logger.info("Configuration changed - broadcasting to clients")
        new_config = get_config()
        monitoring_config = {
            "poll_interval_seconds": new_config.get("monitoring.poll_interval_seconds", 60),
            "fast_poll_interval_seconds": new_config.get("monitoring.fast_poll_interval_seconds", 30),
            "batch_size": new_config.get("monitoring.batch_size", 30),
            "device_timeout_seconds": new_config.get("monitoring.device_timeout_seconds", 5),
        }

        # Update state monitor intervals (thread-safe via properties)
        state_monitor.interval = monitoring_config["poll_interval_seconds"]
        state_monitor.fast_interval = monitoring_config["fast_poll_interval_seconds"]
        state_monitor.batch_size = monitoring_config["batch_size"]
        state_monitor.device_timeout = monitoring_config["device_timeout_seconds"]

        # Broadcast config change to SSE clients (use tracked task)
        state_monitor._create_background_task(
            sse_broadcaster.send_config_change(monitoring_config),
            name="sse_config_change"
        )

    config.start_watching(callback=on_config_change)
    logger.info("Configuration hot-reload enabled with SSE broadcast")

    # Start state monitoring
    await state_monitor.start()

    # Start service health monitoring
    await service_monitor.start()

    # Start cron scheduler for unified scheduling
    await cron_scheduler.start()

    # Start protection service for artwork overuse prevention
    await protection_service.start()

    logger.info("MuTech Control Service started successfully")
    logger.info("API documentation available at /docs")

    yield

    # Shutdown
    logger.info("Shutting down MuTech Control Service...")

    # Cancel all active verifications first
    cancelled = await orchestrator.command_verifier.cancel_all_verifications()
    if cancelled:
        logger.info(f"Cancelled {cancelled} active verifications")

    # Stop protection service
    await protection_service.stop()

    # Stop cron scheduler
    await cron_scheduler.stop()

    # Stop service health monitoring
    await service_monitor.stop()

    # Stop state monitoring (this also cancels background tasks)
    await state_monitor.stop()

    # Stop SSE broadcaster
    await sse_broadcaster.stop()

    config.stop_watching()

    # Close device manager connections
    for device_type, manager in device_managers.items():
        if hasattr(manager, "close"):
            try:
                await manager.close()
                logger.info(f"Closed {device_type} manager")
            except Exception as e:
                logger.error(f"Error closing {device_type} manager: {e}")

    await db_manager.close()

    logger.info("MuTech Control Service shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="MuTech Control Service",
    description="Museum device control system API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
config = get_config()
cors_origins = config.get("api.cors_origins", ["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(control.router)
app.include_router(fast.router)
app.include_router(state.router)
app.include_router(admin.router)
app.include_router(debug.router)
app.include_router(assets.router)
app.include_router(satellite.router)

# Mount static files directory if it exists
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Root endpoint - serve web interface
@app.get("/")
async def root():
    """Serve web interface."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"service": "MuTech Control Service", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


# PWA files - serve from root for proper service worker scope
@app.get("/sw.js")
async def service_worker():
    """Serve service worker from root for proper scope."""
    sw_path = static_dir / "sw.js"
    if sw_path.exists():
        return FileResponse(sw_path, media_type="application/javascript")
    return Response(status_code=404)


@app.get("/manifest.json")
async def manifest():
    """Serve PWA manifest from root."""
    manifest_path = static_dir / "manifest.json"
    if manifest_path.exists():
        return FileResponse(manifest_path, media_type="application/manifest+json")
    return Response(status_code=404)


@app.get("/icon-{size}.png")
async def pwa_icon(size: str):
    """Serve PWA icons from root."""
    icon_path = static_dir / f"icon-{size}.png"
    if icon_path.exists():
        return FileResponse(icon_path, media_type="image/png")
    return Response(status_code=404)


@app.get("/apple-touch-icon.png")
async def apple_touch_icon():
    """Serve Apple touch icon from root."""
    icon_path = static_dir / "apple-touch-icon.png"
    if icon_path.exists():
        return FileResponse(icon_path, media_type="image/png")
    return Response(status_code=404)


@app.get("/icon.svg")
async def svg_icon():
    """Serve SVG icon from root."""
    icon_path = static_dir / "icon.svg"
    if icon_path.exists():
        return FileResponse(icon_path, media_type="image/svg+xml")
    return Response(status_code=404)


@app.get("/info")
async def info():
    """System information endpoint."""
    config = get_config()

    return {
        "version": "1.0.0",
        "device_types_supported": ["pjlink", "netio", "anel", "shell"],
        "features": {
            "on_stagger": True,
            "off_verification": True,
            "fast_lane": True,
            "hot_reload_config": True,
        },
        "orchestrator": {
            "on_stagger_delay": config.get("orchestrator.on_stagger_delay_seconds"),
            "max_concurrent_on": config.get("orchestrator.max_concurrent_on_commands"),
            "off_verification_enabled": config.get("orchestrator.enable_off_verification"),
        },
    }


if __name__ == "__main__":
    import uvicorn

    config = get_config()
    host = config.get("server.host", "0.0.0.0")
    port = config.get("server.port", 8000)
    reload = config.get("server.reload", False)

    uvicorn.run(
        "mutech_control.main:app",
        host=host,
        port=port,
        reload=reload,
    )
