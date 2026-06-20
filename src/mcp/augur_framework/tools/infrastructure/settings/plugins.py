"""Plugin/skill install, export, import, onboarding, and wizard scope handlers."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from . import _helpers

# ---------------------------------------------------------------------------
# Write handlers
# ---------------------------------------------------------------------------


def _handle_plugin_install(params: dict[str, Any]) -> dict[str, Any]:
    source = params.get("source")
    if not source:
        return {"success": False, "error": "Missing 'source' parameter"}

    path = _helpers._get_state_dir() / "plugins" / "install-log.json"
    data = _helpers._read_json(path)
    entries = data.setdefault("entries", [])
    entry = {
        "id": str(uuid.uuid4()),
        "source": source,
        "name": params.get("name"),
        "bundle": params.get("bundle", "core"),
        "masterClient": params.get("masterClient"),
        "status": "requested",
        "requestedAt": datetime.now().isoformat(),
    }
    entries.append(entry)
    _helpers._write_json(path, data)
    return {
        "success": True,
        "plugin": entry["name"],
        "bundle": entry["bundle"],
        "path": None,
        "message": f"Plugin install requested for {source}",
        "requiresRebuild": True,
    }


def _handle_plugin_uninstall(params: dict[str, Any]) -> dict[str, Any]:
    plugin_id = params.get("pluginId")
    if not plugin_id:
        return {"success": False, "error": "Missing 'pluginId' parameter"}

    path = _helpers._get_state_dir() / "plugins" / "uninstall-log.json"
    data = _helpers._read_json(path)
    entries = data.setdefault("entries", [])
    entry = {
        "id": str(uuid.uuid4()),
        "pluginId": plugin_id,
        "status": "requested",
        "requestedAt": datetime.now().isoformat(),
    }
    entries.append(entry)
    _helpers._write_json(path, data)
    return {
        "success": True,
        "plugin": plugin_id,
        "bundle": None,
        "message": f"Plugin uninstall requested for {plugin_id}",
        "requiresRebuild": True,
    }


def _handle_plugin_export(params: dict[str, Any]) -> dict[str, Any]:
    plugin_id = params.get("pluginId")
    if not plugin_id:
        return {"success": False, "error": "Missing 'pluginId' parameter"}
    target = params.get("target", "tarball")

    path = _helpers._get_state_dir() / "plugins" / "export-log.json"
    data = _helpers._read_json(path)
    entries = data.setdefault("entries", [])
    entry = {
        "id": str(uuid.uuid4()),
        "pluginId": plugin_id,
        "target": target,
        "status": "requested",
        "requestedAt": datetime.now().isoformat(),
    }
    entries.append(entry)
    _helpers._write_json(path, data)
    return {
        "success": True,
        "plugin": plugin_id,
        "target": target,
        "path": None,
        "message": f"Plugin export requested for {plugin_id} as {target}",
    }


def _handle_plugin_dependencies(params: dict[str, Any]) -> dict[str, Any]:
    plugin_id = params.get("pluginId")

    path = _helpers._get_state_dir() / "plugins" / "dependencies.json"
    data = _helpers._read_json(path)
    entries = data.setdefault("entries", [])
    entry = {
        "id": str(uuid.uuid4()),
        "pluginId": plugin_id,
        "action": params.get("action", "install"),
        "status": "requested",
        "requestedAt": datetime.now().isoformat(),
    }
    entries.append(entry)
    _helpers._write_json(path, data)
    return {"success": True, "pluginId": plugin_id, "message": "Dependency install requested"}


def _handle_skill_import(params: dict[str, Any]) -> dict[str, Any]:
    action = params.get("action", "analyze")

    path = _helpers._get_state_dir() / "setup" / "skill-import.json"
    data = _helpers._read_json(path)
    entries = data.setdefault("entries", [])
    entry = {
        "id": str(uuid.uuid4()),
        "action": action,
        "url": params.get("url"),
        "sourceId": params.get("sourceId"),
        "onConflict": params.get("onConflict"),
        "slug": params.get("slug"),
        "status": "requested",
        "requestedAt": datetime.now().isoformat(),
    }
    entries.append(entry)
    _helpers._write_json(path, data)
    return {"success": True, "action": action, "message": f"Skill {action} requested"}


def _handle_skill_export(params: dict[str, Any]) -> dict[str, Any]:
    skill = params.get("skill")
    if not skill:
        return {"success": False, "error": "Missing 'skill' parameter"}

    path = _helpers._get_state_dir() / "setup" / "skill-export.json"
    data = _helpers._read_json(path)
    entries = data.setdefault("entries", [])
    entry = {
        "id": str(uuid.uuid4()),
        "skill": skill,
        "status": "requested",
        "requestedAt": datetime.now().isoformat(),
    }
    entries.append(entry)
    _helpers._write_json(path, data)
    return {
        "success": True,
        "skill": skill,
        "path": None,
        "message": f"Skill export requested for {skill}",
    }


def _handle_analyze_placement(params: dict[str, Any]) -> dict[str, Any]:
    skill_name = params.get("skillName")
    description = params.get("description")
    if not skill_name:
        return {"success": False, "error": "Missing 'skillName' parameter"}
    if not description:
        return {"success": False, "error": "Missing 'description' parameter"}

    path = _helpers._get_state_dir() / "wizard" / "analyze-placement.json"
    data = _helpers._read_json(path)
    entries = data.setdefault("entries", [])
    entry = {
        "id": str(uuid.uuid4()),
        "skillName": skill_name,
        "description": description,
        "patterns": params.get("patterns", []),
        "status": "requested",
        "requestedAt": datetime.now().isoformat(),
    }
    entries.append(entry)
    _helpers._write_json(path, data)
    return {
        "success": True,
        "recommendation": None,
        "existingSkills": [],
        "message": f"Placement analysis requested for {skill_name}",
    }


def _handle_onboarding_complete(params: dict[str, Any]) -> dict[str, Any]:
    onboarding_data = params.get("data", {})

    path = _helpers._get_state_dir() / "setup" / "onboarding.json"
    data = _helpers._read_json(path)
    data["completed"] = True
    data["completedAt"] = datetime.now().isoformat()
    data["data"] = onboarding_data
    _helpers._write_json(path, data)
    return {"ok": True, "completed": True}


def _handle_onboarding_test(params: dict[str, Any]) -> dict[str, Any]:
    test = params.get("test", "")
    if not test:
        return {"ok": False, "error": "Missing 'test' parameter"}

    path = _helpers._get_state_dir() / "setup" / "onboarding-tests.json"
    data = _helpers._read_json(path)
    tests = data.setdefault("tests", {})
    tests[test] = {
        "status": "requested",
        "requestedAt": datetime.now().isoformat(),
    }
    _helpers._write_json(path, data)
    return {"ok": True, "test": test, "status": "requested"}


def _handle_wizard_sources_combine(params: dict[str, Any]) -> dict[str, Any]:
    sources = params.get("sources", [])
    skill_name = params.get("skillName", "new-skill")
    layer = params.get("layer", "vertical")

    path = _helpers._get_state_dir() / "wizard" / "sources-combine.json"
    data = _helpers._read_json(path)
    entries = data.setdefault("entries", [])
    entry = {
        "id": str(uuid.uuid4()),
        "sources": sources,
        "skillName": skill_name,
        "layer": layer,
        "status": "requested",
        "requestedAt": datetime.now().isoformat(),
    }
    entries.append(entry)
    _helpers._write_json(path, data)
    return {
        "combined": True,
        "context": {"requirements": [], "content": [], "structure": None, "metadata": {}},
        "suggested": {
            "name": skill_name,
            "description": f"Combined from {len(sources)} sources",
            "layer": layer,
            "patterns": ["inbox", "database"],
        },
    }


def _handle_wizard_sources_extract(params: dict[str, Any]) -> dict[str, Any]:
    source_type = params.get("type", "unknown")
    value = params.get("value", "")

    path = _helpers._get_state_dir() / "wizard" / "sources-extract.json"
    data = _helpers._read_json(path)
    entries = data.setdefault("entries", [])
    entry = {
        "id": str(uuid.uuid4()),
        "type": source_type,
        "value": value,
        "branch": params.get("branch", "main"),
        "status": "requested",
        "requestedAt": datetime.now().isoformat(),
    }
    entries.append(entry)
    _helpers._write_json(path, data)
    return {
        "type": source_type,
        "value": value,
        "extracted": True,
        "message": f"Extraction requested for {source_type}",
    }


# ---------------------------------------------------------------------------
# Read handlers
# ---------------------------------------------------------------------------


def _read_plugin_dependencies(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "plugins" / "dependencies.json"
    data = _helpers._read_json(path)
    return {
        "plugins": data.get("plugins", []),
        "summary": data.get("summary", {"total": 0, "installed": 0, "needsInstall": 0}),
    }


def _read_plugin_dependency_tree(params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "plugins" / "dependency-tree.json"
    data = _helpers._read_json(path)
    return {
        "graph": data.get("graph", {}),
        "cycle": data.get("cycle"),
        "validation": data.get("validation", {}),
        "pluginCount": data.get("pluginCount", 0),
    }


def _read_analyze_placement(_params: dict[str, Any]) -> dict[str, Any]:
    path = _helpers._get_state_dir() / "wizard" / "analyze-placement.json"
    data = _helpers._read_json(path)
    return {
        "skills": data.get("skills", []),
    }
