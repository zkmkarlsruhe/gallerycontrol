#!/usr/bin/env python3
# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""
Remote development runner - routes network traffic through SOCKS proxy.

This patches socket.create_connection and the socket.socket.connect method
to route remote connections through a SOCKS5 proxy.

Usage:
    poetry run python remote_dev_runner.py

Prerequisites:
    - SSH tunnel running: ssh -D 1080 -f -N museumstechnik@docker.mutech.zkm.de
    - PostgreSQL accessible at 172.17.0.1:5432
"""

# =============================================================================
# STEP 1: Patch socket module BEFORE any other imports
# =============================================================================
import socket
import socks

SOCKS_PROXY_HOST = "127.0.0.1"
SOCKS_PROXY_PORT = 1080

# Store originals
_original_socket_class = socket.socket
_original_create_connection = socket.create_connection


def _is_local(host: str) -> bool:
    """Check if host should bypass proxy."""
    if host in ("localhost", "host.docker.internal", ""):
        return True
    if host.startswith("127.") or host.startswith("172.17.") or host.startswith("10."):
        return True
    if host.startswith("0.0.0.0"):
        return True
    return False


def _patched_create_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    """Create connection, using proxy for remote hosts."""
    host, port = address

    if _is_local(host):
        return _original_create_connection(address, timeout, source_address)
    else:
        # Use SOCKS proxy
        sock = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
        sock.set_proxy(socks.SOCKS5, SOCKS_PROXY_HOST, SOCKS_PROXY_PORT, rdns=True)
        if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
            sock.settimeout(timeout)
        sock.connect(address)
        return sock


# Apply patches - only patch create_connection, not socket.socket
# Patching socket.socket causes issues with asyncio and uvicorn
socket.create_connection = _patched_create_connection

print(f"[remote_dev] Patched socket.create_connection for SOCKS5 proxy at {SOCKS_PROXY_HOST}:{SOCKS_PROXY_PORT}")
print(f"[remote_dev] Note: PJLink uses direct sockets - won't work through tunnel")

# =============================================================================
# STEP 2: Verify proxy is reachable
# =============================================================================
import os
import sys

test_sock = _original_socket_class(socket.AF_INET, socket.SOCK_STREAM)
test_sock.settimeout(2)
try:
    test_sock.connect((SOCKS_PROXY_HOST, SOCKS_PROXY_PORT))
    test_sock.close()
    print(f"[remote_dev] SOCKS proxy is reachable")
except Exception as e:
    print(f"[remote_dev] ERROR: Cannot connect to SOCKS proxy: {e}")
    print(f"[remote_dev] Start SSH tunnel: ssh -D 1080 -f -N museumstechnik@docker.mutech.zkm.de")
    sys.exit(1)

# =============================================================================
# STEP 3: Patch httpx for NETIO devices
# =============================================================================
import httpx
from httpx_socks import AsyncProxyTransport

_original_async_client_init = httpx.AsyncClient.__init__


def _patched_async_client_init(self, *args, **kwargs):
    """Patch AsyncClient to use SOCKS proxy transport by default."""
    if "transport" not in kwargs and "mounts" not in kwargs:
        proxy_url = f"socks5://{SOCKS_PROXY_HOST}:{SOCKS_PROXY_PORT}"
        kwargs["transport"] = AsyncProxyTransport.from_url(proxy_url)
    _original_async_client_init(self, *args, **kwargs)


httpx.AsyncClient.__init__ = _patched_async_client_init
print(f"[remote_dev] Patched httpx.AsyncClient for SOCKS5 proxy")

# =============================================================================
# STEP 4: Set up environment and run
# =============================================================================
def main():
    """Run the backend."""
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://mutech:mutech_password@172.17.0.1:5432/mutech")
    os.environ.setdefault("ENVIRONMENT", "development")

    # Add curl wrapper to PATH for shell commands
    curl_wrapper_dir = os.path.expanduser("~/.local/bin")
    if os.path.exists(os.path.join(curl_wrapper_dir, "curl")):
        current_path = os.environ.get("PATH", "")
        if curl_wrapper_dir not in current_path:
            os.environ["PATH"] = f"{curl_wrapper_dir}:{current_path}"
            print(f"[remote_dev] Added curl wrapper to PATH")

    print("[remote_dev] Starting backend...")

    import uvicorn
    uvicorn.run(
        "gallerycontrol.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
