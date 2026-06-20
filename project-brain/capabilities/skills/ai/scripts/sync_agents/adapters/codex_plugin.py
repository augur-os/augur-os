"""sync_agents/adapters/codex_plugin.py — Codex plugin bundle adapter."""
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
import sys
from pathlib import Path

from .base import BaseAdapter
from ..constants import CODEX_HOME, PROJECT_ROOT, logger


def _plugin_pack_scripts_dir(project_root: Path) -> Path:
    from src.lib.staged_skill_catalog import find_skill_dir
    skill_dir = find_skill_dir(project_root, "plugin-pack")
    if skill_dir is None:
        raise FileNotFoundError(
            "plugin-pack skill payload not found in repo or vault skills"
        )
    return skill_dir / "scripts"


class CodexPluginAdapter(BaseAdapter):
    """Assembles and installs the Augur plugin bundle for Codex."""

    adapter_name = "codex_plugin"

    def __init__(self) -> None:
        super().__init__()
        self._output_dir = PROJECT_ROOT / "build" / "codex"

    def get_managed_files(self) -> list[str]:
        return [
            str(self._output_dir) + "/",
            str(PROJECT_ROOT / ".codex" / "plugins" / "cache" / "augur-local") + "/",
            str(CODEX_HOME / "plugins" / "cache" / "augur-local") + "/",
            str(PROJECT_ROOT / "plugins" / "augur") + "/",
            str(PROJECT_ROOT / ".agents" / "plugins" / "marketplace.json"),
        ]

    def detect_installed(self) -> bool:
        import shutil as _shutil
        if _shutil.which("codex") is not None:
            return True
        home = Path.home()
        system_root = Path(home.anchor or "/")
        return any(
            p.exists()
            for p in [
                home / "Applications" / "Codex.app",
                system_root / "Applications" / "Codex.app",
            ]
        )

    def sync_rules(self, content: str) -> None:
        pass  # Plugin bundle carries its own instructions

    def sync_memory(self) -> None:
        pass

    def cleanup(self, exclude_paths: set[Path] | None = None, dry_run: bool = False) -> list[str]:
        deleted: list[str] = []

        # Build output dir
        if self._output_dir.exists():
            deleted.append(str(self._output_dir) + "/")
            if not dry_run:
                shutil.rmtree(self._output_dir)

        # Cache dir
        codex_cache = PROJECT_ROOT / ".codex" / "plugins" / "cache" / "augur-local"
        if codex_cache.exists():
            deleted.append(str(codex_cache) + "/")
            if not dry_run:
                shutil.rmtree(codex_cache)

        runtime_cache = CODEX_HOME / "plugins" / "cache" / "augur-local"
        if runtime_cache.resolve() != codex_cache.resolve() and runtime_cache.exists():
            deleted.append(str(runtime_cache) + "/")
            if not dry_run:
                shutil.rmtree(runtime_cache)

        # Local plugin copy beside marketplace
        local_plugin = PROJECT_ROOT / "plugins" / "augur"
        if local_plugin.exists():
            deleted.append(str(local_plugin) + "/")
            if not dry_run:
                shutil.rmtree(local_plugin)

        # Surgical edit: remove augur entry from .agents/plugins/marketplace.json
        agents_mp = PROJECT_ROOT / ".agents" / "plugins" / "marketplace.json"
        if agents_mp.exists():
            try:
                data = json.loads(agents_mp.read_text(encoding="utf-8"))
                plugins = data.get("plugins", [])
                if isinstance(plugins, list) and any(p.get("name") == "augur" for p in plugins):
                    deleted.append(str(agents_mp))
                    if not dry_run:
                        remaining = [p for p in plugins if p.get("name") != "augur"]
                        if remaining:
                            data["plugins"] = remaining
                            agents_mp.write_text(
                                json.dumps(data, indent=2) + "\n", encoding="utf-8"
                            )
                        else:
                            agents_mp.unlink()
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("Failed to clean %s: %s", agents_mp, e)

        return deleted

    def generate_mcp_config(self) -> None:
        """Assemble and install the Codex plugin bundle."""
        scripts_path = str(_plugin_pack_scripts_dir(PROJECT_ROOT))
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)

        from plugin_assembler import assemble, install

        output, version = assemble("codex", self._output_dir)
        install("codex", output, version)
        repo_cache_dir = PROJECT_ROOT / ".codex" / "plugins" / "cache"
        runtime_cache_dir = CODEX_HOME / "plugins" / "cache"
        if runtime_cache_dir.resolve() != repo_cache_dir.resolve():
            install(
                "codex",
                output,
                version,
                cache_dir=runtime_cache_dir,
                global_marketplace_dir=PROJECT_ROOT / ".agents" / "plugins",
            )
