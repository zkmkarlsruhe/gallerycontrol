# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Satellite WebSocket API endpoints."""

from typing import Optional

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from mutech_control.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["satellite"])


@router.websocket("/ws/satellite/onboard")
async def satellite_onboard(websocket: WebSocket):
    """
    WebSocket endpoint for new satellite onboarding.

    Protocol:
    1. Satellite connects and sends: {"type": "hello", "api_key": "...", "info": {...}}
    2. Server responds: {"type": "pending", "message": "Awaiting approval"}
    3. When approved, server sends: {"type": "approved", "satellite_id": "...", "name": "..."}
    4. Satellite should reconnect to /ws/satellite with its api_key

    Or if already approved:
    1. Satellite sends hello
    2. Server responds: {"type": "approved", "satellite_id": "...", "name": "..."}
    """
    await websocket.accept()

    satellite_manager = websocket.app.state.satellite_manager

    try:
        # Wait for hello message
        data = await websocket.receive_json()

        if data.get("type") != "hello":
            await websocket.send_json({
                "type": "error",
                "message": "Expected hello message",
            })
            await websocket.close(code=4000, reason="Invalid protocol")
            return

        api_key = data.get("api_key")
        if not api_key:
            await websocket.send_json({
                "type": "error",
                "message": "Missing api_key",
            })
            await websocket.close(code=4000, reason="Missing api_key")
            return

        info = data.get("info", {})
        hostname = info.get("hostname")
        version = info.get("version")

        # Handle onboarding
        result = await satellite_manager.handle_onboard(
            websocket, api_key, hostname, version
        )

        if result:
            # Already approved - notify and close (satellite should reconnect to main endpoint)
            await websocket.send_json({
                "type": "approved",
                "satellite_id": result["satellite_id"],
                "name": result["name"],
            })
            await websocket.close(code=1000, reason="Approved")
            return

        # Pending - send pending message and keep connection open
        await websocket.send_json({
            "type": "pending",
            "message": "Awaiting approval from administrator",
        })

        logger.info(
            "Satellite awaiting approval",
            hostname=hostname,
            version=version,
        )

        # Keep connection alive until approved, rejected, or disconnected
        # The satellite manager will notify us via the WebSocket when approved/rejected
        while True:
            try:
                # Just keep the connection alive and wait for messages
                data = await websocket.receive_json()

                if data.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

            except WebSocketDisconnect:
                logger.info("Satellite disconnected during onboarding")
                break

    except WebSocketDisconnect:
        logger.info("Satellite disconnected during onboarding")
    except Exception as e:
        logger.error(f"Error in satellite onboarding: {e}")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=4000, reason=str(e))


@router.websocket("/ws/satellite")
async def satellite_main(websocket: WebSocket):
    """
    Main WebSocket endpoint for approved satellites.

    Protocol:
    1. Satellite connects and sends: {"type": "auth", "api_key": "..."}
    2. Server responds: {"type": "connected", "satellite_id": "...", "name": "..."}
    3. Server sends commands: {"type": "command", "cmd_id": "...", "device_type": "...", ...}
    4. Satellite responds: {"type": "result", "cmd_id": "...", "success": true, "state": 1}
    5. Satellite can send heartbeats: {"type": "heartbeat"}
    """
    await websocket.accept()

    satellite_manager = websocket.app.state.satellite_manager
    connection = None

    try:
        # Wait for auth message
        data = await websocket.receive_json()

        if data.get("type") != "auth":
            await websocket.send_json({
                "type": "error",
                "message": "Expected auth message",
            })
            await websocket.close(code=4000, reason="Invalid protocol")
            return

        api_key = data.get("api_key")
        if not api_key:
            await websocket.send_json({
                "type": "error",
                "message": "Missing api_key",
            })
            await websocket.close(code=4000, reason="Missing api_key")
            return

        # Connect
        connection = await satellite_manager.connect(websocket, api_key)

        if not connection:
            await websocket.send_json({
                "type": "error",
                "message": "Unauthorized",
            })
            await websocket.close(code=4001, reason="Unauthorized")
            return

        # Send connected confirmation
        await websocket.send_json({
            "type": "connected",
            "satellite_id": str(connection.satellite_id),
            "name": connection.name,
        })

        logger.info(
            "Satellite authenticated",
            satellite_id=str(connection.satellite_id)[:8],
            name=connection.name,
        )

        # Main message loop
        while True:
            try:
                data = await websocket.receive_json()
                msg_type = data.get("type")

                if msg_type == "result":
                    # Command result
                    cmd_id = data.get("cmd_id")
                    if cmd_id:
                        await satellite_manager.handle_result(cmd_id, {
                            "success": data.get("success", False),
                            "state": data.get("state", -1),
                            "error": data.get("error"),
                            "raw_response": data.get("raw_response"),
                        })

                elif msg_type == "heartbeat":
                    await satellite_manager.handle_heartbeat(connection.satellite_id)
                    await websocket.send_json({"type": "heartbeat_ack"})

                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

                else:
                    logger.warning(
                        "Unknown message type from satellite",
                        msg_type=msg_type,
                        satellite_id=str(connection.satellite_id)[:8],
                    )

            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Error in satellite main connection: {e}")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=4000, reason=str(e))
    finally:
        if connection:
            await satellite_manager.disconnect(connection.satellite_id)
