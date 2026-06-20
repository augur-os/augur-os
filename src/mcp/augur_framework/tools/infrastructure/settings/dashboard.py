"""Dashboard UI state scope handlers — layout, nav, preferences, LLM config."""

from __future__ import annotations

import copy
import os
import tempfile
from datetime import datetime
from pathlib import Path
from subprocess import DEVNULL, TimeoutExpired, run
from typing import Any

import yaml
from src.config.paths import get_project_brain_skills_dir
from src.config.schemas.llm_schema import LlmSchemaError, validate_llm_config
from src.config.schemas.settings_schema import SettingsSchemaError, validate_settings_config
from src.config.system_config import invalidate_caches, llm_config_raw, settings_config_raw
from src.mcp.augur_shared.logging import get_entity_logger

from . import _helpers

logger = get_entity_logger("mcp.settings")

_PROFILE_MUTATION_KEYS = {
    "provider",
    "base_url",
    "model",
    "timeout_s",
    "api_key_env",
    "api_key",
    "command",
    "disable_thinking",
}


def _atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write YAML via same-directory temp file and os.replace."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            yaml.safe_dump(data, handle, sort_keys=False, default_flow_style=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        finally:
            raise


def _schema_error(exc: Exception) -> dict[str, Any]:
    return {
        "success": False,
        "error": str(exc),
        "refusal_category": "schema_violation",
    }


