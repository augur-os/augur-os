"""Tests for auto-block-wiring scan/fix protocol."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

from src.lib.ops_protocol import OpsContext, ScanResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "block_wiring.py"
_SPEC = importlib.util.spec_from_file_location("block_wiring_under_test", _MODULE_PATH)
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


def test_scan_no_plugins_dir(tmp_path: Path) -> None:
    result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.issues == []
    assert result.summary == "0 block wiring issue(s)"


def test_scan_detects_missing_datasource(tmp_path: Path) -> None:
    """Block with non-client-only type but no dataSource produces an issue."""
    _write(
        _shared_skills(tmp_path) / "browse" / "config.yaml",
        yaml.dump({
            "contributions": {
                "blocks": [{"id": "test:block", "type": "data-list"}],
            },
        }),
    )
    result = mod.scan(_ctx(tmp_path))
    assert len(result.issues) == 1
    assert result.issues[0]["type"] == "missing_datasource"


def test_scan_accepts_client_only_block_without_datasource(tmp_path: Path) -> None:
    """Client-only block types (markdown, notes) do not need dataSource."""
    _write(
        _shared_skills(tmp_path) / "browse" / "config.yaml",
        yaml.dump({
            "contributions": {
                "blocks": [{"id": "test:md", "type": "markdown"}],
            },
        }),
    )
    result = mod.scan(_ctx(tmp_path))
    assert result.issues == []


def test_scan_detects_missing_api_route(tmp_path: Path) -> None:
    """Block referencing a non-existent API route is flagged."""
    _write(
        _shared_skills(tmp_path) / "browse" / "config.yaml",
        yaml.dump({
            "contributions": {
                "blocks": [{
                    "id": "test:block",
                    "type": "data-list",
                    "dataSource": {"apiRoute": "/api/nonexistent"},
                }],
            },
        }),
    )
    result = mod.scan(_ctx(tmp_path))
    api_issues = [i for i in result.issues if i["type"] == "missing_api_route"]
    assert len(api_issues) == 1
    assert api_issues[0]["api_route"] == "/api/nonexistent"


def test_scan_clean_when_all_wired(tmp_path: Path) -> None:
    """No issues when blocks have valid dataSource and routes exist."""
    _write(
        _shared_skills(tmp_path) / "browse" / "config.yaml",
        yaml.dump({
            "mcp": {"tools": [{"name": "get-browse-data"}]},
            "contributions": {
                "blocks": [{
                    "id": "test:block",
                    "type": "data-list",
                    "dataSource": {"mcpTool": "get-browse-data"},
                }],
            },
        }),
    )
    result = mod.scan(_ctx(tmp_path))
    assert result.issues == []


def test_scan_accepts_expandto_route_from_plugin_page_source(tmp_path: Path) -> None:
    """expandTo is satisfied by a mounted plugin page, not only app/page.tsx files."""
    _write(
        tmp_path / "plugins" / "ui" / "pages" / "life" / "attention" / "page.tsx",
        "export default function Page() { return null; }\n",
    )
    _write(
        tmp_path / ".claude" / "skills" / "browse" / "config.yaml",
        yaml.dump({
            "mcp": {"tools": [{"name": "get-browse-data"}]},
            "contributions": {
                "blocks": [{
                    "id": "test:block",
                    "type": "data-list",
                    "expandTo": "/life/attention",
                    "dataSource": {"mcpTool": "get-browse-data"},
                }],
            },
        }),
    )

    result = mod.scan(_ctx(tmp_path))

    assert result.issues == []


def test_scan_clears_stale_report_on_clean(tmp_path: Path, monkeypatch) -> None:
    cleared: list[str] = []
    monkeypatch.setattr(mod, "clear_report", lambda filename: cleared.append(filename))

    _write(
        tmp_path / ".claude" / "skills" / "browse" / "config.yaml",
        yaml.dump({
            "mcp": {"tools": [{"name": "get-browse-data"}]},
            "contributions": {
                "blocks": [{
                    "id": "test:block",
                    "type": "data-list",
                    "dataSource": {"mcpTool": "get-browse-data"},
                }],
            },
        }),
    )

    result = mod.scan(_ctx(tmp_path))

    assert result.issues == []
    assert cleared == ["block-wiring-latest.json"]
