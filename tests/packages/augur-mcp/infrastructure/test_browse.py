"""
Tests for browse-related MCP tools (infrastructure/browse.py).

Validates path security, vault listing, prompt listing, script listing,
CLI command listing, ADR listing, and other browse operations.

Run with: pytest tests/packages/augur-mcp/infrastructure/test_browse.py -v
"""

# TODO_CLEANUP: This file is 984 lines — consider splitting into smaller modules

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.lib.frontmatter_utils import write_frontmatter
from src.mcp.augur_framework.tools.infrastructure.browse import (
    _is_path_allowed,
    browse_index_impl,
    cli_help_impl,
    list_adrs_impl,
    list_agents_impl,
    list_cli_commands_impl,
    list_knowledge_hub_files_impl,
    list_prompts_impl,
    list_scripts_impl,
    list_vault_items_impl,
    open_file_impl,
    reveal_in_finder_impl,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_project_root(tmp_path: Path, monkeypatch):
    """Set up a mock project root with minimal structure."""
    project_root = tmp_path / "project"
    project_root.mkdir()

    # Create current project-brain skill directory structure.
    (project_root / "project-brain" / "capabilities" / "skills").mkdir(parents=True)

    # Retired repo-root skill directory remains absent; browse tools should use
    # project-brain/capabilities/skills and generated client skill roots.

    # Create legacy plugins directory structure for compatibility checks
    (project_root / "plugins").mkdir()

    # Create docs directory
    (project_root / "docs" / "decisions").mkdir(parents=True)

    # Create config directory
    (project_root / "config" / "agents").mkdir(parents=True)

    # Create apps directory
    (project_root / "apps" / "dashboard" / "app" / "api").mkdir(parents=True)

    # Create tests directory
    (project_root / "tests").mkdir()

    # Patch get_project_root in every submodule that uses it
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse._helpers.get_project_root", lambda: project_root
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.skills.get_project_root", lambda: project_root
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.agents.get_project_root", lambda: project_root
    )
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.dev.get_project_root", lambda: project_root
    )

    # Isolate the private vault so prompt listing (ADR-748/751 scans the
    # brain capture dir for `x-augur-note-type: prompt` cards) does not read
    # the real user vault. list_prompts_impl imports get_vault_dir locally
    # from src.config.paths, so patch it there.
    vault_root = project_root / "vault"
    (vault_root / "knowledge" / "notes").mkdir(parents=True)
    monkeypatch.setattr("src.config.paths.get_vault_dir", lambda: vault_root)

    return project_root


@pytest.fixture
def mock_vault_dir(tmp_path: Path, monkeypatch):
    """Set up a mock vault directory."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir()
    monkeypatch.setattr("src.mcp.augur_framework.tools.infrastructure.browse._helpers.get_vault_dir", lambda: vault_dir)
    monkeypatch.setattr("src.mcp.augur_framework.tools.infrastructure.browse.vault.get_vault_dir", lambda: vault_dir)
    return vault_dir


@pytest.fixture
def mock_documents_dir(tmp_path: Path, monkeypatch):
    """Set up a mock documents directory."""
    from src.lib.index.document_sources import DocumentSource

    docs_dir = tmp_path / "documents"
    docs_dir.mkdir()
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse._helpers.get_documents_dir", lambda: docs_dir
    )
    monkeypatch.setattr("src.mcp.augur_framework.tools.infrastructure.browse.vault.get_documents_dir", lambda: docs_dir)
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse.vault.default_document_sources",
        lambda documents_dir: [DocumentSource("documents", "Au-docs", documents_dir, preserve_legacy_output=True)],
    )
    return docs_dir


@pytest.fixture
def mock_allowed_roots(mock_project_root, mock_vault_dir, mock_documents_dir, tmp_path, monkeypatch):
    """Set up mock allowed roots for path validation."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    monkeypatch.setattr("src.mcp.augur_framework.tools.infrastructure.browse._helpers.get_logs_dir", lambda: logs_dir)
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    monkeypatch.setattr(
        "src.mcp.augur_framework.tools.infrastructure.browse._helpers.get_runtime_dir",
        lambda: runtime_dir,
    )
    return {
        "project": mock_project_root,
        "vault": mock_vault_dir,
        "documents": mock_documents_dir,
        "logs": logs_dir,
        "runtime": runtime_dir,
    }


# =============================================================================
# _is_path_allowed
# =============================================================================


class TestIsPathAllowed:
    """Tests for path security validation."""

    def test_allowed_path(self, mock_allowed_roots):
        """Path within an allowed root is accepted."""
        root = mock_allowed_roots["project"]
        assert _is_path_allowed(str(root / "src" / "main.py")) is True

    def test_disallowed_path(self, mock_allowed_roots):
        """Path outside all roots is rejected."""
        assert _is_path_allowed("/etc/passwd") is False

    def test_root_itself_allowed(self, mock_allowed_roots):
        """The root directory itself is allowed."""
        root = mock_allowed_roots["project"]
        assert _is_path_allowed(str(root)) is True

    def test_adr_extract_destination_allowed(self, mock_allowed_roots):
        """Extracted archived-ADR bodies (runtime adr-extracts) can be opened."""
        runtime = mock_allowed_roots["runtime"]
        extracted = runtime / "adr-extracts" / "ADR-004" / "ADR-004-markdown-rag.md"
        assert _is_path_allowed(str(extracted)) is True

    def test_other_runtime_state_still_disallowed(self, mock_allowed_roots):
        """Only adr-extracts is exposed, not the rest of the runtime state dir."""
        runtime = mock_allowed_roots["runtime"]
        assert _is_path_allowed(str(runtime / "daemon" / "journal.log")) is False


# =============================================================================
# reveal_in_finder_impl
# =============================================================================


