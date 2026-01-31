# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Scheduler task implementations."""

from gallerycontrol.scheduler.tasks.asset_linker import run_asset_linker
from gallerycontrol.scheduler.tasks.device_info_cache import run_device_info_cache
from gallerycontrol.scheduler.tasks.lamp_hours_check import run_lamp_hours_check
from gallerycontrol.scheduler.tasks.lamp_hours_record import run_lamp_hours_record
from gallerycontrol.scheduler.tasks.log_cleanup import run_log_cleanup
from gallerycontrol.scheduler.tasks.memory_cleanup import run_memory_cleanup

__all__ = [
    "run_asset_linker",
    "run_device_info_cache",
    "run_lamp_hours_check",
    "run_lamp_hours_record",
    "run_log_cleanup",
    "run_memory_cleanup",
]
