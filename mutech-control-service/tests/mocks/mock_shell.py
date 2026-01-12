"""Mock shell device for testing."""

from typing import Dict, List


class MockShellDevice:
    """Simulates shell command execution for testing."""

    def __init__(self, host: str):
        self.host = host
        self.state = 0  # 0=off, 1=on
        self.call_history: List[Dict] = []
        self.simulate_timeout = False
        self.simulate_error = False
        self.custom_output: Dict[str, str] = {}  # command -> output mapping

    def execute_command(self, command: str, timeout: int = 30) -> dict:
        """
        Simulate shell command execution.

        Args:
            command: Shell command to execute
            timeout: Timeout in seconds

        Returns:
            Dict with returncode, stdout, stderr
        """
        self.call_history.append({"command": command, "timeout": timeout})

        if self.simulate_timeout:
            raise TimeoutError(f"Command timed out after {timeout}s")

        if self.simulate_error:
            return {
                "returncode": 1,
                "stdout": "",
                "stderr": "Simulated error",
            }

        # Check for custom output
        if command in self.custom_output:
            return {
                "returncode": 0,
                "stdout": self.custom_output[command],
                "stderr": "",
            }

        # Simulate common commands
        if "ps" in command or "status" in command.lower():
            # Status check - return output based on current state
            if self.state == 1:
                output = "app is running\nPID 12345"
            else:
                output = "app is not running"
            return {"returncode": 0, "stdout": output, "stderr": ""}

        elif "start" in command.lower() or "./start.sh" in command:
            # Start command
            self.state = 1
            return {"returncode": 0, "stdout": "Started successfully", "stderr": ""}

        elif "stop" in command.lower() or "killall" in command or "./stop.sh" in command:
            # Stop command
            self.state = 0
            return {"returncode": 0, "stdout": "Stopped successfully", "stderr": ""}

        elif "reboot" in command.lower():
            # Reboot command
            self.state = 0
            return {"returncode": 0, "stdout": "Rebooting...", "stderr": ""}

        elif "ping" in command or "ssh" in command and "exit" in command:
            # Connection test
            return {"returncode": 0, "stdout": "", "stderr": ""}

        else:
            # Unknown command - return generic success
            return {"returncode": 0, "stdout": "Command executed", "stderr": ""}

    def set_state(self, state: int):
        """Manually set device state (for testing)."""
        self.state = state

    def get_state(self) -> int:
        """Get current device state."""
        return self.state

    def set_custom_output(self, command: str, output: str):
        """
        Set custom output for a command.

        Args:
            command: Command string
            output: Expected stdout output
        """
        self.custom_output[command] = output

    def reset_call_history(self):
        """Clear command history."""
        self.call_history.clear()
