# Mode: --migrate

Run when upgrading an existing Augur installation to the current structure. Skip clone/install steps.

## Migration Steps

1. **Detect legacy data** — Scan for data in deprecated paths:
   - `plugins/` (pre-ADR-426 skill locations)
   - `.agent/` (retired legacy workflow root)
   - `config/dashboard/*.yaml` (centralized config, should be decentralized per ADR-163)
   - Old vault paths that don't match `get_vault_dir()` layout

2. **Migrate to vault** — Move user-editable data (memory, actions, skill data) to `get_vault_dir()` following ADR-270 external directory layout. Use `src.config.paths` for path resolution, never hardcode.

3. **Verify plugin structure** — Confirm skills are in `skills/{skill}/` per ADR-426/ADR-430. Flag any skills still in legacy `plugins/` directories.

4. **Verify MCP wiring** — Run `python3 src/scripts/configure_mcp.py --apply` to ensure IDE integration is current.

5. **Seed vault prompt library docs** — Ensure `<get_vault_dir()>/prompts/README.md` exists. If missing, copy `project-brain/capabilities/skills/onboard/templates/vault-prompts-readme.md` without overwriting existing prompt notes.

6. **Run Post-Onboarding Checklist** (see `references/mode-default.md`).

---

## Vault Recovery

During `--migrate` or `--full`, recover the vault if missing:

1. Check if the vault directory (resolved via `get_vault_dir()`) exists (the directory, not just a symlink)
2. If it exists and contains `.git/`, vault is present — skip recovery
3. If missing:
   a. Verify GitHub auth: run `gh auth status` — if it fails, stop and tell the user to run `gh auth login`
   b. Read `config/system/vault.yaml` — parse YAML, extract `vault.remote` (the git URL) and `vault.path` (resolved via `get_vault_dir()`)
   c. If `vault.remote` is empty or the file doesn't exist, stop and tell the user: "No vault remote configured. Run `/onboard --connect vault <repo-url>` first."
   d. Clone: `git clone <vault.remote> <vault.path>` (expand `~` to `$HOME`)
   e. Validate: check that the cloned directory has expected top-level dirs (actions/, memory/, skills/)
   f. If clone fails (private repo, wrong URL), show the git error and suggest: "Check the remote URL in `config/system/vault.yaml` or re-run with `/onboard --connect vault <correct-url>`"

---

## Connect Vault

`/onboard --connect vault <repo-url>` — wire a git remote for the vault:

1. **Update config**: Read `config/system/vault.yaml`. Set `vault.remote` to `<repo-url>`. Write back with `vault.path` preserved (resolved via `get_vault_dir()` if not set). Use standard YAML format:
   ```yaml
   vault:
     remote: <repo-url>
     path: <get_vault_dir()>
   ```
2. **Initialize git if needed**: Expand `vault.path` to an absolute path. If the directory doesn't exist, create it with `mkdir -p`.
   - If `<vault.path>/.git` does NOT exist: run `git init` then `git remote add origin <repo-url>` inside the directory
   - If `<vault.path>/.git` EXISTS: run `git remote set-url origin <repo-url>` (or `git remote add origin <repo-url>` if no origin remote exists)
3. **Verify**: Run `git remote -v` in the vault directory and confirm the origin URL matches `<repo-url>`
4. **Report**: Tell the user the vault remote is configured and they can run `/onboard --migrate` to clone content if the directory is empty
