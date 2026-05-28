# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Service Health Monitor - tracks health of external services/runners."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

from gallerycontrol.utils.datetime_utils import utc_now
from enum import Enum
from typing import Callable

import httpx

logger = logging.getLogger(__name__)


class ServiceStatus(str, Enum):
    """Service health status."""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealth:
    """Health state of a service."""
    service_id: str
    name: str
    description: str
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_check: datetime | None = None
    last_seen: datetime | None = None
    error: str | None = None
    response_time_ms: int | None = None
    affects_device_types: list[str] = field(default_factory=list)
    consecutive_failures: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "service_id": self.service_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "error": self.error,
            "response_time_ms": self.response_time_ms,
            "affects_device_types": self.affects_device_types,
            "consecutive_failures": self.consecutive_failures,
        }


class ServiceHealthMonitor:
    """Monitor health of external services/runners.

    Periodically checks health endpoints and tracks service status.
    Emits events when service status changes.
    """

    def __init__(self, services_config: dict):
        """Initialize with services configuration.

        Args:
            services_config: Dict of service_id -> service config
        """
        self.services_config = services_config
        self._services: dict[str, ServiceHealth] = {}
        self._http_client: httpx.AsyncClient | None = None
        self._check_tasks: dict[str, asyncio.Task] = {}
        self._running = False
        self._status_callbacks: list[Callable[[str, ServiceStatus, ServiceStatus], None]] = []

        # Initialize service health objects
        for service_id, config in services_config.items():
            self._services[service_id] = ServiceHealth(
                service_id=service_id,
                name=config.get("name", service_id),
                description=config.get("description", ""),
                affects_device_types=config.get("affects_device_types", []),
            )

    def on_status_change(self, callback: Callable[[str, ServiceStatus, ServiceStatus], None]):
        """Register callback for status changes.

        Callback receives: (service_id, old_status, new_status)
        """
        self._status_callbacks.append(callback)

    async def start(self):
        """Start health monitoring."""
        if self._running:
            return

        self._running = True
        self._http_client = httpx.AsyncClient()

        logger.info(f"Service health monitor starting for services: {list(self.services_config.keys())}")

        # Start check loop for each service
        for service_id, config in self.services_config.items():
            task = asyncio.create_task(
                self._check_loop(service_id, config),
                name=f"service_health_{service_id}",
            )
            self._check_tasks[service_id] = task

        logger.info("Service health monitor started")

    async def stop(self):
        """Stop health monitoring."""
        self._running = False

        # Cancel all check tasks
        for task in self._check_tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._check_tasks.clear()

        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        logger.info("Service health monitor stopped")

    async def _check_loop(self, service_id: str, config: dict):
        """Health check loop for a single service."""
        interval = config.get("check_interval_seconds", 30)

        # Initial check immediately
        await self._check_service(service_id, config)

        while self._running:
            try:
                await asyncio.sleep(interval)
                if not self._running:
                    break
                await self._check_service(service_id, config)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in service health check loop: service={service_id}, error={e}")

    async def _check_service(self, service_id: str, config: dict):
        """Check health of a single service."""
        service = self._services[service_id]
        old_status = service.status

        url = config.get("url", "")
        health_endpoint = config.get("health_endpoint", "/health")
        timeout = config.get("timeout_seconds", 5)

        if not url:
            service.status = ServiceStatus.UNKNOWN
            service.error = "No URL configured"
            service.last_check = utc_now()
            return

        full_url = f"{url.rstrip('/')}{health_endpoint}"

        try:
            start = asyncio.get_event_loop().time()
            response = await self._http_client.get(full_url, timeout=timeout)
            elapsed_ms = int((asyncio.get_event_loop().time() - start) * 1000)

            service.last_check = utc_now()
            service.response_time_ms = elapsed_ms

            if response.status_code == 200:
                service.status = ServiceStatus.ONLINE
                service.last_seen = utc_now()
                service.error = None
                service.consecutive_failures = 0

                logger.debug(f"Service health check OK: service={service_id}, response_time_ms={elapsed_ms}")
            else:
                service.status = ServiceStatus.DEGRADED
                service.error = f"HTTP {response.status_code}"
                service.consecutive_failures += 1

                logger.warning(f"Service health check failed: service={service_id}, status_code={response.status_code}")

        except httpx.ConnectError as e:
            service.status = ServiceStatus.OFFLINE
            service.error = "Connection refused"
            service.last_check = utc_now()
            service.consecutive_failures += 1

            logger.warning(f"Service offline: service={service_id}, error=Connection refused")

        except httpx.TimeoutException:
            service.status = ServiceStatus.OFFLINE
            service.error = f"Timeout after {timeout}s"
            service.last_check = utc_now()
            service.consecutive_failures += 1

            logger.warning(f"Service health check timeout: service={service_id}, timeout={timeout}s")

        except Exception as e:
            service.status = ServiceStatus.OFFLINE
            service.error = str(e)
            service.last_check = utc_now()
            service.consecutive_failures += 1

            logger.error(f"Service health check error: service={service_id}, error={e}")

        # Notify callbacks if status changed
        if old_status != service.status:
            logger.info(f"Service status changed: service={service_id}, {old_status.value} -> {service.status.value}")
            for callback in self._status_callbacks:
                try:
                    result = callback(service_id, old_status, service.status)
                    if asyncio.iscoroutine(result):
                        # Create task with error handling
                        task = asyncio.create_task(result)
                        task.add_done_callback(
                            lambda t: logger.error(
                                f"Async callback failed: service={service_id}, error={t.exception()}"
                            ) if t.exception() else None
                        )
                except Exception as e:
                    logger.error(f"Error in status change callback: service={service_id}, error={e}")

    def get_service_health(self, service_id: str) -> ServiceHealth | None:
        """Get health status of a specific service."""
        return self._services.get(service_id)

    def get_all_services(self) -> dict[str, ServiceHealth]:
        """Get health status of all services."""
        return dict(self._services)

    def is_service_online(self, service_id: str) -> bool:
        """Check if a service is online."""
        service = self._services.get(service_id)
        return service is not None and service.status == ServiceStatus.ONLINE

    def get_service_for_device_type(self, device_type: str) -> ServiceHealth | None:
        """Get the service that affects a device type."""
        for service in self._services.values():
            if device_type in service.affects_device_types:
                return service
        return None

    async def check_now(self, service_id: str) -> ServiceHealth | None:
        """Trigger immediate health check for a service."""
        if service_id not in self.services_config:
            return None

        await self._check_service(service_id, self.services_config[service_id])
        return self._services.get(service_id)
