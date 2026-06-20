"""Scan generated global MCP configs for unsafe Augur checkout references."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from src.config.worktrees import is_linked_worktree

IssueKind = Literal["linked_worktree", "missing_path"]

_WINDOWS_ENV_VAR_RE = re.compile(r"%([A-Za-z_][A-Za-z0-9_]*)%")
_SERVER_KEYS = ("mcpServers", "mcp_servers", "mcp", "servers")


@dataclass(frozen=True)
class McpConfigPathIssue:
    kind: IssueKind
    client_key: str
    client_label: str
    config_path: Path
    server_name: str
    referenced_path: Path
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "clientKey": self.client_key,
            "clientLabel": self.client_label,
            "configPath": str(self.config_path),
            "serverName": self.server_name,
            "referencedPath": str(self.referenced_path),
            "detail": self.detail,
        }


def _expand_environment_tokens(raw_path: str) -> str:
    expanded = os.path.expanduser(os.path.expandvars(raw_path))
    return _WINDOWS_ENV_VAR_RE.sub(
        lambda match: os.environ.get(match.group(1), match.group(0)),
        expanded,
    )


def _config_path_templates(ide_config: dict[str, Any]) -> list[str]:
    config_path = ide_config.get("config_path")
    if isinstance(config_path, str):
        return [config_path]
    if isinstance(config_path, dict):
        return [value for value in config_path.values() if isinstance(value, str)]
    return []


def _is_repo_local_config(ide_config: dict[str, Any]) -> bool:
    return any("{repo_root}" in template for template in _config_path_templates(ide_config))


def _platform_config_path(config_path: Any, project_root: Path) -> Path | None:
    if isinstance(config_path, str):
        raw = config_path
    elif isinstance(config_path, dict):
        platform_key = {
            "darwin": "darwin",
            "linux": "linux",
            "win32": "windows",
        }.get(sys.platform, "all")
        raw = config_path.get(platform_key) or config_path.get("all") or ""
    else:
        raw = ""
    if not raw.strip():
        return None
    expanded = _expand_environment_tokens(raw.replace("{repo_root}", str(project_root)))
    return Path(expanded).expanduser().resolve(strict=False)


def _load_config(path: Path, config_format: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        if config_format == "toml":
            try:
                import tomllib
            except ModuleNotFoundError:  # pragma: no cover
                import tomli as tomllib  # type: ignore
            return tomllib.loads(path.read_text(encoding="utf-8"))
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return None


def _is_augur_server_name(name: str) -> bool:
    return name == "augur" or name.startswith("augur-")


def _iter_augur_server_entries(node: Any) -> list[tuple[str, Any]]:
    entries: list[tuple[str, Any]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _SERVER_KEYS and isinstance(value, dict):
                for server_name, server_config in value.items():
                    if _is_augur_server_name(str(server_name)):
                        entries.append((str(server_name), server_config))
            if isinstance(value, dict):
                entries.extend(_iter_augur_server_entries(value))
            elif isinstance(value, list):
                for item in value:
                    entries.extend(_iter_augur_server_entries(item))
    return entries


def _normalize_path(path: Path) -> Path:
    try:
        return path.expanduser().resolve(strict=False)
    except OSError:
        return path.expanduser()


def _looks_like_path(value: str) -> bool:
    value = value.strip()
    return (
        value.startswith(("/", "~"))
        or bool(re.match(r"^[A-Za-z]:[\\/]", value))
        or "/.worktrees/" in value
        or "\\.worktrees\\" in value
    )


def _path_from_string(value: str) -> Path | None:
    value = value.strip()
    if not value or not _looks_like_path(value):
        return None
    return _normalize_path(Path(_expand_environment_tokens(value)))


def _checkout_root_for_reference(path: Path) -> Path:
    path = _normalize_path(path)
    parts = path.parts

    for candidate in (path, *path.parents):
        if (candidate / "project.yaml").exists():
            return candidate

    if ".worktrees" in parts:
        index = parts.index(".worktrees")
        if index + 1 < len(parts):
            return Path(*parts[: index + 2])

    if ".venv" in parts:
        index = parts.index(".venv")
        if index > 0:
            return Path(*parts[:index])

    if path.name == "mcp" and path.parent.name == "src":
        return path.parent.parent

    if path.name == "capabilities" and path.parent.name == "project-brain":
        return path.parent.parent

    return path


def _env_maps(server_config: dict[str, Any]) -> list[dict[str, Any]]:
    maps: list[dict[str, Any]] = []
    for key in ("env", "environment"):
        env = server_config.get(key)
        if isinstance(env, dict):
            maps.append(env)
    return maps


def _extract_reference_paths(server_config: Any) -> set[Path]:
    if not isinstance(server_config, dict):
        return set()

    references: set[Path] = set()
    for key in ("cwd", "command"):
        value = server_config.get(key)
        if isinstance(value, str):
            path = _path_from_string(value)
            if path:
                references.add(path)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    path = _path_from_string(item)
                    if path:
                        references.add(path)

    for env in _env_maps(server_config):
        for env_key in ("AUGUR_ROOT", "AUGUR_CORE"):
            env_path = env.get(env_key)
            if isinstance(env_path, str):
                path = _path_from_string(env_path)
                if path:
                    references.add(path)

        pythonpath = env.get("PYTHONPATH")
        if isinstance(pythonpath, str):
            for raw_part in pythonpath.split(os.pathsep):
                path = _path_from_string(raw_part)
                if path:
                    references.add(path)

    return references


def _issue_for_reference(
    *,
    client_key: str,
    client_label: str,
    config_path: Path,
    server_name: str,
    reference: Path,
) -> McpConfigPathIssue | None:
    checkout_root = _checkout_root_for_reference(reference)

    if checkout_root.exists() and is_linked_worktree(checkout_root):
        return McpConfigPathIssue(
            kind="linked_worktree",
            client_key=client_key,
            client_label=client_label,
            config_path=config_path,
            server_name=server_name,
            referenced_path=checkout_root,
            detail="global MCP config references a linked worktree checkout",
        )

    if ".worktrees" in checkout_root.parts:
        return McpConfigPathIssue(
            kind="missing_path" if not checkout_root.exists() else "linked_worktree",
            client_key=client_key,
            client_label=client_label,
            config_path=config_path,
            server_name=server_name,
            referenced_path=checkout_root,
            detail="global MCP config references a worktree checkout path",
        )

    if not reference.exists() and reference.is_absolute():
        return McpConfigPathIssue(
            kind="missing_path",
            client_key=client_key,
            client_label=client_label,
            config_path=config_path,
            server_name=server_name,
            referenced_path=reference,
            detail="global MCP config references a missing local path",
        )

    return None


def scan_global_mcp_config_references(
    *,
    project_root: Path,
    config_catalog_path: Path | None = None,
) -> list[McpConfigPathIssue]:
    """Return unsafe path references from generated user-global MCP configs.

    Repo-local config targets with ``{repo_root}`` are intentionally skipped:
    those files are allowed to point at the active checkout or worktree.
    """
    root = project_root.resolve()
    catalog_path = config_catalog_path or root / "config" / "agents" / "ide_mcp_configs.yaml"
    if not catalog_path.exists():
        return []

    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    ides = catalog.get("ides", {}) if isinstance(catalog, dict) else {}
    issues: list[McpConfigPathIssue] = []
    seen: set[tuple[str, str, str, str]] = set()

    for client_key, ide_config in ides.items():
        if not isinstance(ide_config, dict):
            continue
        if ide_config.get("enabled") is False:
            continue
        if _is_repo_local_config(ide_config):
            continue

        config_path = _platform_config_path(ide_config.get("config_path"), root)
        if not config_path:
            continue

        config = _load_config(config_path, str(ide_config.get("config_format", "json")))
        if config is None:
            continue

        for server_name, server_config in _iter_augur_server_entries(config):
            for reference in _extract_reference_paths(server_config):
                issue = _issue_for_reference(
                    client_key=str(client_key),
                    client_label=str(ide_config.get("display_name") or client_key),
                    config_path=config_path,
                    server_name=server_name,
                    reference=reference,
                )
                if not issue:
                    continue
                marker = (
                    issue.kind,
                    issue.client_key,
                    issue.server_name,
                    str(issue.referenced_path),
                )
                if marker in seen:
                    continue
                seen.add(marker)
                issues.append(issue)

    return issues