class TestRevealInFinderImpl:
    """Tests for Finder reveal functionality."""

    @pytest.mark.asyncio
    async def test_disallowed_path(self, mock_allowed_roots):
        """Disallowed path returns error."""
        result = json.loads(await reveal_in_finder_impl("/etc/passwd"))
        assert result["success"] is False
        assert "not within allowed" in result["error"]

    @pytest.mark.asyncio
    async def test_nonexistent_path(self, mock_allowed_roots):
        """Nonexistent path returns error."""
        root = mock_allowed_roots["project"]
        result = json.loads(await reveal_in_finder_impl(str(root / "nope.txt")))
        assert result["success"] is False
        assert "does not exist" in result["error"]

    @pytest.mark.asyncio
    async def test_valid_path(self, mock_allowed_roots):
        """Valid path triggers reveal."""
        root = mock_allowed_roots["project"]
        test_file = root / "test.txt"
        test_file.write_text("content")

        with patch("src.mcp.augur_framework.tools.infrastructure.browse.file_actions.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = json.loads(await reveal_in_finder_impl(str(test_file)))
            assert result["success"] is True


# =============================================================================
# open_file_impl
# =============================================================================


class TestOpenFileImpl:
    """Tests for file open functionality."""

    @pytest.mark.asyncio
    async def test_disallowed_path(self, mock_allowed_roots):
        """Disallowed path returns error."""
        result = json.loads(await open_file_impl("/etc/passwd"))
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_nonexistent_path(self, mock_allowed_roots):
        """Nonexistent path returns error."""
        root = mock_allowed_roots["project"]
        result = json.loads(await open_file_impl(str(root / "nope.txt")))
        assert result["success"] is False


# =============================================================================
# Indexed document-source roots (Desktop / Downloads)
# =============================================================================


class TestIndexedDocumentSourceAllowed:
    """reveal/open accept files inside indexed document-source roots.

    Regression (2026-06): Desktop/Downloads documents are indexed into Browse
    but reveal-in-finder/open-file rejected them as 'not within allowed
    directories'. The allow-list must include the same roots the indexer scans.
    """

    @pytest.fixture
    def desktop_source(self, mock_allowed_roots, tmp_path, monkeypatch):
        from src.lib.index.document_sources import DocumentSource

        desktop = tmp_path / "Desktop"
        desktop.mkdir()

        def patched_sources(documents_dir):
            return [DocumentSource("desktop", "Desktop", desktop)]

        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse._helpers.default_document_sources",
            patched_sources,
        )
        monkeypatch.setattr(
            "src.lib.index.document_source_config.default_document_sources",
            patched_sources,
        )
        return desktop

    def test_is_path_allowed_includes_indexed_desktop(self, desktop_source):
        """A Desktop document path passes _is_path_allowed."""
        assert _is_path_allowed(str(desktop_source / "report.doc")) is True

    @pytest.mark.asyncio
    async def test_reveal_accepts_indexed_desktop(self, desktop_source):
        """reveal-in-finder reveals an existing indexed Desktop file."""
        doc = desktop_source / "report.doc"
        doc.write_text("x")
        with patch("src.mcp.augur_framework.tools.infrastructure.browse.file_actions.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = json.loads(await reveal_in_finder_impl(str(doc)))
        assert result["success"] is True


class TestConfiguredSharedDocumentSourceAllowed:
    """reveal/open accept configured shared document cache paths."""

    @pytest.fixture
    def shared_source_cache(self, mock_allowed_roots, tmp_path, monkeypatch):
        project_root = mock_allowed_roots["project"]
        brain_manifest = project_root / "project-brain" / "BRAIN.yaml"
        brain_manifest.write_text(
            "schema_version: 1\n" "id: project-y\n" "type: project\n" f"root: {project_root / 'project-brain'}\n",
            encoding="utf-8",
        )
        source_config = project_root / "config" / "documents" / "sources.yaml"
        source_config.parent.mkdir(parents=True, exist_ok=True)
        source_config.write_text(
            "sources:\n"
            "  - id: project-y-drive\n"
            "    name: Project Y Drive\n"
            "    provider: google-drive\n"
            "    remote_id: drive-folder-123\n",
            encoding="utf-8",
        )
        cache_root = tmp_path / "cache"
        shared_cache = cache_root / "document-sources" / "project-y-drive"
        shared_cache.mkdir(parents=True)
        monkeypatch.setattr(
            "src.lib.index.document_source_config.get_cache_dir",
            lambda: cache_root,
        )
        return shared_cache

    def test_is_path_allowed_includes_configured_shared_cache(self, shared_source_cache):
        assert _is_path_allowed(str(shared_source_cache / "proposal.pdf")) is True

    @pytest.mark.asyncio
    async def test_reveal_accepts_configured_shared_cache(self, shared_source_cache):
        doc = shared_source_cache / "proposal.pdf"
        doc.write_text("x")
        with patch("src.mcp.augur_framework.tools.infrastructure.browse.file_actions.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = json.loads(await reveal_in_finder_impl(str(doc)))
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_open_accepts_configured_shared_cache(self, shared_source_cache):
        doc = shared_source_cache / "proposal.pdf"
        doc.write_text("x")
        with patch("src.mcp.augur_framework.tools.infrastructure.browse.file_actions.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = json.loads(await open_file_impl(str(doc)))
        assert result["success"] is True


# =============================================================================
# list_vault_items_impl
# =============================================================================


class TestListVaultItemsImpl:
    """Tests for vault item listing."""

    @pytest.mark.asyncio
    async def test_empty_vault(self, mock_vault_dir):
        """Empty vault returns empty list."""
        result = json.loads(await list_vault_items_impl())
        assert result["count"] == 0
        assert result["items"] == []

    @pytest.mark.asyncio
    async def test_vault_nonexistent(self, tmp_path, monkeypatch):
        """Nonexistent vault dir returns empty list."""
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.vault.get_vault_dir",
            lambda: tmp_path / "no_vault",
        )
        result = json.loads(await list_vault_items_impl())
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_vault_with_items(self, mock_vault_dir):
        """Vault with files returns item list."""
        # Create a skill directory structure
        skill_dir = mock_vault_dir / "career" / "career-manager"
        skill_dir.mkdir(parents=True)
        (skill_dir / "data.json").write_text('{"key": "value"}')
        (skill_dir / "context" / "profile.json").mkdir(parents=True)
        # Actually need a file, not just a dir
        context_dir = skill_dir / "context"
        (context_dir / "profile.json").rmdir()  # Remove the directory we made by mistake
        skill_dir_context = skill_dir / "context"
        skill_dir_context.mkdir(exist_ok=True)
        (skill_dir_context / "profile.json").write_text("{}")

        result = json.loads(await list_vault_items_impl())
        assert result["count"] == 2
        assert any("data.json" in item["id"] for item in result["items"])


class TestBrowseIndexOverlayScope:
    def test_integrations_include_external_registry_services(self, tmp_path, monkeypatch):
        project_root = tmp_path / "project"
        registry_path = project_root / "config" / "integrations" / "external_mcp_registry.yaml"
        registry_path.parent.mkdir(parents=True)
        registry_path.write_text(
            "version: 2\n"
            "services:\n"
            "  gh:\n"
            "    name: GitHub CLI\n"
            "    type: cli\n"
            "    description: GitHub CLI for repository management\n"
            "    enabled: true\n"
            "    check_command: gh --version\n"
            "    used_by:\n"
            "      - developer\n"
            "    setup_url: https://cli.github.com/\n",
            encoding="utf-8",
        )
        rag_dir = tmp_path / "rag"
        (rag_dir / "integrations").mkdir(parents=True)
        monkeypatch.setattr("src.config.paths.get_rag_category_dir", lambda category: rag_dir / category)
        monkeypatch.setattr("src.lib.external_services.get_project_root", lambda: project_root)
        monkeypatch.setattr(
            "src.lib.external_services.external_service_statuses_by_id",
            lambda project_root=None: {
                "gh": {
                    "service_id": "gh",
                    "name": "GitHub CLI",
                    "type": "cli",
                    "status": "connected",
                    "version": "gh version 2.70.0",
                }
            },
        )

        result = json.loads(browse_index_impl("integrations"))

        assert result["count"] == 1
        item = result["items"][0]
        assert item["id"] == "cli:gh"
        assert item["title"] == "GitHub CLI"
        assert item["metadata"]["external_service_id"] == "gh"
        assert item["metadata"]["service_type"] == "cli"
        assert item["metadata"]["status"] == "connected"
        assert item["metadata"]["version"] == "gh version 2.70.0"
        assert item["metadata"]["check_command"] == "gh --version"
        assert item["cli_tools"] == [
            {
                "name": "gh",
                "installed": True,
                "version": "gh version 2.70.0",
                "configured": None,
                "install_hint": "",
                "homepage": "https://cli.github.com/",
            }
        ]

    def test_filesystem_categories_skip_missing_source_paths(self, tmp_path, monkeypatch):
        project_root = tmp_path / "project"
        active_source = project_root / "project-brain" / "capabilities" / "skills" / "active" / "SKILL.md"
        active_source.parent.mkdir(parents=True)
        active_source.write_text("---\nname: active\n---\n", encoding="utf-8")

        rag_dir = tmp_path / "rag"
        pages_dir = rag_dir / "pages"
        write_frontmatter(
            pages_dir / "active.md",
            {
                "id": "active",
                "name": "active",
                "title": "active",
                "type": "page",
                "hub": "brain",
                "source_path": "project-brain/capabilities/skills/active/SKILL.md",
            },
            "",
        )
        write_frontmatter(
            pages_dir / "stale.md",
            {
                "id": "stale",
                "name": "stale",
                "title": "stale",
                "type": "page",
                "hub": "life",
                "source_path": "project-brain/capabilities/skills/stale/SKILL.md",
            },
            "",
        )

        monkeypatch.setattr(
            "src.config.paths.get_rag_category_dir",
            lambda category: rag_dir / category,
        )
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.index_resolve.get_project_root",
            lambda: project_root,
        )

        result = json.loads(browse_index_impl("pages", limit=10))

        assert [item["id"] for item in result["items"]] == ["active"]
        assert result["count"] == 1
        assert "total_count" not in result

    def test_last_indexed_uses_full_filtered_result_before_limit(self, tmp_path, monkeypatch):
        source_dir = tmp_path / "sources"
        source_dir.mkdir()
        old_source = source_dir / "old.txt"
        new_source = source_dir / "new.txt"
        old_source.write_text("old", encoding="utf-8")
        new_source.write_text("new", encoding="utf-8")

        rag_dir = tmp_path / "rag"
        write_frontmatter(
            rag_dir / "documents" / "a-old.md",
            {
                "id": "old",
                "name": "old",
                "title": "Old",
                "type": "document",
                "hub": "desktop",
                "source_path": str(old_source),
                "indexed_at": "2026-01-01T00:00:00+00:00",
            },
            "",
        )
        write_frontmatter(
            rag_dir / "documents" / "z-new.md",
            {
                "id": "new",
                "name": "new",
                "title": "New",
                "type": "document",
                "hub": "desktop",
                "source_path": str(new_source),
                "indexed_at": "2026-06-01T09:20:00+00:00",
            },
            "",
        )

        monkeypatch.setattr(
            "src.config.paths.get_rag_category_dir",
            lambda category: rag_dir / category,
        )

        result = json.loads(browse_index_impl("documents", limit=1))

        assert [item["id"] for item in result["items"]] == ["old"]
        assert result["total_count"] == 2
        assert result["last_indexed"] == "2026-06-01T09:20:00+00:00"

    def test_documents_preserve_attachment_and_catalog_metadata(self, tmp_path, monkeypatch):
        source_dir = tmp_path / "shared-cache"
        source_dir.mkdir()
        source_file = source_dir / "architecture.md"
        source_file.write_text("architecture", encoding="utf-8")

        rag_dir = tmp_path / "rag"
        write_frontmatter(
            rag_dir / "documents" / "_sources" / "project-y-drive" / "architecture.md",
            {
                "id": "architecture",
                "name": "architecture",
                "title": "Architecture Overview",
                "type": "document",
                "hub": "project-y-drive",
                "source_path": str(source_file),
                "attached_brain_ids": ["project-y", "personal"],
                "source_type": "shared",
                "provider": "google-drive",
                "remote_id": "google-drive:file:def456",
                "index_status": "source_changed",
                "catalog_summary": "Catalog summary used on cards.",
                "summary_status": "auto",
                "remote_revision": "drive-revision-43",
                "indexed_revision": "drive-revision-42",
            },
            "Body",
        )

        monkeypatch.setattr(
            "src.config.paths.get_rag_category_dir",
            lambda category: rag_dir / category,
        )

        result = json.loads(browse_index_impl("documents", limit=10))

        item = result["items"][0]
        assert item["title"] == "Architecture Overview"
        assert item["metadata"]["attached_brain_ids"] == "project-y,personal"
        assert item["metadata"]["attachedBrainIds"] == "project-y,personal"
        assert item["metadata"]["provider"] == "google-drive"
        assert item["metadata"]["indexStatus"] == "source_changed"
        assert item["metadata"]["catalogSummary"] == "Catalog summary used on cards."
        assert item["metadata"]["remoteRevision"] == "drive-revision-43"
        assert item["metadata"]["indexedRevision"] == "drive-revision-42"

    def test_search_ranks_recent_matching_vault_transcript_before_limit(self, tmp_path, monkeypatch):
        rag_dir = tmp_path / "rag"
        vault_dir = rag_dir / "vault"
        query = "offload-demo-short"

        for index in range(3):
            write_frontmatter(
                vault_dir / "notes" / "private" / "demo" / "transcripts" / f"{query}-20260601T0{index}.md",
                {
                    "id": f"vault:private:notes/demo/transcripts/{query}-20260601T0{index}",
                    "type": "vault",
                    "name": f"{query}-20260601T0{index}",
                    "title": f"Transcript: {query}.m4a",
                    "description": f"Older transcript {index}",
                    "journey_category": "notes",
                    "vault_scope": "private",
                    "promotion_state": "private",
                    "source_path": str(
                        tmp_path / "vault" / "notes" / "demo" / "transcripts" / f"{query}-20260601T0{index}.md"
                    ),
                    "modified": f"2026-06-01T0{index}:00:00+00:00",
                    "indexed_at": "2026-06-02T07:12:16+00:00",
                },
                "",
            )
        write_frontmatter(
            vault_dir / "notes" / "private" / "examples" / "transcripts" / f"{query}-20260602T071215Z.md",
            {
                "id": f"vault:private:notes/examples/transcripts/{query}-20260602T071215Z",
                "type": "vault",
                "name": f"{query}-20260602T071215Z",
                "title": "Offload Workflow Example Offline Transcript",
                "description": "New workflow example transcript",
                "journey_category": "notes",
                "vault_scope": "private",
                "promotion_state": "private",
                "source_path": str(
                    tmp_path / "vault" / "notes" / "examples" / "transcripts" / f"{query}-20260602T071215Z.md"
                ),
                "modified": "2026-06-02T07:12:15+00:00",
                "indexed_at": "2026-06-02T07:12:16+00:00",
            },
            "",
        )

        monkeypatch.setattr("src.config.paths.get_rag_category_dir", lambda category: rag_dir / category)

        result = json.loads(browse_index_impl("vault", journey_category="notes", search=query, limit=1))

        assert [item["id"] for item in result["items"]] == [
            f"vault:private:notes/examples/transcripts/{query}-20260602T071215Z",
        ]
        assert result["total_count"] == 4
        assert result["truncated"] is True

    def test_pages_resolve_project_relative_source_path_to_absolute(self, tmp_path, monkeypatch):
        project_root = tmp_path / "project"
        active_source = project_root / "project-brain" / "capabilities" / "skills" / "ai" / "SKILL.md"
        active_source.parent.mkdir(parents=True)
        active_source.write_text("---\nname: ai\n---\n", encoding="utf-8")

        rag_dir = tmp_path / "rag"
        write_frontmatter(
            rag_dir / "pages" / "ai.md",
            {
                "id": "ai",
                "name": "ai",
                "title": "AI",
                "type": "page",
                "hub": "brain",
                "route": "/workspace/ai",
                "source_path": "project-brain/capabilities/skills/ai/SKILL.md",
            },
            "",
        )

        monkeypatch.setattr(
            "src.config.paths.get_rag_category_dir",
            lambda category: rag_dir / category,
        )
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.index_resolve.get_project_root",
            lambda: project_root,
        )

        result = json.loads(browse_index_impl("pages", limit=10))

        assert result["count"] == 1
        assert result["items"][0]["source_path"] == str(active_source)

    def test_pages_do_not_resolve_unsafe_relative_source_path(self, tmp_path, monkeypatch):
        project_root = tmp_path / "project"
        project_root.mkdir()
        outside_source = tmp_path / "outside" / "SKILL.md"
        outside_source.parent.mkdir(parents=True)
        outside_source.write_text("---\nname: outside\n---\n", encoding="utf-8")

        rag_dir = tmp_path / "rag"
        write_frontmatter(
            rag_dir / "pages" / "outside.md",
            {
                "id": "outside",
                "name": "outside",
                "title": "Outside",
                "type": "page",
                "hub": "brain",
                "route": "/workspace/outside",
                "source_path": "../outside/SKILL.md",
            },
            "",
        )

        monkeypatch.setattr(
            "src.config.paths.get_rag_category_dir",
            lambda category: rag_dir / category,
        )
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.index_resolve.get_project_root",
            lambda: project_root,
        )

        result = json.loads(browse_index_impl("pages", limit=10))

        assert result["count"] == 1
        assert result["items"][0]["source_path"] == "../outside/SKILL.md"

    def test_scope_filter_keeps_shared_private_and_packet_distinct(self, tmp_path, monkeypatch):
        rag_dir = tmp_path / "rag"
        vault_dir = rag_dir / "vault"
        write_frontmatter(
            vault_dir / "notes" / "shared" / "plan.md",
            {
                "id": "vault:shared:notes/plan",
                "type": "vault",
                "name": "plan",
                "description": "Shared plan",
                "journey_category": "notes",
                "vault_scope": "shared",
                "promotion_state": "integrated",
                "source_path": str(tmp_path / "project-brain" / "knowledge" / "notes" / "plan.md"),
            },
            "",
        )
        write_frontmatter(
            vault_dir / "notes" / "private" / "plan.md",
            {
                "id": "vault:private:notes/plan",
                "type": "vault",
                "name": "plan",
                "description": "Private plan",
                "journey_category": "notes",
                "vault_scope": "private",
                "promotion_state": "private",
                "source_path": str(tmp_path / "private-vault" / "notes" / "plan.md"),
            },
            "",
        )
        write_frontmatter(
            vault_dir / "inbox" / "promotions" / "packet-a" / "synthesis.md",
            {
                "id": "vault:shared:inbox/promotions/packet-a/synthesis",
                "type": "vault",
                "name": "synthesis",
                "description": "Packet",
                "journey_category": "inbox",
                "vault_scope": "shared",
                "promotion_state": "packet",
                "source_path": str(tmp_path / "project-brain" / "inbox" / "promotions" / "packet-a" / "synthesis.md"),
            },
            "",
        )

        monkeypatch.setattr("src.config.paths.get_rag_category_dir", lambda category: rag_dir / category)

        private_result = json.loads(browse_index_impl("vault", journey_category="notes", scope="private"))
        assert private_result["count"] == 1
        assert private_result["items"][0]["id"] == "vault:private:notes/plan"
        assert private_result["items"][0]["metadata"]["vault_scope"] == "private"

        shared_result = json.loads(browse_index_impl("vault", journey_category="notes", scope="shared"))
        assert [item["id"] for item in shared_result["items"]] == ["vault:shared:notes/plan"]

        packet_result = json.loads(browse_index_impl("vault", journey_category="inbox", scope="packet"))
        assert [item["id"] for item in packet_result["items"]] == [
            "vault:shared:inbox/promotions/packet-a/synthesis",
        ]

    def test_scope_filter_runs_before_limit_for_fallback_journey_filter(self, tmp_path, monkeypatch):
        rag_dir = tmp_path / "rag"
        vault_dir = rag_dir / "vault"
        for index in range(3):
            write_frontmatter(
                vault_dir / "flat" / f"0{index}-shared.md",
                {
                    "id": f"vault:shared:notes/shared-{index}",
                    "type": "vault",
                    "name": f"shared-{index}",
                    "journey_category": "notes",
                    "vault_scope": "shared",
                    "promotion_state": "integrated",
                    "source_path": str(tmp_path / "project-brain" / "knowledge" / "notes" / f"shared-{index}.md"),
                },
                "",
            )
        write_frontmatter(
            vault_dir / "flat" / "99-private.md",
            {
                "id": "vault:private:notes/private-late",
                "type": "vault",
                "name": "private-late",
                "journey_category": "notes",
                "vault_scope": "private",
                "promotion_state": "private",
                "source_path": str(tmp_path / "private-vault" / "notes" / "private-late.md"),
            },
            "",
        )
        monkeypatch.setattr("src.config.paths.get_rag_category_dir", lambda category: rag_dir / category)

        result = json.loads(browse_index_impl("vault", journey_category="notes", scope="private", limit=1))

        assert [item["id"] for item in result["items"]] == ["vault:private:notes/private-late"]

    def test_staged_client_leftovers_show_as_draft_items(self, tmp_path, monkeypatch):
        runtime_dir = tmp_path / "runtime"
        batch = runtime_dir / "staging" / "client-leftovers-20260509-101626"
        for client, relative in {
            "codex": "codex/.tmp/plugins/example/SKILL.md",
            "gemini": "gemini/extensions.disabled/example/SKILL.md",
            "claude": "claude/plugins/cache.disabled/example/SKILL.md",
        }.items():
            skill_path = batch / relative
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text(f"---\nname: {client}-example\n---\n", encoding="utf-8")

        monkeypatch.setattr("src.config.paths.get_rag_category_dir", lambda category: tmp_path / "rag" / category)
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.index_sweep.get_runtime_dir",
            lambda: runtime_dir,
            raising=False,
        )

        result = json.loads(browse_index_impl("vault", journey_category="drafts"))

        assert result["count"] == 1
        item = result["items"][0]
        assert item["id"] == "runtime-staging:client-leftovers-20260509-101626"
        assert item["title"] == "Client leftovers 20260509 101626"
        assert item["type"] == "vault"
        assert item["source_path"] == str(batch)
        assert item["metadata"]["journey_category"] == "drafts"
        assert item["metadata"]["promotion_state"] == "staged-leftover"
        assert item["metadata"]["source_root"] == "runtime-staging"
        assert item["metadata"]["skill_count"] == "3"
        assert item["metadata"]["clients"] == "claude,codex,gemini"

    def test_profile_category_reports_in_progress_without_completed_profile(self, tmp_path, monkeypatch):
        vault_dir = tmp_path / "vault"
        state_path = vault_dir / "profile" / "en" / "interview-in-progress.yaml"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(
            "version: 1\n"
            "language: en\n"
            "total: 100\n"
            "answered: 12\n"
            "started_at: 2026-05-13T00:00:00Z\n"
            "last_answered_at: 2026-05-13T00:10:00Z\n"
            "mode: full\n"
            "qa_pairs: []\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.index_synthetic.get_vault_dir",
            lambda: vault_dir,
        )
        monkeypatch.setattr("src.config.paths.get_rag_category_dir", lambda category: tmp_path / "rag" / category)

        result = json.loads(browse_index_impl("profile"))

        assert result["count"] == 1
        item = result["items"][0]
        assert item["id"] == "voice-profile"
        assert item["description"] == "In progress: EN"
        assert item["metadata"]["completed_languages"] == "In progress"
        assert item["metadata"]["status"] == "in-progress"

    def test_profile_category_uses_latest_completed_profile_path(self, tmp_path, monkeypatch):
        vault_dir = tmp_path / "vault"
        en_profile = vault_dir / "profile" / "en" / "about-me.md"
        he_profile = vault_dir / "profile" / "he" / "about-me.md"
        en_profile.parent.mkdir(parents=True)
        he_profile.parent.mkdir(parents=True)
        en_profile.write_text("# English\n", encoding="utf-8")
        he_profile.write_text("# Hebrew\n", encoding="utf-8")
        os.utime(en_profile, (2_000_000_000, 2_000_000_000))
        os.utime(he_profile, (1_900_000_000, 1_900_000_000))
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.index_synthetic.get_vault_dir",
            lambda: vault_dir,
        )
        monkeypatch.setattr("src.config.paths.get_rag_category_dir", lambda category: tmp_path / "rag" / category)

        result = json.loads(browse_index_impl("profile"))

        assert result["count"] == 1
        item = result["items"][0]
        assert item["source_path"] == str(en_profile)
        assert item["description"] == "Completed: EN, HE"
        assert item["metadata"]["completed_languages"] == "2/2 languages"
        assert item["metadata"]["status"] == "ready"


