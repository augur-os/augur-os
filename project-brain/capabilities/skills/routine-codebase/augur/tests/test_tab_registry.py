"""Tests for auto-tab-registry scanner."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from src.lib.ops_protocol import OpsContext

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "tab_registry.py"
_SPEC = importlib.util.spec_from_file_location("tab_registry_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal project structure with generated-registry.ts."""
    app_dir = tmp_path / "apps" / "dashboard" / "app"

    # Create two hubs: one with catch-all, one without
    brain_catchall = app_dir / "brain" / "[[...slug]]"
    brain_catchall.mkdir(parents=True)
    (brain_catchall / "page.tsx").write_text("'use client'; export default function() {}")
    (brain_catchall / "registry.ts").write_text(
        "export const DEFAULT_PATH: string | null = null;\n"
        "export const PAGES: Record<string, () => Promise<{ default: React.ComponentType }>> = {\n"
        "  'knowledge/memory': () => import('@skill/pages/workspace/knowledge/memory/page'),\n"
        "};\n"
    )

    # templates hub: NO catch-all (should be flagged)
    templates_dir = app_dir / "templates"
    templates_dir.mkdir(parents=True)

    # Create generated-registry.ts
    lib_dir = tmp_path / "apps" / "dashboard" / "lib" / "tabs"
    lib_dir.mkdir(parents=True)
    (lib_dir / "generated-registry.ts").write_text(
        'export const pluginTabRegistry: TabRegistry = {\n'
        '  "brain": {\n'
        '    "title": "Brain",\n'
        '    "basePath": "/brain",\n'
        '    "tabs": [\n'
        '      { "id": "overview", "label": "Overview", "href": "/brain" },\n'
        '      { "id": "knowledge-memory", "label": "Memory", "href": "/workspace/knowledge/memory" }\n'
        '    ],\n'
        '    "source": "plugin"\n'
        '  },\n'
        '  "templates": {\n'
        '    "title": "Templates",\n'
        '    "basePath": "/templates",\n'
        '    "tabs": [\n'
        '      { "id": "overview", "label": "Overview", "href": "/templates" },\n'
        '      { "id": "consulting-template", "label": "Consulting", "href": "/templates/consulting-template" }\n'
        '    ],\n'
        '    "source": "plugin"\n'
        '  }\n'
        '};\n'
    )

    return tmp_path


def test_scan_detects_missing_catchall(tmp_project: Path) -> None:
    """Hub without [[...slug]] directory should produce missing-catchall issue."""
    ctx = OpsContext(project_root=tmp_project, difficulty=0)
    result = mod.scan(ctx)

    missing = [i for i in result.issues if i.get("category") == "missing-catchall"]
    assert len(missing) == 1
    assert "templates" in missing[0]["detail"]


def test_scan_no_issues_when_all_hubs_have_catchall(tmp_project: Path) -> None:
    """All hubs with catch-all routes should produce no issues at d0."""
    # Add catch-all to templates
    catchall = tmp_project / "apps" / "dashboard" / "app" / "templates" / "[[...slug]]"
    catchall.mkdir(parents=True)
    (catchall / "page.tsx").write_text("export default function() {}")
    (catchall / "registry.ts").write_text(
        "export const DEFAULT_PATH: string | null = null;\n"
        "export const PAGES: Record<string, () => Promise<{ default: React.ComponentType }>> = {};\n"
    )

    ctx = OpsContext(project_root=tmp_project, difficulty=0)
    result = mod.scan(ctx)

    missing = [i for i in result.issues if i.get("category") == "missing-catchall"]
    assert len(missing) == 0


