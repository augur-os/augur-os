"""sync_agents/adapters/copilot_plugin.py — Copilot .github bundle adapter."""
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
import shutil
import sys
from pathlib import Path

from .base import BaseAdapter
from ..constants import PROJECT_ROOT


def _plugin_pack_scripts_dir(project_root: Path) -> Path:
    from src.lib.staged_skill_catalog import find_skill_dir
    skill_dir = find_skill_dir(project_root, "plugin-pack")
    if skill_dir is None:
        raise FileNotFoundError(
            "plugin-pack skill payload not found in repo or vault skills"
        )
    return skill_dir / "scripts"


class CopilotPluginAdapter(BaseAdapter):
    """Assembles and installs the Augur .github asset bundle for GitHub Copilot.

    Produces .github/agents/, .github/skills/, .github/prompts/ via the
    plugin-pack copilot formatter; cleanup of those installed outputs is
    owned by CopilotAdapter's managed-files contract.
    """

    adapter_name = "copilot_plugin"

    def __init__(self) -> None:
        super().__init__()
        self._output_dir = PROJECT_ROOT / "build" / "copilot"

    def get_managed_files(self) -> list[str]:
        return [str(self._output_dir) + "/"]

    def detect_installed(self) -> bool:
        import shutil as _shutil
        if _shutil.which("copilot") is not None:
            return True
        return (Path.home() / ".copilot").exists()

    def sync_rules(self, content: str) -> None:
        pass  # .github/copilot-instructions.md is owned by CopilotAdapter

    def sync_memory(self) -> None:
        pass  # .github/copilot-memory.md is owned by CopilotAdapter

    def cleanup(self, exclude_paths: set[Path] | None = None, dry_run: bool = False) -> list[str]:
        deleted: list[str] = []
        if self._output_dir.exists():
            deleted.append(str(self._output_dir) + "/")
            if not dry_run:
                shutil.rmtree(self._output_dir)
        return deleted

    def _load_assembler(self):
        scripts_path = str(_plugin_pack_scripts_dir(PROJECT_ROOT))
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        from plugin_assembler import assemble, install
        return assemble, install

    def generate_mcp_config(self) -> None:
        """Assemble and install the Copilot .github bundle (agents/skills/prompts)."""
        assemble, install = self._load_assembler()
        output, version = assemble("copilot", self._output_dir)
        install("copilot", output, version)
