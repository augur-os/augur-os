"""Regression tests for the auto-stale-routes scanner."""

from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "scan_stale_routes.py"
SPEC = importlib.util.spec_from_file_location("scan_stale_routes_module", MODULE_PATH)
assert SPEC and SPEC.loader
scan_stale_routes_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scan_stale_routes_module)


def test_check_route_exists_uses_apps_dashboard_root(tmp_path: Path) -> None:
    """Existing routes under apps/dashboard/app/api should be recognized."""
    route_file = tmp_path / "apps" / "dashboard" / "app" / "api" / "home" / "home-automation" / "lights" / "route.ts"
    route_file.parent.mkdir(parents=True)
    route_file.write_text("export async function GET() { return Response.json({ ok: true }); }\n")

    assert scan_stale_routes_module._check_route_exists(
        tmp_path,
        "/api/home/home-automation/lights",
    )


def test_scan_stale_routes_skips_existing_apps_dashboard_routes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Static hook URLs should not be flagged when their apps/dashboard route exists."""
    source_file = tmp_path / "plugins" / "home" / "skills" / "home-automation" / "augur" / "dashboard" / "page.tsx"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(
        'const lights = useCachedFetch("/api/home/home-automation/lights");\n',
        encoding="utf-8",
    )

    route_file = tmp_path / "apps" / "dashboard" / "app" / "api" / "home" / "home-automation" / "lights" / "route.ts"
    route_file.parent.mkdir(parents=True)
    route_file.write_text("export async function GET() { return Response.json({ ok: true }); }\n")

    monkeypatch.setattr(
        scan_stale_routes_module,
        "_find_files_using_hooks",
        lambda _project_root: {str(source_file)},
    )

    missing = scan_stale_routes_module.scan_stale_routes(tmp_path)

    assert missing == []


def test_scan_stale_routes_still_reports_truly_missing_routes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The fix should not hide real missing route references."""
    source_file = tmp_path / "plugins" / "ai" / "skills" / "knowledge" / "augur" / "dashboard" / "page.tsx"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(
        'const report = useCachedFetch("/api/ai/knowledge/memory/report");\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        scan_stale_routes_module,
        "_find_files_using_hooks",
        lambda _project_root: {str(source_file)},
    )

    missing = scan_stale_routes_module.scan_stale_routes(tmp_path)

    assert len(missing) == 1
    assert missing[0]["url"] == "/api/ai/knowledge/memory/report"


def test_scan_stale_routes_uses_shared_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_file = tmp_path / "plugins" / "home" / "skills" / "home-automation" / "augur" / "dashboard" / "page.tsx"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(
        'const lights = useCachedFetch("/api/home/home-automation/lights");\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        scan_stale_routes_module,
        "_find_files_using_hooks",
        lambda _project_root: {str(source_file)},
    )

    missing = scan_stale_routes_module.scan_stale_routes(
        tmp_path,
        shared_snapshot={"api_routes": ["/api/home/home-automation/lights"]},
    )

    assert missing == []
