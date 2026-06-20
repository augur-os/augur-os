"""Dynamic skill path resolution — eliminates hardcoded skill names in vault/docs access.

Self-ref:  get_own_data_dir(__file__)       → active vault data dir for my skill
Cross-ref: get_peer_data_dir(__file__, "x") → active vault data dir for x

Both work in full Augur mode and standalone mode (no src.config.paths available).
"""

from __future__ import annotations

import logging
from pathlib import Path, PurePosixPath

logger = logging.getLogger(__name__)

# Cache parsed SKILL.md frontmatter to avoid re-reading on every call
_deps_cache: dict[str, list[str]] = {}
_data_dir_cache: dict[str, str | None] = {}


def derive_skill_name(caller_file: str | Path) -> str:
    """Extract skill name from an absolute __file__ path.

    Walks up the path tree looking for the directory whose parent is
    named 'skills'. Returns that directory's name.

    Raises ValueError if the file is not inside a directory named skills.
    """
    parts = Path(caller_file).resolve().parts
    for i in range(len(parts) - 1, 0, -1):
        if parts[i - 1] == "skills":
            return parts[i]
    raise ValueError(f"Cannot derive skill name: {caller_file!r} is not inside a managed skills directory")


def _find_skill_root(caller_file: str | Path) -> Path:
    """Locate the skill root directory from a file path inside it."""
    parts = Path(caller_file).resolve().parts
    for i in range(len(parts) - 1, 0, -1):
        if parts[i - 1] == "skills":
            return Path(*parts[: i + 1])
    raise ValueError(f"Not inside a managed skills tree: {caller_file}")


def _resolve_vault_dir(skill_name: str) -> Path:
    """Resolve vault dir for a skill name — full Augur first, standalone fallback."""
    try:
        from src.config.paths import get_skill_data_dir

        return get_skill_data_dir(skill_name)
    except ImportError:
        from src.config.path_primitives import resolve_vault_standalone

        return resolve_vault_standalone() / skill_name
    except ValueError:
        try:
            from src.config.paths import (
                _VAULT_FIRST_SKILL_VAULT_DIRS,
                get_skill_vault_relative_dir,
                get_vault_dir,
            )
            from src.lib.brain_layout import join_brain_relative

            if skill_name in _VAULT_FIRST_SKILL_VAULT_DIRS:
                relative = get_skill_vault_relative_dir(skill_name)
                return join_brain_relative(get_vault_dir(), relative)
        except Exception:
            pass
        # validate_dir_name rejected the skill name — fall back to standalone
        from src.config.path_primitives import resolve_vault_standalone

        return resolve_vault_standalone() / skill_name


def _resolve_vault_subdir(dir_name: str) -> Path:
    """Resolve a direct subdirectory under the vault without skill-name validation."""
    try:
        from src.config.paths import get_vault_dir

        return get_vault_dir() / dir_name
    except ImportError:
        from src.config.path_primitives import resolve_vault_standalone

        return resolve_vault_standalone() / dir_name


def get_own_data_dir(caller_file: str | Path) -> Path:
    """Return the vault data directory for the skill containing caller_file.

    Usage in any skill script::

        from src.lib.skill_paths import get_own_data_dir
        DATA_DIR = get_own_data_dir(__file__)
    """
    skill_name = derive_skill_name(caller_file)
    data_dir = _read_data_dir_override(skill_name, caller_file)
    if data_dir and data_dir != skill_name:
        return _resolve_vault_subdir(data_dir)
    return _resolve_vault_dir(skill_name)


def _read_data_deps(skill_name: str, caller_file: str | Path) -> list[str]:
    """Read x-augur-data-deps from a skill's SKILL.md frontmatter."""
    if skill_name in _deps_cache:
        return _deps_cache[skill_name]

    deps: list[str] = []
    try:
        skill_root = _find_skill_root(caller_file)
        skill_md = skill_root / "SKILL.md"
        if skill_md.exists():
            from src.lib.frontmatter_utils import parse_frontmatter

            frontmatter, _ = parse_frontmatter(skill_md)
            if isinstance(frontmatter, dict):
                raw = frontmatter.get("x-augur-data-deps", [])
                if isinstance(raw, list):
                    deps = [str(d) for d in raw]
    except Exception:
        logger.debug("Could not read x-augur-data-deps for %s", skill_name)

    _deps_cache[skill_name] = deps
    return deps


def _read_data_dir_override(skill_name: str, caller_file: str | Path) -> str | None:
    """Read x-augur-data-dir from a skill's SKILL.md frontmatter."""
    if skill_name in _data_dir_cache:
        return _data_dir_cache[skill_name]

    data_dir: str | None = None
    try:
        skill_root = _find_skill_root(caller_file)
        skill_md = skill_root / "SKILL.md"
        if skill_md.exists():
            from src.lib.frontmatter_utils import parse_frontmatter

            frontmatter, _ = parse_frontmatter(skill_md)
            raw = frontmatter.get("x-augur-data-dir") if isinstance(frontmatter, dict) else None
            if isinstance(raw, str) and raw.strip():
                data_dir = _normalize_data_dir_override(skill_name, raw)
    except Exception:
        logger.debug("Could not read x-augur-data-dir for %s", skill_name)

    _data_dir_cache[skill_name] = data_dir
    return data_dir


def _normalize_data_dir_override(skill_name: str, raw: str) -> str | None:
    """Return a safe vault-relative override, ignoring malformed metadata."""
    value = raw.strip().replace("\\", "/")
    path = PurePosixPath(value)
    if " " in value or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        logger.warning("Ignoring invalid x-augur-data-dir for %s: %r", skill_name, raw)
        return None
    return path.as_posix()


def get_peer_data_dir(
    caller_file: str | Path,
    peer_skill: str,
    *,
    validate_declared: bool = True,
) -> Path:
    """Return the vault data directory for a peer skill, with declaration check.

    Args:
        caller_file:        __file__ of the calling script.
        peer_skill:         Name of the target skill (e.g. "career").
        validate_declared:  If True (default), asserts that peer_skill appears
                            in the caller skill's x-augur-data-deps frontmatter.

    Raises:
        ValueError: if peer_skill is not declared in x-augur-data-deps and
                    validate_declared is True.
    """
    if validate_declared:
        caller_skill = derive_skill_name(caller_file)
        declared = _read_data_deps(caller_skill, caller_file)
        if peer_skill not in declared:
            raise ValueError(
                f"Skill '{caller_skill}' accesses vault of '{peer_skill}' but does not "
                f"declare it in x-augur-data-deps. Add '{peer_skill}' to the "
                f"x-augur-data-deps list in the managed SKILL.md for {caller_skill}."
            )
    return _resolve_vault_dir(peer_skill)