class TestPromoteBrowseItemImpl:
    def test_promote_private_note_creates_append_only_packet(self, tmp_path, monkeypatch):
        from src.mcp.augur_framework.tools.infrastructure.browse.promotion import promote_browse_item_impl

        private_vault = tmp_path / "private-vault"
        project_brain = tmp_path / "project" / "project-brain"
        source = private_vault / "notes" / "career" / "plan.md"
        source.parent.mkdir(parents=True)
        source.write_text("---\ntitle: Private Plan\n---\nBody\n", encoding="utf-8")

        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.promotion.get_vault_dir",
            lambda: private_vault,
        )
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.promotion.get_project_brain_dir",
            lambda: project_brain,
        )

        result = json.loads(
            promote_browse_item_impl(
                category="notes",
                title="Private Plan",
                source_path=str(source),
                description="Private note for team review",
            )
        )

        assert result["success"] is True
        packet_path = Path(result["packet_path"])
        assert packet_path.is_dir()
        assert packet_path.parent == project_brain / "inbox" / "promotions"
        assert (packet_path / "manifest.yaml").is_file()
        assert (packet_path / "synthesis.md").is_file()
        synthesis = (packet_path / "synthesis.md").read_text(encoding="utf-8")
        assert "Private note for team review" in synthesis
        assert "Source: notes/career/plan.md" in synthesis
        assert source.read_text(encoding="utf-8").endswith("Body\n")

    def test_rejects_category_source_root_mismatch(self, tmp_path, monkeypatch):
        from src.mcp.augur_framework.tools.infrastructure.browse.promotion import promote_browse_item_impl

        private_vault = tmp_path / "private-vault"
        project_brain = tmp_path / "project" / "project-brain"
        source = private_vault / "notes" / "career" / "plan.md"
        source.parent.mkdir(parents=True)
        source.write_text("---\ntitle: Private Plan\n---\nBody\n", encoding="utf-8")

        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.promotion.get_vault_dir",
            lambda: private_vault,
        )
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.promotion.get_project_brain_dir",
            lambda: project_brain,
        )

        result = json.loads(
            promote_browse_item_impl(
                category="sources",
                title="Private Plan",
                source_path=str(source),
                description="Private note for team review",
            )
        )

        assert result["success"] is False
        assert "does not match category" in result["message"]

    def test_promote_to_explicit_brain_creates_cross_brain_packet(self, tmp_path, monkeypatch):
        import yaml

        from src.lib.brain_registry import clear_cache
        from src.lib.brain_registry_io import save_registry
        from src.lib.brain_registry_models import (
            Brain,
            BrainRegistry,
            BrainType,
            GitArrangement,
            GitConfig,
        )
        from src.mcp.augur_framework.tools.infrastructure.browse.promotion import (
            promote_browse_item_impl,
        )

        private_vault = tmp_path / "private-vault"
        team_root = tmp_path / "team"
        source = private_vault / "notes" / "career" / "plan.md"
        source.parent.mkdir(parents=True)
        source.write_text("---\ntitle: Plan\n---\nBody\n", encoding="utf-8")

        state = tmp_path / "augur-state"
        registry_path = state / "brains.yaml"
        registry_path.parent.mkdir(parents=True)
        monkeypatch.setenv("AUGUR_STATE_DIR", str(state))
        save_registry(
            BrainRegistry(
                version=1,
                brains={
                    "personal": Brain(
                        id="personal",
                        type=BrainType.PERSONAL,
                        data_root=private_vault,
                        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
                    ),
                    "team-core": Brain(
                        id="team-core",
                        type=BrainType.TEAM,
                        data_root=team_root,
                        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
                        write_policy="packets_only",
                    ),
                },
            ),
            registry_path,
        )
        clear_cache()

        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.promotion.get_vault_dir",
            lambda: private_vault,
        )

        try:
            result = json.loads(
                promote_browse_item_impl(
                    category="notes",
                    title="Plan",
                    source_path=str(source),
                    description="Cross-brain note",
                    to="team-core",
                )
            )
        finally:
            clear_cache()

        assert result["success"] is True
        packet_path = Path(result["packet_path"])
        assert packet_path.parent == team_root / "inbox" / "promotions"
        manifest = yaml.safe_load((packet_path / "manifest.yaml").read_text())
        assert manifest["kind"] == "brain-propagation-packet"
        assert manifest["source_brain_id"] == "personal"
        assert manifest["target_brain_id"] == "team-core"
        # Source brain root must not leak into the manifest.
        assert str(private_vault) not in (packet_path / "manifest.yaml").read_text()
        assert (packet_path / "sources" / "plan.md").is_file()

    def test_promote_to_unregistered_brain_fails(self, tmp_path, monkeypatch):
        from src.lib.brain_registry import clear_cache
        from src.mcp.augur_framework.tools.infrastructure.browse.promotion import (
            promote_browse_item_impl,
        )

        private_vault = tmp_path / "private-vault"
        source = private_vault / "notes" / "plan.md"
        source.parent.mkdir(parents=True)
        source.write_text("Body\n", encoding="utf-8")

        state = tmp_path / "augur-state"
        (state).mkdir(parents=True)
        monkeypatch.setenv("AUGUR_STATE_DIR", str(state))
        clear_cache()

        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.promotion.get_vault_dir",
            lambda: private_vault,
        )

        try:
            result = json.loads(
                promote_browse_item_impl(
                    category="notes",
                    title="Plan",
                    source_path=str(source),
                    to="ghost-brain",
                )
            )
        finally:
            clear_cache()

        assert result["success"] is False
        assert "not registered" in result["message"]


