# Docker MCP Server

Provides MCP access to the host Docker engine using @0xshariq/docker-mcp-server.

## How it works

Agentbox mounts `/var/run/docker.sock` only when the Docker MCP is enabled.

The MCP server provides 24 Docker operations including:
- Container management (list, run, stop, remove, logs, exec)
- Image operations (list, pull, build, remove, prune)
- Network and volume management
- Docker Compose operations
- System operations (inspect, prune, login/logout)

## Usage

```bash
abox mcp add docker
```

If a container is already running, rebuild it so the socket mount is applied.

## Implementation Notes

This MCP uses a custom invocation command because the npm package's binary points to a CLI wrapper instead of the MCP server. The config uses:

```bash
bash -c "exec node $(npm root -g 2>/dev/null || npm root)/@0xshariq/docker-mcp-server/dist/index.js"
```

This dynamically resolves the installed package location and executes the actual MCP server entry point.

## Environment Variables

None required for Docker. If you need env vars for other MCPs, put them in
`.agentbox/.env` so Agentbox loads them automatically.
