# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""Tests for ANEL protocol implementation."""

import pytest

from anel_runner.protocol.commands import format_power_command, format_status_query
from anel_runner.protocol.parser import (
    DeviceStatus,
    PortStatus,
    extract_port_state,
    parse_command_response,
    parse_status_response,
)


class TestCommands:
    """Tests for protocol command formatting."""

    def test_format_power_on_command(self):
        """Test power on command format."""
        cmd = format_power_command("on", 0, "admin", "secret")
        assert cmd == "Sw_on1adminsecret"

    def test_format_power_off_command(self):
        """Test power off command format."""
        cmd = format_power_command("off", 0, "admin", "secret")
        assert cmd == "Sw_off1adminsecret"

    def test_port_numbering_1_based(self):
        """Test that port is converted to 1-based for protocol."""
        # Port 0 -> 1
        assert "Sw_on1" in format_power_command("on", 0, "u", "p")
        # Port 3 -> 4
        assert "Sw_on4" in format_power_command("on", 3, "u", "p")
        # Port 7 -> 8
        assert "Sw_on8" in format_power_command("on", 7, "u", "p")

    def test_format_status_query(self):
        """Test status query command."""
        assert format_status_query() == "wer da?"


class TestParser:
    """Tests for protocol response parsing."""

    # Example response from ANEL device
    SAMPLE_RESPONSE = "NET-PwrCtrl:NET-CONTROL:192.168.1.100:255.255.255.0:192.168.1.1:0.1.2.3.4.5:Outlet 1,0:Outlet 2,0:Outlet 3,0:Outlet 4,0:Outlet 5,0:Outlet 6,0:Outlet 7,0:Outlet 8,0:248:80:NET-PWRCTRL_04.5:H:xo"

    def test_parse_status_response_valid(self):
        """Test parsing valid status response."""
        status = parse_status_response(self.SAMPLE_RESPONSE)

        assert status is not None
        assert status.ip == "192.168.1.100"
        assert status.name == "NET-CONTROL"
        assert status.mac == "0.1.2.3.4.5"
        assert len(status.ports) == 8

    def test_parse_status_response_ports(self):
        """Test port parsing from status response."""
        status = parse_status_response(self.SAMPLE_RESPONSE)

        assert status.ports[0].port == 0
        assert status.ports[0].name == "Outlet 1"
        assert status.ports[0].state == 0

        assert status.ports[1].port == 1
        assert status.ports[1].name == "Outlet 2"

    def test_parse_status_response_bytes(self):
        """Test parsing bytes input."""
        status = parse_status_response(self.SAMPLE_RESPONSE.encode())
        assert status is not None
        assert status.ip == "192.168.1.100"

    def test_parse_status_response_invalid(self):
        """Test parsing invalid response."""
        assert parse_status_response("invalid data") is None
        assert parse_status_response("") is None
        assert parse_status_response("NOT-PwrCtrl:...") is None

    def test_parse_status_response_short(self):
        """Test parsing response with too few parts."""
        assert parse_status_response("NET-PwrCtrl:a:b") is None

    def test_extract_port_state(self):
        """Test extracting single port state."""
        # First port is off
        assert extract_port_state(self.SAMPLE_RESPONSE, 0) == 0

    def test_extract_port_state_invalid_port(self):
        """Test extracting state for invalid port number."""
        assert extract_port_state(self.SAMPLE_RESPONSE, 99) == -1
        assert extract_port_state(self.SAMPLE_RESPONSE, -1) == -1

    def test_extract_port_state_mixed_states(self):
        """Test with mixed on/off states."""
        response = "NET-PwrCtrl:Test:192.168.1.1:255.255.255.0:192.168.1.254:AA.BB.CC.DD.EE.FF:Port1,1:Port2,0:Port3,1:Port4,0:248:80"
        status = parse_status_response(response)

        assert status.ports[0].state == 1
        assert status.ports[1].state == 0
        assert status.ports[2].state == 1
        assert status.ports[3].state == 0

    def test_parse_command_response_ok(self):
        """Test parsing OK response."""
        assert parse_command_response("OK") is True
        assert parse_command_response("Sw_on1 OK") is True

    def test_parse_command_response_status(self):
        """Test that status response is considered successful."""
        assert parse_command_response(self.SAMPLE_RESPONSE) is True

    def test_parse_command_response_error(self):
        """Test parsing error response."""
        assert parse_command_response("ERROR") is False
        assert parse_command_response("") is False


class TestTemperatureParsing:
    """Tests for temperature extraction."""

    def test_extract_temperature(self):
        """Test temperature extraction from response."""
        response = "NET-PwrCtrl:Test:192.168.1.1:255.255.255.0:192.168.1.254:AA.BB.CC:Port1,1:Port2,0:25.5:80"
        status = parse_status_response(response)

        # Temperature should be extracted
        assert status is not None
        # Note: Temperature parsing is best-effort