# =============================================================================
# list_prompts_impl
# =============================================================================


class TestListPromptsImpl:
    """Tests for prompt template listing."""

    @pytest.mark.asyncio
    async def test_no_prompts(self, mock_project_root):
        """Empty skills dir returns empty list."""
        result = json.loads(await list_prompts_impl())
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_with_prompts(self, mock_project_root):
        """Prompts are discovered from project-brain/capabilities/skills/*/assets/seeds/prompts/."""
        prompt_dir = (
            mock_project_root
            / "project-brain"
            / "capabilities"
            / "skills"
            / "career-manager"
            / "assets"
            / "seeds"
            / "prompts"
        )
        prompt_dir.mkdir(parents=True)
        (prompt_dir / "interview-prep.md").write_text("# Interview Prep\n")

        result = json.loads(await list_prompts_impl())
        assert result["count"] == 1
        assert result["items"][0]["skill"] == "career-manager"

    @pytest.mark.asyncio
    async def test_with_root_prompt_directory(self, mock_project_root):
        """Prompt files in the Agent Skills prompts/ directory are listed."""
        prompt_dir = mock_project_root / "project-brain" / "capabilities" / "skills" / "ingest" / "prompts"
        prompt_dir.mkdir(parents=True)
        (prompt_dir / "ingest-content.md").write_text(
            "---\n"
            "id: ingest-content\n"
            "label: Ingest Content\n"
            "description: Process dropped content\n"
            "---\n"
            "Process the dropped content.\n"
        )

        result = json.loads(await list_prompts_impl())
        assert result["count"] == 1
        assert result["items"][0]["id"] == "ingest/prompts/ingest-content"
        assert result["items"][0]["title"] == "Ingest Content"
        assert result["items"][0]["description"] == "Process dropped content"
        assert result["items"][0]["skill"] == "ingest"


