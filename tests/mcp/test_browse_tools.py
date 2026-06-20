import json
import unittest.mock
from pathlib import Path

import pytest

# The conftest sets AUGUR_ROOT to a temp dir, so get_project_root() won't
# return the real repo root during tests.  Compute it from this file's location
# so tests that need real project files can patch the browse module.
_REAL_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.asyncio
async def test_reveal_in_finder_validates_allowed_paths():
    from src.mcp.augur_framework.tools.infrastructure.browse import reveal_in_finder_impl

    result = json.loads(await reveal_in_finder_impl("/etc/passwd"))
    assert result["success"] is False
    assert "not within allowed" in result["error"]


@pytest.mark.asyncio
async def test_open_file_validates_allowed_paths():
    from src.mcp.augur_framework.tools.infrastructure.browse import open_file_impl

    result = json.loads(await open_file_impl("/etc/passwd"))
    assert result["success"] is False
    assert "not within allowed" in result["error"]


@pytest.mark.asyncio
async def test_list_vault_items_returns_structure():
    from src.mcp.augur_framework.tools.infrastructure.browse import list_vault_items_impl

    result = json.loads(await list_vault_items_impl())
    assert "items" in result
    assert "count" in result
    assert isinstance(result["items"], list)


@pytest.mark.asyncio
async def test_list_prompts_returns_structure():
    from src.mcp.augur_framework.tools.infrastructure.browse import list_prompts_impl

    result = json.loads(await list_prompts_impl())
    assert "items" in result
    assert isinstance(result["items"], list)


@pytest.mark.asyncio
async def test_list_scripts_returns_structure():
    from src.mcp.augur_framework.tools.infrastructure.browse import list_scripts_impl

    result = json.loads(await list_scripts_impl())
    assert "items" in result
    assert isinstance(result["items"], list)


@pytest.mark.asyncio
async def test_list_cli_commands_returns_structure():
    from src.mcp.augur_framework.tools.infrastructure.browse import list_cli_commands_impl

    result = json.loads(await list_cli_commands_impl())
    assert "items" in result
    assert isinstance(result["items"], list)


@pytest.mark.asyncio
async def test_list_integrations_returns_structure():
    from src.mcp.augur_framework.tools.infrastructure.browse import list_integrations_impl

    result = json.loads(await list_integrations_impl())
    assert "items" in result and isinstance(result["items"], list)


@pytest.mark.asyncio
async def test_list_agents_returns_structure():
    from src.mcp.augur_framework.tools.infrastructure.browse import list_agents_impl

    result = json.loads(await list_agents_impl())
    assert "items" in result and isinstance(result["items"], list)


@pytest.mark.asyncio
async def test_list_adrs_returns_items():
    from src.mcp.augur_framework.tools.infrastructure.browse import list_adrs_impl

    result = json.loads(await list_adrs_impl())
    assert "items" in result and isinstance(result["items"], list)
    assert result["count"] >= 0


@pytest.mark.asyncio
async def test_list_tests_returns_structure():
    from src.mcp.augur_framework.tools.infrastructure.browse import list_tests_impl

    result = json.loads(await list_tests_impl())
    assert "items" in result and isinstance(result["items"], list)


@pytest.mark.asyncio
async def test_list_api_routes_returns_structure():
    from src.mcp.augur_framework.tools.infrastructure.browse import list_api_routes_impl

    result = json.loads(await list_api_routes_impl())
    assert "items" in result and isinstance(result["items"], list)
    assert result["count"] >= 0


def test_browse_index_wiki_items_include_maintenance_status(tmp_path):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index
    from src.mcp.augur_framework.tools.infrastructure.browse import index_wiki

    rag_wiki = tmp_path / "rag" / "wiki"
    concept_entry = rag_wiki / "concepts" / "freshness.md"
    concept_entry.parent.mkdir(parents=True)
    concept_entry.write_text(
        "\n".join(
            [
                "---",
                "id: concepts/freshness",
                "title: Wiki Freshness",
                "description: Shows wiki freshness truth.",
                "type: wiki",
                "source_path: /tmp/wiki/concepts/freshness.md",
                "indexed_at: '2026-06-07T03:35:00+00:00'",
                "---",
                "",
                "Body",
            ]
        ),
        encoding="utf-8",
    )

    status_payload = {
        "verdict": "structure_ok_compile_backlog",
        "healthy": False,
        "compiler": {
            "sources_pending_or_changed": 1812,
            "sources_total": 1930,
        },
        "batches": {
            "last_batch": str(tmp_path / "runtime" / "wiki" / "concept-batches" / "update.json"),
            "last_batch_handle": "update",
            "last_batch_created": "2026-06-07T05:38:36+00:00",
            "last_batch_mode": "update",
        },
        "index": {
            "wiki_rag_entries": 98,
        },
    }

    with (
        unittest.mock.patch("src.config.paths.get_rag_category_dir", return_value=rag_wiki),
        unittest.mock.patch.object(
            index_wiki,
            "_wiki_status_payload_for_browse",
            return_value=status_payload,
            create=True,
        ),
        unittest.mock.patch.object(
            index_wiki,
            "_wiki_batch_quality_for_browse",
            return_value={
                "quality": "weak",
                "reason": "19/20 low-signal sources; reindex refreshed Browse but no wiki pages were applied.",
                "item_count": 20,
            },
            create=True,
        ),
    ):
        result = json.loads(browse_index.browse_index_impl("wiki", limit=1))

    assert result["last_indexed"] == "2026-06-07T03:35:00+00:00"
    item = result["items"][0]
    assert item["metadata"]["wikiMaintenanceVerdict"] == "structure_ok_compile_backlog"
    assert item["metadata"]["wikiPendingSources"] == "1812"
    assert item["metadata"]["wikiSourceTotal"] == "1930"
    assert item["metadata"]["wikiLastReindexedAt"] == "2026-06-07T03:35:00+00:00"
    assert item["metadata"]["wikiLastBatchQuality"] == "weak"
    assert item["metadata"]["wikiLastBatchReason"].startswith("19/20 low-signal sources")


