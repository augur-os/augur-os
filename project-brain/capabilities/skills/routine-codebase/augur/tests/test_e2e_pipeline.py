"""Tests for auto-e2e-pipeline autoloop."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult, make_test_ctx

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "e2e_pipeline.py"
_SPEC = importlib.util.spec_from_file_location("e2e_pipeline_under_test", str(_MODULE_PATH))
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def test_module_name() -> None:
    assert mod.name == "auto-e2e-pipeline"


def test_fix_reports_evolution_gaps_as_maintenance_not_manual(tmp_path: Path) -> None:
    ctx = make_test_ctx(tmp_path)
    issue = {
        "category": "evolution",
        "kind": "maintenance",
        "detail": "All current checks passed. Next: add deeper schema sampling.",
    }

    result = mod.fix(ctx, [issue])

    assert result.success
    assert "evolution gap" in result.summary
    assert "manual investigation" not in result.summary


def test_has_difficulty_spec() -> None:
    assert hasattr(mod, "DIFFICULTY_SPEC")
    assert isinstance(mod.DIFFICULTY_SPEC, dict)
    assert 0 in mod.DIFFICULTY_SPEC
    assert 3 in mod.DIFFICULTY_SPEC


def test_scan_returns_scan_result(tmp_path: Path) -> None:
    ctx = make_test_ctx(tmp_path)
    result = mod.scan(ctx)
    assert isinstance(result, ScanResult)


def test_fix_returns_fix_result(tmp_path: Path) -> None:
    ctx = make_test_ctx(tmp_path)
    result = mod.fix(ctx, [])
    assert isinstance(result, FixResult)


# ── Difficulty-level tests (d0, d1) ────────────────────────────────────


def _patch_paths_to_tmp(tmp_path: Path):
    """Context manager that patches RAG/vault path resolution to use tmp_path."""
    rag_dir = tmp_path / "rag"
    vault_dir = tmp_path / "vault"
    return patch.multiple(
        "src.config.paths",
        get_rag_category_dir=lambda cat: rag_dir / cat,
        get_rag_dir=lambda: rag_dir,
        get_vault_dir=lambda: vault_dir,
    )


def test_d0_empty_project_flags_empty_categories(tmp_path: Path) -> None:
    """d0 on a project with no RAG entries should flag all categories as empty."""
    ctx = make_test_ctx(tmp_path, difficulty=0)
    with _patch_paths_to_tmp(tmp_path):
        result = mod.scan(ctx)
    assert isinstance(result, ScanResult)
    assert result.health == "degraded"
    rag_empty = [issue for issue in result.issues if issue.get("broken_stage") == "rag_empty"]
    assert len(rag_empty) == len(mod.ALL_CATEGORIES)


def test_d0_summary_does_not_count_evolution_gap_as_seed_fallback(tmp_path: Path) -> None:
    rag_dir = tmp_path / "rag"
    for category in mod.ALL_CATEGORIES:
        cat_dir = rag_dir / category
        cat_dir.mkdir(parents=True)
        (cat_dir / "entry.md").write_text("---\nid: entry\n---\n")
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    (vault_dir / "note.md").write_text("note")

    ctx = make_test_ctx(tmp_path, difficulty=0)
    evolution = {
        "category": "evolution",
        "kind": "maintenance",
        "detail": "Current seed checks are clean. Next: add runtime source checks.",
    }
    with patch.multiple(
        "src.config.paths",
        get_rag_category_dir=lambda cat: rag_dir / cat,
        get_rag_dir=lambda: rag_dir,
        get_vault_dir=lambda: vault_dir,
    ), patch.object(mod, "_detect_seed_fallbacks", return_value=[evolution]), patch.object(
        mod, "_detect_dead_pulse_endpoints", return_value=[]
    ):
        result = mod.scan(ctx)

    assert "0 seed fallbacks" in result.summary
    assert result.health == "verified"


def test_d1_source_without_rag_flags_stale(tmp_path: Path) -> None:
    """d1 should flag categories where source items exist but RAG is empty."""
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: test-skill\n---\nTest")

    ctx = make_test_ctx(tmp_path, difficulty=1)
    # Patch path resolution so scan sees tmp_path (empty RAG, 1 source skill).
    with _patch_paths_to_tmp(tmp_path), patch(
        "src.config.paths.get_all_client_skill_dirs",
        return_value=[tmp_path / "skills"],
    ):
        result = mod.scan(ctx)
    assert isinstance(result, ScanResult)
    stale = [i for i in result.issues if i.get("broken_stage") == "rag_stale"]
    assert len(stale) >= 1  # skills category should be flagged as stale


# ── Fix tests ──────────────────────────────────────────────────────────


def test_fix_dry_run_returns_early(tmp_path: Path) -> None:
    ctx = make_test_ctx(tmp_path, dry_run=True)
    issues = [{"broken_stage": "rag_stale", "browse_category": "skills"}]
    result = mod.fix(ctx, issues)
    assert isinstance(result, FixResult)
    assert result.success
    assert "Dry run" in result.summary


def test_fix_no_issues_is_noop(tmp_path: Path) -> None:
    ctx = make_test_ctx(tmp_path)
    result = mod.fix(ctx, [])
    assert isinstance(result, FixResult)
    assert result.success
    assert "No issues" in result.summary


# ── D4 helper tests ───────────────────────────────────────────────────


def test_discover_page_mcp_tools_yaml(tmp_path: Path) -> None:
    """Should discover mcp_tool from YAML auto-pages."""
    skill_dir = tmp_path / "skills" / "test-skill" / "augur" / "pages"
    skill_dir.mkdir(parents=True)
    (skill_dir / "overview.yaml").write_text(
        "title: Overview\nhub: test\nblocks:\n"
        "  - type: stat-grid\n    mcp_tool: get-test-counts\n"
        "  - type: data-table\n    mcp_tool: get-test-items\n"
    )
    (tmp_path / "skills" / "test-skill" / "SKILL.md").write_text(
        "---\nname: test-skill\n---\nTest"
    )
    with patch(
        "src.config.paths.get_all_client_skill_dirs",
        return_value=[tmp_path / "skills"],
    ):
        tools = mod._discover_page_mcp_tools(tmp_path)
    tool_names = {t["mcp_tool"] for t in tools}
    assert "get-test-counts" in tool_names
    assert "get-test-items" in tool_names
    yaml_tools = [t for t in tools if t["source"] == "yaml_page"]
    assert len(yaml_tools) >= 2


def test_discover_page_mcp_tools_skillmd_blocks(tmp_path: Path) -> None:
    """Should discover data_source.mcp_tool from SKILL.md blocks."""
    skill_dir = tmp_path / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\n"
        "x-augur-config:\n"
        "  contributions:\n"
        "    blocks:\n"
        "    - id: my-block\n"
        "      type: data-list\n"
        "      data_source:\n"
        "        mcp_tool: get-block-data\n"
        "---\nTest"
    )
    with patch(
        "src.config.paths.get_all_client_skill_dirs",
        return_value=[tmp_path / "skills"],
    ):
        tools = mod._discover_page_mcp_tools(tmp_path)
    tool_names = {t["mcp_tool"] for t in tools}
    assert "get-block-data" in tool_names


def test_discover_page_mcp_tools_tsx_hooks(tmp_path: Path) -> None:
    """Should discover tool names from useMcpQuery/useMcpMutation in TSX."""
    dash_dir = tmp_path / "apps" / "dashboard" / "app" / "test"
    dash_dir.mkdir(parents=True)
    (dash_dir / "page.tsx").write_text(
        'const { data } = useMcpQuery<Foo>("key", "get-test-data", "config");\n'
        'const { mutate } = useMcpMutation("update-test-data");\n'
    )
    with patch(
        "src.config.paths.get_all_client_skill_dirs",
        return_value=[tmp_path / "skills"],
    ):
        tools = mod._discover_page_mcp_tools(tmp_path)
    tool_names = {t["mcp_tool"] for t in tools}
    assert "get-test-data" in tool_names
    assert "update-test-data" in tool_names
    # Verify source types are correct
    by_tool = {t["mcp_tool"]: t for t in tools}
    assert by_tool["get-test-data"]["source"] == "tsx_hook"
    assert by_tool["update-test-data"]["source"] == "tsx_mutation"


def test_discover_tsx_hooks_skips_array_key_false_positives(tmp_path: Path) -> None:
    """Array keys in useMcpQuery should not produce false-positive tool names."""
    dash_dir = tmp_path / "apps" / "dashboard" / "app" / "test"
    dash_dir.mkdir(parents=True)
    (dash_dir / "page.tsx").write_text(
        'const { data } = useMcpQuery<Resp>(\n'
        '    ["audit-log", page.toString(), actionFilter],\n'
        '    "get-settings",\n'
        '    "live",\n'
        ');\n'
    )
    with patch(
        "src.config.paths.get_all_client_skill_dirs",
        return_value=[tmp_path / "skills"],
    ):
        tools = mod._discover_page_mcp_tools(tmp_path)
    tool_names = {t["mcp_tool"] for t in tools}
    assert "get-settings" in tool_names
    # False positives from the array key should NOT appear
    assert "audit-log" not in tool_names
    assert "actionFilter" not in tool_names


def test_discover_tsx_hooks_skips_utility_files(tmp_path: Path) -> None:
    """Utility files like useBlockData.tsx should be skipped."""
    dash_dir = tmp_path / "apps" / "dashboard" / "lib"
    dash_dir.mkdir(parents=True)
    (dash_dir / "useBlockData.tsx").write_text(
        'export function useBlockData() {\n'
        '  return useMcpQuery("block-key", "fake-tool", "config");\n'
        '}\n'
    )
    with patch(
        "src.config.paths.get_all_client_skill_dirs",
        return_value=[tmp_path / "skills"],
    ):
        tools = mod._discover_page_mcp_tools(tmp_path)
    tool_names = {t["mcp_tool"] for t in tools}
    assert "fake-tool" not in tool_names


def test_seed_fallback_status_suppressed_when_fully_migrated(tmp_path: Path) -> None:
    # When legacy_count == 0 and migrated_count > 0 the scanner should NOT
    # emit the maintenance status issue — there is nothing to action and the
    # executor was surfacing it as 'manual investigation needed' which is
    # misleading. The evolution_gap below already carries the success signal.
    skills_root = tmp_path / "project-brain" / "capabilities" / "skills"
    skills_dir = skills_root / "demo" / "scripts" / "mcp"
    skills_dir.mkdir(parents=True)
    (skills_dir / "demo_tools.py").write_text(
        "from src.lib.data_result import DataResult\n"
        "def get_demo() -> DataResult:\n"
        "    return DataResult(data=[], source='live')\n"
    )

    with patch.object(mod, "get_all_client_skill_dirs", return_value=[skills_root]):
        issues = mod._detect_seed_fallbacks(tmp_path)

    seed_status = [
        i for i in issues if i.get("broken_stage") == "seed_fallback"
    ]
    assert seed_status == [], (
        "Maintenance status issue should be suppressed when migration is complete; "
        f"got: {seed_status}"
    )


def test_data_result_runtime_probe_accepts_source_metadata(tmp_path: Path) -> None:
    skills_root = tmp_path / "project-brain" / "capabilities" / "skills"
    mcp_dir = skills_root / "demo" / "scripts" / "mcp"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "__init__.py").write_text(
        "from src.lib.data_result import DataResult\n"
        "import json\n"
        "def _list_demo() -> DataResult:\n"
        "    return DataResult(data=[], source='seed', vault_status='no_file')\n"
        "def register_tools(mcp, mcp_tool_interceptor, metrics):\n"
        "    @mcp.tool(name='list-demo')\n"
        "    @mcp_tool_interceptor\n"
        "    async def list_demo():\n"
        "        result = _list_demo()\n"
        "        return json.dumps({'success': True, 'data': result.data, 'source': result.source})\n",
        encoding="utf-8",
    )

    with patch.object(mod, "get_all_client_skill_dirs", return_value=[skills_root]):
        issues = mod._detect_seed_fallbacks(tmp_path)

    assert [i for i in issues if i.get("category") == "evolution"] == []
    assert [i for i in issues if i.get("broken_stage") == "data_result_source_missing"] == []


def test_data_result_runtime_probe_flags_missing_source_metadata(tmp_path: Path) -> None:
    skills_root = tmp_path / "project-brain" / "capabilities" / "skills"
    mcp_dir = skills_root / "demo" / "scripts" / "mcp"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "__init__.py").write_text(
        "from src.lib.data_result import DataResult\n"
        "import json\n"
        "def _list_demo() -> DataResult:\n"
        "    return DataResult(data=[], source='seed', vault_status='no_file')\n"
        "def register_tools(mcp, mcp_tool_interceptor, metrics):\n"
        "    @mcp.tool(name='list-demo')\n"
        "    @mcp_tool_interceptor\n"
        "    async def list_demo():\n"
        "        result = _list_demo()\n"
        "        return json.dumps({'success': True, 'data': result.data})\n",
        encoding="utf-8",
    )

    with patch.object(mod, "get_all_client_skill_dirs", return_value=[skills_root]):
        issues = mod._detect_seed_fallbacks(tmp_path)

    missing_source = [
        i for i in issues if i.get("broken_stage") == "data_result_source_missing"
    ]
    assert len(missing_source) == 1
    assert missing_source[0]["mcp_tool"] == "list-demo"


def test_data_result_runtime_probe_ignores_non_data_result_helpers(tmp_path: Path) -> None:
    skills_root = tmp_path / "project-brain" / "capabilities" / "skills"
    mcp_dir = skills_root / "demo" / "scripts" / "mcp"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "__init__.py").write_text(
        "from src.lib.data_result import DataResult\n"
        "import json\n"
        "def _list_demo() -> DataResult:\n"
        "    return DataResult(data=[], source='seed', vault_status='no_file')\n"
        "def _ordinary_helper():\n"
        "    return []\n"
        "def register_tools(mcp, mcp_tool_interceptor, metrics):\n"
        "    @mcp.tool(name='list-demo')\n"
        "    @mcp_tool_interceptor\n"
        "    async def list_demo():\n"
        "        result = _list_demo()\n"
        "        return json.dumps({'success': True, 'data': result.data, 'source': result.source})\n"
        "    @mcp.tool(name='ordinary-list')\n"
        "    @mcp_tool_interceptor\n"
        "    async def ordinary_list():\n"
        "        return json.dumps({'success': True, 'items': _ordinary_helper()})\n",
        encoding="utf-8",
    )

    with patch.object(mod, "get_all_client_skill_dirs", return_value=[skills_root]):
        issues = mod._detect_seed_fallbacks(tmp_path)

    assert [
        i for i in issues
        if i.get("broken_stage") == "data_result_source_missing"
    ] == []


def test_response_has_data_positive() -> None:
    assert mod._response_has_data({"items": [{"id": 1}], "count": 1}) is True
    assert mod._response_has_data({"data": {"key": "val"}}) is True
    assert mod._response_has_data({"count": 5}) is True


def test_response_has_data_negative() -> None:
    assert mod._response_has_data({"items": [], "count": 0}) is False
    assert mod._response_has_data({"error": "not found"}) is False
    assert mod._response_has_data({"success": True}) is False
