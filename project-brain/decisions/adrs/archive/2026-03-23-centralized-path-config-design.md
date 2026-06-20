# Centralized Path Configuration with Self-Discovery

**Date:** 2026-03-23
**Status:** Approved
**Scope:** Path resolution, config management, self-healing

## Problem

Augur has 3 layers of path configuration, none authoritative:

1. **Env vars** (`~/.zshrc`) — `AUGUR_ROOT`, `AUGUR_VAULT`, `AUGUR_DOCUMENTS`
2. **YAML config** (`src/config/path_config.yaml`) — `paths.data`, `paths.core`, `paths.runtime`
3. **Hardcoded defaults** (`path_primitives.py`) — `~/Vault/{name}`, `~/Documents/{name}`

Plus scattered fallback paths across `skills/*/scripts/mcp/__init__.py`, `_shared.py`, `_helpers.py`, `sync_discover.py`, `migrate_vault_flatten.py`, and `src/mcp/augur_mcp/config.py` — each with their own hardcoded fallback when imports fail.

When the user moves a folder, they must update env vars, YAML config, daemon plist, and hunt down hardcoded paths. There is no self-discovery — if a path is wrong, everything silently writes to the wrong location.

## Design

### 1. Single Config File — `project.yaml`

`project.yaml` at the repo root becomes the sole authority for user-configurable paths:

```yaml
name: Augur
port: 3000

paths:
  vault: ~/Projects/Au-vault
  documents: ~/Projects/Au-docs
```

- **Project root** is implicit — derived from the directory containing `project.yaml`.
- **Runtime paths** (state, logs, cache) stay platform-conventional (`~/Library/Application Support/`, `~/Library/Logs/`, `~/Library/Caches/`) and are not configurable here. Env var overrides still work for these.
- **Resolution order:** env var > `project.yaml` > hardcoded default.
- **Schema tolerance:** If `paths:` is missing or not a dict, treat all paths as unconfigured (fall through to env var, then default). Unknown keys under `paths:` are silently ignored. Tilde expansion applies to all path values.

### 2. Path Reading API

New function in `paths.py`:

```python
def get_project_paths() -> dict[str, Path]:
    """Read paths: block from project.yaml. Cached alongside project name."""
```

- Returns `{"vault": Path(...), "documents": Path(...)}` or `{}` if missing/malformed.
- Cached in a module-level `_project_paths_cache` variable.
- Invalidated by `invalidate_project_name_cache()` (renamed to `invalidate_project_cache()`).
- Applies tilde expansion and resolves to absolute paths.

### 3. Marker Files for Self-Discovery

On first successful path resolution (or via `augur config fix`), sentinel files are created:

| Marker file | Location | Content |
|-------------|----------|---------|
| `.augur-vault` | Vault root | `project: Augur` + `created: YYYY-MM-DD` |
| `.augur-docs` | Documents root | Same format |

