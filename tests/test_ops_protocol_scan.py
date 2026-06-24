"""Unit tests for src.lib.ops_protocol._scan.

Exercises the dashboard/skill scanning utilities against a synthetic
project tree under tmp_path: block-id collection from skill frontmatter
and generated registry, page/api route discovery, catch-all registry
parsing, and the HTTP-route scheme guard (no network).
"""

from __future__ import annotations

from pathlib import Path

from src.lib.ops_protocol._scan import (
    CANONICAL_BLOCK_TYPES,
    _collect_page_routes_from_root,
    _dashboard_app_root,
    _parse_catchall_registry,
    check_http_route,
    collect_all_block_ids,
    find_api_routes,
    find_page_routes,
)


def _write_skill(project_root: Path, skill_name: str, block_id: str) -> None:
    skill_dir = project_root / "project-brain" / "capabilities" / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        f"name: {skill_name}\n"
        "x-augur-config:\n"
        "  contributions:\n"
        "    blocks:\n"
        f"      - id: {block_id}\n"
        "        type: stat-card\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )


def test_canonical_block_types_is_frozen_known_set():
    assert "stat-card" in CANONICAL_BLOCK_TYPES
    assert "ops-board" in CANONICAL_BLOCK_TYPES
    assert "not-a-real-block" not in CANONICAL_BLOCK_TYPES


def test_collect_all_block_ids_from_skill_and_registry(tmp_path: Path):
    _write_skill(tmp_path, "alpha", "overview")
    registry = tmp_path / "apps" / "dashboard" / "lib" / "blocks" / "generated-block-registry.ts"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        "export const registry = {\n  'beta:summary': Summary,\n};\n",
        encoding="utf-8",
    )
    ids = collect_all_block_ids(tmp_path)
    # Bare id plus skill-qualified id from frontmatter.
    assert "overview" in ids
    assert "alpha:overview" in ids
    # Qualified id parsed from the generated registry.
    assert "beta:summary" in ids


def test_collect_all_block_ids_empty_when_nothing_present(tmp_path: Path):
    assert collect_all_block_ids(tmp_path) == set()


def test_dashboard_app_root(tmp_path: Path):
    assert _dashboard_app_root(tmp_path) == tmp_path / "apps" / "dashboard" / "app"


def test_collect_page_routes_from_root(tmp_path: Path):
    root = tmp_path / "app"
    (root / "browse").mkdir(parents=True)
    (root / "browse" / "page.tsx").write_text("export default function P(){}", encoding="utf-8")
    (root / "page.tsx").write_text("export default function H(){}", encoding="utf-8")
    routes = _collect_page_routes_from_root(root)
    assert "/" in routes
    assert "/browse" in routes


def test_collect_page_routes_missing_root_returns_empty(tmp_path: Path):
    assert _collect_page_routes_from_root(tmp_path / "does-not-exist") == set()


def test_find_page_routes_uses_shared_snapshot(tmp_path: Path):
    snapshot = {"page_routes": ["/workspace", "/browse", 123]}
    routes = find_page_routes(tmp_path, shared_snapshot=snapshot)
    # Non-string entries filtered out.
    assert routes == {"/workspace", "/browse"}


def test_find_page_routes_scans_app_dir(tmp_path: Path):
    app = _dashboard_app_root(tmp_path)
    (app / "workspace").mkdir(parents=True)
    (app / "workspace" / "page.tsx").write_text("x", encoding="utf-8")
    routes = find_page_routes(tmp_path)
    assert "/workspace" in routes


def test_find_api_routes(tmp_path: Path):
    api = _dashboard_app_root(tmp_path) / "api" / "mcp" / "tool"
    api.mkdir(parents=True)
    (api / "route.ts").write_text("export async function POST(){}", encoding="utf-8")
    routes = find_api_routes(tmp_path)
    assert "/api/mcp/tool" in routes


def test_find_api_routes_shared_snapshot(tmp_path: Path):
    routes = find_api_routes(tmp_path, shared_snapshot={"api_routes": ["/api/x", 5]})
    assert routes == {"/api/x"}


def test_parse_catchall_registry(tmp_path: Path):
    app_root = tmp_path / "app"
    catchall_dir = app_root / "life" / "[[...slug]]"
    catchall_dir.mkdir(parents=True)
    registry = catchall_dir / "registry.ts"
    registry.write_text(
        "export const pages = {\n  'habits': Habits,\n  'goals': Goals,\n};\n",
        encoding="utf-8",
    )
    routes = _parse_catchall_registry(registry, app_root)
    assert routes == {"/life/habits", "/life/goals"}


def test_check_http_route_rejects_non_http_scheme():
    result = check_http_route("file:///etc/passwd")
    assert result["ok"] is False
    assert "Refusing non-HTTP URL scheme" in result["error"]


def test_check_http_route_connection_error_is_handled():
    # Unroutable port on localhost -> connection refused, not an exception.
    result = check_http_route("http://127.0.0.1:1/never", timeout=1)
    assert result["ok"] is False
    assert "error" in result
