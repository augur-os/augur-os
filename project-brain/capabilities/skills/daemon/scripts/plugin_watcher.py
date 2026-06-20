#!/usr/bin/env python3
"""
Plugin Filesystem Watcher (ADR-122).

Polls canonical managed skills every 10 seconds, detects skill additions and
removals, and emits structured events to state/plugin_events.json.

Snapshot: state/plugin_watcher_snapshot.json
  {
    "skills":   { "{scope}/{skill}": mtime_float, ... },
    "bundles":  {}
  }

  Legacy format (flat dict of "scope/skill" keys) is auto-migrated on load.

Events: state/plugin_events.json
  List of up to 100 event dicts (FIFO), append-only.
  Each event: { type, bundle, skill?, timestamp, acknowledged }

Event types:
  skill_added      — new managed skill detected
  skill_removed    — managed skill no longer present

ADR-802 retired hub-level bundle events. The "bundles" snapshot key is kept only
so older snapshot files migrate without losing the stable JSON shape.

Usage:
    python3 plugin_watcher.py          # Run once
    python3 plugin_watcher.py --loop   # Continuous (used by unified daemon)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# ─── project root & sys.path ──────────────────────────────────────────────────
try:
    from bootstrap_paths import ensure_project_paths
except ImportError:
    _SCRIPTS_DIR = Path(__file__).resolve().parent
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    from bootstrap_paths import ensure_project_paths

PROJECT_ROOT = ensure_project_paths(__file__)

try:
    from src.config.paths import get_project_root, get_runtime_dir, get_project_brain_skills_dir
    from src.plugins.skill_discovery import discover_all_skills, invalidate_discovery_cache
    from src.logging import get_entity_logger
except ImportError:
    import importlib

    def get_project_root() -> Path:  # type: ignore[misc]
        return PROJECT_ROOT

    def get_runtime_dir() -> Path:  # type: ignore[misc]
        runtime_dir = os.environ.get("AUGUR_STATE") or os.environ.get("AUGUR_RUNTIME")
        if runtime_dir:
            return Path(runtime_dir)
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "Augur" / "state"
        return Path.home() / ".local" / "state" / "augur"

    def get_project_brain_skills_dir(project_root: Path | None = None) -> Path:  # type: ignore[misc]
        return (project_root or get_project_root()) / "project-brain" / "capabilities" / "skills"

    def get_entity_logger(name: str):  # type: ignore[misc]
        logging = importlib.import_module("logging")
        _log = logging.getLogger(name)
        if not _log.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s - %(message)s"))
            _log.addHandler(handler)
            _log.setLevel(logging.INFO)
        return _log

    def discover_all_skills(*, tiers=None):  # type: ignore[misc]
        return []

    def invalidate_discovery_cache() -> None:  # type: ignore[misc]
        return None


logger = get_entity_logger("plugin_watcher")

# ─── paths ─────────────────────────────────────────────────────────────────────

POLL_INTERVAL = 30   # seconds — skill add/remove detection does not need to be
# tighter than this, and each poll re-discovers skills (cache invalidation +
# filesystem walk), so a short interval kept the daemon busy at ~10% of a core.
MAX_EVENTS = 100     # FIFO cap

RUNTIME_DIR = get_runtime_dir()
SKILLS_DIR = get_project_brain_skills_dir(PROJECT_ROOT)

SNAPSHOT_FILE = RUNTIME_DIR / "plugin_watcher_snapshot.json"
EVENTS_FILE = RUNTIME_DIR / "plugin_events.json"
TODOS_DIR = RUNTIME_DIR / "todos"

# ═══════════════════════════════════════════════════════════════════════════════
# SNAPSHOT  —  { "skills": {"bundle/skill": mtime}, "bundles": {"bundle": mtime} }
# ═══════════════════════════════════════════════════════════════════════════════


def _load_snapshot() -> tuple[dict[str, float], dict[str, float]]:
    """
    Load snapshot from disk.

    Returns (skill_snapshot, bundle_snapshot).
    Handles legacy format (flat dict of "bundle/skill" keys) transparently.
    """
    if not SNAPSHOT_FILE.exists():
        return {}, {}
    try:
        data = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            # New format: { "skills": {...}, "bundles": {...} }
            if "skills" in data or "bundles" in data:
                skills = {str(k): float(v) for k, v in data.get("skills", {}).items()}
                bundles = {str(k): float(v) for k, v in data.get("bundles", {}).items()}
                return skills, bundles
            # Legacy format: flat { "bundle/skill": mtime }
            # Migrate: reconstruct bundle snapshot from skill keys
            skills = {str(k): float(v) for k, v in data.items() if "/" in str(k)}
            bundles: dict[str, float] = {}
            return skills, bundles
    except Exception as exc:
        logger.warning("Failed to read snapshot, starting fresh: %s", exc)
    return {}, {}


def _save_snapshot(skills: dict[str, float], bundles: dict[str, float]) -> None:
    """Atomically write snapshot to disk."""
    SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SNAPSHOT_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"skills": skills, "bundles": bundles}, indent=2),
        encoding="utf-8",
    )
    tmp.replace(SNAPSHOT_FILE)


# ═══════════════════════════════════════════════════════════════════════════════
# FILESYSTEM SCAN
# ═══════════════════════════════════════════════════════════════════════════════


def _is_stale_repo_root_skill_dir(skill_dir: Path) -> bool:
    """Return True for the retired repo-root skills/{name} layout."""
    try:
        rel = Path(skill_dir).resolve().relative_to(Path(PROJECT_ROOT).resolve())
    except ValueError:
        return False
    return len(rel.parts) >= 2 and rel.parts[0] == "skills"


def _discover_project_skills() -> list[tuple[str, str, Path]]:
    """Return canonical (scope, skill, path) tuples from managed skill discovery."""
    invalidate_discovery_cache()
    discovered: list[tuple[str, str, Path]] = []
    for record in discover_all_skills(tiers=(0,)):
        scope = _record_event_scope(record)
        name = str(getattr(record, "name", "") or "").strip()
        path = Path(getattr(record, "path"))
        if not scope or not name or not path.exists():
            continue
        if _is_stale_repo_root_skill_dir(path):
            continue
        discovered.append((scope, name, path))
    return sorted(discovered, key=lambda item: (item[0], item[1]))


def _record_event_scope(record: object) -> str:
    hub = str(getattr(record, "hub", "") or "").strip()
    if hub:
        return hub
    source_root = str(getattr(record, "source_root", "") or "").strip()
    if source_root:
        return source_root
    origin = str(getattr(record, "origin", "") or "").strip()
    return origin or "skills"


def _resolve_skill_dir(bundle: str, skill: str) -> Path | None:
    """Resolve a skill directory by its current scope and name."""
    for scope, name, path in _discover_project_skills():
        if scope == bundle and name == skill:
            return path
    return None


def _scan_skills(
    discovered: list[tuple[str, str, Path]] | None = None,
) -> dict[str, float]:
    """
    Return { "bundle/skill": mtime } for every canonical managed skill.

    Accepts a pre-computed discovery list so a poll cycle can discover once and
    reuse it for both the skill and bundle snapshots (skill discovery
    invalidates a cache + re-walks the filesystem, so calling it twice per poll
    doubled the watcher's CPU).
    """
    if discovered is None:
        discovered = _discover_project_skills()
    result: dict[str, float] = {}
    for bundle, skill, skill_dir in discovered:
        key = f"{bundle}/{skill}"
        try:
            result[key] = skill_dir.stat().st_mtime
        except OSError:
            pass  # Disappeared mid-scan

    return result


def _scan_bundles(
    discovered: list[tuple[str, str, Path]] | None = None,
) -> dict[str, float]:
    """
    Bundle-level notifications were retired with the hub model (ADR-802).
    """
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# EVENTS
# ═══════════════════════════════════════════════════════════════════════════════


def _load_events() -> list[dict]:
    """Load events list from disk; return empty list if missing or corrupt."""
    if not EVENTS_FILE.exists():
        return []
    try:
        data = json.loads(EVENTS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception as exc:
        logger.warning("Failed to read events file, starting fresh: %s", exc)
    return []


def _save_events(events: list[dict]) -> None:
    """Atomically write events list to disk, capping at MAX_EVENTS (FIFO)."""
    if len(events) > MAX_EVENTS:
        events = events[-MAX_EVENTS:]  # keep most recent
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = EVENTS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(events, indent=2), encoding="utf-8")
    tmp.replace(EVENTS_FILE)


def _make_event(event_type: str, bundle: str, skill: str | None = None) -> dict:
    """Build a single event dict."""
    ev: dict = {
        "type": event_type,
        "bundle": bundle,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "acknowledged": False,
    }
    if skill is not None:
        ev["skill"] = skill
    return ev


def _emit_events(new_events: list[dict]) -> None:
    """Append new events to the events file (FIFO, max 100)."""
    if not new_events:
        return
    existing = _load_events()
    combined = existing + new_events
    _save_events(combined)


# ═══════════════════════════════════════════════════════════════════════════════
# TODO MARKERS
# ═══════════════════════════════════════════════════════════════════════════════


def _mark_skill_new(bundle: str, skill: str) -> None:
    """Mark a newly detected skill as new-to-dashboard in runtime UI state."""
    skill_dir = _resolve_skill_dir(bundle, skill)
    if skill_dir is None or not skill_dir.exists():
        return
    try:
        from src.plugins.skill_ui_state import mark_skill_new_to_dashboard

        mark_skill_new_to_dashboard(skill, hub=bundle)
        logger.debug("Marked skill as new in runtime dashboard state: %s/%s", bundle, skill)
    except Exception as exc:
        logger.warning("Could not mark runtime dashboard state for %s/%s: %s", bundle, skill, exc)


def _create_todo_skill_removed(bundle: str, skill: str) -> None:
    """Create TODO_SKILL_REMOVED file in state/todos/."""
    TODOS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    todo_path = TODOS_DIR / f"TODO_SKILL_REMOVED_{bundle}_{skill}"
    content = f"""\
# Skill removed: {bundle}/{skill}
# Detected: {timestamp}
#
# Actions required:
# 1. Run mount-plugins --clean to remove stale routes and nav entries
# 2. Check if any other skills declare this as a required dependency
# 3. Delete this file once cleanup is confirmed
#
# To restore: recover the source skill at project-brain/capabilities/skills/{skill} and keep x-augur-hub: {bundle}
"""
    try:
        todo_path.write_text(content, encoding="utf-8")
        logger.debug("Created TODO_SKILL_REMOVED: %s", todo_path)
    except OSError as exc:
        logger.warning("Could not write TODO_SKILL_REMOVED for %s/%s: %s", bundle, skill, exc)


# ═══════════════════════════════════════════════════════════════════════════════
# DEPENDENCY IMPACT CHECKER
# ═══════════════════════════════════════════════════════════════════════════════


def _read_dashboard_yaml(skill_dir: Path) -> dict:
    """
    Read and parse a skill's dashboard.yaml.  Returns empty dict on any error.
    Uses stdlib only — no PyYAML dependency required.
    """
    yaml_path = skill_dir / "dashboard.yaml"
    if not yaml_path.exists():
        return {}
    try:
        # Use PyYAML if available; fall back to a minimal key-list extractor
        try:
            import yaml  # type: ignore[import]
            return yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        except ImportError:
            pass

        # Minimal fallback: extract `required:` and `optional:` list values
        # This handles the common dashboard.yaml format without a YAML parser.
        text = yaml_path.read_text(encoding="utf-8")
        result: dict = {"dependencies": {}}
        in_deps = False
        in_required = False
        in_optional = False
        req: list[str] = []
        opt: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == "dependencies:":
                in_deps = True
                continue
            if in_deps:
                if stripped == "required:":
                    in_required, in_optional = True, False
                    continue
                if stripped == "optional:":
                    in_optional, in_required = True, False
                    continue
                if stripped.startswith("- ") and in_required:
                    req.append(stripped[2:].strip())
                    continue
                if stripped.startswith("- ") and in_optional:
                    opt.append(stripped[2:].strip())
                    continue
                # Any non-list line at top indent level ends the deps block
                if line and not line[0].isspace() and stripped:
                    in_deps = False
        result["dependencies"] = {"required": req, "optional": opt}
        return result
    except Exception as exc:
        logger.debug("Could not read dashboard.yaml at %s: %s", yaml_path, exc)
        return {}


def _check_dependency_impact(removed_skill: str) -> None:
    """
    Scan all remaining skills' dashboard.yaml for dependencies on `removed_skill`.

    - required dependency broken → create TODO_BROKEN_DEP in the dependent skill folder
    - optional dependency broken → log only (graceful degradation per ADR-112)

    `removed_skill` is a bare skill name (e.g. "channels"), not a "bundle/skill" key.
    """
    for bundle, skill, skill_dir in _discover_project_skills():
            config = _read_dashboard_yaml(skill_dir)
            deps = config.get("dependencies", {}) or {}
            required = deps.get("required") or []
            optional = deps.get("optional") or []

            if removed_skill in required:
                logger.warning(
                    "Broken required dependency: %s/%s depends on removed skill '%s'",
                    bundle, skill, removed_skill,
                )
                _create_todo_broken_dep(bundle, skill, removed_skill)

            elif removed_skill in optional:
                logger.info(
                    "Optional dependency %s in %s/%s is now missing — graceful degradation expected",
                    removed_skill, bundle, skill,
                )


def _create_todo_broken_dep(bundle: str, skill: str, missing_dep: str) -> None:
    """Create TODO_BROKEN_DEP marker in the affected skill's folder."""
    skill_dir = _resolve_skill_dir(bundle, skill)
    if skill_dir is None or not skill_dir.exists():
        return
    todo_path = skill_dir / f"TODO_BROKEN_DEP_{missing_dep}"
    if todo_path.exists():
        return  # idempotent
    timestamp = datetime.now(timezone.utc).isoformat()
    content = f"""\
# Broken required dependency detected
# Skill: {bundle}/{skill}
# Missing: {missing_dep}
# Detected: {timestamp}
#
# The skill '{missing_dep}' was removed but is declared as a required
# dependency of this skill in dashboard.yaml.
#
# Options:
# 1. Restore the missing skill under project-brain/capabilities/skills/{missing_dep}
# 2. Remove the dependency from dashboard.yaml if it is no longer needed
# 3. Replace with an alternative skill that provides the same functionality
#
# Until resolved, some features of {bundle}/{skill} may not work correctly.
"""
    try:
        todo_path.write_text(content, encoding="utf-8")
        logger.info("Created TODO_BROKEN_DEP in %s/%s for missing dep '%s'", bundle, skill, missing_dep)
    except OSError as exc:
        logger.warning("Could not write TODO_BROKEN_DEP for %s/%s: %s", bundle, skill, exc)


# ═══════════════════════════════════════════════════════════════════════════════
# DIFF HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def _diff(
    old: dict[str, float],
    new: dict[str, float],
) -> tuple[list[str], list[str]]:
    """Return (added_keys, removed_keys) comparing two snapshots."""
    old_keys = set(old)
    new_keys = set(new)
    return sorted(new_keys - old_keys), sorted(old_keys - new_keys)


