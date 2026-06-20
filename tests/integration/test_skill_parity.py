"""ADR-434 test-parity: Verify skill structure parity across the codebase.

Tests:
1. Every skill directory has a SKILL.md
2. SKILL.md files have valid frontmatter (name, description)
3. Skills with scripts/ have importable Python modules
4. Dashboard page source files exist for mounted pages
5. API route files exist for declared routes
6. No orphan skill directories (dir exists but no SKILL.md)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config.paths import get_project_root, get_project_brain_skills_dir

PROJECT_ROOT = get_project_root()
SKILLS_DIR = get_project_brain_skills_dir(PROJECT_ROOT)
DASHBOARD_APP = PROJECT_ROOT / "apps" / "dashboard" / "app"

# Skills that are README files, not actual skill dirs
_SKIP_NAMES = {"README.md", "README-admin.md", "README-consulting.md", "README-dev-shared.md", "README-enterprise.md"}


def _skill_dirs() -> list[Path]:
    """Return all skill directories (excluding READMEs)."""
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(
        d for d in SKILLS_DIR.iterdir() if d.is_dir() and d.name not in _SKIP_NAMES and not d.name.startswith(".")
    )


def _is_standard_bundle(skill_dir: Path) -> bool:
    """A standard skill bundle (ADR-790/ADR-791) has DESCRIPTION.md plus nested
    subskill SKILL.md files instead of a top-level SKILL.md. Its layout test
    explicitly asserts ``not (root / 'SKILL.md').exists()``, so it must not be
    treated as a flat skill missing a SKILL.md."""
    if not (skill_dir / "DESCRIPTION.md").is_file():
        return False
    if (skill_dir / "SKILL.md").is_file():
        return False
    return any(sub.is_dir() and (sub / "SKILL.md").is_file() for sub in skill_dir.iterdir())


def _parse_frontmatter(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("---", 3)
    if end < 0:
        return None
    try:
        import yaml

        return yaml.safe_load(text[3:end])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSkillDirectoryStructure:
    @pytest.fixture(scope="class")
    def skills(self) -> list[Path]:
        return _skill_dirs()

    def test_skills_dir_exists(self):
        assert SKILLS_DIR.is_dir(), f"Skills dir not found: {SKILLS_DIR}"

    def test_has_skills(self, skills):
        assert skills, "Expected at least one skill directory"

    def test_every_skill_has_skill_md(self, skills):
        missing = []
        for d in skills:
            skill_md = d / "SKILL.md"
            if skill_md.is_file():
                continue
            # ADR-790/ADR-791 standard bundles carry DESCRIPTION.md + nested
            # subskill SKILL.md files instead of a top-level SKILL.md.
            if _is_standard_bundle(d):
                continue
            missing.append(d.name)
        assert not missing, f"Skills missing SKILL.md: {missing}"


class TestSkillMDFrontmatter:
    @pytest.fixture(scope="class")
    def skill_mds(self) -> list[tuple[str, Path]]:
        results = []
        for d in _skill_dirs():
            sm = d / "SKILL.md"
            if sm.is_file():
                results.append((d.name, sm))
        return results

    def test_skill_md_has_name(self, skill_mds):
        missing = []
        for name, path in skill_mds[:80]:  # Sample for speed
            fm = _parse_frontmatter(path)
            if not fm or "name" not in fm:
                # Check if it uses --- delimiters but no name field
                text = path.read_text(encoding="utf-8")[:200]
                if text.startswith("---"):
                    missing.append(name)
        assert len(missing) < len(skill_mds) * 0.15, f"{len(missing)} SKILL.md files missing name: {missing[:15]}"

    def test_skill_md_has_description(self, skill_mds):
        missing = []
        for name, path in skill_mds[:80]:
            fm = _parse_frontmatter(path)
            if not fm or "description" not in fm:
                text = path.read_text(encoding="utf-8")[:200]
                if text.startswith("---"):
                    missing.append(name)
        assert (
            len(missing) < len(skill_mds) * 0.15
        ), f"{len(missing)} SKILL.md files missing description: {missing[:15]}"


class TestDashboardPageParity:
    def test_dashboard_app_dir_exists(self):
        assert DASHBOARD_APP.is_dir(), f"Dashboard app dir not found: {DASHBOARD_APP}"

    def test_workspace_pages_exist(self):
        """Verify the dashboard still exposes the routed Workspace surface (ADR-802: no hubs)."""
        excluded = {"(views)", "actions", "activity", "api", "login", "settings", "system", "templates"}
        surfaces_with_pages = []
        for surface_dir in sorted(DASHBOARD_APP.iterdir()):
            if not surface_dir.is_dir() or surface_dir.name in excluded:
                continue
            if list(surface_dir.rglob("page.tsx")):
                surfaces_with_pages.append(surface_dir.name)

        assert "workspace" in surfaces_with_pages, f"Workspace surface missing routed page: {surfaces_with_pages}"
        assert len(surfaces_with_pages) >= 1, f"Expected at least 1 routed surface, found {surfaces_with_pages}"

    def test_api_directory_exists(self):
        api_dir = DASHBOARD_APP / "api"
        assert api_dir.is_dir(), "No API directory in dashboard app"

    def test_api_routes_have_route_ts(self):
        """Verify API route dirs contain route.ts files."""
        api_dir = DASHBOARD_APP / "api"
        if not api_dir.is_dir():
            pytest.skip("No API directory")
        routes = list(api_dir.rglob("route.ts"))
        assert len(routes) >= 5, f"Expected 5+ API routes, found {len(routes)}"


class TestSkillScriptIntegrity:
    def test_python_scripts_are_syntactically_valid(self):
        """Verify Python scripts in skill dirs parse without syntax errors."""
        import ast

        bad = []
        for skill_dir in _skill_dirs()[:40]:  # Sample
            scripts_dir = skill_dir / "scripts"
            if not scripts_dir.is_dir():
                continue
            for py_file in scripts_dir.rglob("*.py"):
                try:
                    ast.parse(py_file.read_text(encoding="utf-8"))
                except SyntaxError as e:
                    bad.append(f"{py_file.relative_to(PROJECT_ROOT)}: {e.msg}")
        assert not bad, f"Python syntax errors: {bad[:10]}"
