"""Skill lifecycle operations: adopt and status.

Manages transitions between external skills and Augur-managed skills.
"""

from __future__ import annotations

import importlib
import re
import shutil
from pathlib import Path

from src.config.paths import (
    get_configured_vault_skills_dir,
    get_managed_skill_source_dirs,
    get_project_brain_skills_dir,
    get_runtime_dir,
)
from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter
from src.plugins.skill_discovery import invalidate_discovery_cache
from src.plugins.skill_ui_state import read_skill_dashboard_state

try:
    _check_github_update = importlib.import_module("skills.import.augur.lib.update_checker").check_github_update
except Exception:  # pragma: no cover - import fallback for tests/runtime packaging
    _check_github_update = None


def _validate_skill_name(name: str) -> str | None:
    """Validate skill name contains no path traversal characters."""
    if not name or not name.strip():
        return "Skill name cannot be empty"
    if ".." in name or "/" in name or "\\" in name:
        return f"Invalid skill name: '{name}'. Must not contain path separators or '..'"
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        return f"Invalid skill name: '{name}'. Must contain only alphanumeric characters, hyphens, and underscores"
    return None


# Client folder patterns keyed by source tag.
_CLIENT_SKILL_PATHS: dict[str, tuple[str, bool]] = {
    # source_tag: (relative_path_template, is_flat)
    "claude-local": (".claude/skills/{name}", False),
    "claude-global": ("~/.claude/skills/{name}", False),
    "codex-local": (".codex/skills/{name}", False),
    "codex-global": ("~/.codex/skills/{name}", False),
    "gemini-local": (".gemini/skills/{name}", False),
    "gemini-global": ("~/.gemini/skills/{name}", False),
    "cursor-local": (".cursor/rules/{name}.mdc", True),
    "cursor-global": ("~/.cursor/rules/{name}.mdc", True),
    "copilot-local": (".github/instructions/{name}.instructions.md", True),
    "copilot-global": ("~/.github/instructions/{name}.instructions.md", True),
    "opencode-local": (".opencode/skills/{name}", False),
    "opencode-global": ("~/.config/opencode/skills/{name}", False),
}


def _resolve_client_path(source: str, name: str, project_root: Path) -> Path:
    """Resolve the client-side path for a skill given its source tag."""
    template, _is_flat = _CLIENT_SKILL_PATHS[source]
    path_str = template.replace("{name}", name)
    if path_str.startswith("~/"):
        return Path.home() / path_str[2:]
    return project_root / path_str


def _source_skill_file(source: str, name: str, project_root: Path) -> tuple[Path, bool] | None:
    """Return the source skill file and whether it came from a flat client."""
    if source not in _CLIENT_SKILL_PATHS:
        return None

    client_path = _resolve_client_path(source, name, project_root)
    _template, is_flat = _CLIENT_SKILL_PATHS[source]
    if is_flat:
        return client_path, True
    return client_path / "SKILL.md", False


def _relative_upstream_path(path: Path, project_root: Path) -> str:
    """Return a stable upstream path string for frontmatter."""
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def _build_upstream_metadata(source: str, source_path: Path, source_meta: dict, project_root: Path) -> dict:
    """Build structured upstream metadata for an adopted skill."""
    upstream = {
        "source": source,
        "path": _relative_upstream_path(source_path, project_root),
    }
    version = source_meta.get("version") or source_meta.get("x-augur-version")
    if version:
        upstream["version"] = str(version)
    return upstream


def _resolve_upstream_repo(upstream: dict) -> str | None:
    """Return a GitHub repo URL from structured upstream metadata when available."""
    repo = upstream.get("repo")
    if isinstance(repo, str) and repo.strip():
        return repo.strip()
    return None


def _resolve_upstream_ref(upstream: dict) -> str | None:
    """Return the stored upstream revision when available."""
    for key in ("ref", "version", "revision", "commit"):
        value = upstream.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _build_update_status(upstream: dict) -> dict:
    """Compute upstream update status for adopted skills when repo/ref are known."""
    repo = _resolve_upstream_repo(upstream)
    installed_ref = _resolve_upstream_ref(upstream)
    if not repo or not installed_ref or _check_github_update is None:
        return {
            "update_available": False,
            "latest_upstream_commit": None,
        }

    result = _check_github_update(repo, installed_ref)
    latest_commit = result.get("latest_commit")
    return {
        "update_available": bool(result.get("update_available")),
        "latest_upstream_commit": latest_commit if isinstance(latest_commit, str) and latest_commit else None,
    }


def _managed_source_label(skills_dir: Path, project_root: Path) -> str:
    """Return a user-facing source label for a managed skill root."""
    resolved = skills_dir.resolve()
    if resolved == get_project_brain_skills_dir(project_root).resolve():
        return "project-brain"
    if resolved == get_configured_vault_skills_dir(project_root).resolve():
        return "private-vault"
    return "unknown"


def _active_managed_skill_source_dirs(project_root: Path) -> list[Path]:
    """Return managed skill roots that are valid after the project-brain migration."""
    allowed = {
        get_project_brain_skills_dir(project_root).resolve(),
        get_configured_vault_skills_dir(project_root).resolve(),
    }
    dirs: list[Path] = []
    seen: set[Path] = set()
    for skills_dir in get_managed_skill_source_dirs(project_root):
        resolved = skills_dir.resolve()
        if resolved not in allowed or resolved in seen:
            continue
        dirs.append(skills_dir)
        seen.add(resolved)
    return dirs


