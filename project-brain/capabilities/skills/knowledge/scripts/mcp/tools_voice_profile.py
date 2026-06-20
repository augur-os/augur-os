"""Voice-profile MCP tools for ADR-729.

The agent conducts the interview and uses vault-write after each answer. These
tools expose profile state, final profile reads, final writes, and age metadata
to the dashboard and command surfaces.
"""
from __future__ import annotations

import importlib.util as _augur_importlib_util
import json
import sys as _augur_sys
from datetime import datetime, timezone
from pathlib import Path as _AugurPath
from typing import TYPE_CHECKING, Any, Callable

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)

TOOLS_DIR = _AugurPath(__file__).resolve().parent
SCRIPTS_DIR = TOOLS_DIR.parent
if str(SCRIPTS_DIR) not in _augur_sys.path:
    _augur_sys.path.insert(0, str(SCRIPTS_DIR))

from profile_state import (  # noqa: E402
    SUPPORTED_LANGUAGES,
    about_me_path,
    archive_dir,
    archive_state,
    get_about_me_age_days,
    load_state,
    normalize_language,
    state_path,
    write_about_me,
)
from src.lib.frontmatter_utils import parse_frontmatter  # noqa: E402

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from src.mcp.augur_shared.annotations import tool_annotations
except ImportError:

    def tool_annotations(annotations: dict) -> dict:
        return annotations

try:
    from src.mcp.augur_shared.logging import get_entity_logger
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        return logging.getLogger(name)


logger = get_entity_logger("mcp.knowledge.voice_profile")


def _resolve_vault_dir() -> _AugurPath:
    from src.config.paths import get_vault_dir

    return get_vault_dir()


def _mtime_iso(path: _AugurPath) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _language_paths(language: str, *, vault_dir: _AugurPath | None = None) -> tuple[_AugurPath, _AugurPath, _AugurPath]:
    vault = vault_dir or _resolve_vault_dir()
    lang = normalize_language(language)
    return state_path(vault, lang), about_me_path(vault, lang), archive_dir(vault, lang)


def _profile_status_sync(
    *,
    language: str,
    state_file: _AugurPath,
    about_me_file: _AugurPath,
) -> dict[str, Any]:
    lang = normalize_language(language)
    state = load_state(state_file)
    about_exists = about_me_file.exists() and about_me_file.stat().st_size > 0
    answered = state.answered if state else 0
    total = state.total if state else 100
    percentage = state.percentage if state else 0
    about_mtime = _mtime_iso(about_me_file) if about_exists else None
    about_age = get_about_me_age_days(about_me_file) if about_exists else None

    return {
        "success": True,
        "language": lang,
        "in_progress": state is not None and not about_exists,
        "answered": answered,
        "total": total,
        "percentage": percentage,
        "started_at": state.started_at if state else None,
        "last_answered_at": state.last_answered_at if state else None,
        "complete": about_exists,
        "mode": state.mode if state else None,
        "about_me": {
            "exists": about_exists,
            "last_updated_at": about_mtime,
            "age_days": about_age,
            "size_bytes": about_me_file.stat().st_size if about_exists else None,
        },
    }


def _profile_status_all_sync(*, vault_dir: _AugurPath) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for language in SUPPORTED_LANGUAGES:
        state_file, about_me_file, _ = _language_paths(language, vault_dir=vault_dir)
        payload[language] = _profile_status_sync(
            language=language,
            state_file=state_file,
            about_me_file=about_me_file,
        )
    return payload


def _profile_read_sync(*, language: str, about_me_file: _AugurPath) -> dict[str, Any]:
    lang = normalize_language(language)
    if not about_me_file.exists():
        return {
            "success": False,
            "error": "profile_not_found",
            "language": lang,
            "hint": f"Run /profile interview and choose {lang} to create this voice profile.",
        }

    frontmatter, body = parse_frontmatter(about_me_file, include_sidecar_config=False)
    return {
        "success": True,
        "language": lang,
        "content": body.lstrip("\n"),
        "frontmatter": frontmatter,
        "metadata": {
            "last_updated_at": _mtime_iso(about_me_file),
            "age_days": get_about_me_age_days(about_me_file),
            "size_bytes": about_me_file.stat().st_size,
        },
    }


