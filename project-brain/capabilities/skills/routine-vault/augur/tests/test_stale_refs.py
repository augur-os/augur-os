"""Tests for auto-stale-refs scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import yaml

from src.lib.ops_protocol import OpsContext, ScanResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "stale_refs.py"
_SPEC = importlib.util.spec_from_file_location("stale_refs_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_scan_no_plugins(tmp_path: Path) -> None:
    result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []


def test_scan_detects_stale_page_ref(tmp_path: Path) -> None:
    """Action referencing a non-existent page route is flagged."""
    skill_dir = tmp_path / "skills" / "browse"
    action_dir = skill_dir / "assets" / "actions"
    _write(
        action_dir / "open-page.yaml",
        yaml.dump({"id": "open-page", "page": "/nonexistent/page"}),
    )

    with patch.object(mod, "get_all_client_skill_dirs", return_value=[tmp_path / "skills"]):
        with patch.object(mod, "get_skill_assets_dir", return_value=skill_dir / "assets"):
            with patch.object(mod, "get_skill_data_dir", return_value=tmp_path / "nodata"):
                result = mod.scan(_ctx(tmp_path))
    stale = [i for i in result.issues if i["type"] == "stale_page_ref"]
    assert len(stale) == 1
    assert stale[0]["page"] == "/nonexistent/page"


def test_scan_no_issue_when_page_exists(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "browse"
    action_dir = skill_dir / "assets" / "actions"
    _write(
        action_dir / "open-page.yaml",
        yaml.dump({"id": "open-page", "page": "/browse"}),
    )
    _write(
        tmp_path / "apps" / "dashboard" / "app" / "browse" / "page.tsx",
        "export default function() {}",
    )

    with patch.object(mod, "get_all_client_skill_dirs", return_value=[tmp_path / "skills"]):
        with patch.object(mod, "get_skill_assets_dir", return_value=skill_dir / "assets"):
            with patch.object(mod, "get_skill_data_dir", return_value=tmp_path / "nodata"):
                result = mod.scan(_ctx(tmp_path))
    stale = [i for i in result.issues if i["type"] == "stale_page_ref"]
    assert stale == []


def test_scan_detects_stale_block_ref(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "browse"
    action_dir = skill_dir / "assets" / "actions"
    _write(
        action_dir / "expand-block.yaml",
        yaml.dump({"id": "expand-block", "block": "nonexistent:block"}),
    )

    with patch.object(mod, "get_all_client_skill_dirs", return_value=[tmp_path / "skills"]):
        with patch.object(mod, "get_skill_assets_dir", return_value=skill_dir / "assets"):
            with patch.object(mod, "get_skill_data_dir", return_value=tmp_path / "nodata"):
                result = mod.scan(_ctx(tmp_path))
    stale = [i for i in result.issues if i["type"] == "stale_block_ref"]
    assert len(stale) == 1
