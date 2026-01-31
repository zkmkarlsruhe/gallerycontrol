# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""ANEL Runner Service - UDP-to-HTTP relay for ANEL device control.

This service is a simple bridge between HTTP and UDP. It has no state,
no credential storage - everything comes from the backend per-request.
"""

import asyncio
import logging
import os
import socket
import select
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ANEL UDP ports
ANEL_SEND_PORT = 75
ANEL_RECV_PORT = 77

# Timeouts
DEFAULT_TIMEOUT = 3.0  # seconds

# Create FastAPI app
app = FastAPI(
    title="ANEL Runner Service",
    description="UDP-to-HTTP relay for ANEL power distribution control",
    version="2.0.0",
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


class QueryRequest(BaseModel):
    ip: str
    timeout: float = DEFAULT_TIMEOUT


class SwitchRequest(BaseModel):
    ip: str
    port: int  # 0-based port number
    state: bool  # True = on, False = off
    username: str
    password: str
    timeout: float = DEFAULT_TIMEOUT


class DeviceState(BaseModel):
    ip: str
    name: str
    ports: list[dict]  # [{port: 0, name: "...", state: 0/1}, ...]
    raw: str


def parse_anel_response(data: bytes, sender_ip: str) -> DeviceState:
    """Parse ANEL UDP response into structured data.

    Format: NET-PwrCtrl:NAME:IP:MASK:GW:MAC:port1_name,state:port2_name,state:...:flags
    """
    msg = data.decode('latin-1').strip()

    if not msg.startswith('NET-PwrCtrl:'):
        raise ValueError(f"Invalid ANEL response: {msg[:50]}")

    parts = msg.split(':')
    device_name = parts[1].strip() if len(parts) > 1 else "Unknown"

    # Find port states - format is "name,state" for each port
    # They come after the MAC address (which has format XX.XX.XX.XX.XX.XX)
    ports = []
    port_idx = 0

    for i, part in enumerate(parts):
        if ',' in part and len(part.split(',')) == 2:
            name_state = part.split(',')
            try:
                state = int(name_state[1])
                ports.append({
                    "port": port_idx,
                    "name": name_state[0].strip() or f"Port {port_idx + 1}",
                    "state": state
                })
                port_idx += 1
            except ValueError:
                continue

    return DeviceState(
        ip=sender_ip,
        name=device_name,
        ports=ports,
        raw=msg
    )


def udp_query(ip: str, timeout: float) -> bytes:
    """Send UDP query and wait for response."""
    import time

    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    recv_sock.bind(('0.0.0.0', ANEL_RECV_PORT))
    recv_sock.setblocking(False)

    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        # Send query
        send_sock.sendto(b'wer da?', (ip, ANEL_SEND_PORT))
        logger.debug(f"Sent query to {ip}:{ANEL_SEND_PORT}")

        # Wait for response from this specific IP
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError(f"No response from {ip} within {timeout}s")

            ready, _, _ = select.select([recv_sock], [], [], min(remaining, 0.5))
            if ready:
                data, addr = recv_sock.recvfrom(4096)
                if addr[0] == ip:
                    logger.debug(f"Received response from {ip}: {len(data)} bytes")
                    return data
                # Ignore responses from other devices
                logger.debug(f"Ignoring response from {addr[0]}, waiting for {ip}")
    finally:
        recv_sock.close()
        send_sock.close()


def udp_switch(ip: str, port: int, state: bool, username: str, password: str) -> None:
    """Send switch command via UDP."""
    port_num = port + 1  # ANEL uses 1-based port numbers

    if state:
        cmd = f"Sw_on{port_num}{username}{password}"
    else:
        cmd = f"Sw_off{port_num}{username}{password}"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(cmd.encode('latin-1'), (ip, ANEL_SEND_PORT))
        logger.info(f"Sent {'ON' if state else 'OFF'} command to {ip} port {port}")
    finally:
        sock.close()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "ANEL Runner Service",
        "version": "2.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint (no auth required)."""
    return {"status": "healthy"}


@app.post("/query")
async def query_device(
    request: QueryRequest,
    authorization: str = Header(...),
):
    """Query ANEL device state via UDP.

    Sends "wer da?" query and returns parsed response.
    """
    verify_api_key(authorization)

    try:
        # Run UDP in thread pool to not block
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None,
            udp_query,
            request.ip,
            request.timeout
        )

        state = parse_anel_response(data, request.ip)
        return {"success": True, "device": state.model_dump()}

    except TimeoutError as e:
        logger.warning(f"Timeout querying {request.ip}: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error querying {request.ip}: {e}")
        return {"success": False, "error": str(e)}


@app.post("/switch")
async def switch_port(
    request: SwitchRequest,
    authorization: str = Header(...),
):
    """Switch ANEL port on/off.

    Sends switch command, then queries state to confirm.
    """
    verify_api_key(authorization)

    try:
        # Send switch command
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            udp_switch,
            request.ip,
            request.port,
            request.state,
            request.username,
            request.password
        )

        # Small delay for device to process
        await asyncio.sleep(0.3)

        # Query state to confirm
        data = await loop.run_in_executor(
            None,
            udp_query,
            request.ip,
            request.timeout
        )

        state = parse_anel_response(data, request.ip)

        # Check if port state matches requested
        port_state = None
        for p in state.ports:
            if p["port"] == request.port:
                port_state = p["state"]
                break

        expected = 1 if request.state else 0
        confirmed = port_state == expected

        return {
            "success": True,
            "confirmed": confirmed,
            "device": state.model_dump(),
            "requested_port": request.port,
            "requested_state": request.state,
            "actual_state": port_state
        }

    except TimeoutError as e:
        logger.warning(f"Timeout switching {request.ip}: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error switching {request.ip}: {e}")
        return {"success": False, "error": str(e)}


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
