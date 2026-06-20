# Track 2 — Vault Server Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Worktree required:** Before starting, use `superpowers:using-git-worktrees` to create a worktree off `main` with branch name `track2-vault-server-split`.

> **Cross-repo work:** PRs 4-6 modify both this Augur repo and the user's Au-vault repo at `~/Projects/Au-vault/`. The plan documents both sides; verify Au-vault is clean before each cross-repo PR.

**Goal:** Move 5 vault bundles (apple, lifestyle, file-manager, obsidian, ingest) from the monolith MCP server into per-bundle stdio servers (`augur-apple`, `augur-lifestyle`, etc.). Build the supporting CLI (`aug config sync`) and manifest infrastructure as PR 0 prerequisites.

**Architecture:** Generic per-bundle launcher in `src/mcp/augur_mcp/bundle_server.py`. Source-of-truth manifest at `config/system/mcp_servers.yaml`. Hybrid transition strategy: validation PR for apple before atomic switches.

**Tech Stack:** Python 3.11+, FastMCP (existing), pyyaml, pytest, uv. No new dependencies.

**Related specs:**
- Layer 1: `docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md`
- Layer 4 migration: `docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md`
- Track 2 design: `docs/superpowers/specs/2026-04-29-track2-vault-server-split-design.md`
- Prior plans (Track 1): `2026-04-29-track1-{doc-extractor,knowledge-memory,daemon-runtime,rag-index,ai}-extraction.md`

## File Structure

### New files (created in PR 0)

| File | Purpose |
|---|---|
| `config/system/mcp_servers.yaml` | Source-of-truth manifest for all MCP server topology. Initial state has only the project-tier `augur` monolith and empty `vault_tier` / `monolith_exclusions`. |
| `src/mcp/augur_mcp/bundle_server.py` | Generic per-bundle stdio server launcher. Invoked as `python -m augur_mcp.bundle_server <name>`. |
| `src/cli_config/__init__.py` | Package init for config-sync CLI module. |
| `src/cli_config/manifest.py` | Loader + validator for `config/system/mcp_servers.yaml`. |
| `src/cli_config/config_sync.py` | Main orchestrator; subcommand entry point `register_config_subcommands(subparsers)`. |
| `src/cli_config/adapters/__init__.py` | Adapter registry. |
| `src/cli_config/adapters/base.py` | `ClientConfigAdapter` protocol — read/write/diff client config. |
| `src/cli_config/adapters/claude.py` | Adapter for `~/.claude/settings.json` MCP servers section. |
| `src/cli_config/adapters/codex.py` | Adapter for `~/.codex/config.toml`. |
| `src/cli_config/adapters/gemini.py` | Adapter for `~/.gemini/settings.json`. |
| `tests/cli/test_config_sync.py` | Test the orchestrator end-to-end with all 3 adapters via tmp dirs. |
| `tests/cli/test_config_adapters.py` | Per-adapter tests for shape correctness + idempotency + augur-prefix scoping. |
| `tests/cli/test_manifest.py` | Manifest loader/validator tests. |
| `tests/cli/test_bundle_server.py` | Smoke test for `bundle_server.run()` — starts FastMCP, exposes correct tools. |

### Files modified (across PRs)

| File | PR | Change |
|---|---|---|
| `pyproject.toml` | 0 | No change to console script (`aug` already exists). Subcommand wired via existing argparse subparsers. |
| `src/cli.py` | 0 | Wire `aug config <subcommand>` to `src.cli_config.config_sync.register_config_subcommands(subparsers)`. |
| `src/mcp/augur_mcp/plugin_tools.py` | 0 | Extract `_load_bundle_mcp_module(skill_dir)` helper; use it from both `register_plugin_tools()` and `bundle_server.run()`. Read manifest's `monolith_exclusions` from `_collect_skill_dirs()`. |
| `config/system/mcp_servers.yaml` | 1-6 | Each PR appends entries (PRs 2-6 to `vault_tier` + `monolith_exclusions`). |
| `~/Projects/Au-vault/skills/apple/` | 1 | No change in Au-vault — apple already lives there. |
| Augur `skills/file-manager/`, `skills/obsidian/`, `skills/ingest/` | 4-6 | `git rm -r` (Augur side); `git mv` to Au-vault (separate commit in Au-vault repo). |
| `tests/architecture/test_no_cross_skill_imports.py` | 6 (last) | No retirement in Track 2; entries persist for Track 3a. |

## Critical execution rules (read before every task)

- **Never** use `--no-verify` on `git commit`. Pre-commit failures must be fixed by creating a NEW commit.
- **Never** edit user-tier client configs (`~/.claude/...`, `~/.codex/config.toml`, `~/.gemini/...`) directly during plan execution. The `aug config sync` CLI is what writes them, and it's run by the user (or by a test invoking it against tmp dirs). The plan never causes the implementer to write to those paths.
- **Cross-repo PRs (4-6)**: Au-vault commits land first (push to user's vault remote), then the Augur PR merges. Each PR's verification step checks Au-vault HEAD before allowing Augur-side commit.
- **Worktree pollution**: every commit step verifies `git status --short` shows only expected files. If anything else, restore with `git checkout HEAD --` before committing.
- **No shortcuts**: per user directive, build the proper long-term shape. CLI adapters are real with proper round-trip read/write, not stubs. Manifest schema is fully validated, not just dict-coerced.

---

## Task 0: PR 0 — Manifest + CLI infrastructure + per-bundle launcher

**Files (Create):**
- `config/system/mcp_servers.yaml`
- `src/mcp/augur_mcp/bundle_server.py`
- `src/cli_config/{__init__.py, manifest.py, config_sync.py}`
- `src/cli_config/adapters/{__init__.py, base.py, claude.py, codex.py, gemini.py}`
- `tests/cli/{test_config_sync.py, test_config_adapters.py, test_manifest.py, test_bundle_server.py}`

**Files (Modify):**
- `src/cli.py` — wire `aug config` subcommand
- `src/mcp/augur_mcp/plugin_tools.py` — extract `_load_bundle_mcp_module()` + read manifest exclusions

PR 0 is the largest in Track 2. It builds the foundation that PRs 1-6 reuse. No bundle migrations happen here.

### Step 0.1: Verify branch + worktree state

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  git branch --show-current && \
  git status --short
```
Expected: `track2-vault-server-split`, clean. STOP if not.

### Step 0.2: Create `config/system/mcp_servers.yaml`

Save:

```yaml
# Augur MCP server topology manifest.
# Source-of-truth for which MCP servers should be registered with AI clients
# (Claude Code, Codex, Gemini).
#
# Read by:
#   - aug config sync         — to write client configs
#   - augur_mcp.plugin_tools  — to apply monolith_exclusions during skill scan
#   - augur_mcp.bundle_server — to resolve a bundle's launch parameters
#
# Layer 1 spec: docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md
# Track 2 spec: docs/superpowers/specs/2026-04-29-track2-vault-server-split-design.md

# Project-tier servers (always registered; ship with Augur framework).
project_tier:
  - id: augur
    description: Project-tier monolith MCP server (split into augur-core + augur-framework in Track 3a)
    command: python
    args: [-m, augur_mcp]
    cwd_required: true
    env:
      PYTHONPATH: "${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
      PYTHONUNBUFFERED: "1"

# Vault-tier per-bundle servers (added by Track 2 PRs 2-6).
vault_tier: []

# Bundles excluded from the monolith's skill scan because they're served
# by per-bundle vault-tier servers. Modified by Track 2 PRs 2-6.
monolith_exclusions: []
```

### Step 0.3: Create `src/cli_config/__init__.py`

```python
"""Augur CLI: config-sync subcommand.

Reads config/system/mcp_servers.yaml and writes corresponding entries
to user-tier AI client configs (Claude Code, Codex, Gemini).

Wired into the `aug` CLI via src/cli.py:setup_subparsers().
"""
from __future__ import annotations
```

### Step 0.4: Create `src/cli_config/manifest.py`

```python
"""Manifest loader and validator for config/system/mcp_servers.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ServerEntry:
    """One MCP server in the manifest (project-tier or vault-tier)."""

    id: str
    description: str
    command: str
    args: list[str]
    cwd_required: bool = False
    env: dict[str, str] = field(default_factory=dict)
    bundle: str | None = None  # Set for vault_tier entries.
    bundle_path: str | None = None  # Set for vault_tier entries.


@dataclass(frozen=True)
class Manifest:
    """Parsed config/system/mcp_servers.yaml."""

    project_tier: list[ServerEntry]
    vault_tier: list[ServerEntry]
    monolith_exclusions: list[str]

    def all_augur_servers(self) -> list[ServerEntry]:
        """Both project- and vault-tier servers (used by adapters)."""
        return [*self.project_tier, *self.vault_tier]


def load_manifest(path: Path | None = None) -> Manifest:
    """Load and validate config/system/mcp_servers.yaml.

    Args:
        path: Override path (used by tests). Defaults to the canonical
            project-relative location.

    Raises:
        FileNotFoundError: if the manifest doesn't exist.
        ValueError: if any entry is malformed.
    """
    if path is None:
        from src.config.paths import get_project_root

        path = get_project_root() / "config" / "system" / "mcp_servers.yaml"

    if not path.exists():
        raise FileNotFoundError(f"Manifest not found at {path}")

    raw = yaml.safe_load(path.read_text()) or {}
    return _build_manifest(raw)


def _build_manifest(raw: dict[str, Any]) -> Manifest:
    project_tier = [_build_entry(e, tier="project") for e in raw.get("project_tier", []) or []]
    vault_tier = [_build_entry(e, tier="vault") for e in raw.get("vault_tier", []) or []]
    monolith_exclusions = list(raw.get("monolith_exclusions", []) or [])

    _validate_unique_ids(project_tier + vault_tier)
    _validate_vault_entries(vault_tier)
    _validate_exclusions_against_vault(monolith_exclusions, vault_tier)

    return Manifest(
        project_tier=project_tier,
        vault_tier=vault_tier,
        monolith_exclusions=monolith_exclusions,
    )


def _build_entry(raw: dict[str, Any], tier: str) -> ServerEntry:
    required = {"id", "command", "args"}
    missing = required - set(raw.keys())
    if missing:
        raise ValueError(f"{tier}_tier entry missing required fields: {sorted(missing)}; raw={raw!r}")
    if not isinstance(raw["args"], list):
        raise ValueError(f"args must be a list; got {type(raw['args']).__name__}; raw={raw!r}")
    return ServerEntry(
        id=str(raw["id"]),
        description=str(raw.get("description", "")),
        command=str(raw["command"]),
        args=[str(a) for a in raw["args"]],
        cwd_required=bool(raw.get("cwd_required", False)),
        env={str(k): str(v) for k, v in (raw.get("env") or {}).items()},
        bundle=raw.get("bundle"),
        bundle_path=raw.get("bundle_path"),
    )


def _validate_unique_ids(entries: list[ServerEntry]) -> None:
    seen: set[str] = set()
    for e in entries:
        if e.id in seen:
            raise ValueError(f"Duplicate server id in manifest: {e.id!r}")
        seen.add(e.id)


def _validate_vault_entries(vault_tier: list[ServerEntry]) -> None:
    for e in vault_tier:
        if not e.id.startswith("augur-"):
            raise ValueError(f"vault_tier entry id must start with 'augur-'; got {e.id!r}")
        if not e.bundle:
            raise ValueError(f"vault_tier entry {e.id!r} missing 'bundle' field")
        if not e.bundle_path:
            raise ValueError(f"vault_tier entry {e.id!r} missing 'bundle_path' field")


def _validate_exclusions_against_vault(exclusions: list[str], vault_tier: list[ServerEntry]) -> None:
    """Every monolith exclusion must correspond to a vault_tier entry."""
    vault_bundles = {e.bundle for e in vault_tier if e.bundle}
    extra = set(exclusions) - vault_bundles
    if extra:
        raise ValueError(
            f"monolith_exclusions contains bundle(s) without vault_tier entry: {sorted(extra)}"
        )
```

### Step 0.5: Create `src/cli_config/adapters/base.py`

```python
"""ClientConfigAdapter protocol: read/diff/write a single AI-client's config."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from src.cli_config.manifest import Manifest, ServerEntry


@dataclass(frozen=True)
class ConfigDiff:
    """Pending changes the adapter would write."""

    added: list[ServerEntry]
    updated: list[ServerEntry]
    removed: list[str]  # ids of augur-* entries no longer in manifest

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.updated or self.removed)


