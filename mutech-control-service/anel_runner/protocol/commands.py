"""ANEL protocol command formatting."""


def format_power_command(command: str, port: int, user: str, password: str) -> str:
    """
    Format power command for ANEL protocol.

    Args:
        command: 'on' or 'off'
        port: Port number (0-based)
        user: Username for authentication
        password: Password for authentication

    Returns:
        Formatted command string: Sw_on<port+1><user><password> or Sw_off<port+1><user><password>
        Port is 1-based in protocol (add 1 to port index).
    """
    cmd = "Sw_on" if command == "on" else "Sw_off"
    port_num = port + 1  # Convert to 1-based
    return f"{cmd}{port_num}{user}{password}"


def format_status_query() -> str:
    """Return status query command."""
    return "wer da?"
