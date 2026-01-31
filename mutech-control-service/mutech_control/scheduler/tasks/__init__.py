# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Scheduler task implementations."""

from mutech_control.scheduler.tasks.asset_linker import run_asset_linker
from mutech_control.scheduler.tasks.device_info_cache import run_device_info_cache
from mutech_control.scheduler.tasks.lamp_hours_check import run_lamp_hours_check
from mutech_control.scheduler.tasks.lamp_hours_record import run_lamp_hours_record
from mutech_control.scheduler.tasks.log_cleanup import run_log_cleanup
from mutech_control.scheduler.tasks.memory_cleanup import run_memory_cleanup

__all__ = [
    "run_asset_linker",
    "run_device_info_cache",
    "run_lamp_hours_check",
    "run_lamp_hours_record",
    "run_log_cleanup",
    "run_memory_cleanup",
]