class ClientConfigAdapter(Protocol):
    """Per-client config read/write adapter.

    Each adapter is responsible for:
    - Locating the user-tier config file (defaults; override-able for tests).
    - Reading existing config; preserving non-augur entries verbatim.
    - Computing the diff vs. manifest.
    - Writing the new config atomically with a timestamped backup.

    All adapters scope their writes to entries with id matching `augur*`.
    """

    name: str  # 'claude' | 'codex' | 'gemini'

    def default_config_path(self) -> Path:
        """Default config path for this client."""
        ...

    def diff(self, manifest: Manifest, config_path: Path | None = None) -> ConfigDiff:
        """Compute the diff between manifest and current config."""
        ...

    def apply(self, manifest: Manifest, config_path: Path | None = None) -> Path:
        """Apply the manifest. Returns path of the backup file written."""
        ...
```

### Step 0.6: Create `src/cli_config/adapters/codex.py`

The Codex adapter is the most complex (TOML format with shell-script wrapping for the existing monolith). Build it first since Steps 0.7 / 0.8 (Claude/Gemini) follow the same pattern.

```python
"""Adapter for ~/.codex/config.toml MCP servers section.

Codex stores MCP servers as `[mcp_servers.<id>]` TOML tables with
`command` and `args`. The existing `augur` monolith uses a complex
shell launcher (passes its commands through `bash -lc` with a long
inline script) — the adapter preserves that exactly.

Per-bundle servers use a simpler pattern: `command = "python"` and
`args = ["-m", "augur_mcp.bundle_server", "<bundle>"]`, with PYTHONPATH
and AUGUR_ROOT set via env. The adapter generates these from manifest
ServerEntry fields.

Per Track 2 spec: only entries with id matching `augur*` are managed.
Other servers (context7, claude-in-chrome, etc.) are preserved verbatim.
"""
from __future__ import annotations

import datetime as _dt
import shutil
import sys
from pathlib import Path

# tomllib is stdlib in 3.11+; tomli_w writes (we add this dependency).
import tomllib  # type: ignore[import-not-found]

try:
    import tomli_w  # type: ignore[import-not-found]
except ImportError as e:
    raise ImportError(
        "tomli_w is required for the codex adapter. Add to dependencies: `uv add tomli_w`."
    ) from e

from src.cli_config.adapters.base import ConfigDiff
from src.cli_config.manifest import Manifest, ServerEntry


class CodexAdapter:
    name = "codex"

    def default_config_path(self) -> Path:
        return Path.home() / ".codex" / "config.toml"

    def diff(self, manifest: Manifest, config_path: Path | None = None) -> ConfigDiff:
        path = config_path or self.default_config_path()
        existing = self._read(path) if path.exists() else {}
        existing_servers = (existing.get("mcp_servers") or {})

        # Filter to augur-* entries only
        existing_augur = {
            sid: cfg for sid, cfg in existing_servers.items() if sid.startswith("augur")
        }

        wanted_by_id = {e.id: self._render_entry(e) for e in manifest.all_augur_servers()}

        added: list[ServerEntry] = []
        updated: list[ServerEntry] = []
        for entry in manifest.all_augur_servers():
            current = existing_augur.get(entry.id)
            wanted = wanted_by_id[entry.id]
            if current is None:
                added.append(entry)
            elif current != wanted:
                updated.append(entry)

        removed = [sid for sid in existing_augur if sid not in wanted_by_id]

        return ConfigDiff(added=added, updated=updated, removed=removed)

    def apply(self, manifest: Manifest, config_path: Path | None = None) -> Path:
        path = config_path or self.default_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        existing = self._read(path) if path.exists() else {}
        existing_servers = dict(existing.get("mcp_servers") or {})

        # Drop all augur-* servers, then re-add from manifest (idempotent, no merge).
        for sid in list(existing_servers):
            if sid.startswith("augur"):
                del existing_servers[sid]

        for entry in manifest.all_augur_servers():
            existing_servers[entry.id] = self._render_entry(entry)

        existing["mcp_servers"] = existing_servers

        backup = self._backup(path) if path.exists() else _no_backup_path(path)
        self._write(path, existing)
        return backup

    @staticmethod
    def _read(path: Path) -> dict:
        with path.open("rb") as fh:
            return tomllib.load(fh)

    @staticmethod
    def _write(path: Path, data: dict) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("wb") as fh:
            tomli_w.dump(data, fh)
        tmp.replace(path)

    @staticmethod
    def _backup(path: Path) -> Path:
        ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = path.with_suffix(path.suffix + f".bak.{ts}")
        shutil.copy2(path, backup)
        return backup

    @staticmethod
    def _render_entry(entry: ServerEntry) -> dict:
        """Translate a ServerEntry into the dict shape Codex expects."""
        out: dict = {"command": entry.command, "args": list(entry.args)}
        if entry.env:
            out["env"] = dict(entry.env)
        return out


def _no_backup_path(path: Path) -> Path:
    """Sentinel path returned when no existing config to back up."""
    return path.with_suffix(path.suffix + ".never-backed-up")
```

### Step 0.7: Create `src/cli_config/adapters/claude.py`

Claude Code stores MCP servers in `~/.claude/settings.json` under a top-level `mcpServers` key (camelCase, JSON object). Same pattern as codex, different format.

```python
"""Adapter for ~/.claude/settings.json mcpServers section.

Claude Code stores MCP servers as JSON object under top-level "mcpServers"
key. Each server entry is `{"command": str, "args": [str], "env": {...}}`.

Per Track 2 spec: only entries with id matching `augur*` are managed.
"""
from __future__ import annotations

import datetime as _dt
import json
import shutil
from pathlib import Path

from src.cli_config.adapters.base import ConfigDiff
from src.cli_config.adapters.codex import _no_backup_path
from src.cli_config.manifest import Manifest, ServerEntry


