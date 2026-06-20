---
status: Implemented
date: 2026-05-25
deciders:
  - gsannikov
related: [781, 782, 784, 785, 786]
hub: null
tags: [multi-brain, harness, cli, mcp, tier-scoping, capability-exposure]
superseded_by: null
spec_file: 2026-05-25-harness-layering-family-design.md
plan_file: 2026-05-25-harness-c2-cli-mcp-tier-scoping.md
---

# ADR-783: C2 — CLI & MCP Tier-Scoping

> Child of the **ADR-781** harness-layering family. Canonical design: [`2026-05-25-harness-layering-family-design.md`](../superpowers/specs/2026-05-25-harness-layering-family-design.md).

## Decision summary

Make `aug` subcommand discovery and MCP/capability exposure **tier-aware**: subcommands and exposure can be declared at Global / User / Project, merged most-specific-wins, with project-level `.mcp.json` generation for the Project tier.

## Status notes

Implemented 2026-05-25. `src/cli_plugins.py` now discovers managed skill
source dirs from the layered stack and registers subcommands from most-specific
to least-specific so project/user commands win while built-ins remain
protected. Capability exposure policy now accepts `scope: global | user |
project | mixed`, filters by the active stack, and maps the runtime
`personal` tier to ADR-783's `user` scope. `config/system/mcp_servers.yaml`
declares explicit server scopes, the manifest parser preserves them, and
`src/lib/mcp_project_config.py` writes project-scoped `.mcp.json` payloads.
Real-stack verification found project-brain plus Au-vault skill sources, 7
CLI-contributing skills, 9 discovered subcommands (`note-url`, `sync`, and
`wiki` present), 543 active capability records, and project `.mcp.json`
servers `augur-core` and `augur-framework`.

## Context

`aug` subcommand discovery (`src/cli_plugins.py` `discover_subcommands`) and exposure config (`config/system/capability_exposure.yaml`, `mcp_servers.yaml`) are **global-only** today — there is no way for a personal or project brain to contribute its own `aug` subcommands or scope MCP/exposure to a tier. ADR-781 D4 calls for `aug` subcommands and MCP-tool exposure as tier-carrying capabilities.

## Decision

1. **Tier-aware `discover_subcommands`** — merge Global + User + Project subcommand sources; most-specific name wins.
2. **Tier-scoped exposure** — `capability_exposure.yaml` and `mcp_servers.yaml` gain a `scope: global | user | project`; project-scoped entries add onto global.
3. **Project-level `.mcp.json`** — generate the project tier's MCP servers into the client REPO `.mcp.json`, merged under the global HOME MCP config (project wins on name collision).

## Completion gate

`aug` resolves tier-correct subcommands on the real stack; `verify-harness` (781 §2a) covers MCP config + exposure per client; project `.mcp.json` loads in a real client.

## Consequences

**Positive:** personal and project brains become first-class CLI/MCP contributors. **Negative:** exposure/MCP config schemas grow a tier dimension (migration of existing entries to `scope: global`). **Neutral:** global-tier behavior preserved as the default scope.

## Dependencies

C1 (projection model + shared resolver). Blocks C5.

## References

- ADR-781 (parent) · family spec
- `src/cli_plugins.py`, `config/system/capability_exposure.yaml`, `config/system/mcp_servers.yaml`
