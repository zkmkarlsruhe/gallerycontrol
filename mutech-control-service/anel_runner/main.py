"""ANEL Runner Service - FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from anel_runner import __version__
from anel_runner.api.models import HealthResponse, ServiceInfoResponse
from anel_runner.api.routes import router
from anel_runner.config import ANELConfig, get_config
from anel_runner.core.anel_service import ANELService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    config = get_config()

    # Configure log level from config
    logging.getLogger().setLevel(config.log_level)

    # Initialize ANEL service
    service = ANELService(config)
    await service.start()

    app.state.anel_service = service
    app.state.config = config

    logger.info(f"ANEL Runner v{__version__} started on {config.host}:{config.port}")
    logger.info(f"UDP send port: {config.udp_send_port}, receive port: {config.udp_receive_port}")
    logger.info(f"Command delay: {config.command_delay_seconds}s")

    yield

    # Shutdown
    logger.info("Shutting down ANEL Runner...")
    await service.shutdown()
    logger.info("ANEL Runner shutdown complete")


app = FastAPI(
    title="ANEL Runner Service",
    description="REST API for ANEL power outlet control via UDP protocol",
    version=__version__,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include device routes
app.include_router(router)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """
    Service health check.

    Returns queue status and processing state.
    """
    service: ANELService = app.state.anel_service
    return HealthResponse(
        status="healthy",
        queue_length=service.queue_length,
        is_processing=service.is_processing,
    )


@app.get("/info", response_model=ServiceInfoResponse, tags=["system"])
async def info() -> ServiceInfoResponse:
    """
    Service information.

    Returns configuration details.
    """
    config: ANELConfig = app.state.config
    return ServiceInfoResponse(
        version=__version__,
        udp_send_port=config.udp_send_port,
        udp_receive_port=config.udp_receive_port,
        command_delay_seconds=config.command_delay_seconds,
    )


def main():
    """Run the ANEL runner service."""
    import uvicorn

    config = get_config()
    uvicorn.run(
        "anel_runner.main:app",
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    main()