class ClaudeAdapter:
    name = "claude"

    def default_config_path(self) -> Path:
        return Path.home() / ".claude" / "settings.json"

    def diff(self, manifest: Manifest, config_path: Path | None = None) -> ConfigDiff:
        path = config_path or self.default_config_path()
        existing = self._read(path) if path.exists() else {}
        existing_servers = dict(existing.get("mcpServers") or {})

        existing_augur = {
            sid: cfg for sid, cfg in existing_servers.items() if sid.startswith("augur")
        }
        wanted_by_id = {e.id: self._render_entry(e) for e in manifest.all_augur_servers()}

        added: list[ServerEntry] = []
        updated: list[ServerEntry] = []
        for entry in manifest.all_augur_servers():
            current = existing_augur.get(entry.id)
            wanted = wanted_by_id[entry.id]
            if current is None:
                added.append(entry)
            elif current != wanted:
                updated.append(entry)

        removed = [sid for sid in existing_augur if sid not in wanted_by_id]
        return ConfigDiff(added=added, updated=updated, removed=removed)

    def apply(self, manifest: Manifest, config_path: Path | None = None) -> Path:
        path = config_path or self.default_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        existing = self._read(path) if path.exists() else {}
        existing_servers = dict(existing.get("mcpServers") or {})

        for sid in list(existing_servers):
            if sid.startswith("augur"):
                del existing_servers[sid]
        for entry in manifest.all_augur_servers():
            existing_servers[entry.id] = self._render_entry(entry)
        existing["mcpServers"] = existing_servers

        backup = self._backup(path) if path.exists() else _no_backup_path(path)
        self._write(path, existing)
        return backup

    @staticmethod
    def _read(path: Path) -> dict:
        return json.loads(path.read_text())

    @staticmethod
    def _write(path: Path, data: dict) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n")
        tmp.replace(path)

    @staticmethod
    def _backup(path: Path) -> Path:
        ts = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = path.with_suffix(path.suffix + f".bak.{ts}")
        shutil.copy2(path, backup)
        return backup

    @staticmethod
    def _render_entry(entry: ServerEntry) -> dict:
        out: dict = {"command": entry.command, "args": list(entry.args)}
        if entry.env:
            out["env"] = dict(entry.env)
        return out
```

### Step 0.8: Create `src/cli_config/adapters/gemini.py`

Gemini stores MCP servers in `~/.gemini/settings.json` under a `mcpServers` key (same shape as Claude). The adapter is structurally identical to Claude's; only the default path differs.

```python
"""Adapter for ~/.gemini/settings.json mcpServers section.

Same shape as Claude's adapter; only the default config path differs.
"""
from __future__ import annotations

from pathlib import Path

from src.cli_config.adapters.claude import ClaudeAdapter


class GeminiAdapter(ClaudeAdapter):
    name = "gemini"

    def default_config_path(self) -> Path:
        return Path.home() / ".gemini" / "settings.json"
```

### Step 0.9: Create `src/cli_config/adapters/__init__.py`

```python
"""Per-client adapters for `aug config sync`."""
from __future__ import annotations

from src.cli_config.adapters.base import ClientConfigAdapter, ConfigDiff
from src.cli_config.adapters.claude import ClaudeAdapter
from src.cli_config.adapters.codex import CodexAdapter
from src.cli_config.adapters.gemini import GeminiAdapter

ALL_ADAPTERS: tuple[ClientConfigAdapter, ...] = (
    ClaudeAdapter(),
    CodexAdapter(),
    GeminiAdapter(),
)

__all__ = [
    "ALL_ADAPTERS",
    "ClaudeAdapter",
    "ClientConfigAdapter",
    "CodexAdapter",
    "ConfigDiff",
    "GeminiAdapter",
]
```

### Step 0.10: Create `src/cli_config/config_sync.py`

```python
"""`aug config sync` orchestrator.

Reads config/system/mcp_servers.yaml and applies it to user-tier
client configs (Claude / Codex / Gemini).

Subcommand entry registered into the existing `aug` CLI via
register_config_subcommands(subparsers).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.cli_config.adapters import ALL_ADAPTERS, ClientConfigAdapter, ConfigDiff
from src.cli_config.manifest import Manifest, load_manifest


def register_config_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Wire `aug config <subcommand>` into the parent CLI."""
    config = subparsers.add_parser("config", help="Manage Augur MCP server topology and client configs")
    sub = config.add_subparsers(dest="config_command", required=True)

    sync = sub.add_parser("sync", help="Sync user-tier AI client configs from manifest")
    sync.add_argument(
        "--dry-run",
        action="store_true",
        help="Show diffs without writing to client configs.",
    )
    sync.add_argument(
        "--client",
        choices=[a.name for a in ALL_ADAPTERS],
        help="Sync only one client; default syncs all three.",
    )
    sync.set_defaults(handler=_handle_sync)

    status = sub.add_parser("status", help="Show drift between manifest and client configs")
    status.set_defaults(handler=_handle_status)


