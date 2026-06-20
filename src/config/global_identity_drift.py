"""Audit and repair shared Augur global identity drift."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import shutil
import site
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from src.config.mcp_config_drift import scan_global_mcp_config_references
from src.config.runtime_identity import (
    GlobalIdentityLock,
    default_global_identity_lock_path,
    resolve_runtime_identity,
)


@dataclass(frozen=True)
class IdentityIssue:
    surface: str
    name: str
    path: Path
    expected: Path
    detail: str
    repairable: bool = False

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["path"] = str(self.path)
        data["expected"] = str(self.expected)
        return data


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_under(path: Path, root: Path) -> bool:
    try:
        _resolved(path).relative_to(_resolved(root))
    except ValueError:
        return False
    return True


def _is_worktree_path(path: Path, authority_root: Path) -> bool:
    resolved = _resolved(path)
    if _is_under(resolved, authority_root):
        return False
    normalized = resolved.as_posix()
    return "augur-wt-" in normalized or "/.worktrees/" in normalized


def _outside_authority(path: Path, authority_root: Path) -> bool:
    return not _is_under(path, authority_root)


def scan_editable_install_locations(
    *,
    pip_json: str,
    authority_root: Path,
) -> list[IdentityIssue]:
    """Return Augur editable installs that point at non-authority worktrees."""
    try:
        rows = json.loads(pip_json)
    except (TypeError, ValueError):
        rows = []
    if not isinstance(rows, list):
        rows = []

    expected = _resolved(authority_root)
    issues: list[IdentityIssue] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "")
        location = row.get("editable_project_location") or row.get("location")
        if not name.lower().startswith("augur") or not isinstance(location, str):
            continue
        path = _resolved(Path(location))
        if _outside_authority(path, expected):
            detail = (
                "editable install points at a worktree"
                if _is_worktree_path(path, expected)
                else "editable install points at a non-authority Augur checkout"
            )
            issues.append(
                IdentityIssue(
                    surface="editable-install",
                    name=name,
                    path=path,
                    expected=expected,
                    detail=detail,
                    repairable=True,
                )
            )
    return issues


def scan_pth_files(
    *,
    site_package_dirs: Iterable[Path],
    authority_root: Path,
) -> list[IdentityIssue]:
    """Return .pth entries that point at non-authority worktrees."""
    expected = _resolved(authority_root)
    issues: list[IdentityIssue] = []
    for site_dir in site_package_dirs:
        site_path = _resolved(Path(site_dir))
        if not site_path.exists():
            continue
        for pth in site_path.glob("*.pth"):
            with contextlib.suppress(OSError, UnicodeDecodeError):
                for line in pth.read_text(encoding="utf-8").splitlines():
                    raw = line.strip()
                    if not raw or raw.startswith("import "):
                        continue
                    candidate = Path(raw).expanduser()
                    path = _resolved(candidate if candidate.is_absolute() else pth.parent / candidate)
                    is_worktree = _is_worktree_path(path, expected)
                    is_augur_pth = "augur" in pth.name.lower()
                    if is_worktree or (is_augur_pth and _outside_authority(path, expected)):
                        detail = (
                            ".pth file points at a worktree"
                            if is_worktree
                            else ".pth file points at a non-authority Augur checkout"
                        )
                        issues.append(
                            IdentityIssue(
                                surface="pth",
                                name=str(pth),
                                path=path,
                                expected=expected,
                                detail=detail,
                                repairable=True,
                            )
                        )
    return issues


def scan_import_specs(*, authority_root: Path) -> list[IdentityIssue]:
    """Return Augur module specs that resolve to non-authority worktrees."""
    expected = _resolved(authority_root)
    issues: list[IdentityIssue] = []
    for module_name in ("augur_core", "augur_framework", "augur_shared"):
        spec = importlib.util.find_spec(module_name)
        origin = getattr(spec, "origin", None) if spec else None
        if not origin:
            continue
        path = _resolved(Path(origin))
        if _outside_authority(path, expected):
            detail = (
                "import spec resolves to a worktree"
                if _is_worktree_path(path, expected)
                else "import spec resolves outside the authority checkout"
            )
            issues.append(
                IdentityIssue(
                    surface="import-spec",
                    name=module_name,
                    path=path,
                    expected=expected,
                    detail=detail,
                    repairable=True,
                )
            )
    return issues


def _pip_editable_json(python_executable: str) -> str:
    result = subprocess.run(
        [python_executable, "-m", "pip", "list", "--editable", "--format=json"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout if result.returncode == 0 else "[]"


def _site_package_dirs() -> list[Path]:
    candidates: list[str] = []
    with contextlib.suppress(Exception):
        candidates.extend(site.getsitepackages())
    with contextlib.suppress(Exception):
        candidates.append(site.getusersitepackages())
    return [Path(candidate) for candidate in candidates if candidate]


def scan_global_identity_drift(
    *,
    project_root: Path | None = None,
    python_executable: str | None = None,
    site_package_dirs: Iterable[Path] | None = None,
    config_catalog_path: Path | None = None,
) -> list[IdentityIssue]:
    """Combine editable install, .pth, import-spec, and MCP config drift issues."""
    identity = resolve_runtime_identity(project_root)
    authority = identity.authority_root
    python = python_executable or sys.executable
    issues: list[IdentityIssue] = []

    issues.extend(
        scan_pth_files(
            site_package_dirs=site_package_dirs or _site_package_dirs(),
            authority_root=authority,
        )
    )
    issues.extend(
        scan_editable_install_locations(
            pip_json=_pip_editable_json(python),
            authority_root=authority,
        )
    )
    issues.extend(scan_import_specs(authority_root=authority))
    for issue in scan_global_mcp_config_references(
        project_root=authority,
        config_catalog_path=config_catalog_path,
    ):
        issues.append(
            IdentityIssue(
                surface="mcp-config",
                name=f"{issue.client_key}:{issue.server_name}",
                path=issue.referenced_path,
                expected=authority,
                detail=issue.detail,
                repairable=True,
            )
        )
    return issues


def repair_editable_identity(
    *,
    authority_root: Path,
    python_executable: str,
) -> subprocess.CompletedProcess[str]:
    """Reinstall shared editable Augur packages from the authority checkout."""
    authority = _resolved(authority_root)
    uv = shutil.which("uv")
    if uv:
        cmd = [
            uv,
            "pip",
            "install",
            "--python",
            python_executable,
            "-e",
            str(authority),
            "-e",
            str(authority / "src" / "mcp"),
        ]
    else:
        cmd = [
            python_executable,
            "-m",
            "pip",
            "install",
            "-e",
            str(authority),
            "-e",
            str(authority / "src" / "mcp"),
        ]

    with GlobalIdentityLock(default_global_identity_lock_path()):
        return subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=120)
