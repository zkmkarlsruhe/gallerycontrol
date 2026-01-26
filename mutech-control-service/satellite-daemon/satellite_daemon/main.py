"""Main entry point for satellite daemon."""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from .config import Config
from .ws_client import WebSocketClient
from .handlers import handle_command

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_daemon(config: Config) -> None:
    """Run the satellite daemon."""
    logger.info("Starting satellite daemon...")
    logger.info(f"Server URL: {config.server_url}")
    logger.info(f"Hostname: {config.hostname}")

    if config.is_approved:
        logger.info(f"Satellite ID: {config.satellite_id}")
        logger.info(f"Satellite name: {config.satellite_name}")
    else:
        logger.info("Not yet approved - will connect for onboarding")

    client = WebSocketClient(config, handle_command)

    # Set up signal handlers
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Received shutdown signal")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Run client with graceful shutdown
    client_task = asyncio.create_task(client.run())

    try:
        await stop_event.wait()
    finally:
        logger.info("Shutting down...")
        await client.stop()
        client_task.cancel()
        try:
            await client_task
        except asyncio.CancelledError:
            pass

    logger.info("Satellite daemon stopped")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Satellite daemon for MuTech Control")
    parser.add_argument(
        "-c", "--config",
        type=Path,
        help="Path to config file (default: /etc/satellite-daemon/config.yaml)",
    )
    parser.add_argument(
        "-s", "--state",
        type=Path,
        help="Path to state file (default: /var/lib/satellite-daemon/state.yaml)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load configuration
    config = Config(
        config_path=args.config,
        state_path=args.state,
    )

    try:
        config.load()
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    # Validate config
    try:
        _ = config.server_url
    except ValueError as e:
        logger.error(str(e))
        logger.error("Please create config.yaml with server_url setting")
        sys.exit(1)

    # Run daemon
    try:
        asyncio.run(run_daemon(config))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
