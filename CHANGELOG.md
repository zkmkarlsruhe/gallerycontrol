# Changelog

All notable changes to GalleryControl will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.4.0] - 2026-05-26

### Fixed
- **Satellite-routed devices showed state=ERROR forever.** `StateMonitor` and `CommandVerifier` were calling `device_managers[type].get_state/set_power(...)` directly, bypassing `SatelliteRouter`. For an ANEL device on an isolated subnet routed via a satellite, polling went through the main-network ANEL Runner (which can't reach the isolated host) instead of the satellite WebSocket. Now every device interaction (state poll, command, verification, info fetch) consults `SatelliteRouter` first and falls back to direct managers only when `device.satellite_id` is null.
- **Satellite-daemon's ANEL handler had never actually worked.** Hardcoded UDP ports `9975/9977` (real Subraum devices use `75/77`), and socket setup called `sock.bind("",0)` *after* `sendto()`, meaning replies were silently dropped even with correct ports. Rewritten using the production ANEL Runner's dual-socket pattern: listener bound to recv port before send; default ports `75/77` overridable per-device via `device.config.anel_send_port` / `anel_recv_port`. Proper colon-separated response parsing for outlet state and device metadata.

### Added
- `SatelliteRouter.get_device_info(device)` — routes metadata queries (MAC, firmware, lamp hours) through the satellite when applicable. Wired into debug API, scheduler tasks (`device_info_cache`, `lamp_hours_check`), and `AssetService`. New `info` command type in the satellite daemon protocol.

## [2.3.0] - 2026-05-26

### Changed
- **Many-to-many satellites per exhibition.** Exhibitions enable a set of satellites (multi-select checklist in Edit Exhibition). Each device then picks one of those satellites — or "Direct connection" — from a dropdown in its own modal. Supports topologies like an exhibition spanning multiple isolated networks. Replaces 2.2.0's single-satellite-per-exhibition model.

### Migration
- `023_exhibition_satellite_mn`: adds join table `exhibition_satellites`, adds `devices.satellite_id` FK, drops `exhibitions.satellite_id`. Existing single-satellite assignments are carried forward as a single-entry M:N row (no data loss).

## [2.2.0] - 2026-05-26

### Changed
- **Satellite routing simplified to pure exhibition-level.** A satellite is assigned per exhibition; every device in that exhibition inherits the routing automatically. No per-device dropdown, no `use_satellite` opt-in checkbox, no two-step flow. Replaces the brittle "Exhibition.satellite_id + Device.use_satellite" combo introduced in 019 and the per-device picker briefly shipped in 2.1.0.

### Fixed
- Reject pending satellite (Admin → Satellites) now works: the backend was reading `api_key_hash` as a query parameter while the UI sent it in the JSON body. Switched to a Pydantic body model.
- Exhibition update silently ignored `satellite_id: null` clear requests. Update handler now uses `exclude_unset=True` so null clearing actually persists.
- `useApi.updateDevice` / `updateExhibition` TypeScript signatures now expose `satellite_id` and `schedules_enabled` properly.

### Added
- Device card shows a `bi-broadcast-pin` icon when its exhibition has a satellite assigned, tinted warning-yellow if the satellite is offline.

### Migration
- `021_per_device_satellite` (2.1.0, never used in prod): briefly added `devices.satellite_id` and dropped `exhibitions.satellite_id`.
- `022_exhibition_satellite_again` (2.2.0): drops `devices.satellite_id` and re-adds `exhibitions.satellite_id`. The single LH 7 Subraum exhibition needs to be re-assigned to the satellite once after upgrade.

## [2.1.0] - 2026-05-26 — withdrawn

Per-device satellite picker proved to be UI clutter. Reverted in 2.2.0 — see above. No production deployment used this design.

## [1.3.0] - 2026-01-31

### Changed
- **Open source release** under MIT license
- Renamed project from mutech-control to GalleryControl
- Full codebase rename: package, Docker images, database
- Production-ready: daily driver at ZKM since 2025

## [1.2.10] - 2026-01-30

### Added
- Self-healing timeline visualization
- Device host/port display in tooltips
- Europe/Berlin timezone configuration

### Fixed
- Protection service edge cases
- Scheduler deadlock issues

### Changed
- Removed cooldown from `get_state()` in all device managers

## [1.2.0] - 2026-01-15

### Added
- Sensor integration for protection service
- Artwork protection with temperature/humidity thresholds
- Satellite daemon for remote device control

### Changed
- Split admin documentation into focused topic files

## [1.1.0] - 2025-12-01

### Added
- Scheduled jobs for automatic on/off
- One-shot tasks for special events
- Device info caching
- Lamp hours tracking and alerts

### Changed
- Migrated from SQLite to PostgreSQL

## [1.0.0] - 2025-10-01

### Added
- Initial release
- PJLink projector support
- NETIO power outlet support
- ANEL power distribution support
- Shell command execution via SSH
- React frontend
- REST API with FastAPI
- Exhibition and artwork management
- Device state monitoring
