"""WebSocket client for satellite daemon."""

import asyncio
import json
import logging
from typing import Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosed

from .config import Config
from . import __version__

logger = logging.getLogger(__name__)


class WebSocketClient:
    """WebSocket client for connecting to the control server."""

    def __init__(self, config: Config, command_handler: Callable):
        self.config = config
        self.command_handler = command_handler
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def run(self) -> None:
        """Main run loop with automatic reconnection."""
        self._running = True

        while self._running:
            try:
                if not self.config.is_approved:
                    await self._run_onboarding()
                else:
                    await self._run_main()
            except Exception as e:
                logger.error(f"Connection error: {e}")

            if self._running:
                logger.info(f"Reconnecting in {self.config.reconnect_delay}s...")
                await asyncio.sleep(self.config.reconnect_delay)

    async def stop(self) -> None:
        """Stop the client."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()

    async def _run_onboarding(self) -> None:
        """Run onboarding flow to get approved."""
        onboard_url = self.config.server_url.rstrip("/") + "/ws/satellite/onboard"
        logger.info(f"Connecting to onboarding endpoint: {onboard_url}")

        async with websockets.connect(onboard_url) as ws:
            self._ws = ws

            # Send hello
            hello_msg = json.dumps({
                "type": "hello",
                "api_key": self.config.api_key,
                "info": {
                    "hostname": self.config.hostname,
                    "version": __version__,
                },
            })
            await ws.send(hello_msg)

            # Wait for response
            while True:
                try:
                    data = await asyncio.wait_for(ws.recv(), timeout=60)
                    msg = json.loads(data)

                    if msg.get("type") == "approved":
                        logger.info(f"Approved as: {msg.get('name')}")
                        self.config.satellite_id = msg.get("satellite_id")
                        self.config.satellite_name = msg.get("name")
                        return
                    elif msg.get("type") == "rejected":
                        logger.error("Registration rejected by server")
                        await asyncio.sleep(60)  # Wait before retrying
                        return
                    elif msg.get("type") == "pending":
                        logger.info("Waiting for approval from administrator...")
                    elif msg.get("type") == "pong":
                        pass

                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    await ws.send('{"type": "ping"}')

    async def _run_main(self) -> None:
        """Run main connection loop."""
        main_url = self.config.server_url.rstrip("/") + "/ws/satellite"
        logger.info(f"Connecting to main endpoint: {main_url}")

        async with websockets.connect(main_url) as ws:
            self._ws = ws

            # Send auth
            auth_msg = json.dumps({
                "type": "auth",
                "api_key": self.config.api_key,
            })
            await ws.send(auth_msg)

            # Wait for connected confirmation
            data = await ws.recv()
            msg = json.loads(data)

            if msg.get("type") == "error":
                logger.error(f"Auth failed: {msg.get('message')}")
                # Clear state and re-onboard
                self.config._state.pop("satellite_id", None)
                self.config._state.pop("name", None)
                self.config.save_state()
                return

            if msg.get("type") != "connected":
                logger.error(f"Unexpected response: {msg}")
                return

            logger.info(f"Connected as: {msg.get('name')}")

            # Start heartbeat task
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # Main message loop
            try:
                async for message in ws:
                    await self._handle_message(message)
            except ConnectionClosed:
                logger.warning("Connection closed by server")
            finally:
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        while True:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)
                if self._ws:
                    await self._ws.send('{"type": "heartbeat"}')
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                break

    async def _handle_message(self, raw_message: str) -> None:
        """Handle incoming message."""
        try:
            msg = json.loads(raw_message)
            msg_type = msg.get("type")

            if msg_type == "command":
                await self._handle_command(msg)
            elif msg_type == "heartbeat_ack":
                pass
            elif msg_type == "pong":
                pass
            else:
                logger.warning(f"Unknown message type: {msg_type}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def _handle_command(self, msg: dict) -> None:
        """Handle command from server."""
        cmd_id = msg.get("cmd_id")
        device_type = msg.get("device_type")
        device = msg.get("device", {})
        command = msg.get("command")

        logger.info(
            f"Received command: {command} for {device.get('name')} ({device_type})"
        )

        try:
            result = await asyncio.wait_for(
                self.command_handler(device_type, device, command),
                timeout=self.config.command_timeout,
            )
        except asyncio.TimeoutError:
            result = {"success": False, "state": -1, "error": "Command timeout"}
        except Exception as e:
            result = {"success": False, "state": -1, "error": str(e)}

        # Send result back
        response = {
            "type": "result",
            "cmd_id": cmd_id,
            "success": result.get("success", False),
            "state": result.get("state", -1),
            "error": result.get("error"),
            "raw_response": result.get("raw_response"),
        }

        await self._ws.send(json.dumps(response))