@pytest.mark.asyncio
async def test_knowledge_hub_files_returns_documents():
    """knowledge-hub-files should return document files from ~/Documents/Augur/."""
    from src.mcp.augur_framework.tools.infrastructure.browse import list_knowledge_hub_files_impl

    result = json.loads(await list_knowledge_hub_files_impl())
    assert "files" in result
    assert isinstance(result["files"], list)
    # User has documents in ~/Documents/Augur/
    if result["count"] > 0:
        f = result["files"][0]
        assert "path" in f
        assert "name" in f
        assert "skill" in f


@pytest.mark.asyncio
async def test_reveal_in_finder_accepts_project_paths():
    """reveal-in-finder accepts paths within the project root."""
    from src.mcp.augur_framework.tools.infrastructure.browse import reveal_in_finder_impl

    # Use the real project root so pyproject.toml exists on disk
    test_path = str(_REAL_PROJECT_ROOT / "pyproject.toml")
    # Patch get_project_root inside the browse module so the allowlist
    # includes the real repo, and mock subprocess.run to avoid opening Finder.
    with (
        unittest.mock.patch(
            "src.mcp.augur_framework.tools.infrastructure.browse.get_project_root",
            return_value=_REAL_PROJECT_ROOT,
        ),
        unittest.mock.patch("src.mcp.augur_framework.tools.infrastructure.browse.subprocess.run"),
    ):
        result = json.loads(await reveal_in_finder_impl(test_path))
        assert result["success"] is True


@pytest.mark.asyncio
async def test_list_vault_items_fields():
    """Vault items have required fields."""
    from src.mcp.augur_framework.tools.infrastructure.browse import list_vault_items_impl

    result = json.loads(await list_vault_items_impl())
    if result["count"] > 0:
        item = result["items"][0]
        assert "id" in item
        assert "title" in item
        assert "skill" in item
        assert "path" in item
        assert "file_type" in item


@pytest.mark.asyncio
async def test_list_adrs_item_fields():
    """ADR items have required fields including adr_number."""
    from src.mcp.augur_framework.tools.infrastructure.browse import list_adrs_impl

    # Patch get_project_root so list_adrs_impl can find the real vault ADR directory
    with unittest.mock.patch(
        "src.mcp.augur_framework.tools.infrastructure.browse.get_project_root",
        return_value=_REAL_PROJECT_ROOT,
    ):
        result = json.loads(await list_adrs_impl())
    assert result["count"] > 0, "Project should have ADRs"
    item = result["items"][0]
    assert "id" in item
    assert "title" in item
    assert "hub" in item
    assert "path" in item
    assert "status" in item
    assert "adr_number" in item


@pytest.mark.asyncio
async def test_list_cli_commands_item_fields():
    """CLI command items have required fields."""
    from src.mcp.augur_framework.tools.infrastructure.browse import list_cli_commands_impl

    # Patch get_project_root so we scan real SKILL.md files
    with unittest.mock.patch(
        "src.mcp.augur_framework.tools.infrastructure.browse.get_project_root",
        return_value=_REAL_PROJECT_ROOT,
    ):
        result = json.loads(await list_cli_commands_impl())
    if result["count"] > 0:
        item = result["items"][0]
        assert "id" in item
        assert item["id"].startswith("/")
        assert "title" in item
        assert "hub" in item
        assert "category" in item


@pytest.mark.asyncio
async def test_open_file_rejects_nonexistent_path():
    """open-file rejects paths that don't exist even if within allowed roots."""
    from src.mcp.augur_framework.tools.infrastructure.browse import open_file_impl
    from src.config.paths import get_project_root

    fake_path = str(get_project_root() / "nonexistent_file_xyz.txt")
    result = json.loads(await open_file_impl(fake_path))
    assert result["success"] is False
    assert "does not exist" in result["error"]
