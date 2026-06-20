---
status: Implemented
date: ''
deciders: []
related: []
hub: null
tags:
- mcp
- instance
- management
- transport
- strategy
superseded_by: null
---

# ADR-014: MCP Instance Management and Transport Strategy

## Context
As the usage of the Augur MCP server expanded to multiple clients (Claude Desktop, Cursor, VS Code) and potentially different environments (local desktop vs. team server), we encountered significant reliability issues.
Specifically, running multiple simultaneous instances of the MCP server caused:
- Resource contention (high memory usage, N × ~300MB).
- File conflicts (race conditions on metrics logging and cache files).
- Handshake timeouts and connection failures ("1 MCP server failed").
- Orphaned processes.

We needed a robust strategy to manage server instances and a clear understanding of when to use different transport protocols (swapping between `stdio`, `sse`, and `http`).

## Decision

We have adopted a **Hybrid Instance Management Strategy** enforced by a custom **Instance Locking System**. The choice of transport dictates the locking behavior.

### 1. Transport-Based Locking Logic

We support two distinct modes of operation managed by `augur_mcp.instance_lock`:

| Buffer | Transport | Architecture | Locking Strategy | Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **stdio** | Process-based pipes | One process per client | **Per-Client Lock** (`mcp-{client_id}.pid`) | Desktop Apps (Claude, Cursor) |
| **SSE/HTTP** | Network (HTTP/SSE) | Single src/lib server | **Global Lock** (`mcp.pid`) | Servers, Teams, Multi-user |

#### stdio (Default for Desktop)
In `stdio` mode, we allow multiple simultaneous processes *only if they are serving different clients*.
- We automatically detect the client based on the parent process name (e.g., "Claude", "Cursor", "Code").
- We enforce a **Per-Client Singleton**: Only one instance can run for "Claude". If a second attempts to start (e.g., zombie process or rapid reconnect), it is blocked.
- **Benefit**: Complete isolation between clients while preventing local resource conflicts *within* a client's scope.

#### SSE/HTTP (Shared Server)
In `sse` or `http` mode, we enforce a **Global Singleton**.
- Only one server instance can run on the machine/port.
- All clients connect to this single instance via network.
- **Benefit**: Maximum resource efficiency (1x RAM) and src/lib state (unified metrics).

### 2. Transport Protocol Selection

We defined clear criteria for choosing the transport:

| Feature | stdio | SSE / HTTP |
| :--- | :--- | :--- |
| **Setup** | Zero-config (Command path) | Requires Port, Net, Auth |
| **Security** | High (Process isolation, no exposure) | Requires Auth/TLS |
| **State** | Isolated per client | Shared across clients |
| **Remote** | Impossible | Supported |
| **Recommendation** | **Default for Local Dev** | **Default for Deployment** |

**Standard adoption path**:
1. Start with `stdio` for local personal use (current Augur default).
2. Migrate to `sse` if memory is constrained (< 8GB) or > 3 clients are needed.
3. Use `http` for complex deployments behind reverse proxies.

## Implementation Details

### Instance Locking Mechanism
Implemented in `src/mcp/augur_mcp/instance_lock.py`:
- **PID Files**: Stored in temp dir (`/tmp/augur-mcp-{scope}.pid`).
- **Stale Lock Detection**: On startup, checks if the PID in the lock file is actually running. If not, it self-heals by deleting the stale lock.
- **Graceful Wait**: Waits up to 2.0s for an old instance to exit before failing.
- **Force Override**: Support for `--force` flag to explicitly kill hung instances.

### Troubleshooting Tools
To support this architecture, we added specialized tooling:
- `debug-mcp.sh`: Wrapper to capture startup logs when stdio pipes are swallowed by the client.
- `cleanup-mcp.sh`: Interactive utility to find and kill orphaned MCP processes and clear locks.

## Consequences

### Positive
- **Reliability**: Eliminated "Server failed to start" errors due to race conditions.
- **Resource Usage**: deterministic memory footprint (Control over N instances).
- **UX**: Clear error messages ("Another instance is running") instead of silent failures.
- **Flexibility**: Seamlessly supports both isolated local dev and src/lib server models.

### Negative
- **Complexity**: The locking logic adds overhead to the startup sequence (~5ms).
- **Maintenance**: Need to maintain client detection logic (heuristics for parent process names).

## References
- Previous docs (Consolidated): `INSTANCE-LOCKING.md`, `MULTI-CLIENT-SUPPORT.md`, `MCP-TRANSPORT-COMPARISON.md`.
- Code: `augur_mcp.instance_lock`, `augur_mcp.server`.
