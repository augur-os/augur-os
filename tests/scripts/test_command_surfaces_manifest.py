from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = PROJECT_ROOT / "config" / "system" / "command_surfaces.yaml"
MODULE_PATH = (
    PROJECT_ROOT
    / "project-brain"
    / "capabilities"
    / "skills"
    / "platform-admin"
    / "scripts"
    / "command_surface_lint.py"
)
SPEC = importlib.util.spec_from_file_location("command_surface_lint", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
lint = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = lint
SPEC.loader.exec_module(lint)


def test_manifest_declares_launcher_surfaces() -> None:
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    for name, mode in {"xa": "codex", "ca": "claude", "ga": "gemini"}.items():
        surface = data["surfaces"][name]
        assert set(surface["platforms"]) == {"windows", "posix"}
        assert surface["canonical_engine"] == {
            "type": "python",
            "module": "src.scripts.agent_launch",
            "mode": mode,
        }
        assert surface["adapters"]["windows"].endswith(f"{name}-launch.ps1")
        assert surface["adapters"]["posix"].endswith(f"{name}-launch.sh")
        assert surface["tests"]
    assert "--desktop" in data["surfaces"]["xa"]["description"]


def test_committed_manifest_lints_cleanly() -> None:
    issues = lint.lint_manifest(PROJECT_ROOT, MANIFEST)
    assert issues == []