# =============================================================================
# list_scripts_impl
# =============================================================================


class TestListScriptsImpl:
    """Tests for script listing."""

    @pytest.mark.asyncio
    async def test_no_scripts(self, mock_project_root):
        """Empty skills dir returns empty list."""
        result = json.loads(await list_scripts_impl())
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_with_scripts(self, mock_project_root):
        """Scripts are discovered from project-brain/capabilities/skills/*/scripts/ directories."""
        scripts_dir = mock_project_root / "project-brain" / "capabilities" / "skills" / "developer" / "scripts"
        scripts_dir.mkdir(parents=True)
        (scripts_dir / "build.py").write_text("#!/usr/bin/env python3\n")
        (scripts_dir / "deploy.sh").write_text("#!/bin/bash\n")

        result = json.loads(await list_scripts_impl())
        assert result["count"] == 2
        languages = [item["language"] for item in result["items"]]
        assert "Python" in languages
        assert "Shell" in languages


# =============================================================================
# list_cli_commands_impl
# =============================================================================


class TestListCliCommandsImpl:
    """Tests for command listing from skills/*/commands/*.md."""

    @pytest.mark.asyncio
    async def test_no_commands(self, mock_project_root):
        """No SKILL.md files returns empty list."""
        result = json.loads(await list_cli_commands_impl())
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_with_command_doc(self, mock_project_root):
        """Commands are extracted from command docs, not generic skill visibility."""
        skill_dir = mock_project_root / "project-brain" / "capabilities" / "skills" / "developer"
        command_dir = skill_dir / "commands"
        command_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: developer\ndescription: Developer tools\nx-augur-hub: studio\n---\n\n# Developer\n"
        )
        (command_dir / "dev-build.md").write_text(
            "---\ndescription: Build the dashboard\nvisibility: dev\n---\n\n# /dev-build\n"
        )

        result = json.loads(await list_cli_commands_impl())
        assert result["count"] == 1
        assert result["items"][0]["id"] == "/dev-build"
        assert result["items"][0]["category"] == "DEV"

    @pytest.mark.asyncio
    async def test_excludes_prompt_docs_in_commands_folder(self, mock_project_root):
        """Prompt docs living in commands/ do not appear in browse commands."""
        skill_dir = mock_project_root / "project-brain" / "capabilities" / "skills" / "developer"
        command_dir = skill_dir / "commands"
        command_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("---\nname: developer\nx-augur-hub: studio\n---\n\n# Developer\n")
        (command_dir / "prompt-seed.md").write_text(
            "---\nskill: developer\ndescription: Prompt template\n---\n\n# Prompt\n"
        )

        result = json.loads(await list_cli_commands_impl())
        assert result["count"] == 0


