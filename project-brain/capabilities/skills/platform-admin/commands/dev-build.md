---
description: Clean caches, rebuild the dashboard UI, and validate pages have no build issues.
visibility: dev
x-augur-export-command: false
---

# /dev-build

Clean all caches, rebuild the dashboard UI, and validate pages have no build issues.

## Gotchas

### 1. All dashboard state changes go through the lifecycle gate
Per CLAUDE.md rule 18, never run `npm run dev`, `npm run build`, or kill dashboard processes directly. Use `dashboard_lifecycle.request_action()` or `/dev-build` which calls the gate internally. Direct manipulation bypasses crash-loop protection and breaks coordination between concurrent agents.

### 2. Turbopack cache corruption produces a running-but-broken server
A corrupted `.next/cache` (missing `.sst` files) makes the server return 500 on all routes while appearing healthy. The startup guard cannot detect mid-session corruption. When all routes fail simultaneously, delete `.next/cache` and rebuild; do not debug individual routes.

### 3. Newly mounted plugin routes require a dev server restart
Turbopack does not pick up routes added by `mount-plugins` at runtime. After running mount-plugins, the dev server must be fully restarted. Edits to existing routes hot-reload fine, but new `page.tsx` files are invisible until restart.

## Usage

```bash
/dev-build
/dev-build --all
/dev-build --pages /health,/career
/dev-build --watch
```

## Execution Steps

See [../references/dev-build-execution-steps.md](../references/dev-build-execution-steps.md) for the full build workflow and [../references/dev-build-troubleshooting.md](../references/dev-build-troubleshooting.md) for common dashboard build failures.

## Worktree Targeting

When invoked from a registered Augur worktree, `/dev-build` targets the current
worktree instance by default:

- dashboard port comes from `.augur-worktree.yaml` or `worktree_registry.yaml`
- MCP port comes from the same instance record
- lifecycle state and build lock are scoped to `worktree:<name>`
- browser verification uses isolated/headless automation
- the current main browser tab must remain untouched

Use `--target main` only when the user explicitly asks to validate the main
checkout. Use `--interactive` only when the user explicitly wants a separate
visible worktree debug surface.

When `--interactive` is passed, the agent must export `AUGUR_INTERACTIVE=1`
before invoking `apps/dashboard/scripts/start-dev.sh` (or `start-dev.mjs`).
That env var is the contract between the slash command and the dev-server
entrypoint: the entrypoint forwards `--interactive` to `worktree_preflight.py`,
which sets `browser_mode=isolated_visible` for the worktree/isolated
instance. `visibility_policy` stays `no_visible_mutation` so the main
user-visible browser is untouched regardless.

## Examples

- `/dev-build` — Smart mode: check pages based on recent changes
- `/dev-build --all` — Full mode: check all pages
- `/dev-build --pages /health,/career` — Check specific pages only
- `/dev-build --watch` — Quick reload: clear cache and restart dev server

## Options

| Flag | Description |
|------|-------------|
| `--all` | Full mode: check all pages |
| `--pages` | Check specific pages only |
| `--watch` | Quick reload: clear cache and restart dev server |
| `--target main` | Validate the main checkout even when invoked from a worktree |
| `--interactive` | Open a separate visible worktree debug surface (`browser_mode=isolated_visible`); main browser still untouched |

## Mode Selection

| Argument | Example | Description |
|----------|---------|-------------|
| `*(none)*` | `/dev-build` | Smart mode: check pages based on recent changes |
| `--all` | `/dev-build --all` | Full mode: check all pages |
| `--pages` | `/dev-build --pages /health,/career` | Check specific pages only |
| `--watch` | `/dev-build --watch` | Quick reload: clear cache and restart dev server |