Properties:
- Gitignored (added to vault's `.gitignore` if present)
- Only created by explicit system action, never silently
- Used solely for discovery — never as a path source during normal operation
- Minimal YAML content for identity and disambiguation

### 4. Self-Discovery Flow

Triggers on first call to `get_vault_dir()` or `get_documents_dir()` when the configured path doesn't exist.

```
get_vault_dir() called
  → configured path exists? → return it
  → run discovery (once per session, cached)
      → scan locations for .augur-vault marker
      → if no marker found, scan for structure fingerprint:
          - vault: contains memory/ AND at least 3 subdirs whose names
            match entries in skills/ (case-sensitive). If skills/ is
            unreadable, require memory/ + dev/ + config/.
          - docs: has skill-named subdirs with binary files
      → if found:
          → log: "Vault not found at /old/path. Found at /new/path."
          → if interactive (TTY): prompt "Update project.yaml? (y/n)"
          → if non-interactive (daemon): log warning, use discovered path for session
      → if not found:
          → log error, cache failure, return configured path anyway
```

**Scan locations** (in order, stop on first match):
1. Sibling directories of configured path (e.g., `~/Projects/*/`)
2. `~/` direct children
3. `~/Documents/*/`
4. `~/Desktop/*/`
5. Mounted volumes (`/Volumes/*/`)

**Scan budget:** Stop after checking 100 candidate directories or 5 seconds elapsed, whichever comes first. Log if budget is exhausted without a match. `/Volumes/*/` is only scanned by `augur config fix --deep`, not by automatic discovery.

**One-shot cache:** Discovery result (found path or failure) is stored in a module-level variable. Never runs twice in the same process.

**Daemon vs interactive:** The daemon can't prompt, so it uses the discovered path silently and logs a warning. Interactive sessions (Claude Code, CLI) prompt the user.

### 5. Config Update Mechanism

When the user confirms "Update project.yaml? (y/n)":

1. Read `project.yaml`
2. Update only the stale path (e.g., `paths.vault`) — don't touch other fields
3. Write back using PyYAML `safe_load` + `safe_dump` (the file is simple enough that comment preservation is not needed; no new dependency required)
4. Write atomically via `tempfile` + `os.replace` to handle concurrent access
5. Invalidate the path cache
6. Regenerate daemon plist with updated `AUGUR_VAULT` value and print "Run `launchctl unload/load` to pick up changes"

**CLI command:** `augur config fix` — runs discovery for all paths, prompts for each stale one, updates `project.yaml` in one shot. Supports `--deep` flag to include `/Volumes/*/` scan.

**Concurrency:** Writes to `project.yaml` use atomic rename (`tempfile` + `os.replace`). Running processes retain their cached paths for the session; cache invalidation only affects the process that performs the write.

### 6. Migration Plan

| What | Action |
|------|--------|
| `src/config/path_config.yaml` | Delete. Alert thresholds stay as dataclass defaults in `AlertThresholds` (they are operational constants, not user config). No `config/monitoring.yaml` needed. |
| `paths.py` `_vault_home_dir()` etc. | Rewrite: env var > `project.yaml` (via `get_project_paths()`) > hardcoded default. |
| `path_primitives.py` `vault_home_dir()` | Stays as-is — hardcoded last-resort default. |
| `path_config.py` `PathConfig.from_yaml()` | Rewrite to build from `project.yaml` + `paths.py` functions instead of reading `path_config.yaml`. |
| All `skills/*/scripts/mcp/__init__.py`, `_shared.py`, `_helpers.py` with `AUGUR_VAULT`/`AUGUR_DOCUMENTS` fallbacks | Sweep: replace with `from src.config.paths import get_vault_dir, get_documents_dir`. If import fails (standalone context), read `AUGUR_VAULT` env var, then hardcoded default. Covers ~15 skill MCP modules. |
| `src/mcp/augur_mcp/config.py` | Explicit fix — has its own parallel path resolution that must use `paths.py`. |
| `src/lib/sync_discover.py`, `src/scripts/migrate_vault_flatten.py` | Replace hardcoded fallbacks with `paths.py` imports. |
| `~/.zshrc` env vars | Remove `AUGUR_VAULT` and `AUGUR_DOCUMENTS` lines. `AUGUR_ROOT` stays (used by shell aliases). |
| `.claude/settings.json` Stop hook | Replace with: `python3 -c "from src.config.paths import get_vault_dir; print(get_vault_dir())"` to resolve vault path, then run git commands. This uses the full resolution chain. |
| Daemon plist `EnvironmentVariables` | Regenerate with `AUGUR_VAULT` from `project.yaml` on each `augur config fix`. Daemon also reads `project.yaml` directly at startup as primary source; plist env var is fallback for pre-startup context. |

### 7. Rollback Plan

If the migration breaks path resolution:
1. Restore `src/config/path_config.yaml` from git
2. Set `AUGUR_PATH_LEGACY=1` env var to force old code path (paths.py checks this flag and skips project.yaml reading)
3. Debug and fix
4. Remove env var once `project.yaml` paths are verified

### 8. File Changes Summary

**New files:**
- `src/config/path_discovery.py` — self-discovery logic (marker scanning, fingerprinting, prompt, scan budget)

**Modified files:**
- `project.yaml` — add `paths:` block
- `src/config/paths.py` — add `get_project_paths()`, rewrite `_vault_home_dir()` / `_documents_home_dir()` to use resolution chain, integrate discovery on failure
- `src/config/path_config.py` — rewrite `from_yaml()` to use `project.yaml` + `paths.py`, remove `get_config_path()` YAML file lookup
- `skills/*/scripts/mcp/__init__.py` (~15 files) — remove hardcoded vault fallbacks
- `skills/*/scripts/mcp/_shared.py`, `_helpers.py` — same sweep
- `src/mcp/augur_mcp/config.py` — use `paths.py` instead of parallel resolution
- `src/lib/sync_discover.py` — remove hardcoded fallback
- `src/scripts/migrate_vault_flatten.py` — remove hardcoded fallback
- `~/.zshrc` — remove `AUGUR_VAULT`, `AUGUR_DOCUMENTS` lines
- `.claude/settings.json` — update Stop hook to use `paths.py` resolution

**Deleted files:**
- `src/config/path_config.yaml`

### 9. Testing Strategy

- Unit test: `project.yaml` path reading with all 3 resolution layers (env > yaml > default)
- Unit test: malformed `project.yaml` (missing `paths:`, non-dict, unknown keys) falls through gracefully
- Unit test: discovery scanning finds marker files
- Unit test: discovery fingerprinting identifies vault by structure (matching skill names against `skills/`)
- Unit test: one-shot cache prevents repeated scans
- Unit test: scan budget terminates after 100 candidates or 5 seconds
- Unit test: interactive vs non-interactive prompt behavior
- Unit test: atomic write to `project.yaml` via `os.replace`
- Integration test: move vault directory, verify discovery triggers and prompts
- Integration test: `augur config fix` batch-updates all stale paths
- Integration test: `AUGUR_PATH_LEGACY=1` rollback flag forces old code path
