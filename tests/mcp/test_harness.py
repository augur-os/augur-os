from __future__ import annotations

import json
from pathlib import Path

from src.mcp.augur_framework.tools.infrastructure.harness import (
    CAPABILITY_TYPES,
    build_harness_snapshot,
    get_brain_harness_snapshot_impl,
    harness_manager_snapshot_impl,
    refresh_brain_harness_snapshot_impl,
    read_harness_snapshot_file,
    write_harness_snapshot_file,
)


def write_skill(root: Path, name: str, body: str) -> Path:
    skill_dir = root / "project-brain" / "capabilities" / "skills" / name
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(body, encoding="utf-8")
    return skill_md


def test_capability_type_contract_is_small_and_explicit() -> None:
    assert CAPABILITY_TYPES == {
        "memory",
        "skill",
        "mcp_tool",
        "dashboard_page",
        "command",
        "protocol",
        "loop",
        "document_surface",
    }


def test_build_snapshot_maps_skill_tools_pages_and_relationships(tmp_path: Path) -> None:
    write_skill(
        tmp_path,
        "knowledge",
        """---
name: knowledge
description: Search and curate Augur memory.
x-augur-hub: workspace
x-augur-mcp-tools:
  - memory-stats
x-augur-dashboard-pages:
  - /workspace/knowledge
x-augur-commands:
  - id: memory-curate
    type: workflow
    visibility: core
    description: Curate memory
---
# Knowledge
""",
    )
    tool_file = tmp_path / "src" / "mcp" / "tools.py"
    tool_file.parent.mkdir(parents=True)
    tool_file.write_text(
        '@mcp.tool(name="memory-stats")\ndef tool():\n    pass\n',
        encoding="utf-8",
    )

    snapshot = build_harness_snapshot(tmp_path, generated_at="2026-04-19T10:00:00Z")

    assert snapshot["generated_at"] == "2026-04-19T10:00:00Z"
    capability_ids = {item["id"] for item in snapshot["capabilities"]}
    assert "skill:knowledge" in capability_ids
    assert "mcp_tool:memory-stats" in capability_ids
    assert "dashboard_page:/workspace/knowledge" in capability_ids
    assert "command:knowledge:memory-curate" in capability_ids
    assert {
        "from_id": "skill:knowledge",
        "to_id": "mcp_tool:memory-stats",
        "kind": "skill_declares_tool",
        "source_path": "project-brain/capabilities/skills/knowledge/SKILL.md",
        "confidence": "high",
    } in snapshot["relationships"]


def test_missing_declared_mcp_tool_emits_wiring_diagnostic(tmp_path: Path) -> None:
    write_skill(
        tmp_path,
        "ai",
        """---
name: ai
description: AI integration layer.
x-augur-hub: workspace
x-augur-mcp-tools:
  - missing-tool
---
# AI
""",
    )

    snapshot = build_harness_snapshot(tmp_path, generated_at="2026-04-19T10:00:00Z")

    diagnostics = snapshot["diagnostics"]
    assert diagnostics == [
        {
            "id": "diagnostic:missing-mcp-tool:missing-tool",
            "severity": "warning",
            "family": "dashboard_mcp_wiring",
            "reason": "Skill declares MCP tool 'missing-tool' but no @mcp.tool registration was found.",
            "affected_capability_ids": ["mcp_tool:missing-tool"],
            "source_path": "project-brain/capabilities/skills/ai/SKILL.md",
            "recommended_action": {
                "kind": "dispatch_ide_repair",
                "label": "Ask IDE agent to repair missing MCP tool wiring",
            },
        }
    ]


def test_snapshot_persistence_round_trips_json(tmp_path: Path) -> None:
    snapshot = build_harness_snapshot(tmp_path, generated_at="2026-04-19T10:00:00Z")
    snapshot_path = tmp_path / "harness" / "brain-harness-snapshot.json"

    write_harness_snapshot_file(snapshot_path, snapshot)

    assert json.loads(snapshot_path.read_text(encoding="utf-8"))["generated_at"] == "2026-04-19T10:00:00Z"
    assert read_harness_snapshot_file(snapshot_path)["capabilities"] == []


def test_shared_capability_id_is_merged_and_reported_as_structural_issue(tmp_path: Path) -> None:
    write_skill(
        tmp_path,
        "alpha",
        """---
name: alpha
x-augur-hub: workspace
x-augur-mcp-tools:
  - shared-tool
---
# Alpha
""",
    )
    write_skill(
        tmp_path,
        "beta",
        """---
name: beta
x-augur-hub: workspace
x-augur-mcp-tools:
  - shared-tool
---
# Beta
""",
    )
    (tmp_path / "src" / "mcp" / "tools.py").parent.mkdir(parents=True)
    (tmp_path / "src" / "mcp" / "tools.py").write_text(
        '@mcp.tool(name="shared-tool")\ndef tool():\n    pass\n',
        encoding="utf-8",
    )

    snapshot = build_harness_snapshot(tmp_path, generated_at="2026-04-19T10:00:00Z")

    tool_capabilities = [cap for cap in snapshot["capabilities"] if cap["id"] == "mcp_tool:shared-tool"]
    assert len(tool_capabilities) == 1
    assert sorted(tool_capabilities[0]["declared_by"]) == ["alpha", "beta"]

    skill_relations = {
        (relationship["from_id"], relationship["to_id"])
        for relationship in snapshot["relationships"]
        if relationship["kind"] == "skill_declares_tool" and relationship["to_id"] == "mcp_tool:shared-tool"
    }
    assert ("skill:alpha", "mcp_tool:shared-tool") in skill_relations
    assert ("skill:beta", "mcp_tool:shared-tool") in skill_relations

    structural = [
        diagnostic
        for diagnostic in snapshot["diagnostics"]
        if diagnostic["family"] == "structural_integrity"
        and diagnostic["id"].startswith("diagnostic:duplicate-capability")
    ]
    assert len(structural) == 1
    assert structural[0]["affected_capability_ids"] == ["mcp_tool:shared-tool"]


