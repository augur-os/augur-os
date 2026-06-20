# Main-Rooted Global MCP Config Design

## Problem

Augur writes generated MCP configuration into user-global client files such as Claude Desktop, Cursor, Codex, Gemini, Cline, and Perplexity. When `scripts/configure_mcp.py` runs from a linked git worktree, those global files can be stamped with absolute paths to the worktree. Removing or archiving the worktree then breaks MCP while the main repository still looks clean.

## Decision

Generated MCP config must use two roots:

- User-global client config uses the main checkout root.
- Repo-local config paths containing `{repo_root}` use the active checkout or worktree root.

This keeps global tools pointed at stable infrastructure while preserving local worktree config for workspace-scoped clients such as VS Code and generic repo-local MCP config.

## Scope

The implementation changes all MCP projection paths found during debugging:

- `scripts/configure_mcp.py` chooses an effective root per IDE target.
- `sync_agents` global MCP writers use a main-checkout root when invoked from a linked worktree.
- Antigravity global sync preserves non-Augur MCP servers instead of overwriting the file.
- Cowork/Claude Desktop connector registration uses the same main-root rule.

Existing downstream validation remains in `auto-heal-validate`, which catches stale generated MCP config and stale daemon service registration. Metadata stamping and richer drift provenance can follow later, but the root-cause guard now prevents known global config writers from stamping ephemeral worktree paths.

## Acceptance Criteria

- Running `configure_mcp.py --repo-root <linked-worktree> --client cursor --auto` writes global Cursor config entries that reference the main checkout, not the linked worktree.
- Repo-local config paths that contain `{repo_root}` continue to resolve against the active checkout.
- `configure_mcp.py --check --verbose` remains clean on the real main checkout.
- Tests cover global config root selection from simulated linked worktrees across `configure_mcp`, sync-agent adapters, and Cowork connector registration.
