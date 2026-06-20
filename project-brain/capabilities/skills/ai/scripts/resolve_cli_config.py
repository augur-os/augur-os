"""Resolve CLI configurations from cli_agents.yaml for the dashboard API."""

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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import sys

import yaml


@dataclass
class CliConfig:
    """Configuration for a single CLI agent."""

    cli_id: str
    cmd: list[str]
    cwd: str
    env: dict[str, str] = field(default_factory=dict)
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cli_id": self.cli_id,
            "cmd": self.cmd,
            "cwd": self.cwd,
            "env": self.env,
            "label": self.label,
        }


# CLIs defined in cli_agents.yaml that are interactive agent CLIs
CLI_ENTRIES = {
    "claude": "Claude Code",
    "codex": "Codex",
    "copilot-cli": "GitHub Copilot CLI",
    "cursor-cli": "Cursor CLI",
    "kimi": "Kimi",
    "gemini": "Gemini",
    "opencode": "OpenCode",
    "claude-kimi": "Claude (Kimi model)",
}


def get_cli_agents_path() -> Path:
    """Get path to cli_agents.yaml in the vault config root."""
    from src.config.paths import get_vault_config_dir

    return get_vault_config_dir() / "ai" / "cli_agents.yaml"


def get_cli_configs(config_path: Path | None = None) -> dict[str, CliConfig]:
    """
    Read cli_agents.yaml and return CLI launch configurations.

    Args:
        config_path: Path to cli_agents.yaml. If None, auto-detected from the vault config dir.

    Returns:
        Dict mapping cli_id to CliConfig.

    Raises:
        FileNotFoundError: If cli_agents.yaml does not exist.
    """
    if config_path is None:
        config_path = get_cli_agents_path()

    if not config_path.exists():
        raise FileNotFoundError(f"cli_agents.yaml not found at {config_path}")

    with open(config_path) as f:
        data = yaml.safe_load(f)

    procs = data.get("agents", {})
    configs: dict[str, CliConfig] = {}

    for proc_name, proc_config in procs.items():
        if proc_name not in CLI_ENTRIES:
            continue

        cmd = proc_config.get("cmd", [])
        # Some entries use 'shell' instead of 'cmd' - skip those (they're shells, not CLIs)
        if not cmd:
            continue

        cwd = proc_config.get("cwd", ".")
        env = proc_config.get("env", {})
        label = CLI_ENTRIES[proc_name]

        configs[proc_name] = CliConfig(
            cli_id=proc_name,
            cmd=cmd,
            cwd=cwd,
            env=env,
            label=label,
        )

    return configs


if __name__ == "__main__":
    import json

    configs = get_cli_configs()
    sys.stdout.write(f"{json.dumps({k: v.to_dict() for k, v in configs.items()}, indent=2)}\n")