# =============================================================================
# list_adrs_impl
# =============================================================================


class TestListAdrsImpl:
    """Tests for ADR listing."""

    @pytest.mark.asyncio
    async def test_no_adrs(self, mock_project_root, tmp_path):
        """Empty ADR dir returns empty list."""
        adr_dir = tmp_path / "adrs"
        adr_dir.mkdir()
        with patch("src.lib.adr_utils.get_adr_dir", return_value=adr_dir):
            result = json.loads(await list_adrs_impl())
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_with_adrs(self, mock_project_root, tmp_path):
        """ADRs are listed with frontmatter metadata."""
        adr_dir = tmp_path / "adrs"
        adr_dir.mkdir()
        (adr_dir / "adr-001-initial-architecture.md").write_text(
            "---\ntitle: Initial Architecture\nstatus: accepted\nhub: dev\ndate: 2025-01-01\n---\n\n# ADR-001\n"
        )
        (adr_dir / "adr-002-plugin-system.md").write_text(
            "---\ntitle: Plugin System\nstatus: draft\n---\n\n# ADR-002\n"
        )

        with patch("src.lib.adr_utils.get_adr_dir", return_value=adr_dir):
            result = json.loads(await list_adrs_impl())
        assert result["count"] == 2
        titles = [item["title"] for item in result["items"]]
        assert any("Initial Architecture" in t for t in titles)

    @pytest.mark.asyncio
    async def test_adr_without_frontmatter(self, mock_project_root, tmp_path):
        """ADRs without frontmatter still get listed with defaults."""
        adr_dir = tmp_path / "adrs"
        adr_dir.mkdir()
        (adr_dir / "adr-099-quick-note.md").write_text("# Quick Note\n\nNo frontmatter here.\n")

        with patch("src.lib.adr_utils.get_adr_dir", return_value=adr_dir):
            result = json.loads(await list_adrs_impl())
        assert result["count"] == 1
        assert result["items"][0]["status"] == "unknown"

    @pytest.mark.asyncio
    async def test_live_adrs_have_archived_false(self, mock_project_root, tmp_path):
        """ADR-608 Phase 2: live ADR entries get archived: false."""
        adr_dir = tmp_path / "adrs"
        adr_dir.mkdir()
        (adr_dir / "adr-001-initial.md").write_text("---\ntitle: Initial\nstatus: accepted\n---\n\n# ADR-001\n")

        with patch("src.lib.adr_utils.get_adr_dir", return_value=adr_dir):
            result = json.loads(await list_adrs_impl())
        assert result["count"] == 1
        assert result["items"][0]["archived"] is False

    @pytest.mark.asyncio
    async def test_archived_adrs_appended_from_index(self, mock_project_root, tmp_path):
        """ADR-608 Phase 2: archive index entries appear with archived: true
        and a synthetic archive://ADR-NNN path."""
        adr_dir = tmp_path / "adrs"
        adr_dir.mkdir()
        (adr_dir / "adr-009-live.md").write_text("---\ntitle: Live ADR\nstatus: Accepted\n---\n\n# ADR-009\n")

        archive_dir = adr_dir / "archive"
        archive_dir.mkdir()
        index = [
            {
                "adr_number": "ADR-001",
                "title": "Three-Layer Architecture",
                "status": "Implemented",
                "date": "2025-01-01",
                "hub": "core",
                "tags": ["architecture"],
                "zip": "archived-adrs-001-100.zip",
            },
            {
                "adr_number": "ADR-042",
                "title": "Hitchhiker",
                "status": "Implemented",
                "date": "2025-02-02",
                "hub": None,
                "tags": [],
                "zip": "archived-adrs-001-100.zip",
            },
        ]
        (archive_dir / "archived-adrs-index.json").write_text(json.dumps(index))

        with patch("src.lib.adr_utils.get_adr_dir", return_value=adr_dir):
            result = json.loads(await list_adrs_impl())

        items = result["items"]
        assert result["count"] == 3
        live = [i for i in items if not i["archived"]]
        archived = [i for i in items if i["archived"]]
        assert len(live) == 1
        assert len(archived) == 2

        first_archived = next(i for i in archived if i["adr_number"] == "001")
        assert first_archived["path"] == "archive://ADR-001"
        assert first_archived["title"].startswith("ADR-001:")
        assert first_archived["status"] == "Implemented"
        assert first_archived["hub"] == "core"

        # Hub falls back to "system" when null in the JSON.
        hitchhiker = next(i for i in archived if i["adr_number"] == "042")
        assert hitchhiker["hub"] == "system"
        assert hitchhiker["path"] == "archive://ADR-042"

    @pytest.mark.asyncio
    async def test_live_adr_wins_over_archived_dupe(self, mock_project_root, tmp_path):
        """If the same ADR number is both live and in the archive index,
        the live copy wins."""
        adr_dir = tmp_path / "adrs"
        adr_dir.mkdir()
        (adr_dir / "adr-001-initial.md").write_text("---\ntitle: Initial\nstatus: Accepted\n---\n\n# ADR-001\n")
        archive_dir = adr_dir / "archive"
        archive_dir.mkdir()
        (archive_dir / "archived-adrs-index.json").write_text(
            json.dumps(
                [
                    {
                        "adr_number": "ADR-001",
                        "title": "Old",
                        "status": "Implemented",
                        "date": "2024-01-01",
                        "hub": None,
                        "tags": [],
                        "zip": "archived-adrs-001-100.zip",
                    }
                ]
            )
        )

        with patch("src.lib.adr_utils.get_adr_dir", return_value=adr_dir):
            result = json.loads(await list_adrs_impl())
        assert result["count"] == 1
        assert result["items"][0]["archived"] is False
        assert result["items"][0]["status"] == "Accepted"

    @pytest.mark.asyncio
    async def test_missing_archive_index_is_tolerated(self, mock_project_root, tmp_path):
        """If archived-adrs-index.json is absent, only live ADRs surface."""
        adr_dir = tmp_path / "adrs"
        adr_dir.mkdir()
        (adr_dir / "adr-001-initial.md").write_text("---\ntitle: Initial\nstatus: Accepted\n---\n\n# ADR-001\n")

        with patch("src.lib.adr_utils.get_adr_dir", return_value=adr_dir):
            result = json.loads(await list_adrs_impl())
        assert result["count"] == 1
        assert result["items"][0]["archived"] is False


