"""Tank CLI integration for routine-security autoloop."""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

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
import json
import shutil
import subprocess
from pathlib import Path


def is_tank_installed() -> bool:
    """Check if tank CLI is available via the CLI registry."""
    # Use the existing CLI integration infrastructure
    try:
        from src.mcp.augur_framework.tools.infrastructure.browse.cli import _check_cli_status, _build_cli_registry
        registry = _build_cli_registry()
        if "tank" not in registry:
            return False
        status = _check_cli_status("tank", registry["tank"])
        return status.get("installed", False)
    except Exception:
        # Fallback: direct PATH check
        return shutil.which("tank") is not None


def scan_skill_with_tank(skill_dir: Path) -> list[dict]:
    """Run tank scan --offline --json on a skill directory."""
    if not is_tank_installed():
        return []

    tank_bin = shutil.which("tank")
    if not tank_bin:
        return []

    findings = []
    try:
        proc = subprocess.run(
            [tank_bin, "scan", "--offline", "--json", str(skill_dir)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout)
            for issue in data.get("issues", []):
                findings.append({
                    "stage": "Tank",
                    "category_name": issue.get("category", "unknown"),
                    "severity": issue.get("severity", "info").lower(),
                    "file": issue.get("file", ""),
                    "line": issue.get("line", 0),
                    "message": issue.get("message", ""),
                    "pattern": issue.get("rule_id", ""),
                })
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        pass

    return findings
