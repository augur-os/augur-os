# Mode: --connect <platform>

Add a new platform to an existing Augur installation. Supported platforms: `vault`, `vscode`, `cursor`, `claude-code`, `codex`, `gemini`, `copilot`.

`vault` is the platform-neutral knowledge-store target — a plain Markdown vault on disk. It works without Obsidian installed; the optional `vault-scaffold` step drops in an `.obsidian/` config for users who want an Obsidian-flavored view of the same vault.

## Steps

1. **Verify Augur is installed** — Check the Augur repo root or `$AUGUR_DIR` exists.
2. **Configure MCP** — Run `python scripts/configure_mcp.py --client <platform> --auto`.
3. **Platform-specific setup**:
   - `vault`: Optionally run the `vault-scaffold` MCP tool to create `.obsidian/` config in the vault for Obsidian-flavored viewing. Skip this step if the user does not use Obsidian.
   - `vscode`/`cursor`: No additional setup needed (MCP wiring is sufficient)
4. **Update state** — Add platform to `configured_clients` in the runtime state file under `get_runtime_dir()` (Windows uses AppData-backed runtime storage; macOS uses `~/Library/Application Support/...`).
5. **Show getting-started message** for the platform (see below).

---

## Getting-Started Messages

After install, show a platform-relevant message:

**From Claude Code (`--from claude-code` or default):**
> Augur is installed. Run `/commands` to see available commands, or open `localhost:3000` for the dashboard.

**Vault target (`--from vault`):**
> Augur is installed and your vault is configured. The vault is plain Markdown at the path configured in `project.yaml` (resolved via `get_vault_dir()`) and works with any editor. If you prefer an Obsidian-flavored view, run `vault-scaffold` to drop in an `.obsidian/` config. The dashboard is at localhost:3000.

**From VS Code (`--from vscode`):**
> Augur is installed and MCP is configured. Open the Augur sidebar to check status. The dashboard is at localhost:3000.

**From Cursor (`--from cursor`):**
> Augur is installed and MCP is configured. The dashboard is at localhost:3000.
