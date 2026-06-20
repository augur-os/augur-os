"""sync_agents/adapters/gemini_plugin.py — Gemini plugin bundle adapter."""
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
import uuid
from pathlib import Path
from types import ModuleType

from .base import BaseAdapter
from ..constants import PROJECT_ROOT

_PLUGIN_PACK_MODULES = (
    "plugin_assembler",
    "profiles",
    "formatters",
    "formatters.base",
    "formatters.codex",
    "formatters.cowork",
    "formatters.antigravity",
)


def _checkout_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _plugin_pack_scripts_dir(
    project_root: Path,
    *,
    checkout_root: Path | None = None,
) -> Path:
    from src.lib.staged_skill_catalog import find_skill_dir

    roots = [checkout_root or _checkout_root(), project_root]
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        skill_dir = find_skill_dir(root, "plugin-pack")
        if skill_dir is not None:
            return skill_dir / "scripts"

    else:
        raise FileNotFoundError(
            "plugin-pack skill payload not found in repo or vault skills"
        )


class GeminiPluginAdapter(BaseAdapter):
    """Assembles and installs the Augur plugin bundle for Gemini."""

    adapter_name = "gemini_plugin"

    def __init__(self) -> None:
        super().__init__()
        self._output_dir = PROJECT_ROOT / "build" / "gemini"

    def get_managed_files(self) -> list[str]:
        return [
            str(self._output_dir) + "/",
            str(self._extension_dir()) + "/",
        ]

    @staticmethod
    def _extension_dir() -> Path:
        return Path.home() / ".antigravity" / "plugins" / "augur"

    def detect_installed(self) -> bool:
        return shutil.which("gemini") is not None or (Path.home() / ".antigravity").is_dir()


    def sync_rules(self, content: str) -> None:
        pass

    def sync_memory(self) -> None:
        pass

    def cleanup(self, exclude_paths: set[Path] | None = None, dry_run: bool = False) -> list[str]:
        exclude_paths = {path.resolve() for path in (exclude_paths or set())}
        deleted: list[str] = []

        output_dir = self._output_dir
        if output_dir.exists() and output_dir.resolve() not in exclude_paths:
            deleted.append(str(self._output_dir) + "/")
            if not dry_run:
                shutil.rmtree(self._output_dir)

        extension_dir = self._extension_dir()
        if (
            (extension_dir.exists() or extension_dir.is_symlink())
            and extension_dir.resolve() not in exclude_paths
        ):
            deleted.append(str(extension_dir) + "/")
            if not dry_run:
                if extension_dir.is_dir() and not extension_dir.is_symlink():
                    shutil.rmtree(extension_dir)
                else:
                    extension_dir.unlink()

        return deleted

    def generate_mcp_config(self) -> ModuleType:
        """Assemble and install the Gemini plugin bundle."""
        scripts_dir = _plugin_pack_scripts_dir(PROJECT_ROOT)
        scripts_path = str(scripts_dir)
        added_scripts_path = scripts_path not in sys.path
        if added_scripts_path:
            sys.path.insert(0, scripts_path)

        saved_modules = {
            name: sys.modules.pop(name)
            for name in _PLUGIN_PACK_MODULES
            if name in sys.modules
        }
        try:
            import importlib.util

            module_name = f"_augur_gemini_plugin_assembler_{uuid.uuid4().hex}"
            spec = importlib.util.spec_from_file_location(
                module_name,
                scripts_dir / "plugin_assembler.py",
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Unable to load plugin assembler from {scripts_dir}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            output, version = module.assemble("gemini", self._output_dir)
            module.install("gemini", output, version)
            return module
        finally:
            for name in _PLUGIN_PACK_MODULES:
                if name in sys.modules:
                    del sys.modules[name]
            sys.modules.update(saved_modules)
            if added_scripts_path:
                try:
                    sys.path.remove(scripts_path)
                except ValueError:
                    pass
