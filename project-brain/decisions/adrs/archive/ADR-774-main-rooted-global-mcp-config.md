---
status: Implemented
date: 2026-05-22
deciders:
  - gsannikov
related: [ADR-608, ADR-642]
hub: command
tags: [mcp, config, worktrees, daemon, self-heal]
superseded_by: null
spec_file: 2026-05-22-main-rooted-global-mcp-config-design.md
plan_file: 2026-05-22-main-rooted-global-mcp-config.md
---

# ADR-774: Main-Rooted Global MCP Config

> **ADR-774 is an index file.** The substantive design and implementation steps live in the linked spec + plan. This file carries pointers, status, and a one-line decision summary.

## Decision summary

Generated user-global MCP client configs must be rooted at the stable main checkout, while repo-local `{repo_root}` config targets may use the active worktree.

## Spec (canonical)

- [`docs/superpowers/specs/2026-05-22-main-rooted-global-mcp-config-design.md`](../superpowers/specs/2026-05-22-main-rooted-global-mcp-config-design.md)

## Plan (canonical, drives `/adr implement`)

- [`docs/superpowers/plans/2026-05-22-main-rooted-global-mcp-config.md`](../superpowers/plans/2026-05-22-main-rooted-global-mcp-config.md)

## Status notes

Accepted 2026-05-22. This ADR addresses repeated MCP/client configuration drift caused by global client configs being generated from linked worktree paths that later disappear.

Implemented 2026-05-23 (landed in commit `514b061c7` "fix(mcp): root global
configs at main checkout"). The stable-root selection is centralized in
`src/config/worktrees.py:global_mcp_project_root()` → `main_checkout_for_worktree()`,
and every user-global MCP config generator routes through it: `scripts/configure_mcp.py`
(returns the main checkout when `_is_linked_worktree`), `sync_agents` templates +
the opencode/antigravity adapters, and the plugin-pack `mcp_config.py` / `cowork.py`
formatters. Repo-local `{repo_root}` targets still resolve to the active worktree.
Covered by `tests/scripts/test_configure_mcp_cli.py::test_global_client_config_from_worktree_uses_main_checkout_root`.

## Related

- ADR-608: ADRs live in-repo and are part of the public release.
- ADR-642: ADR central JSON is the source of truth for ADR indexing.

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "scripts/configure_mcp.py root-selection behavior for linked worktrees"
    - "sync_agents global MCP projection behavior for linked worktrees"
    - "Cowork connector registration root-selection behavior for linked worktrees"
  patterns_deprecated:
    - "writing user-global MCP config with linked-worktree absolute paths"
  files_affected:
    - "src/config/worktrees.py"
    - "scripts/configure_mcp.py"
    - "tests/scripts/test_configure_mcp_cli.py"
    - "project-brain/capabilities/skills/ai/scripts/sync_agents/templates.py"
    - "project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/opencode.py"
    - "project-brain/capabilities/skills/ai/scripts/sync_agents/adapters/antigravity.py"
    - "project-brain/capabilities/skills/ai/scripts/sync_agents/tests/test_adapter_lifecycle.py"
    - "project-brain/capabilities/skills/plugin-pack/scripts/formatters/mcp_config.py"
    - "project-brain/capabilities/skills/plugin-pack/scripts/formatters/cowork.py"
    - "project-brain/capabilities/skills/plugin-pack/augur/tests/test_cowork_formatter.py"
    - "docs/adrs/ADR-774-main-rooted-global-mcp-config.md"
    - "docs/superpowers/specs/2026-05-22-main-rooted-global-mcp-config-design.md"
    - "docs/superpowers/plans/2026-05-22-main-rooted-global-mcp-config.md"
```
