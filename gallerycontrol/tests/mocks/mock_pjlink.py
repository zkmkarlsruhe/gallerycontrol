# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Mock PJLink device for testing."""

import hashlib
from typing import List


class MockPJLinkDevice:
    """Simulates PJLink TCP protocol for testing."""

    def __init__(self, host: str, port: int = 4352, password: str = None, initial_state: int = 0):
        self.host = host
        self.port = port
        self.password = password
        self.state = initial_state  # 0=off, 1=on, 2=cooling, 3=warming
        self.lamp_hours = 1000
        self.mute_video = False
        self.mute_audio = False
        self.input_source = "11"  # RGB 1
        self.call_history: List[str] = []
        self.simulate_timeout = False
        self.simulate_error = False

    def handle_command(self, command: str) -> str:
        """
        Simulate PJLink protocol responses.

        Args:
            command: PJLink command string

        Returns:
            PJLink response string
        """
        self.call_history.append(command)

        if self.simulate_timeout:
            raise TimeoutError("Simulated timeout")

        if self.simulate_error:
            return "%1ERR2"  # Parameter error

        # Strip header and checksum if present
        if command.startswith("%1"):
            command = command[2:]

        if command == "POWR ?":  # Query power
            return f"%1POWR={self.state}"
        elif command.startswith("POWR "):  # Set power
            new_state = int(command.split()[1])
            if new_state == 1:  # Turn on
                self.state = 3  # warming
            elif new_state == 0:  # Turn off
                self.state = 2  # cooling
            return "%1POWR=OK"
        elif command == "LAMP ?":  # Query lamp hours
            return f"%1LAMP={self.lamp_hours} 0"
        elif command == "INST ?":  # Query input list
            return "%1INST=11 12 21 22 31 32"
        elif command == "INPT ?":  # Query current input
            return f"%1INPT={self.input_source}"
        elif command.startswith("INPT "):  # Set input
            self.input_source = command.split()[1]
            return "%1INPT=OK"
        elif command == "AVMT ?":  # Query mute status
            mute_val = 0
            if self.mute_video and self.mute_audio:
                mute_val = 31
            elif self.mute_video:
                mute_val = 11
            elif self.mute_audio:
                mute_val = 21
            return f"%1AVMT={mute_val}"
        elif command.startswith("AVMT "):  # Set mute
            mute_val = int(command.split()[1])
            self.mute_video = mute_val in [11, 31]
            self.mute_audio = mute_val in [21, 31]
            return "%1AVMT=OK"
        elif command == "NAME ?":  # Query projector name
            return "%1NAME=Test Projector"
        elif command == "INF1 ?":  # Query manufacturer
            return "%1INF1=Panasonic"
        elif command == "INF2 ?":  # Query model
            return "%1INF2=PT-D4000E"
        elif command == "INFO ?":  # Query other info
            return "%1INFO=v1.0"
        elif command == "CLSS ?":  # Query class
            return "%1CLSS=1"
        else:
            return "%1ERR1"  # Undefined command

    def get_state(self) -> int:
        """Get current power state."""
        return self.state

    def set_state(self, state: int):
        """Manually set power state for testing."""
        self.state = state

    def advance_state(self):
        """Simulate state transitions (warming -> on, cooling -> off)."""
        if self.state == 3:  # warming
            self.state = 1  # on
        elif self.state == 2:  # cooling
            self.state = 0  # off

    def reset_call_history(self):
        """Clear command history."""
        self.call_history.clear()