def _handle_sync(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    adapters = _select_adapters(args.client)

    if args.dry_run:
        return _print_diffs(manifest, adapters)

    rc = 0
    for adapter in adapters:
        diff = adapter.diff(manifest)
        if not diff.has_changes:
            print(f"[{adapter.name}] no changes")
            continue
        backup = adapter.apply(manifest)
        print(f"[{adapter.name}] applied: +{len(diff.added)} ~{len(diff.updated)} -{len(diff.removed)} (backup: {backup})")
    return rc


def _handle_status(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    return _print_diffs(manifest, ALL_ADAPTERS)


def _print_diffs(manifest: Manifest, adapters: tuple[ClientConfigAdapter, ...]) -> int:
    any_drift = False
    for adapter in adapters:
        diff = adapter.diff(manifest)
        if not diff.has_changes:
            print(f"[{adapter.name}] in sync")
            continue
        any_drift = True
        print(f"[{adapter.name}] drift:")
        for e in diff.added:
            print(f"  + {e.id}")
        for e in diff.updated:
            print(f"  ~ {e.id}")
        for sid in diff.removed:
            print(f"  - {sid}")
    return 1 if any_drift else 0


def _select_adapters(client: str | None) -> tuple[ClientConfigAdapter, ...]:
    if client is None:
        return ALL_ADAPTERS
    return tuple(a for a in ALL_ADAPTERS if a.name == client)
```

### Step 0.11: Wire `aug config` into `src/cli.py`

Read `src/cli.py` to find where subparsers are defined. Add a call to `register_config_subcommands(subparsers)` next to the existing subcommand wiring (next to `discover_subcommands(subparsers)` from `src.cli_plugins`).

The exact location depends on the current cli.py structure — find the line where `subparsers = parser.add_subparsers(...)` is created, then add:

```python
from src.cli_config.config_sync import register_config_subcommands
register_config_subcommands(subparsers)
```

Verify with:

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run aug config --help 2>&1 | head -20
```
Expected: shows `sync` and `status` subcommands. STOP if not.

### Step 0.12: Create `src/mcp/augur_mcp/bundle_server.py`

```python
"""Per-bundle MCP stdio server.

Usage: python -m augur_mcp.bundle_server <bundle-name>

Resolves the bundle dir via _collect_skill_dirs(), creates a fresh
FastMCP instance, and calls just that bundle's register_tools() —
unlike the monolith, which registers all enabled bundles' tools.

Used by Track 2's per-bundle vault-tier servers (augur-apple, etc.).
"""
from __future__ import annotations

import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]

from src.mcp.augur_mcp.plugin_tools import (
    _collect_skill_dirs,
    _load_bundle_mcp_module,
    _pin_mcp_sdk_package,
)


def run(bundle_name: str) -> int:
    """Start a per-bundle stdio MCP server for `bundle_name`.

    Returns:
        Exit code: 0 on clean shutdown, non-zero on error.
    """
    _pin_mcp_sdk_package()

    skill_entries = {sd.name: sd for _, sd in _collect_skill_dirs(apply_exclusions=False)}
    if bundle_name not in skill_entries:
        print(
            f"[augur_mcp.bundle_server] bundle '{bundle_name}' not found in any registered skill dir",
            file=sys.stderr,
        )
        return 1

    skill_dir: Path = skill_entries[bundle_name]
    mcp_init = skill_dir / "scripts" / "mcp" / "__init__.py"
    if not mcp_init.exists():
        print(
            f"[augur_mcp.bundle_server] bundle '{bundle_name}' has no scripts/mcp/__init__.py",
            file=sys.stderr,
        )
        return 1

    module = _load_bundle_mcp_module(skill_dir)
    if not hasattr(module, "register_tools"):
        print(
            f"[augur_mcp.bundle_server] bundle '{bundle_name}' has no register_tools()",
            file=sys.stderr,
        )
        return 1

    mcp = FastMCP(f"augur-{bundle_name}")
    from src.mcp.augur_mcp.interceptor import mcp_tool_interceptor  # local import to defer FastMCP cost
    from src.mcp.augur_mcp.metrics import metrics

    module.register_tools(mcp, mcp_tool_interceptor, metrics)
    mcp.run()
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m augur_mcp.bundle_server <bundle-name>", file=sys.stderr)
        return 2
    return run(sys.argv[1])


if __name__ == "__main__":
    sys.exit(main())
```

### Step 0.13: Refactor `plugin_tools.py` — extract helper + read manifest exclusions

Read `src/mcp/augur_mcp/plugin_tools.py:register_plugin_tools()` lines 138-240. The bundle-loading machinery (synthetic parent package + spec_from_file_location + exec_module) needs to be extracted into a new function `_load_bundle_mcp_module(skill_dir: Path)` that both `register_plugin_tools()` and `bundle_server.run()` call.

Also modify `_collect_skill_dirs()` to accept `apply_exclusions: bool = True` and consult the manifest for exclusions.

Edits to apply:

1. **Extract `_load_bundle_mcp_module`** (new function near `register_plugin_tools`):

```python
def _load_bundle_mcp_module(skill_dir: Path) -> Any:
    """Load and return the bundle's scripts/mcp/__init__.py as a module.

    Sets up a synthetic parent package so relative imports like `from ..foo`
    in scripts/mcp/*.py resolve to scripts/foo.py within the bundle.

    Used by both register_plugin_tools (monolith) and bundle_server.run()
    (per-bundle stdio launcher).
    """
    import hashlib
    import importlib.machinery
    import importlib.util

    safe_name = skill_dir.name.replace("-", "_")
    scripts_dir = skill_dir / "scripts"
    source_hash = hashlib.sha1(str(skill_dir.resolve()).encode("utf-8")).hexdigest()[:10]
    parent_name = f"plugin_scripts_{safe_name}_{source_hash}"
    module_name = f"{parent_name}.mcp"

    if parent_name not in sys.modules:
        scripts_init = scripts_dir / "__init__.py"
        if scripts_init.exists():
            parent_spec = importlib.util.spec_from_file_location(
                parent_name,
                scripts_init,
                submodule_search_locations=[str(scripts_dir)],
            )
            if parent_spec is not None and parent_spec.loader is not None:
                parent_mod = importlib.util.module_from_spec(parent_spec)
                sys.modules[parent_name] = parent_mod
                parent_spec.loader.exec_module(parent_mod)
        else:
            parent_spec = importlib.machinery.ModuleSpec(parent_name, None, is_package=True)
            parent_spec.submodule_search_locations = [str(scripts_dir)]
            parent_mod = importlib.util.module_from_spec(parent_spec)
            sys.modules[parent_name] = parent_mod

    mcp_init = skill_dir / "scripts" / "mcp" / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        module_name,
        mcp_init,
        submodule_search_locations=[str(mcp_init.parent)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load spec for {skill_dir.name}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
```

2. **Modify `_collect_skill_dirs`** to apply manifest exclusions:

```python
def _collect_skill_dirs(*, apply_exclusions: bool = True) -> list[tuple[str, Path]]:
    # ... existing body ...
    # At the end, before `return result`, add:
    if apply_exclusions:
        try:
            from src.cli_config.manifest import load_manifest
            manifest = load_manifest()
            excluded = set(manifest.monolith_exclusions)
            result = [(pid, sd) for (pid, sd) in result if sd.name not in excluded]
        except FileNotFoundError:
            # Manifest not yet committed (e.g., during PR 0). Skip exclusions.
            pass
    return result
```

3. **Modify `register_plugin_tools`** to use `_load_bundle_mcp_module` (replace the inline bundle-loading code with a single call):

Find the block in `register_plugin_tools()` that does `parent_name = f"plugin_scripts_..."` through `spec.loader.exec_module(module)` and replace with:

```python
        try:
            module = _load_bundle_mcp_module(skill_dir)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Could not load {plugin_id}: {exc}")
            continue
```

Verify monolith still works:

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run python -c "from src.mcp.augur_mcp.plugin_tools import _load_bundle_mcp_module, _collect_skill_dirs; print('OK', len(_collect_skill_dirs()))"
```
Expected: `OK <count>` where count is the existing skill count.

### Step 0.14: Create `tests/cli/test_manifest.py`

```python
"""Tests for src/cli_config/manifest.py."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.cli_config.manifest import Manifest, ServerEntry, _build_manifest, load_manifest


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "mcp_servers.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_loads_minimal_manifest(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "project_tier": [
                {"id": "augur", "command": "python", "args": ["-m", "augur_mcp"]},
            ],
            "vault_tier": [],
            "monolith_exclusions": [],
        },
    )
    m = load_manifest(p)
    assert isinstance(m, Manifest)
    assert m.project_tier[0].id == "augur"
    assert m.vault_tier == []
    assert m.monolith_exclusions == []


def test_validates_unique_ids(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "project_tier": [
                {"id": "augur", "command": "python", "args": []},
                {"id": "augur", "command": "python", "args": []},
            ],
        },
    )
    with pytest.raises(ValueError, match="Duplicate server id"):
        load_manifest(p)


def test_vault_entry_must_have_bundle(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "project_tier": [],
            "vault_tier": [{"id": "augur-apple", "command": "python", "args": []}],
        },
    )
    with pytest.raises(ValueError, match="missing 'bundle'"):
        load_manifest(p)


def test_vault_entry_id_must_have_augur_prefix(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "vault_tier": [
                {
                    "id": "apple",
                    "command": "python",
                    "args": [],
                    "bundle": "apple",
                    "bundle_path": "/tmp/apple",
                },
            ],
        },
    )
    with pytest.raises(ValueError, match="must start with 'augur-'"):
        load_manifest(p)


def test_exclusion_must_have_corresponding_vault_entry(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "vault_tier": [],
            "monolith_exclusions": ["apple"],
        },
    )
    with pytest.raises(ValueError, match="without vault_tier entry"):
        load_manifest(p)


def test_empty_manifest_loads(tmp_path: Path) -> None:
    p = _write(tmp_path, {})
    m = load_manifest(p)
    assert m.project_tier == m.vault_tier == []
    assert m.monolith_exclusions == []


def test_canonical_manifest_loads() -> None:
    """The committed config/system/mcp_servers.yaml must load cleanly."""
    m = load_manifest()
    assert any(e.id == "augur" for e in m.project_tier)
```

### Step 0.15: Create `tests/cli/test_config_adapters.py`

```python
"""Tests for the per-client config adapters."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import tomllib

from src.cli_config.adapters import ClaudeAdapter, CodexAdapter, GeminiAdapter
from src.cli_config.manifest import Manifest, ServerEntry


def _make_manifest(*entries: ServerEntry) -> Manifest:
    project = [e for e in entries if not e.id.startswith("augur-")]
    vault = [e for e in entries if e.id.startswith("augur-")]
    return Manifest(project_tier=project, vault_tier=vault, monolith_exclusions=[])


@pytest.fixture
def manifest_with_apple() -> Manifest:
    return _make_manifest(
        ServerEntry(
            id="augur",
            description="monolith",
            command="python",
            args=["-m", "augur_mcp"],
            cwd_required=True,
            env={"PYTHONUNBUFFERED": "1"},
        ),
        ServerEntry(
            id="augur-apple",
            description="apple per-bundle server",
            command="python",
            args=["-m", "augur_mcp.bundle_server", "apple"],
            bundle="apple",
            bundle_path="~/Projects/Au-vault/skills/apple",
        ),
    )


def test_codex_adapter_writes_toml(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    cfg = tmp_path / "config.toml"
    adapter = CodexAdapter()
    adapter.apply(manifest_with_apple, config_path=cfg)
    data = tomllib.loads(cfg.read_text())
    assert "augur" in data["mcp_servers"]
    assert "augur-apple" in data["mcp_servers"]
    assert data["mcp_servers"]["augur-apple"]["args"] == ["-m", "augur_mcp.bundle_server", "apple"]


def test_codex_adapter_preserves_non_augur_servers(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[mcp_servers.context7]\ncommand = "npx"\nargs = ["-y", "@upstash/context7-mcp"]\n'
    )
    adapter = CodexAdapter()
    adapter.apply(manifest_with_apple, config_path=cfg)
    data = tomllib.loads(cfg.read_text())
    assert "context7" in data["mcp_servers"]
    assert data["mcp_servers"]["context7"]["command"] == "npx"
    assert "augur" in data["mcp_servers"]


def test_codex_adapter_idempotent(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    cfg = tmp_path / "config.toml"
    adapter = CodexAdapter()
    adapter.apply(manifest_with_apple, config_path=cfg)
    first = cfg.read_text()
    adapter.apply(manifest_with_apple, config_path=cfg)
    second = cfg.read_text()
    assert first == second


def test_codex_adapter_diff_signals_changes(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    cfg = tmp_path / "config.toml"
    adapter = CodexAdapter()
    diff = adapter.diff(manifest_with_apple, config_path=cfg)
    assert {e.id for e in diff.added} == {"augur", "augur-apple"}
    adapter.apply(manifest_with_apple, config_path=cfg)
    diff2 = adapter.diff(manifest_with_apple, config_path=cfg)
    assert not diff2.has_changes


def test_codex_adapter_creates_backup(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text("[other]\nkey = 'value'\n")
    adapter = CodexAdapter()
    backup = adapter.apply(manifest_with_apple, config_path=cfg)
    assert backup.exists()
    assert backup.name.startswith("config.toml.bak.")


def test_codex_adapter_removes_stale_augur_entries(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[mcp_servers.augur-apple]\ncommand = "old"\nargs = []\n'
        '[mcp_servers.context7]\ncommand = "npx"\nargs = []\n'
    )
    empty = Manifest(project_tier=[], vault_tier=[], monolith_exclusions=[])
    CodexAdapter().apply(empty, config_path=cfg)
    data = tomllib.loads(cfg.read_text())
    assert "augur-apple" not in data["mcp_servers"]
    assert "context7" in data["mcp_servers"]


def test_claude_adapter_writes_json(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text("{}")
    adapter = ClaudeAdapter()
    adapter.apply(manifest_with_apple, config_path=cfg)
    data = json.loads(cfg.read_text())
    assert "augur" in data["mcpServers"]
    assert "augur-apple" in data["mcpServers"]


def test_claude_adapter_preserves_other_keys(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text(json.dumps({"theme": "dark", "mcpServers": {"context7": {"command": "npx", "args": []}}}))
    adapter = ClaudeAdapter()
    adapter.apply(manifest_with_apple, config_path=cfg)
    data = json.loads(cfg.read_text())
    assert data["theme"] == "dark"
    assert "context7" in data["mcpServers"]


def test_gemini_adapter_uses_gemini_path() -> None:
    adapter = GeminiAdapter()
    assert adapter.default_config_path() == Path.home() / ".gemini" / "settings.json"
```

### Step 0.16: Create `tests/cli/test_config_sync.py`

```python
"""End-to-end test for `aug config sync`."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.cli_config.adapters import ClaudeAdapter, CodexAdapter, GeminiAdapter
from src.cli_config.config_sync import _handle_status, _handle_sync
from src.cli_config.manifest import Manifest


@pytest.fixture
def manifest_path(tmp_path: Path) -> Path:
    p = tmp_path / "mcp_servers.yaml"
    p.write_text(
        yaml.safe_dump(
            {
                "project_tier": [
                    {"id": "augur", "command": "python", "args": ["-m", "augur_mcp"]},
                ],
                "vault_tier": [
                    {
                        "id": "augur-apple",
                        "command": "python",
                        "args": ["-m", "augur_mcp.bundle_server", "apple"],
                        "bundle": "apple",
                        "bundle_path": "/tmp/apple",
                    }
                ],
                "monolith_exclusions": ["apple"],
            }
        )
    )
    return p


def test_sync_runs_against_tmp_configs(monkeypatch, tmp_path: Path, manifest_path: Path) -> None:
    """Full orchestrator round-trip: sync writes to tmp paths for each adapter."""
    claude_cfg = tmp_path / "claude_settings.json"
    codex_cfg = tmp_path / "codex_config.toml"
    gemini_cfg = tmp_path / "gemini_settings.json"

    claude_cfg.write_text("{}")
    codex_cfg.write_text("")
    gemini_cfg.write_text("{}")

    with patch("src.cli_config.config_sync.load_manifest") as load_m, \
         patch.object(ClaudeAdapter, "default_config_path", return_value=claude_cfg), \
         patch.object(CodexAdapter, "default_config_path", return_value=codex_cfg), \
         patch.object(GeminiAdapter, "default_config_path", return_value=gemini_cfg):
        from src.cli_config.manifest import load_manifest
        load_m.return_value = load_manifest(manifest_path)

        import argparse
        args = argparse.Namespace(dry_run=False, client=None)
        rc = _handle_sync(args)
        assert rc == 0

    assert "augur-apple" in json.loads(claude_cfg.read_text())["mcpServers"]
    assert "augur-apple" in json.loads(gemini_cfg.read_text())["mcpServers"]
    assert "augur-apple" in codex_cfg.read_text()


def test_status_signals_drift(monkeypatch, tmp_path: Path, manifest_path: Path) -> None:
    claude_cfg = tmp_path / "claude_settings.json"
    codex_cfg = tmp_path / "codex_config.toml"
    gemini_cfg = tmp_path / "gemini_settings.json"
    claude_cfg.write_text("{}")
    codex_cfg.write_text("")
    gemini_cfg.write_text("{}")

    with patch("src.cli_config.config_sync.load_manifest") as load_m, \
         patch.object(ClaudeAdapter, "default_config_path", return_value=claude_cfg), \
         patch.object(CodexAdapter, "default_config_path", return_value=codex_cfg), \
         patch.object(GeminiAdapter, "default_config_path", return_value=gemini_cfg):
        from src.cli_config.manifest import load_manifest
        load_m.return_value = load_manifest(manifest_path)

        import argparse
        args = argparse.Namespace()
        rc = _handle_status(args)
        assert rc == 1  # drift exists


def test_dry_run_does_not_write(monkeypatch, tmp_path: Path, manifest_path: Path) -> None:
    claude_cfg = tmp_path / "claude_settings.json"
    codex_cfg = tmp_path / "codex_config.toml"
    gemini_cfg = tmp_path / "gemini_settings.json"
    claude_cfg.write_text("{}")
    codex_cfg.write_text("")
    gemini_cfg.write_text("{}")
    before_claude = claude_cfg.read_text()

    with patch("src.cli_config.config_sync.load_manifest") as load_m, \
         patch.object(ClaudeAdapter, "default_config_path", return_value=claude_cfg), \
         patch.object(CodexAdapter, "default_config_path", return_value=codex_cfg), \
         patch.object(GeminiAdapter, "default_config_path", return_value=gemini_cfg):
        from src.cli_config.manifest import load_manifest
        load_m.return_value = load_manifest(manifest_path)
        import argparse
        args = argparse.Namespace(dry_run=True, client=None)
        _handle_sync(args)

    assert claude_cfg.read_text() == before_claude
```

### Step 0.17: Create `tests/cli/test_bundle_server.py`

```python
"""Smoke test for the per-bundle MCP server launcher.

Verifies that `python -m augur_mcp.bundle_server <bundle>` resolves
the bundle dir, calls register_tools, and would run a stdio loop.
We don't actually run the stdio loop in tests (it'd block); we
verify FastMCP receives the correct tools via mocked register.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mcp.augur_mcp import bundle_server


def test_run_unknown_bundle_returns_1(capsys) -> None:
    rc = bundle_server.run("definitely-does-not-exist-bundle")
    assert rc == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err


def test_run_known_bundle_calls_register_tools() -> None:
    """For an existing bundle, register_tools is invoked exactly once."""
    register_calls = []

    fake_module = MagicMock()
    fake_module.register_tools = lambda mcp, interceptor, metrics: register_calls.append(
        (mcp, interceptor, metrics)
    )

    with patch("src.mcp.augur_mcp.bundle_server._load_bundle_mcp_module", return_value=fake_module), \
         patch("src.mcp.augur_mcp.bundle_server._pin_mcp_sdk_package"), \
         patch("src.mcp.augur_mcp.bundle_server._collect_skill_dirs") as collect, \
         patch("mcp.server.fastmcp.FastMCP") as fast_mcp_cls:
        # Pretend a bundle named 'apple' exists in /tmp/fake/apple with scripts/mcp/__init__.py.
        # We bypass the file-existence check by making the path look real.
        fake_dir = Path("/tmp/test-bundle-apple")
        # We need scripts/mcp/__init__.py to exist for the existence check.
        (fake_dir / "scripts" / "mcp").mkdir(parents=True, exist_ok=True)
        (fake_dir / "scripts" / "mcp" / "__init__.py").write_text("")

        try:
            collect.return_value = [("life/apple", fake_dir)]
            mcp_instance = MagicMock()
            fast_mcp_cls.return_value = mcp_instance

            rc = bundle_server.run("apple")
            assert rc == 0
            assert len(register_calls) == 1
            mcp_instance.run.assert_called_once()
        finally:
            import shutil
            shutil.rmtree(fake_dir, ignore_errors=True)
```

### Step 0.18: Run the test cascade

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run pytest tests/cli/ -v 2>&1 | tail -25
```
Expected: all new tests pass.

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run pytest tests/architecture/ tests/lib/ 2>&1 | tail -5
```
Expected: existing tests still pass.

If `tomli_w` is missing, add it as a dependency:
```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv add tomli_w 2>&1 | tail -3
```

### Step 0.19: Smoke-test the CLI

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run aug config status 2>&1 | head -20
```
Expected: per-client drift report (or "in sync" if user's actual configs already match the empty manifest). Exit code = 0 or 1, both acceptable.

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run aug config sync --dry-run 2>&1 | head -20
```
Expected: prints intended diffs without writing. (May show changes if user's existing `~/.codex/config.toml` has the monolith with different command shape than the manifest's; this is expected — would be reconciled when user runs without `--dry-run`.)

### Step 0.20: Worktree pollution check + commit

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  git status --short
```
Expected: only new files under `config/system/`, `src/cli_config/`, `src/mcp/augur_mcp/`, `tests/cli/`, plus modifications to `src/cli.py` and `src/mcp/augur_mcp/plugin_tools.py`. STOP if anything else.

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  git add config/system/mcp_servers.yaml \
          src/cli_config/ \
          src/mcp/augur_mcp/bundle_server.py \
          src/mcp/augur_mcp/plugin_tools.py \
          src/cli.py \
          tests/cli/ \
          pyproject.toml uv.lock && \
  git commit -m "$(cat <<'EOF'
feat(track2): manifest, aug config sync CLI, and per-bundle MCP launcher

PR 0 of Track 2 (vault server split). Builds the foundation that PRs
1-6 reuse. No bundles are migrated in this PR; the manifest is initialized
with the project-tier monolith and empty vault_tier / monolith_exclusions.

Adds:
- config/system/mcp_servers.yaml: source-of-truth manifest for MCP server
  topology. Layer-1 spec ID for Track 2's contract surface.
- src/cli_config/: new package implementing `aug config sync` and
  `aug config status` with adapters for Claude / Codex / Gemini
  user-tier configs. Idempotent, atomic-write, timestamped backup,
  scoped to entries with id matching `augur*`.
- src/mcp/augur_mcp/bundle_server.py: generic per-bundle stdio MCP
  launcher. Invoked as `python -m augur_mcp.bundle_server <name>`.
  Used by Track 2 PRs 2-6's vault-tier servers.

Modifies:
- src/cli.py: wires `aug config <subcommand>` into the existing CLI.
- src/mcp/augur_mcp/plugin_tools.py: extracts _load_bundle_mcp_module
  helper (used by both monolith and per-bundle launcher); extends
  _collect_skill_dirs to apply manifest exclusions.

Tests: tests/cli/{test_manifest, test_config_adapters, test_config_sync,
test_bundle_server}.py — all pass.

Architecture per Track 2 design spec:
docs/superpowers/specs/2026-04-29-track2-vault-server-split-design.md

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If pre-commit rejects, STOP and report.

---

## Task 1: PR 1 — Apple validation (no client config exposure)

**Goal:** Prove the per-bundle launcher pattern works against the real apple bundle BEFORE switching live client configs in PR 2.

**Files (modified):** none directly — the launcher and apple bundle already exist after PR 0. This PR adds an integration test that connects to a launched apple stdio server.

### Step 1.1: Create integration test

Save to `tests/cli/test_bundle_server_apple.py`:

```python
"""Integration test: launch augur_mcp.bundle_server for apple and
verify tools/list returns apple's tools.

Requires the apple bundle to exist at ~/Projects/Au-vault/skills/apple/.
Skipped on systems without the vault repo present.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


APPLE_BUNDLE = Path.home() / "Projects" / "Au-vault" / "skills" / "apple"


@pytest.mark.skipif(not APPLE_BUNDLE.exists(), reason="Au-vault apple bundle not present locally")
def test_apple_per_bundle_server_starts_and_lists_tools() -> None:
    """Launch the per-bundle server for apple, send tools/list, verify response."""
    project_root = Path(__file__).resolve().parents[2]

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{project_root}:{project_root}/src/mcp:{env.get('PYTHONPATH', '')}"
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [sys.executable, "-m", "augur_mcp.bundle_server", "apple"],
        cwd=str(project_root),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Send MCP initialize then tools/list over stdio.
        init_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "track2-test", "version": "0.0.0"}},
        }
        list_msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        assert proc.stdin is not None
        assert proc.stdout is not None
        proc.stdin.write((json.dumps(init_msg) + "\n").encode())
        proc.stdin.write((json.dumps(list_msg) + "\n").encode())
        proc.stdin.flush()

        # Drain output for a few seconds; FastMCP responds line-by-line.
        deadline = time.monotonic() + 10.0
        responses: list[dict] = []
        while time.monotonic() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            try:
                responses.append(json.loads(line.decode()))
            except json.JSONDecodeError:
                continue
            if any(r.get("id") == 2 for r in responses):
                break

        tools_response = next((r for r in responses if r.get("id") == 2), None)
        assert tools_response is not None, f"no tools/list response; got {responses!r}"
        tools = tools_response["result"]["tools"]
        assert len(tools) > 0, f"apple per-bundle server returned no tools; full response: {tools_response!r}"
        # Sanity: should include known apple tool names. Tolerant match.
        names = {t["name"] for t in tools}
        assert any("apple" in n.lower() or "note" in n.lower() or "calendar" in n.lower() for n in names), (
            f"no recognizable apple tool names in {sorted(names)}"
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
```

### Step 1.2: Run the integration test

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run pytest tests/cli/test_bundle_server_apple.py -v 2>&1 | tail -15
```
Expected: 1 passed (or 1 skipped if Au-vault apple isn't present — STOP and report if skipped, since the user's environment was confirmed to have it).

If the test fails with stderr from the subprocess, capture it and report. Common failure modes:
- ImportError in apple's `register_tools()` (missing vault-side dependency)
- FastMCP version mismatch
- Bundle path resolution issue in `_collect_skill_dirs`

### Step 1.3: Worktree pollution check + commit

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  git status --short
```
Expected: only `tests/cli/test_bundle_server_apple.py` new.

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  git add tests/cli/test_bundle_server_apple.py && \
  git commit -m "$(cat <<'EOF'
test(track2): apple per-bundle server validation

PR 1 of Track 2. Validates the per-bundle launcher pattern (added in
PR 0) against the real apple bundle at ~/Projects/Au-vault/skills/apple/.

Test launches `python -m augur_mcp.bundle_server apple` as a subprocess,
sends MCP initialize + tools/list over stdio, and asserts that the
response contains apple's tools. Skipped automatically if Au-vault
apple is not present.

No client config changes; no manifest update. PR 2 is the atomic
switch that registers augur-apple in user-tier configs and excludes
apple from the monolith's skill scan.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: PR 2 — Apple atomic switch

**Goal:** Register `augur-apple` in the manifest and add `apple` to the monolith exclusions. After this PR + the user's `aug config sync`, apple's tools are served by `augur-apple` only, not the monolith.

**Files (modify):**
- `config/system/mcp_servers.yaml` — append `augur-apple` to `vault_tier`, append `apple` to `monolith_exclusions`.

### Step 2.1: Edit `config/system/mcp_servers.yaml`

Read the current file, then update both lists. Use the Edit tool with sufficient context:

Replace:
```yaml
vault_tier: []

# Bundles excluded from the monolith's skill scan because they're served
# by per-bundle vault-tier servers. Modified by Track 2 PRs 2-6.
monolith_exclusions: []
```

with:

```yaml
vault_tier:
  - id: augur-apple
    description: Apple ecosystem (Notes / Reminders / Calendar / voice / shortcuts)
    command: python
    args: [-m, augur_mcp.bundle_server, apple]
    bundle: apple
    bundle_path: ~/Projects/Au-vault/skills/apple
    env:
      PYTHONPATH: "${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
      PYTHONUNBUFFERED: "1"

# Bundles excluded from the monolith's skill scan because they're served
# by per-bundle vault-tier servers. Modified by Track 2 PRs 2-6.
monolith_exclusions:
  - apple
```

### Step 2.2: Verify manifest still loads

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run python -c "from src.cli_config.manifest import load_manifest; m = load_manifest(); print('vault:', [e.id for e in m.vault_tier]); print('exclusions:', m.monolith_exclusions)"
```
Expected: `vault: ['augur-apple']` and `exclusions: ['apple']`.

### Step 2.3: Verify the monolith now skips apple

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run python -c "
from src.mcp.augur_mcp.plugin_tools import _collect_skill_dirs
dirs = _collect_skill_dirs()
names = [sd.name for _, sd in dirs]
assert 'apple' not in names, f'apple still in monolith scan: {names}'
print('OK monolith excludes apple')
"
```
Expected: `OK monolith excludes apple`.

### Step 2.4: Run all tests

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run pytest tests/cli/ tests/architecture/ tests/lib/ 2>&1 | tail -5
```
Expected: all pass.

### Step 2.5: Commit

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  git status --short
```
Expected: only `M config/system/mcp_servers.yaml`.

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  git add config/system/mcp_servers.yaml && \
  git commit -m "$(cat <<'EOF'
feat(track2): split apple into per-bundle vault server (augur-apple)

PR 2 of Track 2. Registers `augur-apple` in the vault_tier manifest
and adds `apple` to monolith_exclusions. After the user runs
`aug config sync` and reloads their AI clients, apple's tools are
served exclusively by the augur-apple per-bundle stdio server, no
longer by the monolith.

POST-MERGE STEPS REQUIRED BY USER:
  1. cd ~/Projects/Augur (main checkout)
  2. git pull
  3. uv run aug config sync         (writes augur-apple to all 3 client configs)
  4. Reload Claude Code, Codex, Gemini sessions
  5. Verify: tools/list against augur-apple shows apple's tools;
     monolith no longer advertises them.

The per-bundle launcher pattern was validated in PR 1 against this
exact bundle, so this is a low-risk topology change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: PR 3 — Lifestyle atomic switch

Same shape as PR 2. The lifestyle bundle already lives in Au-vault.

### Step 3.1: Edit `config/system/mcp_servers.yaml`

Append to `vault_tier`:

```yaml
  - id: augur-lifestyle
    description: Lifestyle (health / habits / routines / personal data)
    command: python
    args: [-m, augur_mcp.bundle_server, lifestyle]
    bundle: lifestyle
    bundle_path: ~/Projects/Au-vault/skills/lifestyle
    env:
      PYTHONPATH: "${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
      PYTHONUNBUFFERED: "1"
```

Append to `monolith_exclusions`:
```yaml
  - lifestyle
```

### Step 3.2: Verify

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run python -c "
from src.cli_config.manifest import load_manifest
m = load_manifest()
assert any(e.id == 'augur-lifestyle' for e in m.vault_tier), 'augur-lifestyle missing'
assert 'lifestyle' in m.monolith_exclusions, 'lifestyle not in exclusions'
print('OK')
"
```

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run pytest tests/cli/ tests/architecture/ tests/lib/ 2>&1 | tail -3
```
Expected: pass.

### Step 3.3: (Optional) integration smoke test against lifestyle

If desired, add a parallel `tests/cli/test_bundle_server_lifestyle.py` mirroring `test_bundle_server_apple.py`. Per "no shortcuts" directive, do add it for consistency.

Save (mirroring apple's test, swap `apple` → `lifestyle`):

```python
"""Integration test: launch augur_mcp.bundle_server for lifestyle."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


LIFESTYLE_BUNDLE = Path.home() / "Projects" / "Au-vault" / "skills" / "lifestyle"


@pytest.mark.skipif(not LIFESTYLE_BUNDLE.exists(), reason="Au-vault lifestyle bundle not present locally")
def test_lifestyle_per_bundle_server_starts_and_lists_tools() -> None:
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{project_root}:{project_root}/src/mcp:{env.get('PYTHONPATH', '')}"
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [sys.executable, "-m", "augur_mcp.bundle_server", "lifestyle"],
        cwd=str(project_root),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        init_msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
        list_msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write((json.dumps(init_msg) + "\n").encode())
        proc.stdin.write((json.dumps(list_msg) + "\n").encode())
        proc.stdin.flush()

        deadline = time.monotonic() + 10.0
        responses: list[dict] = []
        while time.monotonic() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            try:
                responses.append(json.loads(line.decode()))
            except json.JSONDecodeError:
                continue
            if any(r.get("id") == 2 for r in responses):
                break

        tools_response = next((r for r in responses if r.get("id") == 2), None)
        assert tools_response is not None
        assert len(tools_response["result"]["tools"]) > 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
```

Run it:

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run pytest tests/cli/test_bundle_server_lifestyle.py -v 2>&1 | tail -10
```
Expected: pass.

### Step 3.4: Commit

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  git status --short
```
Expected: `M config/system/mcp_servers.yaml` + `?? tests/cli/test_bundle_server_lifestyle.py`.

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  git add config/system/mcp_servers.yaml tests/cli/test_bundle_server_lifestyle.py && \
  git commit -m "$(cat <<'EOF'
feat(track2): split lifestyle into per-bundle vault server (augur-lifestyle)

PR 3 of Track 2. Registers `augur-lifestyle` in vault_tier and adds
`lifestyle` to monolith_exclusions. lifestyle already lives in
~/Projects/Au-vault/skills/lifestyle/ — only the topology changes.

POST-MERGE: user runs `uv run aug config sync` and reloads AI clients.

Adds tests/cli/test_bundle_server_lifestyle.py (mirror of apple's
integration test).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: PR 4 — file-manager (cross-repo: Augur → Au-vault)

**Goal:** Move `skills/file-manager/` from Augur to Au-vault. Register `augur-file-manager` per-bundle server.

**Files (Augur side):**
- Delete: `skills/file-manager/` (entire directory)
- Modify: `config/system/mcp_servers.yaml`

**Files (Au-vault side):**
- Add: `~/Projects/Au-vault/skills/file-manager/` (entire directory copied from Augur)

### Step 4.1: Verify Au-vault is clean

```bash
cd ~/Projects/Au-vault && git status --short && git log -1 --oneline
```
Expected: clean working tree on `main`. STOP and report if dirty.

### Step 4.2: Audit any Augur consumers of `file-manager`

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  grep -rn "from skills\.file_manager\|skills/file-manager\|skills\.file-manager" \
    --include="*.py" --include="*.ts" --include="*.tsx" --include="*.yaml" --include="*.json" \
    skills/ src/ apps/ tests/ scripts/ .github/ config/ 2>/dev/null \
  | grep -v "__pycache__\|node_modules\|skills/file-manager/" \
  | head -30
```
Acceptable matches: dashboard registry references that auto-regenerate, allowlist comments, doc strings. STOP and report any actual import sites that need migrating before the move.

### Step 4.3: Copy `skills/file-manager/` to Au-vault and commit there

```bash
cp -R ~/Projects/Augur/.worktrees/track2-vault-server-split/skills/file-manager \
      ~/Projects/Au-vault/skills/file-manager && \
  cd ~/Projects/Au-vault && \
  git add skills/file-manager/ && \
  git commit -m "$(cat <<'EOF'
feat(track2): receive file-manager from Augur

Track 2 PR 4 (Au-vault side). Receives skills/file-manager/ from
the Augur repo. Coordinates with the corresponding Augur-side commit
that removes skills/file-manager/ and registers augur-file-manager
in the manifest.

The bundle's contents are unchanged from the Augur snapshot at the
time of the move.
EOF
)" 2>&1 | tail -3
```

### Step 4.4: Push Au-vault commit to remote

```bash
cd ~/Projects/Au-vault && git push origin main 2>&1 | tail -5
```
STOP and report if push fails (e.g., remote ahead, credential issue).

### Step 4.5: Remove `skills/file-manager/` from Augur

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  rm -rf skills/file-manager/ && \
  ls skills/ | grep file-manager || echo "OK: file-manager gone from Augur"
```
Expected: "OK: file-manager gone from Augur".

### Step 4.6: Update manifest

Append to `vault_tier` in `config/system/mcp_servers.yaml`:

```yaml
  - id: augur-file-manager
    description: File-manager (vault file ops, image/document indexing)
    command: python
    args: [-m, augur_mcp.bundle_server, file-manager]
    bundle: file-manager
    bundle_path: ~/Projects/Au-vault/skills/file-manager
    env:
      PYTHONPATH: "${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
      PYTHONUNBUFFERED: "1"
```

Append to `monolith_exclusions`:
```yaml
  - file-manager
```

### Step 4.7: Run tests

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run pytest tests/cli/ tests/architecture/ tests/lib/ 2>&1 | tail -5
```
Expected: pass.

If tests fail because file-manager's Augur-side test files were deleted but were previously running independently of skills/, those test failures need investigation. Some file-manager tests may live in `skills/file-manager/augur/tests/` and were just deleted with the directory — that's expected. Other Augur tests in `tests/` that imported from `skills.file_manager` would fail; if any do, migrate them to consume the bundle's new location or delete them if they were testing internal behavior that's now Au-vault's concern.

### Step 4.8: Add file-manager integration smoke test

Save `tests/cli/test_bundle_server_file_manager.py` (mirror of apple's, swap names):

```python
"""Integration test: launch augur_mcp.bundle_server for file-manager."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


FILE_MANAGER_BUNDLE = Path.home() / "Projects" / "Au-vault" / "skills" / "file-manager"


@pytest.mark.skipif(not FILE_MANAGER_BUNDLE.exists(), reason="Au-vault file-manager bundle not present")
def test_file_manager_per_bundle_server_starts_and_lists_tools() -> None:
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{project_root}:{project_root}/src/mcp:{env.get('PYTHONPATH', '')}"
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [sys.executable, "-m", "augur_mcp.bundle_server", "file-manager"],
        cwd=str(project_root),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        init_msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
        list_msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write((json.dumps(init_msg) + "\n").encode())
        proc.stdin.write((json.dumps(list_msg) + "\n").encode())
        proc.stdin.flush()
        deadline = time.monotonic() + 10.0
        responses: list[dict] = []
        while time.monotonic() < deadline:
            line = proc.stdout.readline()
            if not line:
                break
            try:
                responses.append(json.loads(line.decode()))
            except json.JSONDecodeError:
                continue
            if any(r.get("id") == 2 for r in responses):
                break
        tools_response = next((r for r in responses if r.get("id") == 2), None)
        assert tools_response is not None
        assert len(tools_response["result"]["tools"]) > 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
```

Run:
```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run pytest tests/cli/test_bundle_server_file_manager.py -v 2>&1 | tail -10
```
Expected: pass.

### Step 4.9: Commit Augur side

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  git status --short | head -20
```
Expected: many `D skills/file-manager/...` lines + `M config/system/mcp_servers.yaml` + `?? tests/cli/test_bundle_server_file_manager.py`.

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  git add -A skills/file-manager/ config/system/mcp_servers.yaml tests/cli/test_bundle_server_file_manager.py && \
  git commit -m "$(cat <<'EOF'
feat(track2): move file-manager bundle from Augur to Au-vault

PR 4 of Track 2. Cross-repo move:
- Augur: removes skills/file-manager/ entirely
- Au-vault: receives skills/file-manager/ (separate commit, pushed first)
- Manifest: adds augur-file-manager to vault_tier; appends file-manager
  to monolith_exclusions
- Tests: tests/cli/test_bundle_server_file_manager.py integration smoke

POST-MERGE: user runs `uv run aug config sync` and reloads AI clients.

After this PR, file-manager's tools are served exclusively by the
augur-file-manager per-bundle stdio server.

Au-vault commit: see ~/Projects/Au-vault on `main`.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: PR 5 — obsidian (cross-repo: Augur → Au-vault)

Same shape as PR 4. Substitute `obsidian` for `file-manager`.

### Steps 5.1-5.9 (mirror of 4.1-4.9)

Repeat the entire PR 4 sequence with these substitutions:
- `file-manager` → `obsidian`
- `augur-file-manager` → `augur-obsidian`
- Manifest description: "Obsidian vault integration (notes / metadata / search)"
- Test file: `tests/cli/test_bundle_server_obsidian.py`

Specific commands:

```bash
# Step 5.1: Verify Au-vault clean
cd ~/Projects/Au-vault && git status --short && git log -1 --oneline
```

```bash
# Step 5.2: Audit consumers
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  grep -rn "from skills\.obsidian\|skills/obsidian\|skills\.obsidian" \
    --include="*.py" --include="*.ts" --include="*.tsx" --include="*.yaml" --include="*.json" \
    skills/ src/ apps/ tests/ scripts/ .github/ config/ 2>/dev/null \
  | grep -v "__pycache__\|node_modules\|skills/obsidian/" \
  | head -30
```
STOP if real imports outside the bundle exist.

```bash
# Step 5.3-5.4: Copy + commit + push Au-vault
cp -R ~/Projects/Augur/.worktrees/track2-vault-server-split/skills/obsidian \
      ~/Projects/Au-vault/skills/obsidian && \
  cd ~/Projects/Au-vault && \
  git add skills/obsidian/ && \
  git commit -m "feat(track2): receive obsidian from Augur" && \
  git push origin main 2>&1 | tail -5
```

```bash
# Step 5.5: Remove from Augur
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  rm -rf skills/obsidian/
```

Step 5.6: Append to manifest:

```yaml
  - id: augur-obsidian
    description: Obsidian vault integration (notes / metadata / search)
    command: python
    args: [-m, augur_mcp.bundle_server, obsidian]
    bundle: obsidian
    bundle_path: ~/Projects/Au-vault/skills/obsidian
    env:
      PYTHONPATH: "${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
      PYTHONUNBUFFERED: "1"
```

```yaml
  - obsidian  # under monolith_exclusions
```

Steps 5.7-5.8: Tests + integration test (file: `tests/cli/test_bundle_server_obsidian.py`, mirror of file-manager's).

Step 5.9: Commit:

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  git add -A skills/obsidian/ config/system/mcp_servers.yaml tests/cli/test_bundle_server_obsidian.py && \
  git commit -m "$(cat <<'EOF'
feat(track2): move obsidian bundle from Augur to Au-vault

PR 5 of Track 2. Cross-repo move (same pattern as PR 4 file-manager):
- Augur: removes skills/obsidian/ entirely
- Au-vault: receives skills/obsidian/ (pushed first)
- Manifest: adds augur-obsidian to vault_tier
- Tests: tests/cli/test_bundle_server_obsidian.py

POST-MERGE: `uv run aug config sync` then reload AI clients.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: PR 6 — ingest (cross-repo, most-coupled bundle)

Same shape as PRs 4-5 with `ingest`. Per Layer 4 spec, this is the most-coupled migration; coupling has been progressively reduced by Track 1's library extractions. Verify thoroughly before moving.

### Step 6.1: Verify Au-vault clean

```bash
cd ~/Projects/Au-vault && git status --short && git log -1 --oneline
```

### Step 6.2: Deep audit — ingest's residual cross-skill coupling

ingest still imports `skills.ai.scripts.sync_agents.skill_sync` per the architecture-test allowlist (`("ingest", "ai")`). After moving ingest to Au-vault, those imports will become **vault → project** imports, which is acceptable but should be documented.

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  grep -rn "from skills\.ingest\|skills/ingest\|skills\.ingest" \
    --include="*.py" --include="*.ts" --include="*.tsx" --include="*.yaml" --include="*.json" \
    src/ apps/ tests/ scripts/ .github/ config/ 2>/dev/null \
  | grep -v "__pycache__\|node_modules\|skills/ingest/" \
  | head -40
```

Acceptable: tests in `tests/architecture/` referencing `("ingest", "ai")` allowlist (will keep allowlist entry; just retarget it from `("ingest", "ai")` to a new `("ingest-vault", "ai")` IF the architecture test now distinguishes vault from project skills — which it doesn't yet, so leave the allowlist entry as-is and update the comment to reflect Track 2 has shipped).

STOP and report if there are real production-code imports of `skills.ingest.X` from outside `skills/ingest/`. Those need migrating before this PR can land.

### Step 6.3: Copy + commit + push Au-vault

```bash
cp -R ~/Projects/Augur/.worktrees/track2-vault-server-split/skills/ingest \
      ~/Projects/Au-vault/skills/ingest && \
  cd ~/Projects/Au-vault && \
  git add skills/ingest/ && \
  git commit -m "feat(track2): receive ingest from Augur" && \
  git push origin main 2>&1 | tail -5
```

### Step 6.4: Remove from Augur

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  rm -rf skills/ingest/
```

### Step 6.5: Update manifest

Append:

```yaml
  - id: augur-ingest
    description: Inbox / wiki / URL capture / source cards
    command: python
    args: [-m, augur_mcp.bundle_server, ingest]
    bundle: ingest
    bundle_path: ~/Projects/Au-vault/skills/ingest
    env:
      PYTHONPATH: "${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
      PYTHONUNBUFFERED: "1"
```

```yaml
  - ingest  # under monolith_exclusions
```

### Step 6.6: Update architecture-test allowlist comment

Edit `tests/architecture/test_no_cross_skill_imports.py`. Find the `("ingest", "ai")` and `("ingest", "rag")` entries. Update the comment to reflect Track 2 has shipped:

```python
# Vault-tier ingest still imports project-tier ai's sync_agents.
# This is a vault→project edge that retires when sync_agents itself
# is split (Track 3a or follow-up).
("ingest", "ai"),
# Vault-tier ingest still imports project-tier rag's mcp wrappers.
# Retires in Track 3a when rag's bundle MCP merges into augur-framework.
("ingest", "rag"),
```

### Step 6.7: Run full test cascade

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run pytest tests/cli/ tests/architecture/ tests/lib/ 2>&1 | tail -5
```
Expected: pass.

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run pytest skills/ 2>&1 | tail -5
```
Expected: existing skill test suites pass (with ingest's tests deleted along with the bundle).

### Step 6.8: Add ingest integration smoke test

Save `tests/cli/test_bundle_server_ingest.py` (mirror of obsidian's).

Run:
```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  uv run pytest tests/cli/test_bundle_server_ingest.py -v 2>&1 | tail -10
```
Expected: pass.

### Step 6.9: Build the dashboard

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  pnpm --filter dashboard build 2>&1 | tail -10
```
Expected: build succeeds. If dashboard regenerated artifacts (`assembled-hubs.json`, `generated-registry.ts`) — restore with `git checkout HEAD --` if not staged for this PR.

### Step 6.10: Commit Augur side

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  git status --short | head -20
```
Expected: many `D skills/ingest/...` + `M config/system/mcp_servers.yaml` + `M tests/architecture/test_no_cross_skill_imports.py` + `?? tests/cli/test_bundle_server_ingest.py`.

```bash
cd ~/Projects/Augur/.worktrees/track2-vault-server-split && \
  git add -A skills/ingest/ config/system/mcp_servers.yaml \
          tests/architecture/test_no_cross_skill_imports.py \
          tests/cli/test_bundle_server_ingest.py && \
  git commit -m "$(cat <<'EOF'
feat(track2): move ingest bundle from Augur to Au-vault — Track 2 complete

PR 6 of Track 2 (final). Cross-repo move:
- Augur: removes skills/ingest/ entirely
- Au-vault: receives skills/ingest/ (pushed first)
- Manifest: adds augur-ingest; appends ingest to monolith_exclusions
- Architecture allowlist: retains ("ingest", "ai") and ("ingest", "rag")
  with updated comments noting they're now vault→project edges that
  retire in Track 3a.
- Tests: tests/cli/test_bundle_server_ingest.py

POST-MERGE: `uv run aug config sync` then reload AI clients.

Track 2 (vault server split) is complete:
  - augur-apple        (PR 2)
  - augur-lifestyle    (PR 3)
  - augur-file-manager (PR 4, cross-repo)
  - augur-obsidian     (PR 5, cross-repo)
  - augur-ingest       (PR 6, cross-repo)

Plus PR 0 infrastructure (manifest, aug config sync, bundle launcher)
and PR 1 apple validation.

Next per Layer 4 spec: Track 3a (project-tier server split into
augur-core + augur-framework) — depends on Track 1's library extraction
(complete) and Track 2's per-bundle pattern (this PR).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Done criteria

Track 2 is complete when:

1. ✅ `config/system/mcp_servers.yaml` exists with all 5 vault bundles registered in `vault_tier` and all 5 listed in `monolith_exclusions`.
2. ✅ `aug config sync` correctly populates `~/.claude/settings.json`, `~/.codex/config.toml`, `~/.gemini/settings.json` with per-bundle entries (verified via tests against tmp paths).
3. ✅ `python -m augur_mcp.bundle_server <bundle>` starts a stdio server for each of the 5 bundles and exposes their tools (verified per-bundle integration tests).
4. ✅ The `augur` monolith's `_collect_skill_dirs()` skips all 5 bundles (verified via test).
5. ✅ `skills/file-manager/`, `skills/obsidian/`, `skills/ingest/` are no longer in the Augur repo. `apple/` and `lifestyle/` continue to live in Au-vault unchanged.
6. ✅ Au-vault has `skills/{file-manager,obsidian,ingest}/` directories with the bundle contents.
7. ✅ All Track 2 PRs merged to `main`. All `tests/cli/` and `tests/architecture/` and `tests/lib/` pass.
8. ✅ Dashboard builds successfully.
9. ✅ ADR `track2-vault-server-split.md` written to `get_adr_dir()` after PR 6.

## After Track 2

The next track per Layer 4 spec ordering is **Track 3a — framework split + src/ vault-private hardcode removal**:
- Splits the `augur` monolith into `augur-core` + `augur-framework`.
- Migrates remaining project-tier bundle tools (daemon, rag, knowledge, platform-admin, etc.) into `augur-framework`.
- Removes the 10 known src/ vault-private hardcodes.
- Retires the remaining architecture-test allowlist entries.

Track 3b (dashboard hub-routing redesign) and Track 4 (visibility filter removal) follow.
