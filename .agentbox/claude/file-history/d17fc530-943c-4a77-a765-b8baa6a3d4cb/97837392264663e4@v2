"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mutech_control.api import admin, control, fast, state
from mutech_control.config import get_config
from mutech_control.database.connection import get_db_manager
from mutech_control.devices.anel_client import ANELClient
from mutech_control.devices.netio_manager import NETIOManager
from mutech_control.devices.pjlink_manager import PJLinkManager
from mutech_control.devices.shell_manager import ShellManager
from mutech_control.orchestrator.command_orchestrator import CommandOrchestrator

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

    # Initialize device managers
    device_types_config = config.get("device_types", {})

    device_managers = {
        "pjlink": PJLinkManager(device_types_config.get("pjlink", {})),
        "netio": NETIOManager(device_types_config.get("netio", {})),
        "anel": ANELClient(device_types_config.get("anel", {})),
        "shell": ShellManager(device_types_config.get("shell", {})),
    }
    logger.info(f"Initialized device managers: {list(device_managers.keys())}")

    # Initialize command orchestrator
    orchestrator_config = config.get_all()
    orchestrator = CommandOrchestrator(db_manager, device_managers, orchestrator_config)
    logger.info("Command orchestrator initialized")

    # Store in app state
    app.state.db_manager = db_manager
    app.state.device_managers = device_managers
    app.state.orchestrator = orchestrator

    # Start config watching (hot-reload)
    def on_config_change(loader):
        """Callback when config changes."""
        logger.info("Configuration changed - updating managers")
        # TODO: Update device manager configs dynamically
        # For now, changes will be picked up on next operation

    config.start_watching(callback=on_config_change)
    logger.info("Configuration hot-reload enabled")

    logger.info("MuTech Control Service started successfully")
    logger.info("API documentation available at /docs")

    yield

    # Shutdown
    logger.info("Shutting down MuTech Control Service...")

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


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {"service": "MuTech Control Service", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


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
