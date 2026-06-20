from __future__ import annotations

import json
from pathlib import Path

from src.lib.ai_artifact_inventory import scan_ai_artifacts, write_ai_artifact_inventory
from src.lib.brain_registry_io import save_registry
from src.lib.brain_registry_models import (
    Brain,
    BrainRegistry,
    BrainType,
    GitArrangement,
    GitConfig,
)
from src.mcp.augur_framework.tools.infrastructure.browse.index import browse_index_impl


def _use_project_inventory_registry(
    *,
    tmp_path: Path,
    project: Path,
    brain_root: Path,
    monkeypatch,
) -> None:
    registry_path = tmp_path / "brains.yaml"
    save_registry(
        BrainRegistry(
            version=1,
            brains={
                "project-repo": Brain(
                    id="project-repo",
                    type=BrainType.PROJECT,
                    data_root=brain_root,
                    git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project),
                )
            },
        ),
        registry_path,
    )

    import src.lib.ai_artifact_inventory as ai_inventory

    monkeypatch.setattr(
        ai_inventory,
        "get_registry",
        lambda: __import__(
            "src.lib.brain_registry_io",
            fromlist=["load_registry"],
        ).load_registry(registry_path),
    )


def test_browse_index_includes_inventory_instruction_cards(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    project.mkdir()
    (project / "AGENTS.md").write_text("Existing project agent rules\n", encoding="utf-8")
    inventory = scan_ai_artifacts(
        project_root=project,
        project_brain_id="project-repo",
        discovered_at="2026-06-04T00:00:00+00:00",
    )
    write_ai_artifact_inventory(inventory, brain_root)

    _use_project_inventory_registry(
        tmp_path=tmp_path,
        project=project,
        brain_root=brain_root,
        monkeypatch=monkeypatch,
    )

    payload = json.loads(browse_index_impl("system-metadata", limit=20))

    matching = [
        item for item in payload["items"] if item["metadata"].get("inventory_source") == "ai-artifact-inventory"
    ]
    assert len(matching) == 1
    card = matching[0]
    assert card["title"] == "Agents"
    assert card["metadata"]["brain_id"] == "project-repo"
    assert card["metadata"]["artifact_type"] == "instruction"
    assert card["metadata"]["client"] == "project"
    # AGENTS.md is repo-authored source now (was mis-flagged unknown); only
    # missing_mcp_config remains (instruction artifact, no .mcp.json fixture).
    assert card["metadata"]["classification"] == "source"
    assert card["metadata"]["problem_tags"] == "missing_mcp_config"
    assert card["metadata"]["problem_count"] == "1"
    assert card["metadata"]["problem_summary"] == "Missing MCP config"
    problem_evidence = json.loads(card["metadata"]["problem_evidence"])
    assert [item["id"] for item in problem_evidence] == [
        "missing_mcp_config",
    ]
    assert "missing_mcp_config" in card["tags"]
    assert card["source_path"] == str(project / "AGENTS.md")


def test_browse_index_dedupes_inventory_cards_against_relative_index_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    project.mkdir()
    (project / "AGENTS.md").write_text("Existing project agent rules\n", encoding="utf-8")
    inventory = scan_ai_artifacts(
        project_root=project,
        project_brain_id="project-repo",
        discovered_at="2026-06-04T00:00:00+00:00",
    )
    write_ai_artifact_inventory(inventory, brain_root)
    _use_project_inventory_registry(
        tmp_path=tmp_path,
        project=project,
        brain_root=brain_root,
        monkeypatch=monkeypatch,
    )

    cat_dir = tmp_path / "rag" / "system-metadata"
    cat_dir.mkdir(parents=True)

    import src.config.paths as config_paths
    import src.lib.index.index_reader as index_reader
    import src.mcp.augur_framework.tools.infrastructure.browse.index as browse_index
    import src.mcp.augur_framework.tools.infrastructure.browse.index_resolve as index_resolve

    monkeypatch.setattr(browse_index, "get_project_root", lambda: project)
    monkeypatch.setattr(index_resolve, "get_project_root", lambda: project)
    monkeypatch.setattr(config_paths, "get_rag_category_dir", lambda category: cat_dir)
    monkeypatch.setattr(index_reader, "count_category_entries", lambda scan_dir, hub=None: 1)
    monkeypatch.setattr(
        index_reader,
        "list_category_entries",
        lambda scan_dir, hub=None, limit=0: [
            {
                "id": "indexed-agents",
                "name": "indexed-agents",
                "title": "Indexed Agents",
                "description": "Indexed instruction artifact",
                "hub": "system",
                "type": "instruction",
                "source_path": "AGENTS.md",
                "tags": ["indexed", "stale_generated"],
                "metadata": {
                    "problem_tags": "stale_generated",
                    "problem_count": "1",
                    "problem_summary": "Stale generated",
                    "owner_note": "keep me",
                },
            }
        ],
    )

    payload = json.loads(browse_index_impl("system-metadata", limit=20))

    agents_path = str(project / "AGENTS.md")
    matching = [item for item in payload["items"] if item["source_path"] == agents_path]
    assert len(matching) == 1
    card = matching[0]
    assert card["id"] == "indexed-agents"
    assert card["title"] == "Indexed Agents"
    assert card["metadata"]["inventory_source"] == "ai-artifact-inventory"
    # AGENTS.md is repo-authored source now (was mis-flagged unknown); only
    # missing_mcp_config remains in the fresh inventory problem set.
    assert card["metadata"]["problem_tags"] == "missing_mcp_config"
    assert card["metadata"]["problem_count"] == "1"
    assert card["metadata"]["problem_summary"] == "Missing MCP config"
    assert card["metadata"]["owner_note"] == "keep me"
    assert "indexed" in card["tags"]
    assert "stale_generated" not in card["tags"]
    assert "missing_mcp_config" in card["tags"]


def test_browse_index_clears_stale_problem_metadata_when_fresh_inventory_has_no_problems(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    project.mkdir()
    (project / ".mcp.json").write_text('{"mcpServers": {}}\n', encoding="utf-8")
    docs = project / "docs" / "agent-topics"
    docs.mkdir(parents=True)
    (docs / "CODING.md").write_text("# Source guidance\n", encoding="utf-8")
    inventory = scan_ai_artifacts(
        project_root=project,
        project_brain_id="project-repo",
        discovered_at="2026-06-04T00:00:00+00:00",
    )
    write_ai_artifact_inventory(inventory, brain_root)
    _use_project_inventory_registry(
        tmp_path=tmp_path,
        project=project,
        brain_root=brain_root,
        monkeypatch=monkeypatch,
    )

    cat_dir = tmp_path / "rag" / "system-metadata"
    cat_dir.mkdir(parents=True)

    import src.config.paths as config_paths
    import src.lib.index.index_reader as index_reader
    import src.mcp.augur_framework.tools.infrastructure.browse.index as browse_index
    import src.mcp.augur_framework.tools.infrastructure.browse.index_resolve as index_resolve

    monkeypatch.setattr(browse_index, "get_project_root", lambda: project)
    monkeypatch.setattr(index_resolve, "get_project_root", lambda: project)
    monkeypatch.setattr(config_paths, "get_rag_category_dir", lambda category: cat_dir)
    monkeypatch.setattr(index_reader, "count_category_entries", lambda scan_dir, hub=None: 1)
    monkeypatch.setattr(
        index_reader,
        "list_category_entries",
        lambda scan_dir, hub=None, limit=0: [
            {
                "id": "indexed-coding",
                "name": "indexed-coding",
                "title": "Indexed Coding",
                "description": "Indexed clean project documentation",
                "hub": "system",
                "type": "project-doc",
                "source_path": "docs/agent-topics/CODING.md",
                "tags": ["indexed", "stale_generated"],
                "metadata": {
                    "problem_tags": "stale_generated",
                    "problem_count": "1",
                    "problem_summary": "Stale generated",
                    "owner_note": "keep me",
                },
            }
        ],
    )

    payload = json.loads(browse_index_impl("system-metadata", limit=20))

    coding_path = str(project / "docs" / "agent-topics" / "CODING.md")
    matching = [item for item in payload["items"] if item["source_path"] == coding_path]
    assert len(matching) == 1
    card = matching[0]
    assert card["id"] == "indexed-coding"
    assert card["metadata"]["owner_note"] == "keep me"
    assert card["metadata"]["inventory_source"] == "ai-artifact-inventory"
    assert "problem_tags" not in card["metadata"]
    assert "problem_count" not in card["metadata"]
    assert "problem_summary" not in card["metadata"]
    assert "indexed" in card["tags"]
    assert "stale_generated" not in card["tags"]


def test_browse_index_preserves_total_count_when_inventory_is_added_to_limited_fetch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    project.mkdir()
    (project / "AGENTS.md").write_text("Existing project agent rules\n", encoding="utf-8")
    inventory = scan_ai_artifacts(
        project_root=project,
        project_brain_id="project-repo",
        discovered_at="2026-06-04T00:00:00+00:00",
    )
    write_ai_artifact_inventory(inventory, brain_root)
    _use_project_inventory_registry(
        tmp_path=tmp_path,
        project=project,
        brain_root=brain_root,
        monkeypatch=monkeypatch,
    )

    cat_dir = tmp_path / "rag" / "system-metadata"
    cat_dir.mkdir(parents=True)
    indexed_rows = [
        {
            "id": "indexed-other",
            "name": "indexed-other",
            "title": "Indexed Other",
            "description": "First indexed system metadata row",
            "hub": "system",
            "type": "project-doc",
            "source_path": "OTHER.md",
        },
        *[
            {
                "id": f"indexed-row-{index}",
                "name": f"indexed-row-{index}",
                "title": f"Indexed Row {index}",
                "description": "Additional indexed system metadata row",
                "hub": "system",
                "type": "project-doc",
                "source_path": f"ROW-{index}.md",
            }
            for index in range(1, 10)
        ],
    ]

    import src.config.paths as config_paths
    import src.lib.index.index_reader as index_reader
    import src.mcp.augur_framework.tools.infrastructure.browse.index as browse_index

    monkeypatch.setattr(browse_index, "get_project_root", lambda: project)
    monkeypatch.setattr(config_paths, "get_rag_category_dir", lambda category: cat_dir)
    monkeypatch.setattr(index_reader, "count_category_entries", lambda scan_dir, hub=None: 10)
    monkeypatch.setattr(
        index_reader,
        "list_category_entries",
        lambda scan_dir, hub=None, limit=0: indexed_rows if limit == 0 else indexed_rows[:limit],
    )

    payload = json.loads(browse_index_impl("system-metadata", limit=1))

    assert payload["count"] == 1
    assert payload["total_count"] == 11
    assert payload["truncated"] is True


def test_browse_index_dedupes_inventory_against_unfetched_limited_index_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    project.mkdir()
    (project / "AGENTS.md").write_text("Existing project agent rules\n", encoding="utf-8")
    inventory = scan_ai_artifacts(
        project_root=project,
        project_brain_id="project-repo",
        discovered_at="2026-06-04T00:00:00+00:00",
    )
    write_ai_artifact_inventory(inventory, brain_root)
    _use_project_inventory_registry(
        tmp_path=tmp_path,
        project=project,
        brain_root=brain_root,
        monkeypatch=monkeypatch,
    )

    cat_dir = tmp_path / "rag" / "system-metadata"
    cat_dir.mkdir(parents=True)
    indexed_rows = [
        {
            "id": "indexed-other",
            "name": "indexed-other",
            "title": "Indexed Other",
            "description": "First indexed system metadata row",
            "hub": "system",
            "type": "project-doc",
            "source_path": "OTHER.md",
        },
        {
            "id": "indexed-agents",
            "name": "indexed-agents",
            "title": "Indexed Agents",
            "description": "Indexed instruction artifact outside the display limit",
            "hub": "system",
            "type": "instruction",
            "source_path": "AGENTS.md",
        },
        *[
            {
                "id": f"indexed-row-{index}",
                "name": f"indexed-row-{index}",
                "title": f"Indexed Row {index}",
                "description": "Additional indexed system metadata row",
                "hub": "system",
                "type": "project-doc",
                "source_path": f"ROW-{index}.md",
            }
            for index in range(2, 10)
        ],
    ]

    import src.config.paths as config_paths
    import src.lib.index.index_reader as index_reader
    import src.mcp.augur_framework.tools.infrastructure.browse.index as browse_index
    import src.mcp.augur_framework.tools.infrastructure.browse.index_resolve as index_resolve

    monkeypatch.setattr(browse_index, "get_project_root", lambda: project)
    monkeypatch.setattr(index_resolve, "get_project_root", lambda: project)
    monkeypatch.setattr(config_paths, "get_rag_category_dir", lambda category: cat_dir)
    monkeypatch.setattr(index_reader, "count_category_entries", lambda scan_dir, hub=None: 10)
    monkeypatch.setattr(
        index_reader,
        "list_category_entries",
        lambda scan_dir, hub=None, limit=0: indexed_rows if limit == 0 else indexed_rows[:limit],
    )

    payload = json.loads(browse_index_impl("system-metadata", limit=1))

    assert payload["count"] == 1
    assert payload["total_count"] == 10
    assert payload["truncated"] is True
    all_items_payload = json.loads(browse_index_impl("system-metadata", limit=20))
    agents_cards = [item for item in all_items_payload["items"] if item["source_path"] == str(project / "AGENTS.md")]
    assert len(agents_cards) == 1
    assert agents_cards[0]["id"] == "indexed-agents"


def test_browse_index_filters_stale_inventory_cards_when_index_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    project.mkdir()
    agents_path = project / "AGENTS.md"
    agents_path.write_text("Existing project agent rules\n", encoding="utf-8")
    inventory = scan_ai_artifacts(
        project_root=project,
        project_brain_id="project-repo",
        discovered_at="2026-06-04T00:00:00+00:00",
    )
    write_ai_artifact_inventory(inventory, brain_root)
    agents_path.unlink()
    _use_project_inventory_registry(
        tmp_path=tmp_path,
        project=project,
        brain_root=brain_root,
        monkeypatch=monkeypatch,
    )

    import src.config.paths as config_paths
    import src.mcp.augur_framework.tools.infrastructure.browse.index as browse_index

    monkeypatch.setattr(browse_index, "get_project_root", lambda: project)
    monkeypatch.setattr(
        config_paths,
        "get_rag_category_dir",
        lambda category: tmp_path / "rag" / "system-metadata",
    )

    payload = json.loads(browse_index_impl("system-metadata", limit=20))

    assert payload["items"] == []
    assert payload["count"] == 0
    assert payload["status"] == "stale"
