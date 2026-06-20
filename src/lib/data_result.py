"""DataResult — vault-first data loader with seed fallback and diagnostic status.

Usage in any skill script::

    from src.lib.data_result import read_skill_data

    result = read_skill_data(__file__, "items.yaml", default=[])
    # result.source  → "vault" | "seed" | "default"
    # result.vault_status → "ok" | "missing_dir" | "no_file" | "empty_file"
    # result.data    → loaded data or default value

ADR: governed by the DataResult & Seed Transparency plan.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.lib.frontmatter_utils import load_collection
from src.lib.skill_paths import _find_skill_root, get_own_data_dir
from src.logging import get_entity_logger

logger = get_entity_logger("lib.data_result")

# Vault status literals
_STATUS_OK = "ok"
_STATUS_MISSING_DIR = "missing_dir"
_STATUS_NO_FILE = "no_file"
_STATUS_EMPTY_FILE = "empty_file"


@dataclass
class DataResult:
    """Result of a skill data read operation.

    Attributes:
        data:         Loaded data (or the default value if nothing was found).
        source:       Where data came from — "vault", "seed", or "default".
        vault_status: Diagnostic state of the vault path — "ok", "missing_dir",
                      "no_file", or "empty_file".
        vault_path:   Absolute path to the vault file/directory that was checked.
                      None if vault dir resolution itself failed.
        seed_path:    Absolute path to the seed file that was used or checked.
                      None if seed lookup was not attempted or seed not found.
    """

    data: Any
    source: str
    vault_status: str
    vault_path: Path | None = None
    seed_path: Path | None = None


def _diagnose_vault(vault_path: Path, loader: str) -> str:
    """Return a diagnostic status string for the given vault path.

    For collection loader the path is a directory; for yaml/json it is a file.

    For collections, a directory that exists but contains ONLY seed-copied files
    (``source: seed`` in frontmatter) is treated as ``no_file`` — the user has
    no real data there, so the caller should fall back to seeds served from
    plugin source.

    Returns:
        "ok"          — path exists and has user content.
        "missing_dir" — parent directory (vault dir itself) does not exist.
        "no_file"     — vault dir exists but the target file/dir is absent
                        or contains only seed copies.
        "empty_file"  — file exists but is empty (zero bytes or whitespace only).
    """
    if loader == "collection":
        # For collections the vault_path IS the directory to scan.
        if not vault_path.parent.exists():
            return _STATUS_MISSING_DIR
        if not vault_path.exists():
            return _STATUS_NO_FILE
        # Directory exists — check for non-seed .md files
        from src.lib.frontmatter_utils import _is_seed_file

        user_files = [f for f in vault_path.glob("*.md") if f.is_file() and not _is_seed_file(f)]
        if not user_files:
            return _STATUS_NO_FILE
        return _STATUS_OK
    else:
        # File-based loaders (yaml, json)
        parent = vault_path.parent
        if not parent.exists():
            return _STATUS_MISSING_DIR
        if not vault_path.exists():
            return _STATUS_NO_FILE
        content = vault_path.read_text(encoding="utf-8")
        if not content.strip():
            return _STATUS_EMPTY_FILE
        return _STATUS_OK


def _load(path: Path, loader: str, default: Any, *, exclude_seeds: bool = False) -> Any:
    """Load data from path using the specified loader.

    Args:
        path:          File or directory path to load from.
        loader:        "yaml", "json", or "collection".
        default:       Value to return if loading produces no data.
        exclude_seeds: If True and loader is "collection", skip files with
                       ``source: seed`` in frontmatter.

    Returns:
        Loaded data, or default if the result is falsy/None.
    """
    try:
        if loader == "yaml":
            content = path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
            return data if data is not None else default
        elif loader == "json":
            content = path.read_text(encoding="utf-8")
            return json.loads(content)
        elif loader == "collection":
            items = load_collection(path, exclude_seeds=exclude_seeds)
            return items if items else default
        else:
            raise ValueError(f"Unknown loader: {loader!r}")
    except Exception:
        logger.exception("Failed to load %s with loader=%r", path, loader)
        return default


def get_skill_seed_path(caller_file: str | Path, filename: str) -> Path:
    """Resolve a bundled seed path relative to the calling skill root."""
    return _find_skill_root(caller_file) / "assets" / "seeds" / filename


def read_path_data(
    vault_path: Path,
    *,
    seed_path: Path | None = None,
    default: Any = None,
    loader: str = "yaml",
) -> DataResult:
    """Read data from explicit vault and seed paths with DataResult diagnostics."""
    vault_status = _diagnose_vault(vault_path, loader)

    if vault_status == _STATUS_OK:
        data = _load(vault_path, loader, default, exclude_seeds=True)
        return DataResult(
            data=data,
            source="vault",
            vault_status=vault_status,
            vault_path=vault_path,
            seed_path=None,
        )

    if seed_path and seed_path.exists():
        data = _load(seed_path, loader, default)
        return DataResult(
            data=data,
            source="seed",
            vault_status=vault_status,
            vault_path=vault_path,
            seed_path=seed_path,
        )

    return DataResult(
        data=default,
        source="default",
        vault_status=vault_status,
        vault_path=vault_path,
        seed_path=seed_path if seed_path and seed_path.exists() else None,
    )


def read_skill_data(
    caller_file: str | Path,
    filename: str,
    default: Any = None,
    *,
    loader: str = "yaml",
) -> DataResult:
    """Read skill data using vault-first loading with seed fallback.

    Resolution order:
      1. Vault path (via get_own_data_dir) — used if file/dir exists and is non-empty.
      2. Seed path ({skill_root}/assets/seeds/{filename}) — fallback.
      3. Default value — if neither vault nor seed is available.

    Args:
        caller_file:  __file__ of the calling script (used for path resolution).
        filename:     Name of the file (or directory for collection loader) to load.
        default:      Value returned when no data source is found.
        loader:       One of "yaml", "json", or "collection".

    Returns:
        DataResult with data, source, vault_status, vault_path, and seed_path.
    """
    vault_dir: Path = get_own_data_dir(caller_file)
    vault_path: Path = vault_dir / filename
    seed_path = get_skill_seed_path(caller_file, filename)
    return read_path_data(vault_path, seed_path=seed_path, default=default, loader=loader)
