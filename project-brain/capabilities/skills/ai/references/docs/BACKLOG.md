# ai — Backlog

## Refactor

- [ ] **Extract src/lib MCP JSON config logic** — The `read-merge-write augur entry` pattern is duplicated across `cursor_cli`, `kimi_cli`, and `opencode` adapters. Extract into a src/lib helper like `_ensure_mcp_json_config(config_path, tool_name)` in `cli_agent_base.py`. (Source: `adapters/cli_agent_base.py:97`)