# =============================================================================
# list_agents_impl
# =============================================================================


class TestListAgentsImpl:
    """Tests for agent listing."""

    @pytest.mark.asyncio
    async def test_centralized_agents(self, mock_project_root):
        """Agents from plugins/agents/*.md are listed."""
        # Current code path: plugins/agents/*.md with YAML frontmatter
        agents_dir = mock_project_root / "plugins" / "agents"
        agents_dir.mkdir(parents=True)
        agent_content = (
            "---\n"
            "name: Architect\n"
            "description: Design systems\n"
            "mode: dev\n"
            "model: claude-opus-4\n"
            "---\n\n# Architect Agent\n"
        )
        (agents_dir / "architect.md").write_text(agent_content)

        result = json.loads(await list_agents_impl())
        assert result["count"] >= 1
        assert any(item["title"] == "Architect" for item in result["items"])

    @pytest.mark.asyncio
    async def test_plugin_agents(self, mock_project_root):
        """Agents from plugins/agents/registry.json are listed."""
        # Current code path: plugins/agents/registry.json
        agents_dir = mock_project_root / "plugins" / "agents"
        agents_dir.mkdir(parents=True)
        registry = {
            "agents": {
                "career-coach": {
                    "description": "Career coaching",
                    "role": "T2",
                    "source": "plugin",
                    "plugin": "career",
                    "defaultModel": "claude-sonnet-4",
                    "tools": [],
                    "tiers": {},
                }
            }
        }
        (agents_dir / "registry.json").write_text(json.dumps(registry))

        result = json.loads(await list_agents_impl())
        assert any(item["title"] == "career-coach" for item in result["items"])


