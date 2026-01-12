"""ANEL Runner Service - REST API for ANEL device control."""

import logging
import os
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="ANEL Runner Service",
    description="REST API for ANEL power distribution control",
    version="1.0.0",
)

# API Key from environment
API_KEY = os.getenv("API_KEY", "secure-api-key-change-me")


def verify_api_key(authorization: Optional[str] = Header(None)):
    """Verify API key from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    token = authorization.replace("Bearer ", "")
    if token != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "ANEL Runner Service",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint (no auth required)."""
    return {"status": "healthy"}


@app.get("/devices/{ip}/state")
async def get_device_state(
    ip: str,
    port: int = Query(..., description="Port number (0-7)"),
    authorization: str = Header(...),
):
    """Get ANEL device state."""
    verify_api_key(authorization)

    try:
        # TODO: Implement pypwrctrl integration
        logger.info(f"Getting state for ANEL device {ip}:{port}")

        # Placeholder response
        return {
            "success": True,
            "state": 0,  # 0 = off, 1 = on
            "ip": ip,
            "port": port
        }

    except Exception as e:
        logger.error(f"Error getting device state: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/devices/{ip}/on")
async def turn_device_on(
    ip: str,
    port: int = Query(..., description="Port number (0-7)"),
    authorization: str = Header(...),
):
    """Turn ANEL device on."""
    verify_api_key(authorization)

    try:
        # TODO: Implement pypwrctrl integration
        logger.info(f"Turning ON ANEL device {ip}:{port}")

        # Placeholder response
        return {
            "success": True,
            "state": 1,
            "ip": ip,
            "port": port
        }

    except Exception as e:
        logger.error(f"Error turning device on: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/devices/{ip}/off")
async def turn_device_off(
    ip: str,
    port: int = Query(..., description="Port number (0-7)"),
    authorization: str = Header(...),
):
    """Turn ANEL device off."""
    verify_api_key(authorization)

    try:
        # TODO: Implement pypwrctrl integration
        logger.info(f"Turning OFF ANEL device {ip}:{port}")

        # Placeholder response
        return {
            "success": True,
            "state": 0,
            "ip": ip,
            "port": port
        }

    except Exception as e:
        logger.error(f"Error turning device off: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.get("/devices/{ip}/info")
async def get_device_info(
    ip: str,
    authorization: str = Header(...),
):
    """Get ANEL device information."""
    verify_api_key(authorization)

    try:
        # TODO: Implement pypwrctrl integration
        logger.info(f"Getting info for ANEL device {ip}")

        # Placeholder response
        return {
            "success": True,
            "ip": ip,
            "model": "ANEL NET-PwrCtrl",
            "ports": 8
        }

    except Exception as e:
        logger.error(f"Error getting device info: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run(
        "anel_runner.main:app",
        host=host,
        port=port,
        reload=False,
    )
