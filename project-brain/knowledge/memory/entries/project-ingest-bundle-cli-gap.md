---
title: project-ingest-bundle-cli-gap
name: project-ingest-bundle-cli-gap
description: ingest (and vault) are vault-tier MCP bundles excluded from the CLI/agent
  monolith, so their tools are unreachable from a CLI agent except via aug subcommands
brain_scope: project
type: project
status: active
source_client: claude-code
source_file: project_ingest_bundle_cli_gap.md
source_hash: 5ef4fcea460e43da
---


`ingest` and `vault` are listed in `config/system/mcp_servers.yaml` `monolith_exclusions` (vault-tier per-bundle servers, `augur_shared.bundle_server`). Consequences that waste time if forgotten:

- `aug <tool>` (the CLI) builds only the **monolith** (core+framework via `register_framework_tools(..., capability_target="cli")`), which calls `_collect_skill_dirs(apply_exclusions=True)` and **drops ingest/vault**. So `aug url-extract`, `aug save-url-source`, `aug wiki-*`, `aug inbox-*` do NOT exist — `aug --list-tools` has none of them.
- Only the **dashboard** connects to the ingest/vault bundle servers, so those tools are "mcp via dashboard" only. A Claude Code / Codex / Gemini CLI session has **no MCP path** to them.
- The sanctioned way to give a CLI agent an ingest/vault op is an **ADR-260 CLI subcommand** (`register_subcommands(subparsers)` in `<skill>/scripts/mcp/__init__.py`, dispatched by `src/cli_plugins.py`). `cli_plugins` loads `__init__.py` *bare* (no package), so that file must avoid top-level relative imports (move them into `register_tools`). This is how `aug note-url` and `aug graph <verb>` work.

Captured by [[ADR-765]] (agent-friction routine + `aug note-url`). The friction routine `auto-friction-audit` detects this class automatically (`cli-tool-unreachable` findings). See also [[feedback-skill-architecture-layering]].
