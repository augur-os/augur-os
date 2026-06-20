"""Historical root-move redirect map for repairing dangling client paths.

When an Augur-managed root moves (documents, vault, runtime, …), external
client-owned MCP configs keep pointing at the pre-migration path and that
client's MCP server silently crash-loops. This module loads the recorded moves
from ``config/system/path_migrations.yaml`` and resolves a *missing* path to its
unambiguous successor — but only when the rewritten path actually exists on
disk, so a repair is never applied speculatively.

See ``src/lib/mcp_client_config_audit.py`` for the consumer.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import yaml

from src.config.paths import get_project_root

_CONFIG_REL = Path("config/system/path_migrations.yaml")
_SNAPSHOT_NAME = "path_roots_snapshot.json"


def _expand(value: str) -> str:
    """Expand ``~`` and env vars to an absolute path string (no symlink resolve)."""
    return os.path.abspath(os.path.expanduser(os.path.expandvars(str(value))))


def load_migrations(config_path: Path | None = None) -> list[dict[str, str]]:
    """Load recorded root moves as ``[{old, new, date, note}]`` with expanded paths.

    ``old`` and ``new`` are normalized to absolute path strings. Malformed or
    missing entries are skipped rather than raising — a bad map must not break
    the health audit.
    """
    path = config_path or (get_project_root() / _CONFIG_REL)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []

    migrations: list[dict[str, str]] = []
    for entry in raw.get("migrations", []) or []:
        if not isinstance(entry, dict):
            continue
        old = entry.get("old")
        new = entry.get("new")
        if not old or not new:
            continue
        migrations.append(
            {
                "old": _expand(old),
                "new": _expand(new),
                "date": str(entry.get("date", "")),
                "note": str(entry.get("note", "")),
            }
        )
    return migrations


def _apply_one(path_abs: str, migration: dict[str, str]) -> str | None:
    """Rewrite ``path_abs`` under a single migration, or ``None`` if it doesn't apply."""
    old, new = migration["old"], migration["new"]
    if path_abs == old:
        return new
    prefix = old.rstrip(os.sep) + os.sep
    if path_abs.startswith(prefix):
        remainder = path_abs[len(prefix) :]
        return os.path.join(new, remainder)
    return None


def resolve_successor(
    missing_path: str | Path,
    migrations: list[dict[str, str]] | None = None,
    *,
    max_hops: int = 5,
) -> Path | None:
    """Return the unambiguous existing successor for a missing path, else ``None``.

    A successor is returned only when:
      * the input does not already exist (nothing to repair), and
      * exactly one chain of recorded migrations rewrites it to a path that
        exists on disk (ambiguous matches are rejected for safety).
    """
    migrations = load_migrations() if migrations is None else migrations
    start = _expand(missing_path)

    if Path(start).exists():
        return None

    # Walk migration chains (a path may move more than once). Collect distinct
    # existing endpoints; refuse to repair if more than one is reachable.
    found: set[str] = set()
    frontier = [start]
    seen = {start}
    hops = 0
    while frontier and hops < max_hops:
        hops += 1
        nxt: list[str] = []
        for cur in frontier:
            for mig in migrations:
                rewritten = _apply_one(cur, mig)
                if rewritten is None or rewritten in seen:
                    continue
                seen.add(rewritten)
                if Path(rewritten).exists():
                    found.add(rewritten)
                else:
                    nxt.append(rewritten)
        frontier = nxt

    if len(found) == 1:
        return Path(next(iter(found)))
    return None


# ── auto-recording: snapshot canonical roots and record moves ──────────────────


def current_roots() -> dict[str, str]:
    """Return the canonical Augur-managed roots a client config might point at.

    Each resolver is best-effort: an unconfigured/raising root is omitted rather
    than aborting reconciliation.
    """
    from src.config import paths as _paths

    resolvers = {
        "documents": _paths.get_documents_dir,
        "vault": _paths.get_vault_dir,
        "private_vault": _paths.get_private_vault_dir,
    }
    roots: dict[str, str] = {}
    for name, resolver in resolvers.items():
        try:
            roots[name] = _expand(str(resolver()))
        except Exception:  # noqa: BLE001 — a single bad root must not break reconcile
            continue
    return roots


def _snapshot_path(snapshot_path: Path | None = None) -> Path:
    if snapshot_path is not None:
        return snapshot_path
    from src.config.paths import get_runtime_dir

    return get_runtime_dir() / _SNAPSHOT_NAME


def _load_snapshot(snapshot_path: Path | None = None) -> dict[str, str]:
    try:
        return json.loads(_snapshot_path(snapshot_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_snapshot(roots: dict[str, str], snapshot_path: Path | None = None) -> None:
    path = _snapshot_path(snapshot_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(roots, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        pass


def append_migration(
    old: str,
    new: str,
    *,
    note: str,
    today: str | None = None,
    config_path: Path | None = None,
) -> bool:
    """Append a ``{old,new,date,note}`` entry to the redirect map (text-append).

    Returns False (no write) if an entry with the same expanded old→new already
    exists. Text-append preserves the file's leading comments; a list item at EOF
    is valid YAML because ``migrations:`` is the file's only top-level key.
    """
    path = config_path or (get_project_root() / _CONFIG_REL)
    old_abs, new_abs = _expand(old), _expand(new)

    for existing in load_migrations(path):
        if existing["old"] == old_abs and existing["new"] == new_abs:
            return False

    today = today or date.today().isoformat()
    block = (
        f"  - old: {json.dumps(old)}\n"
        f"    new: {json.dumps(new)}\n"
        f"    date: {json.dumps(today)}\n"
        f"    note: {json.dumps(note)}\n"
    )
    try:
        text = path.read_text(encoding="utf-8") if path.exists() else "migrations:\n"
        if not text.endswith("\n"):
            text += "\n"
        path.write_text(text + block, encoding="utf-8")
    except OSError:
        return False
    return True


def reconcile_migrations(
    *,
    config_path: Path | None = None,
    snapshot_path: Path | None = None,
    today: str | None = None,
) -> list[dict[str, str]]:
    """Detect canonical roots that moved since last run and auto-record them.

    Compares the current resolved roots against a persisted snapshot. A root
    whose configured value changed is recorded in the redirect map (so the
    client-config audit can self-heal external references), then the snapshot is
    refreshed. The first run only seeds the snapshot — no migrations are invented
    from a cold start.
    """
    snapshot = _load_snapshot(snapshot_path)
    current = current_roots()

    recorded: list[dict[str, str]] = []
    for name, cur in current.items():
        prev = snapshot.get(name)
        if prev and prev != cur:
            note = f"Auto-recorded: {name} root moved {prev} -> {cur}."
            if append_migration(prev, cur, note=note, today=today, config_path=config_path):
                recorded.append({"root": name, "old": prev, "new": cur})

    _write_snapshot(current, snapshot_path)
    return recorded
