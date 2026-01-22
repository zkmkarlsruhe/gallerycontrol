"""Scheduler task implementations."""

from mutech_control.scheduler.tasks.asset_linker import run_asset_linker
from mutech_control.scheduler.tasks.device_info_cache import run_device_info_cache
from mutech_control.scheduler.tasks.lamp_hours_check import run_lamp_hours_check
from mutech_control.scheduler.tasks.log_cleanup import run_log_cleanup

__all__ = [
    "run_asset_linker",
    "run_device_info_cache",
    "run_lamp_hours_check",
    "run_log_cleanup",
]