def _poll_once(
    skill_snap: dict[str, float],
    bundle_snap: dict[str, float],
) -> tuple[dict[str, float], dict[str, float]]:
    """
    Run one poll cycle.

    Takes current snapshots as input, returns updated (skill_snap, bundle_snap).
    Side effects: emits events and creates TODO markers.
    """
    # Discover once per poll and reuse for both snapshots — discovery invalidates
    # a cache and re-walks the skill tree, so calling it per-snapshot doubled CPU.
    discovered = _discover_project_skills()
    current_skills = _scan_skills(discovered)
    current_bundles = _scan_bundles(discovered)

    new_events: list[dict] = []

    # ── skill-level diff ──────────────────────────────────────────────────────
    added_skills, removed_skills = _diff(skill_snap, current_skills)

    for key in added_skills:
        bundle, skill = key.split("/", 1)
        logger.info("Skill added: %s/%s", bundle, skill)
        new_events.append(_make_event("skill_added", bundle, skill))
        _mark_skill_new(bundle, skill)

    for key in removed_skills:
        bundle, skill = key.split("/", 1)
        logger.info("Skill removed: %s/%s", bundle, skill)
        new_events.append(_make_event("skill_removed", bundle, skill))
        _create_todo_skill_removed(bundle, skill)
        _check_dependency_impact(skill)

    _emit_events(new_events)
    return current_skills, current_bundles


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINTS
# ═══════════════════════════════════════════════════════════════════════════════


