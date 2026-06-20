"""Auto-generated importability test for mcp_config."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import importlib
import importlib.util

REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SHARED_VAULT_ROOT = REPO_ROOT / "project-brain"
PLUGIN_PACK_ROOT = SHARED_VAULT_ROOT / "capabilities" / "skills" / "plugin-pack"
for _path in (REPO_ROOT, SHARED_VAULT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

MCP_SRC = REPO_ROOT / "src" / "mcp"
if str(MCP_SRC) not in sys.path:
    sys.path.insert(0, str(MCP_SRC))


def _import_mcp_config():
    package_name = "plugin_pack_formatters_testpkg"
    package_dir = PLUGIN_PACK_ROOT / "scripts" / "formatters"

    if package_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            package_name,
            package_dir / "__init__.py",
            submodule_search_locations=[str(package_dir)],
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[package_name] = module
        spec.loader.exec_module(module)

    return importlib.import_module(f"{package_name}.mcp_config")


def test_mcp_config_importable():
    """Verify that mcp_config can be imported without errors."""
    mod = _import_mcp_config()
    assert mod is not None


def test_resolve_project_python_path_prefers_windows_venv(tmp_path):
    mod = _import_mcp_config()
    python_exe = tmp_path / ".venv" / "Scripts" / "python.exe"
    python_exe.parent.mkdir(parents=True)
    python_exe.write_text("", encoding="utf-8")

    assert mod.resolve_project_python_path(tmp_path) == str(python_exe)


def test_build_augur_mcp_servers_filters_manifest_entries_by_policy(monkeypatch):
    from src.cli_config.manifest import Manifest, ServerEntry

    mod = _import_mcp_config()
    monkeypatch.setattr(
        mod,
        "load_manifest",
        lambda _path: Manifest(
            project_tier=[
                ServerEntry(
                    id="augur-core",
                    description="core",
                    command="python",
                    args=["-m", "augur_core"],
                ),
                ServerEntry(
                    id="augur-framework",
                    description="framework",
                    command="python",
                    args=["-m", "augur_framework"],
                ),
            ],
            vault_tier=[],
            monolith_exclusions=[],
        ),
    )
    monkeypatch.setattr(
        "src.cli_config.manifest.resolve_capability_records",
        lambda _discovered, *, policy=None: [
            SimpleNamespace(
                id="mcp-server:augur-core",
                classification_status="approved",
                export_to=("codex",),
                current_exposure=(),
            ),
            SimpleNamespace(
                id="mcp-server:augur-framework",
                classification_status="blocked",
                export_to=(),
                current_exposure=("codex",),
            ),
        ],
    )

    servers = mod.build_augur_mcp_servers(Path("/fake/root"), "/fake/python", "codex")

    assert set(servers) == {"augur-core"}