def adopt_skill(name: str, source: str, project_root: Path) -> dict:
    """Adopt an external skill into project-brain/capabilities/skills as Augur-managed content."""
    err = _validate_skill_name(name)
    if err:
        return {"success": False, "message": err}

    skills_dir = get_project_brain_skills_dir(project_root)
    target_dir = skills_dir / name

    if not target_dir.resolve().is_relative_to(skills_dir.resolve()):
        return {"success": False, "message": "Invalid skill name — path escapes project-brain skills directory"}

    if target_dir.exists():
        return {
            "success": False,
            "message": f"Skill '{name}' already exists in project-brain/capabilities/skills/. Cannot adopt.",
        }

    source_entry = _source_skill_file(source, name, project_root)
    if source_entry is None:
        return {
            "success": False,
            "message": f"Unknown source: {source}. Expected one of: {list(_CLIENT_SKILL_PATHS.keys())}",
        }

    source_skill_file, is_flat = source_entry
    if not source_skill_file.exists():
        return {"success": False, "message": f"Client skill not found at {source_skill_file}"}

    source_meta, source_body = parse_frontmatter(source_skill_file)
    if is_flat:
        target_dir.mkdir(parents=True, exist_ok=True)
    else:
        shutil.copytree(source_skill_file.parent, target_dir)

    target_skill_md = target_dir / "SKILL.md"
    adopted_meta = dict(source_meta)
    adopted_meta["ownership"] = "adopted"
    upstream_source_path = source_skill_file if is_flat else source_skill_file.parent
    adopted_meta["upstream"] = _build_upstream_metadata(source, upstream_source_path, source_meta, project_root)
    write_frontmatter(target_skill_md, adopted_meta, source_body)

    invalidate_discovery_cache()
    return {
        "success": True,
        "message": f"Skill '{name}' adopted into project-brain/capabilities/skills/{name}/. Ownership is now adopted.",
    }


def skill_status(name: str, project_root: Path) -> dict:
    """Get the lifecycle status of a skill."""
    err = _validate_skill_name(name)
    if err:
        return {
            "name": name,
            "ownership": "unknown",
            "source": "unknown",
            "location": None,
            "upstream": {},
            "description": err,
        }

    dashboard_state = read_skill_dashboard_state(name, runtime_dir=get_runtime_dir())
    is_new_to_dashboard = bool(dashboard_state.get("is_new_to_dashboard"))

    # Check managed roots in authority order. Adopt writes to
    # project-brain/capabilities/skills, but status must also see managed private-vault
    # skills during the migration.
    for skills_dir in _active_managed_skill_source_dirs(project_root):
        skill_dir = skills_dir / name
        if not skill_dir.exists() or not (skill_dir / "SKILL.md").exists():
            continue

        meta, _body = parse_frontmatter(skill_dir / "SKILL.md")
        ownership = str(meta.get("ownership") or "augur").strip().lower() or "augur"
        upstream = meta.get("upstream")
        if not isinstance(upstream, dict):
            upstream = {}
        update_status = (
            _build_update_status(upstream)
            if ownership == "adopted"
            else {
                "update_available": False,
                "latest_upstream_commit": None,
            }
        )
        return {
            "name": name,
            "ownership": ownership,
            "source": _managed_source_label(skills_dir, project_root),
            "location": str(skill_dir),
            "upstream": upstream,
            "description": meta.get("description", ""),
            "is_new_to_dashboard": is_new_to_dashboard,
            **update_status,
        }

    # Check client folders
    for source_tag, (_template, is_flat) in _CLIENT_SKILL_PATHS.items():
        client_path = _resolve_client_path(source_tag, name, project_root)
        if is_flat:
            if client_path.exists():
                meta, _body = parse_frontmatter(client_path)
                return {
                    "name": name,
                    "ownership": "external",
                    "source": source_tag,
                    "location": str(client_path),
                    "upstream": {},
                    "description": meta.get("description", ""),
                    "is_new_to_dashboard": is_new_to_dashboard,
                    "update_available": False,
                    "latest_upstream_commit": None,
                }
        else:
            if client_path.exists() and (client_path / "SKILL.md").exists():
                meta, _body = parse_frontmatter(client_path / "SKILL.md")
                return {
                    "name": name,
                    "ownership": "external",
                    "source": source_tag,
                    "location": str(client_path),
                    "upstream": {},
                    "description": meta.get("description", ""),
                    "is_new_to_dashboard": is_new_to_dashboard,
                    "update_available": False,
                    "latest_upstream_commit": None,
                }

    return {
        "name": name,
        "ownership": "unknown",
        "source": "unknown",
        "location": None,
        "upstream": {},
        "description": "",
        "is_new_to_dashboard": is_new_to_dashboard,
        "update_available": False,
        "latest_upstream_commit": None,
    }


def skill_upstream_status(name: str, project_root: Path) -> dict:
    """Return upstream/update details for adopted skills."""
    status = skill_status(name, project_root)
    return {
        "name": status["name"],
        "ownership": status["ownership"],
        "upstream": status.get("upstream", {}),
        "update_available": bool(status.get("update_available")),
        "latest_upstream_commit": status.get("latest_upstream_commit"),
    }