def run_once() -> None:
    """Single poll pass — used for testing or one-shot invocation."""
    skill_snap, bundle_snap = _load_snapshot()
    if not skill_snap and not bundle_snap:
        _save_snapshot(_scan_skills(), _scan_bundles())
        return
    new_skill_snap, new_bundle_snap = _poll_once(skill_snap, bundle_snap)
    _save_snapshot(new_skill_snap, new_bundle_snap)


def run_loop() -> None:
    """Continuous polling loop — registered as a daemon service."""
    logger.info(
        "Plugin watcher starting (interval=%ds, skills=%s)",
        POLL_INTERVAL,
        SKILLS_DIR,
    )

    skill_snap, bundle_snap = _load_snapshot()

    # Initialise snapshot on first run (no events for existing state)
    if not SNAPSHOT_FILE.exists() or (not skill_snap and not bundle_snap):
        logger.info("No snapshot found — initialising baseline from current filesystem")
        skill_snap = _scan_skills()
        bundle_snap = _scan_bundles()
        _save_snapshot(skill_snap, bundle_snap)

    while True:
        try:
            skill_snap, bundle_snap = _poll_once(skill_snap, bundle_snap)
            _save_snapshot(skill_snap, bundle_snap)
        except Exception as exc:
            logger.error("Poll cycle failed: %s", exc, exc_info=True)
        time.sleep(POLL_INTERVAL)


def main() -> int:
    parser = argparse.ArgumentParser(description="Augur plugin filesystem watcher (ADR-122)")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously (default: run once and exit)",
    )
    args = parser.parse_args()

    if args.loop:
        run_loop()
        return 0
    else:
        run_once()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
