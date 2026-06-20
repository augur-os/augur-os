---
description: Force-stop Augur MCP servers and the dashboard when the runtime is wedged and needs a clean restart.
visibility: core
---

# /kill-augur

Force-stop Augur MCP servers and the dashboard when the environment is stuck and
normal restart flow is no longer enough.

## When To Use

- MCP tools stop responding or hang on every request
- the dashboard will not reconnect after repeated retries
- a local restart is blocked by orphaned Augur processes

## Execution

1. Run the cleanup workflow:

```bash
python3 project-brain/capabilities/skills/daemon/scripts/cleanup_processes.py
```

2. Verify that the Augur MCP processes are gone:

```bash
pgrep -f "python.*(src\\.mcp\\.augur_framework|augur_framework|augur-mcp)" | wc -l
```

3. Restart the dashboard or the specific Augur services you actually need.

## Safety Notes

- this is a hard reset, not a gentle reload
- use it when you want to terminate the current Augur runtime state
- prefer targeted fixes first when a single tool or page is broken

## Usage

```bash
/kill-augur
```
