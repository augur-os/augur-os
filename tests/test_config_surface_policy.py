from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RETIRED_DASHBOARD_ROUTE_PREFIXES = (
    "/adaptive",
    "/command",
    "/dev",
    "/factory",
    "/inbox",
    "/platform",
    "/projects",
    "/terminal-automation-template",
    "/venture",
)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _read_skill_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} is missing YAML frontmatter"
    frontmatter = text.split("---\n", 1)[1].split("\n---", 1)[0]
    return yaml.safe_load(frontmatter) or {}


def _read_yaml_or_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".md" and text.startswith("---\n"):
        return _read_skill_frontmatter(path)
    return yaml.safe_load(text) or {}


def _starts_with_retired_dashboard_route(value: str) -> bool:
    return any(value == prefix or value.startswith(f"{prefix}/") for prefix in RETIRED_DASHBOARD_ROUTE_PREFIXES)


def _collect_page_values(value: object) -> list[str]:
    if isinstance(value, dict):
        pages = []
        for key, child in value.items():
            if key == "page" and isinstance(child, str):
                pages.append(child)
            else:
                pages.extend(_collect_page_values(child))
        return pages
    if isinstance(value, list):
        pages = []
        for child in value:
            pages.extend(_collect_page_values(child))
        return pages
    return []


def test_repo_local_plugin_state_is_not_tracked() -> None:
    tracked = _git("ls-files", "--", "config/system/plugin_state.json")

    assert tracked.returncode == 0, tracked.stderr
    tracked_existing = [path for path in tracked.stdout.splitlines() if (ROOT / path).exists()]
    assert tracked_existing == []


def test_legacy_root_mcp_tool_groups_fallback_is_removed() -> None:
    assert not (ROOT / "config" / "mcp_tool_groups.yaml").exists()


def test_generated_dashboard_tool_config_has_no_retired_domain_pages_or_tools() -> None:
    config_path = ROOT / "config" / "dashboard" / "generated" / "assembled_tool_config.json"
    if not config_path.exists():
        return

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    pages = set((config.get("pages") or {}).keys())

    for retired_page in (
        "/adaptive",
        "/command",
        "/dev",
        "/factory",
        "/inbox",
        "/platform",
        "/projects",
        "/terminal-automation-template",
        "/venture",
    ):
        assert not any(page == retired_page or page.startswith(f"{retired_page}/") for page in pages)

    serialized = yaml.safe_dump(config)
    for retired_tool in (
        "training-answer",
        "training-preferences",
        "training-reset",
        "training-start",
        "virtual-doctor",
        "add-career-job",
    ):
        assert retired_tool not in serialized


def test_retired_hub_coverage_api_routes_are_removed() -> None:
    for route in (
        "apps/dashboard/app/api/auto-command-hub-coverage/route.ts",
        "apps/dashboard/app/api/auto-life-hub-coverage/route.ts",
        "apps/dashboard/app/api/auto-studio-hub-coverage/route.ts",
    ):
        assert not (ROOT / route).exists()


def test_dashboard_code_does_not_link_to_retired_install_route() -> None:
    tracked = _git(
        "grep",
        "-n",
        "command/import/install",
        "--",
        "apps/dashboard/app",
        "apps/dashboard/components",
        "apps/dashboard/features",
        "apps/dashboard/lib",
    )

    assert tracked.returncode == 1, tracked.stdout


def test_dashboard_feature_pages_are_limited_to_live_roots() -> None:
    feature_pages_dir = ROOT / "apps" / "dashboard" / "features" / "pages"
    existing_roots = {path.name for path in feature_pages_dir.iterdir() if path.is_dir()}

    assert existing_roots <= {"workspace", "settings"}


def test_tool_verification_report_only_references_existing_feature_pages() -> None:
    report_path = ROOT / "docs" / "generated" / "tool-verification.json"
    if not report_path.exists():
        return

    report = json.loads(report_path.read_text(encoding="utf-8"))
    feature_pages_dir = ROOT / "apps" / "dashboard" / "features" / "pages"
    missing = sorted(
        page.get("page")
        for page in report.get("pages", [])
        if isinstance(page, dict)
        and isinstance(page.get("page"), str)
        and not (feature_pages_dir / page["page"]).exists()
    )

    assert missing == []


def test_shared_vault_skill_metadata_does_not_declare_retired_dashboard_pages() -> None:
    """ADR-802: skills declare /workspace pages via x-augur-dashboard-pages (route objects);
    no skill may target a retired dashboard route. The hub concept is removed, so there is
    no longer a per-hub page-ownership restriction."""
    failures: list[str] = []

    for skill_file in sorted((ROOT / "project-brain" / "capabilities" / "skills").glob("*/SKILL.md")):
        metadata = _read_skill_frontmatter(skill_file)
        skill_name = skill_file.parent.name

        for entry in metadata.get("x-augur-dashboard-pages") or []:
            route = entry.get("route") if isinstance(entry, dict) else entry
            if isinstance(route, str) and _starts_with_retired_dashboard_route(route):
                failures.append(f"{skill_name}: x-augur-dashboard-pages contains {route}")

    assert failures == []


def test_shared_vault_action_pages_do_not_target_retired_dashboard_routes() -> None:
    failures: list[str] = []
    candidates = [
        *sorted((ROOT / "project-brain" / "capabilities" / "skills").glob("*/SKILL.md")),
        *sorted((ROOT / "project-brain" / "capabilities" / "skills").glob("*/config.yaml")),
    ]

    for path in candidates:
        data = _read_yaml_or_frontmatter(path)
        for page in _collect_page_values(data):
            if _starts_with_retired_dashboard_route(page):
                failures.append(f"{path.relative_to(ROOT)}: page targets {page}")

    assert failures == []
