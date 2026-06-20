---
status: Implemented
date: 2026-03-23
deciders:
  - Gur Sannikov
related:
  - ADR-270
hub: adaptive
tags:
  - paths
  - config
  - self-healing
superseded_by: null
---

# ADR-481: Centralized Path Configuration with Self-Discovery

## Context

Augur had 3 layers of path configuration with no single authority:

1. **Env vars** (`~/.zshrc`) — `AUGUR_ROOT`, `AUGUR_VAULT`, `AUGUR_DOCUMENTS`
2. **YAML config** (`src/config/path_config.yaml`) — `paths.data`, `paths.core`, `paths.runtime`
3. **Hardcoded defaults** (`path_primitives.py`) — `~/Vault/{name}`, `~/Documents/{name}`

Plus ~22 skill MCP modules with their own hardcoded fallback paths in `except ImportError` blocks.

When the user moved vault or documents directories, they had to update env vars, YAML config, daemon plist, and hunt down hardcoded paths. No self-discovery existed — wrong paths caused silent writes to the old location.

## Decision

### Single Config File — `project.yaml`

`project.yaml` at the repo root is the sole authority for user-configurable paths:

```yaml
name: Augur
port: 3000

paths:
  vault: ~/Projects/Au-vault
  documents: ~/Projects/Au-docs
```

**Resolution order:** env var > `project.yaml` > hardcoded default.

Project root is implicit (derived from `project.yaml` location). Runtime paths (state, logs, cache) stay platform-conventional and are not in this config.

### Self-Discovery

When `get_vault_dir()` or `get_documents_dir()` resolves a path that doesn't exist on disk, self-discovery triggers automatically:

1. Scan for `.augur-vault` / `.augur-docs` marker files
2. Fall back to structure fingerprinting (vault: `memory/` + 3 skill-named subdirs; docs: skill-named subdirs with binary files)
3. Scan locations: siblings of configured path, `~/`, `~/Documents/`, `~/Desktop/`
4. Budget: 100 candidates or 5 seconds, whichever first
5. One-shot cached per session — never runs twice

Discovery is silent in the resolution chain (logs a warning). Interactive prompting is only done by the `augur config fix` CLI command.

### Marker Files

`.augur-vault` and `.augur-docs` sentinel files are created by `augur config fix` or `create_marker()`. Minimal YAML content for identity and disambiguation.

### Config Fix CLI

`python -m src.scripts.config_fix` runs discovery for all paths, prompts the user for each stale one, updates `project.yaml` atomically, and regenerates the daemon plist.

### Rollback

Set `AUGUR_PATH_LEGACY=1` env var to skip `project.yaml` reading entirely and fall back to the old behavior.

## Consequences

### Positive

- User changes 2 lines in `project.yaml` to relocate vault/documents — no more hunting across env vars, YAML configs, and daemon plists
- Self-discovery finds moved directories automatically
- Single cached resolution path reduces syscalls vs. previous scattered resolution
- `_dir_cache` avoids repeated `.exists()` checks on hot paths

### Negative

- `project.yaml` is now load-bearing for path resolution (was optional before)
- Self-discovery adds latency (~5s max) on first access when a path is missing
- Marker files (`.augur-vault`, `.augur-docs`) are new artifacts in user directories

### Neutral

- Env vars still work as overrides — existing workflows that set `AUGUR_VAULT` are unaffected
- `path_primitives.py` hardcoded defaults remain as last-resort fallback

## Alternatives Considered

### Alternative A: `project.yaml` delegates to `path_config.yaml`

Keep `path_config.yaml` as the actual path store, add a pointer from `project.yaml`. Rejected because it still requires two files and doesn't solve the "update 3 lines in one file" goal.

### Alternative B: `project.yaml` as authority, `path_config.yaml` as derived/cached

`project.yaml` owns paths, system generates `path_config.yaml` from it. Rejected because the generated file can go stale and two files exist even though one is derived.

## References

- Spec: `docs/superpowers/specs/2026-03-23-centralized-path-config-design.md`
- Plan: `docs/superpowers/plans/2026-03-23-centralized-path-config.md`
- ADR-270: Storage layer separation (predecessor)

## Impact Manifest

```yaml
impact:
  paths_renamed: []
  apis_changed:
    - "invalidate_project_name_cache() → invalidate_project_cache()"
    - "get_path_config_functions() returns 4-tuple (was 5-tuple)"
  patterns_deprecated:
    - "src/config/path_config.yaml (deleted)"
    - "get_config_path() (removed)"
    - "PathConfig.from_yaml() (removed)"
    - "AUGUR_VAULT/AUGUR_DOCUMENTS env vars in ~/.zshrc (removed, project.yaml is authority)"
  files_affected:
    - "project.yaml"
    - "src/config/paths.py"
    - "src/config/path_discovery.py (new)"
    - "src/config/path_config.py"
    - "src/config/path_config.yaml (deleted)"
    - "src/scripts/config_fix.py (new)"
    - "src/mcp/augur_mcp/config.py"
    - "src/mcp/augur_mcp/compat.py"
    - "src/mcp/augur_mcp/infrastructure/paths.py"
    - "skills/*/scripts/mcp/__init__.py (~21 files)"
```