def _merge_llm_payload(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Merge a focused dashboard LLM mutation into the canonical llm.yaml shape."""

    validate_llm_config(existing)
    merged = copy.deepcopy(existing)

    if not isinstance(incoming, dict) or not incoming:
        raise LlmSchemaError("incoming llm config mutation must be a non-empty mapping")

    structural_keys = {"profile", "profile_name", "active_profile", "profiles", "tasks"}
    incoming_keys = set(incoming)
    unknown_top_level = incoming_keys - structural_keys - _PROFILE_MUTATION_KEYS
    if unknown_top_level:
        candidate = copy.deepcopy(incoming)
        candidate.setdefault("tasks", {})
        validate_llm_config(candidate)

    profile_fields = {key: incoming[key] for key in incoming_keys & _PROFILE_MUTATION_KEYS}
    if profile_fields:
        profile_name = incoming.get("profile") or incoming.get("profile_name")
        if not isinstance(profile_name, str) or not profile_name.strip():
            if {"provider", "base_url", "model"}.issubset(profile_fields):
                profile_name = merged.get("active_profile")
            else:
                candidate = copy.deepcopy(incoming)
                candidate.setdefault("tasks", {})
                validate_llm_config(candidate)
        if not isinstance(profile_name, str) or profile_name not in merged.get("profiles", {}):
            raise LlmSchemaError(f"profile {profile_name!r} is not defined in llm.yaml")
        merged["profiles"][profile_name].update(profile_fields)

    profiles = incoming.get("profiles")
    if profiles is not None:
        if not isinstance(profiles, dict):
            raise LlmSchemaError("profiles mutation must be a mapping")
        target_profiles = merged.setdefault("profiles", {})
        for name, profile in profiles.items():
            if not isinstance(name, str) or not isinstance(profile, dict):
                raise LlmSchemaError("profiles mutation must map profile names to mappings")
            existing_profile = target_profiles.get(name, {})
            if not isinstance(existing_profile, dict):
                existing_profile = {}
            target_profiles[name] = {**existing_profile, **copy.deepcopy(profile)}

    if "active_profile" in incoming:
        merged["active_profile"] = incoming["active_profile"]

    tasks = incoming.get("tasks")
    if tasks is not None:
        if not isinstance(tasks, dict):
            raise LlmSchemaError("tasks mutation must be a mapping")
        merged_tasks = merged.setdefault("tasks", {})
        if not isinstance(merged_tasks, dict):
            merged_tasks = {}
            merged["tasks"] = merged_tasks
        merged_tasks.update(copy.deepcopy(tasks))

    validate_llm_config(merged)
    return merged


# ---------------------------------------------------------------------------
# Write handlers
# ---------------------------------------------------------------------------


def _handle_preferences(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_config_dir() / "system" / "preferences.yaml"
    data = _helpers._read_yaml(path)
    key = params.get("key")
    value = params.get("value")
    if not key:
        return {"success": False, "error": "Missing 'key' parameter"}
    data[key] = value
    _helpers._write_yaml(path, data)
    return {"success": True, "key": key, "value": value}


def _handle_layout_presets(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "dashboard" / "layout-presets.json"
    preset = params.get("preset")
    if not preset:
        return {"success": False, "error": "Missing 'preset' parameter"}
    data = _helpers._read_json(path)
    data["activePreset"] = preset
    data["updatedAt"] = datetime.now().isoformat()
    _helpers._write_json(path, data)
    return {"success": True, "activePreset": preset}


def _handle_layout_reset(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "dashboard" / "layout-presets.json"
    reset_scope = params.get("reset_scope", "all")
    if reset_scope == "all":
        _helpers._write_json(path, {"activePreset": "custom", "updatedAt": datetime.now().isoformat()})
    else:
        data = _helpers._read_json(path)
        data.pop(reset_scope, None)
        data["updatedAt"] = datetime.now().isoformat()
        _helpers._write_json(path, data)
    return {"success": True, "reset_scope": reset_scope}


def _handle_nav_order_update(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "dashboard" / "nav-order.json"
    order_type = params.get("type")
    items = params.get("items")
    hub_id = params.get("hub_id") or params.get("hubId")
    if order_type not in ("hub", "tab"):
        return {"success": False, "error": "Invalid type. Use 'hub' or 'tab'."}
    if not isinstance(items, list):
        return {"success": False, "error": "Missing or invalid 'items' parameter"}

    data = _helpers._read_json(path)
    if order_type == "hub":
        data["hubs"] = items
    elif order_type == "tab" and hub_id:
        tabs = data.setdefault("tabs", {})
        tabs[hub_id] = items
    data["updatedAt"] = datetime.now().isoformat()
    _helpers._write_json(path, data)
    return {"success": True, "type": order_type, "items": items}


def _handle_skill_nav_toggle(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "dashboard" / "skill-nav.json"
    skill = params.get("skill")
    visible = params.get("visible")
    if not skill or not isinstance(visible, bool):
        return {"success": False, "error": "skill (string) and visible (boolean) are required"}

    data = _helpers._read_json(path)
    skills_map = data.setdefault("skills", {})
    skills_map[skill] = {
        "visible": visible,
        "category": params.get("category", ""),
        "label": params.get("label", ""),
        "updatedAt": datetime.now().isoformat(),
    }
    _helpers._write_json(path, data)
    return {"success": True, "skill": skill, "visible": visible}


def _handle_dashboard_toggle(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "dashboard" / "dashboard-groups.json"
    group_id = params.get("group_id") or params.get("groupId")
    enabled = params.get("enabled")
    if not group_id or not isinstance(enabled, bool):
        return {"success": False, "error": "group_id (string) and enabled (boolean) are required"}

    data = _helpers._read_json(path)
    groups = data.setdefault("groups", {})
    groups[group_id] = {"enabled": enabled, "updatedAt": datetime.now().isoformat()}
    _helpers._write_json(path, data)
    return {"success": True, "group_id": group_id, "enabled": enabled}


def _handle_dashboard_remove(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "dashboard" / "dashboard-groups.json"
    group_id = params.get("group_id") or params.get("groupId")
    if not group_id:
        return {"success": False, "error": "group_id is required"}

    data = _helpers._read_json(path)
    groups = data.get("groups", {})
    removed = groups.pop(group_id, None)
    data["groups"] = groups
    _helpers._write_json(path, data)

    disable_skills = (
        params.get("disable_skills") if params.get("disable_skills") is not None else params.get("disableSkills", False)
    )
    return {
        "success": True,
        "group_id": group_id,
        "removed": removed is not None,
        "disable_skills": disable_skills,
    }


def _handle_default_cli(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_config_dir() / "system" / "settings.yaml"
    default_cli = params.get("default_cli")
    if not default_cli:
        return {"success": False, "error": "Missing 'default_cli' parameter"}

    try:
        data = settings_config_raw(path)
        data["default_cli"] = str(default_cli)
        validate_settings_config(data)
        _atomic_write_yaml(path, data)
        invalidate_caches()
    except SettingsSchemaError as exc:
        return _schema_error(exc)
    return {"success": True, "default_cli": default_cli}


def _handle_llm_config(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_config_dir() / "system" / "llm.yaml"
    config = params.get("config")
    if not config or not isinstance(config, dict):
        return {"success": False, "error": "Missing or invalid 'config' parameter"}

    try:
        merged = _merge_llm_payload(llm_config_raw(path), config)
        _atomic_write_yaml(path, merged)
        invalidate_caches()
    except (LlmSchemaError, ValueError) as exc:
        return _schema_error(exc)
    return {"success": True, "config_path": str(path)}


def _handle_llm_config_write(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_config_dir() / "system" / "llm.yaml"
    yaml_text = params.get("yaml", "")
    if not yaml_text or not isinstance(yaml_text, str):
        return {"success": False, "error": "Missing 'yaml' parameter"}

    try:
        raw = yaml.safe_load(yaml_text)  # validate before writing
        validate_llm_config(raw)
    except yaml.YAMLError as e:
        return {"success": False, "error": f"Invalid YAML: {e}"}
    except LlmSchemaError as e:
        return _schema_error(e)

    _atomic_write_yaml(path, raw)
    invalidate_caches()
    return {"success": True, "config_path": str(path)}


def _handle_hub_notes(params: dict[str, Any]) -> dict[str, Any]:
    hub_id = params.get("hub_id")
    if not hub_id:
        return {"success": False, "error": "Missing 'hub_id' parameter"}
    content = params.get("value", "")

    path = _helpers._get_state_dir() / "dashboard" / "notes" / f"{hub_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(content), encoding="utf-8")
    return {"success": True, "hub_id": hub_id}


def _handle_usage_stats(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "dashboard" / "usage-stats.json"
    data = _helpers._read_json(path)
    pages = data.setdefault("pages", [])
    pages.append(
        {
            "page": params.get("page", ""),
            "timestamp": params.get("timestamp", datetime.now().isoformat()),
            "action": params.get("action", "view"),
        }
    )
    # Keep last 1000 entries
    if len(pages) > 1000:
        data["pages"] = pages[-1000:]
    _helpers._write_json(path, data)
    return {"success": True}


def _handle_focus_state(params: dict[str, Any]) -> dict[str, Any]:
    current_page = str(params.get("current_page", "")).strip()
    skill_name = str(params.get("skill_name", "")).strip()
    bundle = str(params.get("bundle", "")).strip()
    session_id = str(params.get("session_id", "")).strip()
    source = str(params.get("source", "dashboard")).strip() or "dashboard"
    timestamp = str(params.get("timestamp", datetime.now().isoformat())).strip()

    if not current_page or not skill_name or not bundle or not session_id:
        return {
            "success": False,
            "error": "Missing required fields: current_page, skill_name, bundle, session_id",
        }

    payload = {
        "current_page": current_page,
        "skill_name": skill_name,
        "bundle": bundle,
        "session_id": session_id,
        "timestamp": timestamp,
        "source": source,
    }

    state_dir = _helpers._get_state_dir()
    _helpers._write_json(state_dir / "focus_state.json", payload)
    _helpers._write_json(state_dir / "sessions" / f"{session_id}.json", payload)
    return {"success": True, **payload}


def _handle_skill_set_enabled(params: dict[str, Any]) -> dict[str, Any]:
    slug = params.get("slug")
    enabled = params.get("enabled")
    if not slug or not isinstance(enabled, bool):
        return {"success": False, "error": "slug (string) and enabled (boolean) are required"}

    path = _helpers._get_state_dir() / "dashboard" / "skill-state.json"
    data = _helpers._read_json(path)
    skills = data.setdefault("skills", {})
    skills[slug] = {"enabled": enabled, "updatedAt": datetime.now().isoformat()}
    _helpers._write_json(path, data)
    return {"success": True, "slug": slug, "enabled": enabled}


def _handle_skill_uninstall(params: dict[str, Any]) -> dict[str, Any]:
    slug = params.get("slug")
    if not slug:
        return {"success": False, "error": "Missing 'slug' parameter"}

    path = _helpers._get_state_dir() / "dashboard" / "skill-state.json"
    data = _helpers._read_json(path)
    skills = data.get("skills", {})
    skills.pop(slug, None)
    data["skills"] = skills
    _helpers._write_json(path, data)
    return {"success": True, "slug": slug, "uninstalled": True}


def _handle_cli_upload(params: dict[str, Any]) -> dict[str, Any]:
    import base64

    filename = params.get("filename")
    content_b64 = params.get("content_base64")
    if not filename or not content_b64:
        return {"success": False, "error": "Missing 'filename' or 'content_base64' parameter"}

    try:
        content = base64.b64decode(content_b64)
    except Exception as e:
        return {"success": False, "error": f"Invalid base64 content: {e}"}

    upload_dir = _helpers._get_state_dir() / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Add timestamp prefix to avoid collisions
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"{ts}_{filename}"
    dest = upload_dir / safe_name
    dest.write_bytes(content)

    return {
        "success": True,
        "filename": safe_name,
        "original_filename": filename,
        "path": str(dest),
        "size": len(content),
        "mime_type": params.get("mime_type", "application/octet-stream"),
    }


# ---------------------------------------------------------------------------
# Read handlers
# ---------------------------------------------------------------------------


def _read_preferences(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_config_dir() / "system" / "preferences.yaml"
    data = _helpers._read_yaml(path)
    key = params.get("key")
    if key:
        return {key: data.get(key)} if key in data else {}
    return data


def _read_layout_presets(_params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "dashboard" / "layout-presets.json"
    data = _helpers._read_json(path)
    return {
        "success": True,
        "activePreset": data.get("activePreset", "custom"),
        "availablePresets": ["focus", "review", "compact", "wide"],
        "defaults": data.get("defaults", {}),
    }


def _read_nav_order(_params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "dashboard" / "nav-order.json"
    return _helpers._read_json(path)


def _read_skill_nav(_params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "dashboard" / "skill-nav.json"
    data = _helpers._read_json(path)
    # Return in the shape the dashboard expects
    skills = data.get("skills", {})
    return {"skills": [{"skill": k, **v} for k, v in skills.items()] if isinstance(skills, dict) else skills}


def _read_dashboard_groups(_params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "dashboard" / "dashboard-groups.json"
    return _helpers._read_json(path)


def _read_default_cli(_params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_config_dir() / "system" / "settings.yaml"
    data = settings_config_raw(path)
    return {"default_cli": data.get("default_cli", "")}


def _read_llm_config(_params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_config_dir() / "system" / "llm.yaml"
    if not path.exists():
        return {"config": {}, "raw": "", "effective": {}, "configPath": str(path)}
    raw = path.read_text(encoding="utf-8")
    try:
        parsed = llm_config_raw(path)
        validate_llm_config(parsed)
    except (yaml.YAMLError, LlmSchemaError, ValueError) as exc:
        return {
            "config": {},
            "raw": raw,
            "effective": {},
            "configPath": str(path),
            "success": False,
            "error": str(exc),
        }
    return {
        "config": parsed,
        "raw": raw,
        "effective": parsed,
        "configPath": str(path),
    }


def _read_hub_notes(params: dict[str, Any]) -> dict[str, Any]:
    hub_id = params.get("hub_id")
    if not hub_id:
        return {"content": ""}
    path = _helpers._get_state_dir() / "dashboard" / "notes" / f"{hub_id}.md"
    if not path.exists():
        return {"content": ""}
    return {"content": path.read_text(encoding="utf-8")}


def _read_usage_stats(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "dashboard" / "usage-stats.json"
    data = _helpers._read_json(path)
    pages = data.get("pages", [])
    limit = params.get("limit", 10)
    if isinstance(limit, int) and limit > 0:
        pages = pages[-limit:]
    return {"pages": pages}


def _read_activity_summary(_params: dict[str, Any]) -> dict[str, Any]:
    state_dir = _helpers._get_state_dir()
    focus = _helpers._read_json(state_dir / "focus_state.json")
    usage = _helpers._read_json(state_dir / "dashboard" / "usage-stats.json")
    rows = usage.get("pages", [])
    if not isinstance(rows, list):
        rows = []

    workflows: list[dict[str, Any]] = []
    seen_workflows: set[tuple[str, str]] = set()
    pages: list[dict[str, Any]] = []
    seen_pages: set[str] = set()

    for entry in reversed(rows):
        if not isinstance(entry, dict):
            continue

        page = str(entry.get("page", "")).strip()
        timestamp = str(entry.get("timestamp", "")).strip() or datetime.now().isoformat()
        action = str(entry.get("action", "view")).strip() or "view"

        if page and action == "view" and page not in seen_pages:
            seen_pages.add(page)
            pages.append(
                {
                    "page": page,
                    "label": page.strip("/").replace("/", " / ").replace("-", " ").title() or "Home",
                    "last_visit": timestamp,
                }
            )

        if page and action != "view":
            workflow_key = (page, action)
            if workflow_key not in seen_workflows:
                seen_workflows.add(workflow_key)
                workflows.append(
                    {
                        "label": action.replace("-", " ").replace("_", " ").title(),
                        "prompt": action,
                        "ide": "Dashboard",
                        "timestamp": timestamp,
                        "success": True,
                    }
                )

        if len(pages) >= 6 and len(workflows) >= 6:
            break

    branch = ""
    last_commit = ""
    commit_time = ""
    try:
        project_root = _helpers._get_project_root()
        # CRITICAL (stdio MCP): this tool runs inside the MCP bridge, whose stdin
        # is the JSON-RPC pipe from the dashboard. Without stdin=DEVNULL, git
        # inherits that pipe and can block forever (a credential/askpass/fsmonitor
        # helper reading stdin) — which hung the whole activity-summary widget for
        # the full 60s request timeout. DEVNULL + a timeout + GIT_TERMINAL_PROMPT=0
        # guarantee git can never stall the bridge.
        git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        branch_result = run(
            ["git", "-C", str(project_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            stdin=DEVNULL,
            timeout=10,
            env=git_env,
        )
        branch = branch_result.stdout.strip()

        commit_result = run(
            ["git", "-C", str(project_root), "log", "-1", "--pretty=%s|%ad", "--date=relative"],
            capture_output=True,
            text=True,
            check=False,
            stdin=DEVNULL,
            timeout=10,
            env=git_env,
        )
        if commit_result.stdout.strip():
            subject, _, relative = commit_result.stdout.strip().partition("|")
            last_commit = subject.strip()
            commit_time = relative.strip()
    except TimeoutExpired:
        logger.warning("git summary timed out for activity summary; returning without git info")
    except Exception:
        logger.debug("Failed to read git summary for activity summary", exc_info=True)

    return {
        "focus": focus if isinstance(focus, dict) and focus.get("current_page") else None,
        "workflows": workflows[:4],
        "assets": [],
        "pages": pages[:4],
        "dev": {
            "branch": branch,
            "last_commit": last_commit,
            "commit_time": commit_time,
        },
    }


def _read_layout_snapshot(_params: dict[str, Any]) -> dict[str, Any]:
    presets_path = _helpers._get_state_dir() / "dashboard" / "layout-presets.json"
    nav_path = _helpers._get_state_dir() / "dashboard" / "nav-order.json"
    presets = _helpers._read_json(presets_path)
    nav = _helpers._read_json(nav_path)
    return {
        "success": True,
        "generatedAt": datetime.now().isoformat(),
        "appearance": {"theme": "futuristic", "mode": "system"},
        "navigation": {
            "hubCount": len(nav.get("hubs", [])),
            "orderedHubs": nav.get("hubs", []),
        },
        "activePreset": presets.get("activePreset", "custom"),
        "pulse": {"healthyProbes": 0, "totalProbes": 0, "probes": []},
    }


def _read_workflows(_params: dict[str, Any]) -> dict[str, Any]:
    """List available workflow/command SKILL.md files."""
    project_root = Path(__file__).resolve().parents[5]
    skills_dir = get_project_brain_skills_dir(project_root)
    commands: list[dict[str, Any]] = []

    if skills_dir.exists():
        for skill_dir in sorted(skills_dir.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                # Extract name from directory
                commands.append(
                    {
                        "name": skill_dir.name,
                        "path": str(skill_md.relative_to(project_root)),
                        "type": "skill",
                    }
                )

    return {
        "commands": commands,
        "count": len(commands),
        "generatedAt": datetime.now().isoformat(),
    }


def _read_plugin_data(params: dict[str, Any]) -> dict[str, Any]:
    """List plugin data/asset files for a skill."""
    skill = params.get("skill", "")
    project_root = Path(__file__).resolve().parents[5]
    skill_path = project_root / skill if skill else None
    files: list[dict[str, str]] = []

    if skill_path and skill_path.exists() and skill_path.is_dir():
        for f in sorted(skill_path.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                files.append(
                    {
                        "name": f.name,
                        "path": str(f.relative_to(project_root)),
                        "size": str(f.stat().st_size),
                    }
                )

    return {"files": files, "total": len(files), "skill": skill}


def _read_debug_routes(_params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "debug" / "routes.json"
    data = _helpers._read_json(path)
    return {
        "stats": data.get("stats", {"total": 0}),
        "groups": data.get("groups", {}),
        "routes": data.get("routes", []),
        "metadata": {
            "scannedAt": datetime.now().isoformat(),
            "source": "settings",
        },
    }