def test_parse_errors_are_reported_in_partial_failures_and_diagnostics(tmp_path: Path) -> None:
    malformed = tmp_path / "src" / "mcp" / "broken_tool.py"
    malformed.parent.mkdir(parents=True)
    malformed.write_text(
        "def broken(:\n    pass\n",
        encoding="utf-8",
    )

    snapshot = build_harness_snapshot(tmp_path, generated_at="2026-04-19T10:00:00Z")

    partial_failures = snapshot["provenance"]["partial_failures"]
    assert any(failure["path"].endswith("broken_tool.py") for failure in partial_failures)

    structural = [
        diagnostic
        for diagnostic in snapshot["diagnostics"]
        if diagnostic["family"] == "structural_integrity" and diagnostic["id"].startswith("diagnostic:scan-failure:")
    ]
    assert len(structural) == 1
    assert structural[0]["source_path"].endswith("broken_tool.py")


def test_multiline_mcp_tool_decorator_is_detected_by_ast(tmp_path: Path) -> None:
    write_skill(
        tmp_path,
        "knowledge",
        """---
name: knowledge
x-augur-hub: workspace
x-augur-mcp-tools:
  - memory-stats
---
# Knowledge
""",
    )
    (tmp_path / "src" / "mcp" / "tools.py").parent.mkdir(parents=True)
    (tmp_path / "src" / "mcp" / "tools.py").write_text(
        '@mcp.tool(\n    name="memory-stats",\n)\ndef tool():\n    pass\n',
        encoding="utf-8",
    )

    snapshot = build_harness_snapshot(tmp_path, generated_at="2026-04-19T10:00:00Z")

    capability_ids = {item["id"] for item in snapshot["capabilities"]}
    assert "mcp_tool:memory-stats" in capability_ids
    assert all(diagnostic["id"] != "diagnostic:missing-mcp-tool:memory-stats" for diagnostic in snapshot["diagnostics"])


def test_get_snapshot_impl_returns_empty_state_when_missing(tmp_path: Path) -> None:
    result = get_brain_harness_snapshot_impl(snapshot_path=tmp_path / "missing.json")

    assert result["success"] is True
    assert result["snapshot"] is None
    assert result["state"] == "missing"
    assert result["actions"][0]["kind"] == "refresh_snapshot"


def test_refresh_snapshot_impl_writes_and_returns_snapshot(tmp_path: Path) -> None:
    write_skill(
        tmp_path,
        "knowledge",
        """---
name: knowledge
description: Search and curate Augur memory.
x-augur-hub: workspace
---
# Knowledge
""",
    )
    snapshot_path = tmp_path / "cache" / "harness" / "brain-harness-snapshot.json"

    result = refresh_brain_harness_snapshot_impl(project_root=tmp_path, snapshot_path=snapshot_path)

    assert result["success"] is True
    assert result["state"] == "ready"
    assert snapshot_path.exists()
    assert result["snapshot"]["capabilities"][0]["id"] == "skill:knowledge"


def test_harness_manager_snapshot_impl_wraps_active_stack(monkeypatch, tmp_path: Path) -> None:
    from src.lib.brain_context import ActiveBrainContext
    from src.lib.brain_registry_models import Brain, BrainType, GitArrangement, GitConfig
    from src.lib.brain_stack import BrainStack, resolve_global_brain

    core = tmp_path / "core"
    (core / "capabilities" / "skills" / "core-only").mkdir(parents=True)
    (core / "capabilities" / "skills" / "core-only" / "SKILL.md").write_text(
        "---\nname: core-only\n---\n",
        encoding="utf-8",
    )
    repo = tmp_path / "repo"
    project_brain = repo / "project-brain"
    (project_brain / "capabilities" / "skills" / "project-only").mkdir(parents=True)
    (project_brain / "capabilities" / "skills" / "project-only" / "SKILL.md").write_text(
        "---\nname: project-only\n---\n",
        encoding="utf-8",
    )
    project = Brain(
        id="project-repo",
        type=BrainType.PROJECT,
        data_root=project_brain,
        git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=repo),
    )
    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=None,
        project=ActiveBrainContext(
            active_brain=project,
            attached_project=repo,
            source="nearest-project-brain",
        ),
    )

    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.harness.resolve_active_stack",
        lambda **_kwargs: stack,
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.harness.get_project_root",
        lambda: repo,
    )

    result = harness_manager_snapshot_impl()

    assert result["success"] is True
    assert result["snapshot"]["groups"]["skills"]["effective"] == 2
    skill_names = {row["name"] for row in result["snapshot"]["groups"]["skills"]["entries"]}
    assert skill_names == {"core-only", "project-only"}
    assert result["actions"][0]["kind"] == "refresh_manager_snapshot"