def test_scan_d1_detects_orphan_tab(tmp_project: Path) -> None:
    """Tab whose href doesn't resolve to direct page or catch-all entry should be flagged at d1."""
    # Add catch-all to templates but with empty PAGES
    catchall = tmp_project / "apps" / "dashboard" / "app" / "templates" / "[[...slug]]"
    catchall.mkdir(parents=True)
    (catchall / "page.tsx").write_text("export default function() {}")
    (catchall / "registry.ts").write_text(
        "export const DEFAULT_PATH: string | null = null;\n"
        "export const PAGES: Record<string, () => Promise<{ default: React.ComponentType }>> = {};\n"
    )

    ctx = OpsContext(project_root=tmp_project, difficulty=1)
    result = mod.scan(ctx)

    orphans = [i for i in result.issues if i.get("category") == "orphan-tab"]
    # consulting-template tab has no direct page and no catch-all PAGES entry
    assert len(orphans) >= 1
    assert any("consulting-template" in i["detail"] for i in orphans)


def test_fix_creates_missing_catchall(tmp_project: Path) -> None:
    """Fix at d1 should create missing catch-all directory with page.tsx and registry.ts."""
    ctx = OpsContext(project_root=tmp_project, difficulty=1)
    scan_result = mod.scan(ctx)
    missing = [i for i in scan_result.issues if i.get("category") == "missing-catchall"]
    assert len(missing) == 1

    fix_result = mod.fix(ctx, missing)
    assert fix_result.success

    # Verify the catch-all was created
    catchall = tmp_project / "apps" / "dashboard" / "app" / "templates" / "[[...slug]]"
    assert (catchall / "page.tsx").exists()
    assert (catchall / "registry.ts").exists()


def test_fix_d0_reports_only(tmp_project: Path) -> None:
    """Fix at d0 should not create any files — report only."""
    ctx = OpsContext(project_root=tmp_project, difficulty=0)
    scan_result = mod.scan(ctx)
    missing = [i for i in scan_result.issues if i.get("category") == "missing-catchall"]
    assert len(missing) == 1

    fix_result = mod.fix(ctx, missing)
    assert fix_result.fix_type == "report"

    # Catch-all should NOT have been created
    catchall = tmp_project / "apps" / "dashboard" / "app" / "templates" / "[[...slug]]"
    assert not catchall.exists()


def test_scan_skips_hub_with_page_sources(tmp_project: Path) -> None:
    """Hub with page sources in features/pages/ should NOT be flagged (mount-plugins generates catch-all)."""
    # Create features/pages/templates/consulting-template/page.tsx
    features_dir = tmp_project / "apps" / "dashboard" / "features" / "pages" / "templates" / "consulting-template"
    features_dir.mkdir(parents=True)
    (features_dir / "page.tsx").write_text("export default function ConsultingPage() {}")

    ctx = OpsContext(project_root=tmp_project, difficulty=0)
    result = mod.scan(ctx)

    missing = [i for i in result.issues if i.get("category") == "missing-catchall"]
    assert len(missing) == 0, f"Hub with page sources should not be flagged: {missing}"


def test_scan_d1_skips_tab_with_page_source(tmp_project: Path) -> None:
    """Tab with matching page source should NOT be flagged as orphan at d1."""
    # Create features/pages/templates/consulting-template/page.tsx
    features_dir = tmp_project / "apps" / "dashboard" / "features" / "pages" / "templates" / "consulting-template"
    features_dir.mkdir(parents=True)
    (features_dir / "page.tsx").write_text("export default function ConsultingPage() {}")

    ctx = OpsContext(project_root=tmp_project, difficulty=1)
    result = mod.scan(ctx)

    orphans = [i for i in result.issues if i.get("category") == "orphan-tab"]
    consulting_orphans = [i for i in orphans if "consulting-template" in i.get("detail", "")]
    assert len(consulting_orphans) == 0, f"Tab with page source should not be orphan: {consulting_orphans}"


