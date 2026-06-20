"""Tests for shared adaptive snapshot builder."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from skills.daemon.scripts.adaptive.snapshot import build_shared_snapshot


def test_build_shared_snapshot_discovers_routes_and_skills(tmp_path):
    api_dir = tmp_path / "apps" / "dashboard" / "app" / "api" / "health"
    api_dir.mkdir(parents=True)
    (api_dir / "route.ts").write_text("export async function GET() {}\n")

    bundled_skill_dir = tmp_path / "plugins" / "dev" / "skills" / "devops"
    bundled_skill_dir.mkdir(parents=True)
    client_skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "apple"
    client_skill_dir.mkdir(parents=True)

    with patch("skills.daemon.scripts.adaptive.snapshot._safe_git_dirty_files", return_value=["src/app.tsx"]):
        snapshot = build_shared_snapshot(tmp_path)

    assert snapshot["version"] == 1
    assert snapshot["project_root"] == str(tmp_path)
    assert snapshot["api_route_count"] == 1
    assert snapshot["api_route_paths"] == ["apps/dashboard/app/api/health/route.ts"]
    assert snapshot["api_routes"] == ["/api/health"]
    assert snapshot["page_count"] == 0
    assert snapshot["skill_count"] == 2
    assert set(snapshot["skill_roots"]) == {str(client_skill_dir), str(bundled_skill_dir)}
    assert snapshot["git_dirty_files"] == ["src/app.tsx"]
    assert "runtime_dir" in snapshot["runtime"]


def test_build_shared_snapshot_includes_plugin_page_routes(tmp_path):
    plugin_page = (
        tmp_path
        / "plugins"
        / "ui"
        / "pages"
        / "life"
        / "attention"
        / "page.tsx"
    )
    plugin_page.parent.mkdir(parents=True)
    plugin_page.write_text("export default function Page() {}\n")

    with patch("skills.daemon.scripts.adaptive.snapshot._safe_git_dirty_files", return_value=[]):
        snapshot = build_shared_snapshot(tmp_path)

    assert snapshot["page_routes"] == ["/life/attention"]
    assert snapshot["page_count"] == 1
