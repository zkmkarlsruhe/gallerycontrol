# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Asset tracking service for projector lamp hours."""

import asyncio
import re
import socket
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from gallerycontrol.database.models import Asset, Artwork, Device, Exhibition, LampHoursLog
from gallerycontrol.utils.datetime_utils import ensure_utc
from gallerycontrol.utils.logging import get_logger

logger = get_logger(__name__)


class AssetService:
    """Service for tracking projector assets and lamp hours."""

    def __init__(self, db_manager, device_managers: Dict, config: dict):
        self.db_manager = db_manager
        self.device_managers = device_managers
        self.config = config

        # Get asset tracking config
        asset_config = config.get("asset_tracking", {})
        pattern = asset_config.get("hostname_pattern", r"-(\d{6,})\.")
        self.hostname_pattern = re.compile(pattern)
        self.dns_resolve_interval = asset_config.get("dns_resolve_interval", 3600)

    def extract_asset_number(self, hostname: str) -> Optional[str]:
        r"""Extract asset number from hostname using configurable pattern.

        Default pattern: -(\d{6,})\. matches asset numbers like:
        - projector-100018987.local -> 100018987
        - pj-123456.zkm.de -> 123456
        """
        if not hostname:
            return None
        match = self.hostname_pattern.search(hostname)
        return match.group(1) if match else None

    async def resolve_dns(self, host: str) -> Optional[str]:
        """Resolve IP to hostname or hostname to IP.

        Args:
            host: IP address or hostname

        Returns:
            Resolved hostname if input was IP, resolved IP if input was hostname,
            or None if resolution failed
        """
        try:
            loop = asyncio.get_event_loop()

            # Check if input looks like an IP
            try:
                socket.inet_aton(host)
                is_ip = True
            except socket.error:
                is_ip = False

            if is_ip:
                # Reverse DNS lookup
                result = await loop.run_in_executor(
                    None,
                    lambda: socket.gethostbyaddr(host)
                )
                return result[0]  # Returns (hostname, aliases, addresses)
            else:
                # Forward DNS lookup
                result = await loop.run_in_executor(
                    None,
                    lambda: socket.gethostbyname(host)
                )
                return result

        except (socket.herror, socket.gaierror, socket.timeout) as e:
            logger.debug("DNS resolution failed", host=host, error=str(e))
            return None
        except Exception as e:
            logger.warning("Unexpected DNS error", host=host, error=str(e))
            return None

    async def get_or_create_asset(
        self,
        asset_number: str,
        hostname: Optional[str],
        session
    ) -> Asset:
        """Get existing asset or create new one.

        Args:
            asset_number: Unique asset identifier
            hostname: Full resolved hostname
            session: Database session

        Returns:
            Asset instance
        """
        # Try to find existing asset
        stmt = select(Asset).where(Asset.asset_number == asset_number)
        result = await session.execute(stmt)
        asset = result.scalar_one_or_none()

        if asset:
            # Update hostname if different and not manually set by user
            if hostname and asset.hostname != hostname and not asset.hostname_manual:
                asset.hostname = hostname
                asset.updated_at = datetime.utcnow()
            return asset

        # Create new asset
        asset = Asset(
            asset_number=asset_number,
            hostname=hostname,
        )
        session.add(asset)
        await session.flush()

        logger.info("Created new asset", asset_number=asset_number, hostname=hostname)
        return asset

    async def record_lamp_hours(
        self,
        device_id: UUID,
        event_type: str,
        session=None,
    ) -> Optional[LampHoursLog]:
        """Record lamp hours for a PJLink device.

        Fetches current reading from projector and creates log entry.

        Args:
            device_id: Device UUID
            event_type: 'onboard', 'power_on', 'power_off', 'offboard', 'manual'
            session: Optional existing session (creates own if not provided)

        Returns:
            Created LampHoursLog or None if failed
        """
        own_session = session is None

        if own_session:
            async with self.db_manager.session() as session:
                return await self._record_lamp_hours_impl(device_id, event_type, session)
        else:
            return await self._record_lamp_hours_impl(device_id, event_type, session)

    async def _record_lamp_hours_impl(
        self,
        device_id: UUID,
        event_type: str,
        session,
    ) -> Optional[LampHoursLog]:
        """Internal implementation of lamp hours recording."""
        # Get device with relationships
        stmt = (
            select(Device)
            .where(Device.id == device_id)
            .options(
                selectinload(Device.artwork).selectinload(Artwork.exhibition)
            )
        )
        result = await session.execute(stmt)
        device = result.scalar_one_or_none()

        if not device:
            logger.warning("Device not found for lamp hours", device_id=str(device_id))
            return None

        if device.device_type != 'pjlink':
            logger.debug("Not a PJLink device, skipping lamp hours", device=device.name)
            return None

        if not device.asset_id:
            logger.warning("Device has no asset link, skipping lamp hours", device=device.name)
            return None

        # Query current lamp hours from projector
        try:
            manager = self.device_managers.get('pjlink')
            if not manager:
                logger.error("PJLink manager not available")
                return None

            info = await manager.get_device_info(device)
            lamp_hours = info.get('lamp_hours')

            if lamp_hours is None:
                logger.warning("Could not get lamp hours", device=device.name)
                return None

        except Exception as e:
            logger.error("Failed to query lamp hours", device=device.name, error=str(e))
            return None

        # Get context
        artwork = device.artwork
        exhibition = artwork.exhibition if artwork else None

        # Create log entry
        log = LampHoursLog(
            asset_id=device.asset_id,
            device_id=device.id,
            lamp_hours=lamp_hours,
            event_type=event_type,
            exhibition_name=exhibition.name if exhibition else None,
            artwork_name=artwork.name if artwork else None,
            device_name=device.name,
        )
        session.add(log)

        logger.info(
            "Recorded lamp hours",
            device=device.name,
            asset_id=str(device.asset_id)[:8],
            lamp_hours=lamp_hours,
            event_type=event_type,
        )

        return log

    async def record_lamp_hours_background(self, device_id: UUID, event_type: str):
        """Record lamp hours in background task with own session.

        Use this from command_orchestrator to not block command response.
        """
        try:
            async with self.db_manager.session() as session:
                await self._record_lamp_hours_impl(device_id, event_type, session)
                await session.commit()
        except Exception as e:
            logger.error("Background lamp hours recording failed", error=str(e))

    def _is_ip_address(self, host: str) -> bool:
        """Check if host is an IP address."""
        try:
            socket.inet_aton(host)
            return True
        except socket.error:
            return False

    async def link_device_to_asset(
        self,
        device: Device,
        session,
    ) -> Optional[Asset]:
        """Link a PJLink device to its asset based on hostname.

        1. Resolve DNS if needed
        2. Extract asset number from hostname (checking both original and resolved)
        3. Get or create asset
        4. Link device to asset

        Args:
            device: Device to link
            session: Database session

        Returns:
            Linked Asset or None
        """
        if device.device_type != 'pjlink':
            return None

        # Resolve DNS
        resolved = await self.resolve_dns(device.host)
        if resolved:
            device.resolved = resolved
            device.resolved_at = datetime.utcnow()

        # Extract asset number - try both host and resolved to find a hostname with asset pattern
        # Priority: prefer the value that contains the asset number
        asset_number = None
        hostname_for_asset = None

        # First try the original host (if it's a hostname, not IP)
        if not self._is_ip_address(device.host):
            asset_number = self.extract_asset_number(device.host)
            if asset_number:
                hostname_for_asset = device.host

        # If not found, try the resolved value (useful when host is IP and resolved is hostname)
        if not asset_number and resolved and not self._is_ip_address(resolved):
            asset_number = self.extract_asset_number(resolved)
            if asset_number:
                hostname_for_asset = resolved

        # Also try device.name if it looks like a hostname (contains asset pattern)
        if not asset_number and device.name and not self._is_ip_address(device.name):
            asset_number = self.extract_asset_number(device.name)
            if asset_number:
                hostname_for_asset = device.name

        if not asset_number:
            logger.debug(
                "No asset number found in hostname",
                device=device.name,
                host=device.host,
                resolved=resolved,
            )
            return None

        # Get or create asset
        asset = await self.get_or_create_asset(asset_number, hostname_for_asset, session)
        device.asset_id = asset.id

        logger.info(
            "Linked device to asset",
            device=device.name,
            asset_number=asset_number,
        )

        return asset

    async def unlink_device_from_asset(
        self,
        device_id: UUID,
        session,
    ) -> bool:
        """Record offboard lamp hours before device deletion.

        Args:
            device_id: Device UUID
            session: Database session

        Returns:
            True if offboard recorded, False otherwise
        """
        stmt = select(Device).where(Device.id == device_id)
        result = await session.execute(stmt)
        device = result.scalar_one_or_none()

        if not device or device.device_type != 'pjlink' or not device.asset_id:
            return False

        # Try to record final lamp hours
        log = await self._record_lamp_hours_impl(device_id, 'offboard', session)
        return log is not None

    async def backfill_assets(
        self,
        chunk_size: int = 10,
        delay_between_chunks: float = 2.0,
    ) -> dict:
        """Backfill assets for existing PJLink devices.

        Processes devices in chunks to avoid overloading projectors.

        Args:
            chunk_size: Devices per chunk
            delay_between_chunks: Seconds between chunks

        Returns:
            Progress report dict
        """
        results = {
            "processed": 0,
            "created": 0,
            "linked": 0,
            "failed": [],
            "skipped": [],
        }

        async with self.db_manager.session() as session:
            # Get all PJLink devices without assets
            stmt = select(Device).where(
                Device.device_type == 'pjlink',
                Device.asset_id.is_(None)
            )
            result = await session.execute(stmt)
            devices = list(result.scalars().all())

            logger.info("Starting asset backfill", device_count=len(devices))

            # Process in chunks
            for i in range(0, len(devices), chunk_size):
                chunk = devices[i:i + chunk_size]

                for device in chunk:
                    try:
                        # Resolve DNS
                        resolved = await self.resolve_dns(device.host)
                        if resolved:
                            device.resolved = resolved
                            device.resolved_at = datetime.utcnow()

                        # Extract asset number - try both host and resolved
                        asset_number = None
                        hostname_for_asset = None

                        # First try the original host (if it's a hostname, not IP)
                        if not self._is_ip_address(device.host):
                            asset_number = self.extract_asset_number(device.host)
                            if asset_number:
                                hostname_for_asset = device.host

                        # If not found, try the resolved value
                        if not asset_number and resolved and not self._is_ip_address(resolved):
                            asset_number = self.extract_asset_number(resolved)
                            if asset_number:
                                hostname_for_asset = resolved

                        # Also try device.name if it looks like a hostname
                        if not asset_number and device.name and not self._is_ip_address(device.name):
                            asset_number = self.extract_asset_number(device.name)
                            if asset_number:
                                hostname_for_asset = device.name

                        if not asset_number:
                            results["skipped"].append({
                                "device": device.name,
                                "host": device.host,
                                "resolved": resolved,
                                "reason": "No asset number in hostname",
                            })
                            results["processed"] += 1
                            continue

                        # Get or create asset
                        asset = await self.get_or_create_asset(
                            asset_number, hostname_for_asset, session
                        )
                        device.asset_id = asset.id
                        results["linked"] += 1

                        # Record onboard lamp hours
                        log = await self._record_lamp_hours_impl(
                            device.id, 'onboard', session
                        )
                        if log:
                            results["created"] += 1

                    except Exception as e:
                        results["failed"].append({
                            "device": device.name,
                            "error": str(e),
                        })

                    results["processed"] += 1

                await session.commit()

                # Throttle between chunks
                if i + chunk_size < len(devices):
                    await asyncio.sleep(delay_between_chunks)

        logger.info(
            "Asset backfill completed",
            processed=results["processed"],
            linked=results["linked"],
            created=results["created"],
            failed=len(results["failed"]),
            skipped=len(results["skipped"]),
        )

        return results

    async def record_initial_lamp_hours(
        self,
        chunk_size: int = 10,
        delay_between_chunks: float = 2.0,
    ) -> dict:
        """Record initial lamp hours for linked devices without lamp history.

        This is useful for devices that were linked before lamp hour tracking
        was implemented, or were linked by the scheduler before it recorded
        onboard hours.

        Args:
            chunk_size: Devices per chunk
            delay_between_chunks: Seconds between chunks

        Returns:
            Progress report dict
        """
        from sqlalchemy import exists, and_
        from gallerycontrol.database.models import LampHoursLog

        results = {
            "processed": 0,
            "recorded": 0,
            "failed": [],
            "skipped": [],
        }

        async with self.db_manager.session() as session:
            # Find PJLink devices WITH asset_id but WITHOUT any lamp history
            subquery = (
                select(LampHoursLog.asset_id)
                .where(LampHoursLog.asset_id == Device.asset_id)
                .correlate(Device)
                .exists()
            )
            stmt = select(Device).where(
                Device.device_type == 'pjlink',
                Device.asset_id.isnot(None),
                ~subquery
            )
            result = await session.execute(stmt)
            devices = list(result.scalars().all())

            logger.info(
                "Recording initial lamp hours for linked devices",
                device_count=len(devices)
            )

            if not devices:
                return results

            # Process in chunks
            for i in range(0, len(devices), chunk_size):
                chunk = devices[i:i + chunk_size]

                for device in chunk:
                    try:
                        log = await self._record_lamp_hours_impl(
                            device.id, 'onboard', session
                        )
                        if log:
                            results["recorded"] += 1
                        else:
                            results["skipped"].append({
                                "device": device.name,
                                "reason": "Could not query lamp hours",
                            })
                    except Exception as e:
                        results["failed"].append({
                            "device": device.name,
                            "error": str(e),
                        })

                    results["processed"] += 1

                await session.commit()

                # Throttle between chunks
                if i + chunk_size < len(devices):
                    await asyncio.sleep(delay_between_chunks)

        logger.info(
            "Initial lamp hours recording completed",
            processed=results["processed"],
            recorded=results["recorded"],
            failed=len(results["failed"]),
            skipped=len(results["skipped"]),
        )

        return results

    async def record_lamp_hours_for_assets(
        self,
        asset_ids: list[UUID],
        session,
    ) -> dict:
        """Record lamp hours for specific assets.

        Finds devices linked to the given assets and queries their lamp hours.

        Args:
            asset_ids: List of asset UUIDs to record lamp hours for
            session: Database session

        Returns:
            Progress report dict
        """
        results = {
            "processed": 0,
            "recorded": 0,
            "failed": [],
            "skipped": [],
        }

        if not asset_ids:
            return results

        # Find PJLink devices linked to these assets
        stmt = select(Device).where(
            Device.device_type == 'pjlink',
            Device.asset_id.in_(asset_ids)
        )
        result = await session.execute(stmt)
        devices = list(result.scalars().all())

        logger.info(
            "Recording lamp hours for selected assets",
            asset_count=len(asset_ids),
            device_count=len(devices)
        )

        if not devices:
            return results

        for device in devices:
            try:
                log = await self._record_lamp_hours_impl(
                    device.id, 'manual', session
                )
                if log:
                    results["recorded"] += 1
                else:
                    results["skipped"].append({
                        "device": device.name,
                        "reason": "Could not query lamp hours",
                    })
            except Exception as e:
                results["failed"].append({
                    "device": device.name,
                    "error": str(e),
                })

            results["processed"] += 1

        await session.commit()

        logger.info(
            "Lamp hours recording for selected assets completed",
            processed=results["processed"],
            recorded=results["recorded"],
            failed=len(results["failed"]),
            skipped=len(results["skipped"]),
        )

        return results

    async def should_resolve_dns(self, device: Device) -> bool:
        """Check if device DNS should be re-resolved.

        Returns True if:
        - Never resolved
        - Resolved more than dns_resolve_interval seconds ago
        """
        if not device.resolved_at:
            return True

        # Strip timezone if present to ensure naive comparison
        resolved_at = device.resolved_at
        if resolved_at.tzinfo is not None:
            resolved_at = resolved_at.replace(tzinfo=None)
        elapsed = (datetime.utcnow() - resolved_at).total_seconds()
        return elapsed >= self.dns_resolve_interval

    async def update_device_dns(self, device_id: UUID) -> Optional[str]:
        """Force DNS resolution for a device.

        Args:
            device_id: Device UUID

        Returns:
            Resolved hostname/IP or None
        """
        async with self.db_manager.session() as session:
            stmt = select(Device).where(Device.id == device_id)
            result = await session.execute(stmt)
            device = result.scalar_one_or_none()

            if not device:
                return None

            resolved = await self.resolve_dns(device.host)
            if resolved:
                device.resolved = resolved
                device.resolved_at = datetime.utcnow()
                await session.commit()

            return resolved

    async def add_manual_lamp_hours(
        self,
        asset_id: UUID,
        lamp_hours: int,
        device_id: Optional[UUID] = None,
        notes: Optional[str] = None,
    ) -> LampHoursLog:
        """Add manual lamp hours entry.

        Args:
            asset_id: Asset UUID
            lamp_hours: Lamp hours value
            device_id: Optional device UUID for context
            notes: Optional notes (stored in device_name field)

        Returns:
            Created LampHoursLog
        """
        async with self.db_manager.session() as session:
            # Get context if device provided
            exhibition_name = None
            artwork_name = None
            device_name = notes or "Manual entry"

            if device_id:
                stmt = (
                    select(Device)
                    .where(Device.id == device_id)
                    .options(
                        selectinload(Device.artwork).selectinload(Artwork.exhibition)
                    )
                )
                result = await session.execute(stmt)
                device = result.scalar_one_or_none()

                if device:
                    device_name = device.name
                    artwork_name = device.artwork.name if device.artwork else None
                    exhibition_name = (
                        device.artwork.exhibition.name
                        if device.artwork and device.artwork.exhibition
                        else None
                    )

            log = LampHoursLog(
                asset_id=asset_id,
                device_id=device_id,
                lamp_hours=lamp_hours,
                event_type='manual',
                exhibition_name=exhibition_name,
                artwork_name=artwork_name,
                device_name=device_name,
            )
            session.add(log)
            await session.commit()

            logger.info(
                "Added manual lamp hours",
                asset_id=str(asset_id)[:8],
                lamp_hours=lamp_hours,
            )

            return log