# =============================================================================
# list_knowledge_hub_files_impl
# =============================================================================


class TestListKnowledgeHubFilesImpl:
    """Tests for knowledge hub file listing."""

    @pytest.mark.asyncio
    async def test_empty_documents(self, mock_documents_dir):
        """Empty documents dir returns empty list."""
        result = json.loads(await list_knowledge_hub_files_impl())
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_with_documents(self, mock_documents_dir):
        """Documents are listed with hub categorization."""
        career_dir = mock_documents_dir / "career"
        career_dir.mkdir()
        (career_dir / "resume.pdf").write_bytes(b"fake pdf")
        (career_dir / "notes.md").write_text("# Notes")

        result = json.loads(await list_knowledge_hub_files_impl())
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_hub_filter(self, mock_documents_dir):
        """Hub filter limits results to specific hub."""
        (mock_documents_dir / "career").mkdir()
        (mock_documents_dir / "career" / "resume.pdf").write_bytes(b"fake")
        (mock_documents_dir / "finance").mkdir()
        (mock_documents_dir / "finance" / "budget.csv").write_text("a,b,c")

        result = json.loads(await list_knowledge_hub_files_impl(hub="career"))
        assert result["count"] == 1
        assert result["files"][0]["skill"] == "career"

    @pytest.mark.asyncio
    async def test_with_desktop_and_downloads_sources(self, tmp_path, monkeypatch):
        """All registered document sources are listed with source metadata."""
        from src.lib.index.document_sources import DocumentSource

        docs = tmp_path / "Au-docs"
        desktop = tmp_path / "Desktop"
        downloads = tmp_path / "Downloads"
        for root in (docs, desktop, downloads):
            root.mkdir()
        (docs / "career").mkdir()
        (docs / "career" / "resume.pdf").write_bytes(b"fake")
        (desktop / "todo.txt").write_text("todo", encoding="utf-8")
        (downloads / "meeting.m4a").write_bytes(b"audio")

        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.vault.default_document_sources",
            lambda documents_dir: [
                DocumentSource("documents", "Au-docs", docs, preserve_legacy_output=True),
                DocumentSource("desktop", "Desktop", desktop),
                DocumentSource("downloads", "Downloads", downloads),
            ],
            raising=False,
        )
        monkeypatch.setattr(
            "src.mcp.augur_framework.tools.infrastructure.browse.vault.get_documents_dir",
            lambda: docs,
        )

        result = json.loads(await list_knowledge_hub_files_impl())

        assert result["count"] == 3
        assert {item["source_root"] for item in result["files"]} == {
            "documents",
            "desktop",
            "downloads",
        }
        assert {item["skill"] for item in result["files"]} == {
            "career",
            "desktop",
            "downloads",
        }
        assert all(item["source_root_name"] for item in result["files"])
        assert all(item["source_relative_path"] for item in result["files"])


# =============================================================================
# cli_help_impl
# =============================================================================


class TestCliHelpImpl:
    """Tests for CLI help output."""

    def test_empty_input(self):
        """Empty CLI names returns no-tools message."""
        result = json.loads(cli_help_impl(""))
        assert result["cli_count"] == 0

    def test_skips_osascript_and_brew(self):
        """osascript and brew are skipped."""
        result = json.loads(cli_help_impl("osascript,brew"))
        assert result["cli_count"] == 0

    def test_not_installed_tool(self):
        """Not-installed tool shows install message."""
        result = json.loads(cli_help_impl("totally_fake_tool_xyz123"))
        assert result["cli_count"] == 1
        assert "Not installed" in result["markdown"]

    def test_installed_tool(self):
        """Installed tool returns help output."""
        with patch("shutil.which", return_value="/usr/bin/ls"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout="usage: ls [options]",
                    stderr="",
                )
                result = json.loads(cli_help_impl("ls"))
                assert result["cli_count"] == 1
                assert "usage: ls" in result["markdown"]
