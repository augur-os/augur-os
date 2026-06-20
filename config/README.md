# config/

Configuration directory for the Augur system (ADR-087).

## Structure

| Directory | Purpose |
|-----------|---------|
| `agents/` | Agent runtime config: IDE integrations, hooks, model mapping, headless profiles |
| `dashboard/` | Dashboard settings (action buttons, tool groups, shortcuts) |
| `defaults/` | Default configs copied to fresh installs |
| `integrations/` | MCP server configs, external provider settings |
| `system/` | System-level config (llm.yaml, preferences, paths) |

## Rules

- **No code** in this directory -- only YAML, JSON, and Markdown configuration files
- **No runtime data** -- logs, cache, and state live outside the repo via `src.config.paths`
- User-specific preferences live in the runtime/state directory; legacy repo-local `preferences.yaml` files are gitignored
- User-specific repo-local state files (`plugin_state.json`) are gitignored
- Default configs live in `defaults/` and are copied on first init

## Previously

This content was in `config/` and `data/defaults/`. Moved to root `config/` by ADR-087.
