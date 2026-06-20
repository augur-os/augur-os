"""Tests for auto-view-schema scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import yaml

from src.lib.ops_protocol import OpsContext, ScanResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "view_schema.py"
_SPEC = importlib.util.spec_from_file_location("view_schema_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-view-schema"


def test_scan_no_views_dir(tmp_path: Path) -> None:
    with patch.object(mod, "get_runtime_dir", return_value=tmp_path):
        result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []


def test_scan_valid_view(tmp_path: Path) -> None:
    """Valid view YAML produces no issues."""
    views_dir = tmp_path / "views"
    _write(
        views_dir / "test.yaml",
        yaml.dump({
            "title": "Test View",
            "blocks": [],
            "layout": {"columns": 3, "rowHeight": 200},
        }),
    )
    with patch.object(mod, "get_runtime_dir", return_value=tmp_path):
        result = mod.scan(_ctx(tmp_path))
    assert result.issues == []


def test_scan_detects_missing_fields(tmp_path: Path) -> None:
    """View YAML missing required fields is flagged."""
    views_dir = tmp_path / "views"
    _write(views_dir / "bad.yaml", yaml.dump({"title": "Incomplete View"}))
    with patch.object(mod, "get_runtime_dir", return_value=tmp_path):
        result = mod.scan(_ctx(tmp_path))
    missing = [i for i in result.issues if i["type"] == "missing_field"]
    assert len(missing) >= 2  # missing blocks and layout


def test_check_grid_overlaps_detects_collision() -> None:
    """Two blocks at the same position produce an overlap issue."""
    blocks = [
        {"instanceId": "a", "position": {"x": 0, "y": 0, "w": 2, "h": 2}},
        {"instanceId": "b", "position": {"x": 1, "y": 1, "w": 2, "h": 2}},
    ]
    overlaps = mod._check_grid_overlaps(blocks)
    assert len(overlaps) == 1
    assert overlaps[0] == ("a", "b")


def test_check_grid_overlaps_no_collision() -> None:
    """Non-overlapping blocks produce no issues."""
    blocks = [
        {"instanceId": "a", "position": {"x": 0, "y": 0, "w": 2, "h": 2}},
        {"instanceId": "b", "position": {"x": 3, "y": 0, "w": 2, "h": 2}},
    ]
    overlaps = mod._check_grid_overlaps(blocks)
    assert overlaps == []