def _profile_write_sync(
    *,
    content: str,
    mode: str,
    language: str,
    about_me_file: _AugurPath,
    state_file: _AugurPath,
    target_archive_dir: _AugurPath,
) -> dict[str, Any]:
    lang = normalize_language(language)
    normalized_mode = (mode or "full").strip().lower()
    if normalized_mode not in {"full", "update", "manual"}:
        raise ValueError("mode must be 'full', 'update', or 'manual'")

    write_about_me(about_me_file, content, language=lang)
    archived_to: str | None = None
    if state_file.exists() and normalized_mode in {"full", "update"}:
        archived = archive_state(state_file, target_archive_dir)
        archived_to = str(archived) if archived else None

    return {
        "success": True,
        "language": lang,
        "mode": normalized_mode,
        "about_me_path": str(about_me_file),
        "archived_to": archived_to,
        "metadata": {
            "last_updated_at": _mtime_iso(about_me_file),
            "age_days": get_about_me_age_days(about_me_file),
            "size_bytes": about_me_file.stat().st_size,
        },
    }


def _profile_get_age_sync(*, language: str, about_me_file: _AugurPath) -> dict[str, Any]:
    lang = normalize_language(language)
    if not about_me_file.exists():
        return {"success": True, "language": lang, "exists": False}
    return {
        "success": True,
        "language": lang,
        "exists": True,
        "age_days": get_about_me_age_days(about_me_file),
        "last_updated_at": _mtime_iso(about_me_file),
    }


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def register_voice_profile_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register voice-profile tools with the MCP server."""
    logger.info("Registering voice-profile tools...")

    @mcp.tool(
        name="profile-status",
        annotations=tool_annotations(
            {
                "title": "Voice Profile Status",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def profile_status_tool(language: str | None = None) -> str:
        """Return interview progress and profile metadata for one or both languages."""
        metrics.track_tool("profile_status", skill="knowledge")
        try:
            if language is None:
                return _json(_profile_status_all_sync(vault_dir=_resolve_vault_dir()))
            state_file, about_me_file, _ = _language_paths(language)
            return _json(
                _profile_status_sync(
                    language=language,
                    state_file=state_file,
                    about_me_file=about_me_file,
                )
            )
        except Exception as exc:
            return _json({"success": False, "error": str(exc), "language": language})

    @mcp.tool(
        name="profile-read",
        annotations=tool_annotations(
            {
                "title": "Voice Profile Read",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def profile_read_tool(language: str) -> str:
        """Read vault/profile/<language>/about-me.md without frontmatter."""
        metrics.track_tool("profile_read", skill="knowledge")
        try:
            _, about_me_file, _ = _language_paths(language)
            return _json(_profile_read_sync(language=language, about_me_file=about_me_file))
        except Exception as exc:
            return _json({"success": False, "error": str(exc), "language": language})

    @mcp.tool(
        name="profile-write",
        annotations=tool_annotations(
            {
                "title": "Voice Profile Write",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def profile_write_tool(content: str, language: str, mode: str = "full") -> str:
        """Write vault/profile/<language>/about-me.md and archive in-progress state."""
        metrics.track_tool("profile_write", skill="knowledge")
        try:
            state_file, about_me_file, target_archive_dir = _language_paths(language)
            return _json(
                _profile_write_sync(
                    content=content,
                    mode=mode,
                    language=language,
                    about_me_file=about_me_file,
                    state_file=state_file,
                    target_archive_dir=target_archive_dir,
                )
            )
        except Exception as exc:
            return _json({"success": False, "error": str(exc), "language": language})

    @mcp.tool(
        name="profile-get-age",
        annotations=tool_annotations(
            {
                "title": "Voice Profile Age",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def profile_get_age_tool(language: str) -> str:
        """Return days since vault/profile/<language>/about-me.md changed."""
        metrics.track_tool("profile_get_age", skill="knowledge")
        try:
            _, about_me_file, _ = _language_paths(language)
            return _json(_profile_get_age_sync(language=language, about_me_file=about_me_file))
        except Exception as exc:
            return _json({"success": False, "error": str(exc), "language": language})
