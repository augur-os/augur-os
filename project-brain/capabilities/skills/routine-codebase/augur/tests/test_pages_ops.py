"""Tests for auto-test-pages vertical."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

from src.config.paths import get_runtime_dir
from src.lib.ops_protocol import make_test_ctx


def _load_module():
    """Load test_pages_ops from hyphenated skill directory."""
    skill_dir = Path(__file__).resolve().parents[2]
    module_file = skill_dir / "scripts" / "test_pages_ops.py"
    spec = importlib.util.spec_from_file_location("test_pages_ops", module_file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["test_pages_ops"] = mod
    spec.loader.exec_module(mod)
    return mod


_mod = _load_module()
scan = _mod.scan
fix = _mod.fix


def _write_registry(tmp_path, slugs):
    """Write the Workspace catch-all route registry with the given page slugs.

    Mirrors the mount-plugins-generated ``app/workspace/[[...slug]]/registry.ts``
    that ADR-802 made the live source of mounted page slugs.
    """
    registry_dir = tmp_path / "apps/dashboard/app/workspace/[[...slug]]"
    registry_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "export const PAGES: Record<string, () => Promise<{ default: React.ComponentType }>> = {",
    ]
    lines += [f"  '{slug}': () => import('@/features/pages/workspace/{slug}/page')," for slug in slugs]
    lines.append("};")
    (registry_dir / "registry.ts").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_scan_no_registry(tmp_path):
    result = scan(make_test_ctx(tmp_path))
    assert result.severity == "info"
    assert "No Workspace route registry" in result.summary


def test_scan_uses_shared_snapshot_when_registry_missing(tmp_path):
    result = scan(
        make_test_ctx(
            tmp_path,
            shared_snapshot={"page_routes": ["/workspace/rag", "/workspace/insights"]},
        )
    )
    assert result.severity == "info"
    assert "shared snapshot loaded" in result.summary


def test_scan_all_pages_ok(tmp_path):
    _write_registry(tmp_path, ["rag", "insights"])
    with patch.object(_mod, "check_http_route") as mock_check:
        mock_check.return_value = {"ok": True, "status": 200}
        result = scan(make_test_ctx(tmp_path, difficulty=1))
    assert result.severity == "info"
    assert mock_check.call_count == 3  # 1 probe + 2 page routes


def test_scan_page_fails(tmp_path):
    _write_registry(tmp_path, ["rag"])
    with patch.object(_mod, "check_http_route") as mock_check:
        # Probe succeeds, page route fails
        mock_check.side_effect = [
            {"ok": True, "status": 200},       # base_url probe
            {"ok": False, "status": 404, "error": "Not Found"},  # /workspace/rag route
        ]
        result = scan(make_test_ctx(tmp_path, difficulty=1))
    assert result.severity == "error"
    assert len(result.issues) == 1


def test_scan_hub_scoped(tmp_path):
    _write_registry(tmp_path, ["rag", "insights"])
    with patch.object(_mod, "check_http_route") as mock_check:
        mock_check.return_value = {"ok": True, "status": 200}
        ctx = make_test_ctx(tmp_path, difficulty=1)
        ctx.config["hub"] = "rag"
        scan(ctx)
    assert mock_check.call_count == 2  # 1 probe + 1 page route (rag only)


def test_fix_dry_run(tmp_path):
    ctx = make_test_ctx(tmp_path, dry_run=True)
    result = fix(ctx, [{"hub": "rag", "error": "404"}])
    assert result.success
    assert "Dry run" in result.summary


def test_fix_writes_report(tmp_path):
    result = fix(make_test_ctx(tmp_path), [{"hub": "rag", "error": "404"}])
    assert result.success
    report = get_runtime_dir() / "reports" / "test-pages-latest.json"
    assert report.exists()
