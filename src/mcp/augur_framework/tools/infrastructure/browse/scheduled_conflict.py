"""Per-routine conflict resolution impls: Adopt cloud / Push my version.

Owned by ADR-763. Kept separate from scheduled_executions.py so the listing
aggregator stays read-only and these mutators stay easy to find.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import tomllib
from src.mcp.augur_shared.safe_subprocess import safe_run


def _source_and_native_id(routine_id: str) -> tuple[str, str]:
    """Split a Browse routine id like ``codex:codex-dev-loop-testing``."""
    if ":" not in routine_id:
        return ("", routine_id)
    source, _, native = routine_id.partition(":")
    return (source, native)


def _find_seed_owning_id(schedule_id: str, search_roots: Iterable[Path]) -> Path | None:
    """Locate the routine-schedule.yaml seed whose schedules[].id matches."""
    import yaml

    for root in search_roots:
        if not root.is_dir():
            continue
        for seed_path in root.glob("*/assets/seeds/routine-schedule.yaml"):
            try:
                raw = yaml.safe_load(seed_path.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            schedules = raw.get("schedules") if isinstance(raw, dict) else None
            if not isinstance(schedules, list):
                continue
            for entry in schedules:
                if isinstance(entry, dict) and str(entry.get("id", "")) == schedule_id:
                    return seed_path
    return None


def _default_seed_search_roots() -> list[Path]:
    """Project + private vault skill roots used when caller passes None."""
    try:
        from src.config.paths import (
            get_managed_skill_source_dirs,
            get_project_brain_skills_dir,
            get_project_root,
        )
    except Exception:
        return []

    roots: list[Path] = []
    try:
        roots.extend(Path(r) for r in get_managed_skill_source_dirs())
    except Exception:
        pass
    project_skills = get_project_brain_skills_dir(get_project_root())
    if project_skills.is_dir() and project_skills not in roots:
        roots.append(project_skills)
    return roots


def adopt_cloud_impl(
    routine_id: str,
    *,
    seed_search_roots: Iterable[Path] | None = None,
) -> str:
    """Pull installed-surface state into the seed file for one routine.

    Codex: reads ~/.codex/automations/<id>/automation.toml, finds the seed
    YAML that declares that id, rewrites that single entry to match the TOML
    fields. After adoption the next sync's drift check returns in-sync.

    Claude-remote: there is no seed file for cloud routines today. The action
    is a no-op success that acknowledges the cache as desired.
    """
    from src.lib.runtime.seed_yaml_editor import update_seed_entry

    source, native_id = _source_and_native_id(routine_id)

    if source == "claude-remote":
        return json.dumps(
            {
                "success": True,
                "message": "claude-remote has no seed file; adoption is a no-op (cache is the registry).",
                "items": [row for row in [_refreshed_row_for(routine_id)] if row],
            }
        )

    if source != "codex":
        return json.dumps({"success": False, "error": f"adopt unsupported for source {source!r}"})

    toml_path = Path.home() / ".codex" / "automations" / native_id / "automation.toml"
    if not toml_path.is_file():
        return json.dumps({"success": False, "error": f"installed TOML not found for {native_id!r}"})

    try:
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return json.dumps({"success": False, "error": f"parse failed: {exc}"})

    cwds = data.get("cwds") or [""]
    workspace = str(cwds[0]) if isinstance(cwds, list) and cwds else ""
    new_fields = {
        "rrule": str(data.get("rrule", "")),
        "prompt": str(data.get("prompt", "")),
        "model": str(data.get("model", "")),
        "reasoning_effort": str(data.get("reasoning_effort", "")),
        "workspace": workspace,
    }

    search_roots = list(seed_search_roots) if seed_search_roots is not None else _default_seed_search_roots()
    seed_path = _find_seed_owning_id(native_id, search_roots)
    if seed_path is None:
        return json.dumps({"success": False, "error": f"no seed file owns id {native_id!r} (entry may be external)"})

    updated = update_seed_entry(seed_path, schedule_id=native_id, new_fields=new_fields)
    if not updated:
        return json.dumps({"success": False, "error": "seed update failed unexpectedly"})

    # Re-sync to re-embed a fresh augur_seed_hash in the TOML so the next drift
    # check returns in-sync rather than codex-edited (spec line 85).
    try:
        from src.lib.runtime.codex_automations import sync_codex_automations

        adopted_schedule = {
            "id": native_id,
            "title": str(data.get("name", native_id)),
            "prompt": new_fields["prompt"],
            "rrule": new_fields["rrule"],
            "model": new_fields["model"],
            "reasoning_effort": new_fields["reasoning_effort"],
            "workspace": new_fields["workspace"],
            "runs_in": "local",
        }
        sync_codex_automations([adopted_schedule], apply=True, prune=False, force=True)
    except Exception as exc:
        return json.dumps({"success": False, "error": f"re-sync failed: {exc}"})

    return json.dumps(
        {
            "success": True,
            "message": f"adopted surface state for {native_id!r}",
            "seed_path": str(seed_path),
            "applied_fields": new_fields,
            "re_synced": True,
            "items": [row for row in [_refreshed_row_for(routine_id)] if row],
        }
    )


def _refreshed_row_for(routine_id: str) -> dict[str, Any] | None:
    """Return the Browse row for one routine after a mutation, or None.

    Used by adopt_cloud_impl / push_local_impl to include the post-mutation
    item in their response so the dashboard can clear drift badges without
    triggering a full Browse re-fetch.
    """
    try:
        from src.mcp.augur_framework.tools.infrastructure.browse.scheduled_executions import (
            list_scheduled_execution_items,
        )
    except Exception:
        return None
    try:
        items = list_scheduled_execution_items()
    except Exception:
        return None
    return next((it for it in items if it.get("id") == routine_id), None)


def push_local_impl(
    routine_id: str,
    *,
    desired_schedules: list[dict] | None = None,
) -> str:
    """Force-sync seed state over the installed surface for one routine.

    Codex: invokes sync_codex_automations(force=True) scoped to this id.
    Claude-remote: not implemented in this commit — separate task spawns
    `claude --print` to call RemoteTrigger update.
    """
    from src.lib.runtime.codex_automations import sync_codex_automations

    source, native_id = _source_and_native_id(routine_id)

    if source == "claude-remote":
        return _push_claude_remote(native_id)

    if source != "codex":
        return json.dumps(
            {
                "success": False,
                "error": f"push not supported for source {source!r}",
            }
        )

    if desired_schedules is None:
        desired_schedules = _load_all_desired_codex_schedules()

    target = next(
        (s for s in desired_schedules if str(s.get("id", "")) == native_id),
        None,
    )
    if target is None:
        return json.dumps(
            {
                "success": False,
                "error": f"routine {native_id!r} not in desired seeds; nothing to push",
            }
        )

    written = sync_codex_automations([target], apply=True, prune=False, force=True)
    return json.dumps(
        {
            "success": True,
            "message": f"pushed seed for {native_id!r}",
            "written": [str(p) for p in written],
            "items": [row for row in [_refreshed_row_for(routine_id)] if row],
        }
    )


def _load_all_desired_codex_schedules() -> list[dict]:
    """Default seed loader; mirrors scheduled_sources/codex.py:_load_desired_seeds."""
    try:
        from src.config.paths import get_project_root
        from src.lib.runtime.codex_automations import load_codex_schedule_seed
    except Exception:
        return []

    project_root = get_project_root()
    schedules: list[dict] = []
    seen: set[str] = set()
    for root in _default_seed_search_roots():
        if not root.is_dir():
            continue
        for seed_path in root.glob("*/assets/seeds/routine-schedule.yaml"):
            try:
                rows = load_codex_schedule_seed(seed_path, project_root=project_root)
            except Exception:
                continue
            for row in rows:
                schedule_id = str(row.get("id", ""))
                if schedule_id and schedule_id not in seen:
                    seen.add(schedule_id)
                    schedules.append(row)
    return schedules


def _push_claude_remote(trigger_id: str) -> str:
    """Push the cached cron/prompt for a claude-remote routine back to cloud.

    Spawns `claude --print` so the subprocess inherits OAuth via the Claude
    CLI. Server-side Python never sees the token directly. Matches the
    refresh path's auth boundary.
    """
    from src.config.paths import get_cache_dir

    claude_bin = shutil.which("claude")
    if not claude_bin:
        return json.dumps(
            {
                "success": False,
                "error": "claude CLI not on PATH; install Claude Code to enable cloud push.",
            }
        )

    cache_path = get_cache_dir() / "claude-remote-routines.json"
    if not cache_path.is_file():
        return json.dumps(
            {
                "success": False,
                "error": "claude-remote cache missing; refresh first.",
            }
        )

    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return json.dumps({"success": False, "error": f"cache parse failed: {exc}"})

    routines = cache.get("routines") if isinstance(cache, dict) else None
    if not isinstance(routines, list):
        return json.dumps({"success": False, "error": "cache missing routines array"})

    target = next(
        (r for r in routines if isinstance(r, dict) and str(r.get("id", "")) == trigger_id),
        None,
    )
    if target is None:
        return json.dumps({"success": False, "error": f"trigger {trigger_id!r} not in cache"})

    prompt = (
        f"Call the RemoteTrigger tool with action='update', "
        f"trigger_id='{trigger_id}', and body={{'cron_expression': "
        f"'{target.get('cron_expression', '')}', 'enabled': "
        f"{str(bool(target.get('enabled', True))).lower()}}}. "
        'Reply with only the literal string "OK" on success or "ERR: <reason>" on failure.'
    )

    try:
        result = safe_run(
            [claude_bin, "--print", prompt],
            capture_output=True,
            timeout=120,
            text=True,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return json.dumps({"success": False, "error": "claude --print timed out after 120s"})

    if result.returncode != 0:
        return json.dumps(
            {
                "success": False,
                "error": f"claude --print exited {result.returncode}",
                "stderr": result.stderr[-500:],
            }
        )

    return json.dumps(
        {
            "success": True,
            "message": f"pushed claude-remote routine {trigger_id} to cloud",
            "stdout": result.stdout[-200:],
            "items": [row for row in [_refreshed_row_for(f"claude-remote:{trigger_id}")] if row],
        }
    )
