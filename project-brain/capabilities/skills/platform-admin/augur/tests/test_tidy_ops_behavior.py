"""Behavior tests for auto-tidy classification."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import make_test_ctx

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ops" / "tidy_ops.py"
_SPEC = importlib.util.spec_from_file_location("tidy_ops_behavior", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def test_d0_treats_markers_as_maintenance(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "skills" / "demo" / "scripts"
    src.mkdir(parents=True)
    (src / "tool.py").write_text(
        "# " "TODO_" "BUG(integration/high): investigate test marker\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "get_project_root", lambda: tmp_path)

    result = mod.scan(make_test_ctx(tmp_path, difficulty=0))

    assert result.issues
    assert {issue["kind"] for issue in result.issues} == {"maintenance"}


def test_d1_embedded_high_priority_marker_is_actionable(tmp_path: Path, monkeypatch) -> None:
    src = tmp_path / "skills" / "demo" / "scripts"
    src.mkdir(parents=True)
    (src / "tool.py").write_text(
        "value = '" "TODO_" "BUG(integration/high): investigate test marker'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "get_project_root", lambda: tmp_path)

    result = mod.scan(make_test_ctx(tmp_path, difficulty=1))

    assert result.issues[0]["kind"] == "actionable"
