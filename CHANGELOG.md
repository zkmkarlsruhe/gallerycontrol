# Changelog

All notable changes to GalleryControl will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Open source release under MIT license
- Renamed project from mutech-control to GalleryControl

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
