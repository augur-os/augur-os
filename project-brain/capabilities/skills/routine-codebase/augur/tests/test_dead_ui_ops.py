"""Tests for auto-dead-ui scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from src.lib.ops_protocol import OpsContext, ScanResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dead_ui_ops.py"
_SPEC = importlib.util.spec_from_file_location("dead_ui_ops_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def _shared_skills(tmp_path: Path) -> Path:
    return tmp_path / "project-brain" / "capabilities" / "skills"


def test_scan_no_pages(tmp_path: Path) -> None:
    result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []
    assert "No dashboard pages" in result.summary


def test_scan_d0_surface_count(tmp_path: Path) -> None:
    """d0 counts interactive elements without checking correctness."""
    _write(
        _shared_skills(tmp_path) / "browse" / "augur" / "dashboard" / "page.tsx",
        'export default function Page() { return <button onClick={() => {}}>Click</button>; }',
    )
    result = mod.scan(_ctx(tmp_path, difficulty=0))
    assert result.issues == []
    assert "surface" in result.summary.lower()


def test_scan_d1_detects_empty_handler(tmp_path: Path) -> None:
    """d1 flags empty onClick handlers."""
    _write(
        _shared_skills(tmp_path) / "browse" / "augur" / "dashboard" / "page.tsx",
        'export default function Page() { return <button onClick={() => {}}>Click</button>; }',
    )
    result = mod.scan(_ctx(tmp_path, difficulty=1))
    empty = [i for i in result.issues if i["type"] == "empty_handler"]
    assert len(empty) == 1


def test_scan_d1_detects_console_only_handler(tmp_path: Path) -> None:
    """d1 flags handlers that only log to console."""
    _write(
        _shared_skills(tmp_path) / "browse" / "augur" / "dashboard" / "page.tsx",
        'export default function Page() { return <button onClick={() => { console.log("hi") }}>Click</button>; }',
    )
    result = mod.scan(_ctx(tmp_path, difficulty=1))
    console = [i for i in result.issues if i["type"] == "console_only"]
    assert len(console) == 1


def test_scan_d2_detects_broken_href(tmp_path: Path) -> None:
    """d2 flags href links to non-existent pages."""
    _write(
        _shared_skills(tmp_path) / "browse" / "augur" / "dashboard" / "page.tsx",
        'export default function Page() { return <a href="/nonexistent/page">Link</a>; }',
    )
    result = mod.scan(_ctx(tmp_path, difficulty=2))
    broken = [i for i in result.issues if i["type"] == "broken_link"]
    assert len(broken) == 1
    assert broken[0]["href"] == "/nonexistent/page"
