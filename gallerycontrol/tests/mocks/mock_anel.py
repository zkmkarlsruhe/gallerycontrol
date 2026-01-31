# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Mock ANEL device for testing."""

from typing import List


class MockANELDevice:
    """Simulates ANEL UDP protocol for testing."""

    def __init__(
        self,
        host: str,
        username: str = "admin",
        password: str = "anel",
        port_count: int = 8,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port_states = [0] * port_count  # All off initially
        self.port_names = [f"Port{i}" for i in range(port_count)]
        self.device_name = "Test ANEL"
        self.temperature = 25.5
        self.call_history: List[str] = []
        self.simulate_timeout = False
        self.simulate_error = False

    def handle_udp_command(self, command: str) -> str:
        """
        Simulate UDP command responses.

        Args:
            command: UDP command string

        Returns:
            UDP response string
        """
        self.call_history.append(command)

        if self.simulate_timeout:
            raise TimeoutError("Simulated timeout")

        if self.simulate_error:
            return "ERROR"

        # Status query: "wer da?"
        if command == "wer da?":
            # Format: NET-PwrCtrl:<name>:<ip>:<mask>:<gateway>:<mac>:<port_states>:<port_names>:<locked>:<http>:<temp>
            port_states_str = "".join(str(s) for s in self.port_states)
            port_names_str = ",".join(self.port_names)
            return (
                f"NET-PwrCtrl:{self.device_name}:{self.host}:255.255.255.0:192.168.1.1:"
                f"00:11:22:33:44:55:{port_states_str}:{port_names_str}:0:80:{self.temperature}"
            )

        # Power ON: Sw_on<port+1><username><password>
        if command.startswith("Sw_on"):
            try:
                # Extract port number (1-based in protocol)
                port_num = int(command[5]) - 1  # Convert to 0-based
                if 0 <= port_num < len(self.port_states):
                    # Verify credentials (simplified - just check length)
                    expected_len = 6 + len(self.username) + len(self.password)
                    if len(command) >= expected_len:
                        self.port_states[port_num] = 1
                        return "OK"
                return "ERROR"
            except (IndexError, ValueError):
                return "ERROR"

        # Power OFF: Sw_off<port+1><username><password>
        if command.startswith("Sw_off"):
            try:
                port_num = int(command[6]) - 1  # Convert to 0-based
                if 0 <= port_num < len(self.port_states):
                    expected_len = 7 + len(self.username) + len(self.password)
                    if len(command) >= expected_len:
                        self.port_states[port_num] = 0
                        return "OK"
                return "ERROR"
            except (IndexError, ValueError):
                return "ERROR"

        # Reset device: "Reset"
        if command == "Reset":
            self.port_states = [0] * len(self.port_states)
            return "OK"

        return "ERROR"

    def set_port_state(self, port: int, state: int):
        """
        Directly set port state (for testing).

        Args:
            port: Port number (0-based)
            state: 0=off, 1=on
        """
        if 0 <= port < len(self.port_states):
            self.port_states[port] = state

    def get_port_state(self, port: int) -> int:
        """
        Get port state.

        Args:
            port: Port number (0-based)

        Returns:
            0=off, 1=on, or -1 if invalid port
        """
        if 0 <= port < len(self.port_states):
            return self.port_states[port]
        return -1

    def reset_call_history(self):
        """Clear command history."""
        self.call_history.clear()
