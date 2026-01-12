"""Mock NETIO device for testing."""

from typing import List, Tuple


class MockNETIODevice:
    """Simulates NETIO HTTP API for testing."""

    def __init__(
        self,
        host: str,
        username: str = "netio",
        password: str = "netio",
        port_count: int = 4,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port_states = [0] * port_count  # All off initially
        self.port_names = [f"Port {i+1}" for i in range(port_count)]
        self.call_history: List[Tuple[str, str]] = []  # (method, path)
        self.simulate_timeout = False
        self.simulate_auth_error = False

    def handle_request(self, method: str, path: str, auth: Tuple[str, str] = None) -> dict:
        """
        Simulate HTTP API responses.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path
            auth: Tuple of (username, password)

        Returns:
            Response dict with status and data/error
        """
        self.call_history.append((method, path))

        if self.simulate_timeout:
            raise TimeoutError("Simulated timeout")

        # Check authentication
        if auth != (self.username, self.password):
            return {"status": 401, "error": "Unauthorized"}

        if self.simulate_auth_error:
            return {"status": 401, "error": "Unauthorized"}

        # GET /netio.json - Get all port states
        if path == "/netio.json" and method == "GET":
            return {
                "status": 200,
                "data": {
                    "Agent": {
                        "Model": "NETIO 4",
                        "Version": "3.4.0",
                        "JSONVer": "2.1",
                        "DeviceName": "Test NETIO",
                        "VendorID": 0,
                        "OemID": 0,
                        "SerialNumber": "12345678",
                        "Uptime": 123456,
                        "Time": "2026-01-12T12:00:00+01:00",
                        "NumOutputs": len(self.port_states),
                    },
                    "GlobalMeasure": {
                        "Voltage": 230.5,
                        "Frequency": 50.1,
                        "TotalCurrent": 1.5,
                        "OverallPowerFactor": 0.95,
                        "TotalLoad": 345,
                        "TotalEnergy": 12345,
                    },
                    "Outputs": [
                        {
                            "ID": i + 1,
                            "Name": self.port_names[i],
                            "State": self.port_states[i],
                            "Action": 6,  # No action
                            "Delay": 5000,
                            "Current": 0.5 if self.port_states[i] == 1 else 0.0,
                            "PowerFactor": 0.95,
                            "Load": 115 if self.port_states[i] == 1 else 0,
                            "Energy": 1234,
                        }
                        for i in range(len(self.port_states))
                    ],
                },
            }

        # POST /netio.json - Control specific port
        # Path format: /netio.json or with JSON body containing Outputs array
        if path == "/netio.json" and method == "POST":
            # Simplified: parse would happen with actual JSON body
            # For mock, we'll just return success
            return {"status": 200, "data": {"result": "ok"}}

        # Legacy API: GET /status.xml
        if path == "/status.xml" and method == "GET":
            xml_data = '<?xml version="1.0"?><netio>'
            for i, state in enumerate(self.port_states):
                xml_data += f'<output{i+1}>{state}</output{i+1}>'
            xml_data += "</netio>"
            return {"status": 200, "data": xml_data}

        # Not found
        return {"status": 404, "error": "Not found"}

    def set_port_state(self, port: int, state: int):
        """
        Directly set port state (for testing).

        Args:
            port: Port number (1-based)
            state: 0=off, 1=on
        """
        if 1 <= port <= len(self.port_states):
            self.port_states[port - 1] = state

    def get_port_state(self, port: int) -> int:
        """
        Get port state.

        Args:
            port: Port number (1-based)

        Returns:
            0=off, 1=on, or -1 if invalid port
        """
        if 1 <= port <= len(self.port_states):
            return self.port_states[port - 1]
        return -1

    def reset_call_history(self):
        """Clear request history."""
        self.call_history.clear()