def test_scan_d1_skips_tab_with_yaml_page(tmp_project: Path) -> None:
    """Tab with matching YAML config page should NOT be flagged as orphan at d1."""
    # Create a skill with YAML page config
    skill_dir = tmp_project / "project-brain" / "capabilities" / "skills" / "consulting-template" / "augur" / "pages"
    skill_dir.mkdir(parents=True)
    (skill_dir / "consulting.yaml").write_text(
        "title: Consulting\nhub: templates\nroute: consulting-template\n"
    )

    ctx = OpsContext(project_root=tmp_project, difficulty=1)
    result = mod.scan(ctx)

    orphans = [i for i in result.issues if i.get("category") == "orphan-tab"]
    consulting_orphans = [i for i in orphans if "consulting-template" in i.get("detail", "")]
    assert len(consulting_orphans) == 0, f"Tab with YAML page source should not be orphan: {consulting_orphans}"


def test_scan_skips_generated_config_pages_without_committed_sources(tmp_project: Path) -> None:
    """Generated configPages in the registry should count as valid page sources."""
    lib_dir = tmp_project / "apps" / "dashboard" / "lib" / "tabs"
    (lib_dir / "generated-registry.ts").write_text(
        'export const pluginTabRegistry: TabRegistry = {\n'
        '  "brain": {\n'
        '    "title": "Brain",\n'
        '    "basePath": "/brain",\n'
        '    "tabs": [\n'
        '      { "id": "overview", "label": "Overview", "href": "/brain" },\n'
        '      { "id": "knowledge-memory", "label": "Memory", "href": "/workspace/knowledge/memory" }\n'
        '    ],\n'
        '    "source": "plugin"\n'
        '  },\n'
        '  "templates": {\n'
        '    "title": "Templates",\n'
        '    "basePath": "/templates",\n'
        '    "tabs": [\n'
        '      { "id": "overview", "label": "Overview", "href": "/templates" }\n'
        '    ],\n'
        '    "configPages": [\n'
        '      { "id": "consulting-template", "label": "Consulting", "href": "/templates/consulting-template", "pageSource": "yaml" }\n'
        '    ],\n'
        '    "source": "plugin"\n'
        '  }\n'
        '};\n'
    )

    ctx = OpsContext(project_root=tmp_project, difficulty=1)
    result = mod.scan(ctx)

    missing = [i for i in result.issues if i.get("category") == "missing-catchall"]
    orphans = [i for i in result.issues if i.get("category") == "orphan-tab"]
    assert len(missing) == 0, f"Generated config pages should suppress missing catch-all: {missing}"
    assert len(orphans) == 0, f"Generated config pages should suppress orphan tabs: {orphans}"


def test_scan_overview_only_hub_not_flagged(tmp_project: Path) -> None:
    """Hub with only overview tab (no sub-pages) should NOT need a catch-all."""
    # Modify registry to add overview-only hub
    lib_dir = tmp_project / "apps" / "dashboard" / "lib" / "tabs"
    (lib_dir / "generated-registry.ts").write_text(
        'export const pluginTabRegistry: TabRegistry = {\n'
        '  "brain": {\n'
        '    "title": "Brain",\n'
        '    "basePath": "/brain",\n'
        '    "tabs": [\n'
        '      { "id": "overview", "label": "Overview", "href": "/brain" },\n'
        '      { "id": "knowledge-memory", "label": "Memory", "href": "/workspace/knowledge/memory" }\n'
        '    ],\n'
        '    "source": "plugin"\n'
        '  },\n'
        '  "adaptive": {\n'
        '    "title": "Adaptive",\n'
        '    "basePath": "/adaptive",\n'
        '    "tabs": [\n'
        '      { "id": "overview", "label": "Overview", "href": "/adaptive" }\n'
        '    ],\n'
        '    "source": "plugin"\n'
        '  }\n'
        '};\n'
    )

    ctx = OpsContext(project_root=tmp_project, difficulty=0)
    result = mod.scan(ctx)

    missing = [i for i in result.issues if i.get("category") == "missing-catchall"]
    adaptive_issues = [i for i in missing if "adaptive" in i.get("detail", "")]
    assert len(adaptive_issues) == 0, f"Overview-only hub should not be flagged: {adaptive_issues}"
