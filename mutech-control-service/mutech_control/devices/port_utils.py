"""Port conversion utilities for outlet-based devices.

Convention:
- Database stores 0-indexed ports (0, 1, 2...)
- NETIO API uses 1-indexed IDs (1, 2, 3)
- ANEL protocol uses 1-indexed commands (Sw_on1, Sw_on2...)
- UI displays 1-indexed for users (Port 1, Port 2, Port 3...)
"""


def db_to_device_id(port: int) -> int:
    """Convert 0-indexed DB port to 1-indexed device ID/command."""
    return port + 1


def device_id_to_db(device_id: int) -> int:
    """Convert 1-indexed device ID/command to 0-indexed DB port."""
    return device_id - 1
