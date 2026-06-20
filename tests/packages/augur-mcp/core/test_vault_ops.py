"""Tests for vault file read/write operations."""

import json
import pytest
from pathlib import Path

import yaml


@pytest.fixture
def mock_vault(tmp_path, monkeypatch):
    """Create a mock vault directory with test files."""
    vault = tmp_path / "vault"
    vault.mkdir()
    skill_dir = vault / "test-skill"
    skill_dir.mkdir()
    (skill_dir / "note.md").write_text("---\ntitle: Test Note\ntype: note\n---\n\nThis is the body content.\n")
    sub = skill_dir / "ideas"
    sub.mkdir()
    (sub / "idea-one.md").write_text("---\ntitle: Idea One\ntype: idea\n---\n\nGreat idea here.\n")
    monkeypatch.setattr(
        "src.mcp.augur_core.tools.core.vault_ops.get_skill_data_dir",
        lambda name: vault / name,
    )
    monkeypatch.setattr(
        "src.mcp.augur_core.tools.core.vault_ops.get_runtime_dir",
        lambda: tmp_path / "runtime",
    )
    return vault


def _runtime_knowledge(mock_vault: Path) -> Path:
    return mock_vault.parent / "runtime" / "knowledge"


class TestVaultFileRead:
    @pytest.mark.anyio
    async def test_read_existing_file(self, mock_vault):
        from src.mcp.augur_core.tools.core.vault_ops import vault_file_read_impl

        result = json.loads(await vault_file_read_impl("test-skill", "note.md"))
        assert result["success"] is True
        assert result["frontmatter"]["title"] == "Test Note"
        assert result["frontmatter"]["type"] == "note"
        assert "This is the body content." in result["body"]
        assert result["lines"] > 0

    @pytest.mark.anyio
    async def test_read_nested_file(self, mock_vault):
        from src.mcp.augur_core.tools.core.vault_ops import vault_file_read_impl

        result = json.loads(await vault_file_read_impl("test-skill", "ideas/idea-one.md"))
        assert result["success"] is True
        assert result["frontmatter"]["title"] == "Idea One"

    @pytest.mark.anyio
    async def test_read_nonexistent_file(self, mock_vault):
        from src.mcp.augur_core.tools.core.vault_ops import vault_file_read_impl

        result = json.loads(await vault_file_read_impl("test-skill", "nope.md"))
        assert result["success"] is False
        assert "error" in result

    @pytest.mark.anyio
    async def test_read_path_traversal_blocked(self, mock_vault):
        from src.mcp.augur_core.tools.core.vault_ops import vault_file_read_impl

        result = json.loads(await vault_file_read_impl("test-skill", "../../etc/passwd"))
        assert result["success"] is False

    @pytest.mark.anyio
    async def test_read_nonexistent_skill(self, mock_vault):
        from src.mcp.augur_core.tools.core.vault_ops import vault_file_read_impl

        result = json.loads(await vault_file_read_impl("no-such-skill", "note.md"))
        assert result["success"] is False


class TestVaultFileWrite:
    @pytest.mark.anyio
    async def test_write_new_file(self, mock_vault):
        from src.mcp.augur_core.tools.core.vault_ops import vault_file_write_impl

        result = json.loads(
            await vault_file_write_impl(
                skill="test-skill",
                path="new-note.md",
                title="New Note",
                body="Some content here.",
                metadata={"type": "note"},
            )
        )
        assert result["success"] is True
        assert result["created"] is True
        written = (mock_vault / "test-skill" / "new-note.md").read_text()
        assert "title: New Note" in written
        assert "type: note" in written
        assert "Some content here." in written

    @pytest.mark.anyio
    async def test_write_creates_parent_dirs(self, mock_vault):
        from src.mcp.augur_core.tools.core.vault_ops import vault_file_write_impl

        result = json.loads(
            await vault_file_write_impl(
                skill="test-skill",
                path="deep/nested/file.md",
                title="Nested",
                body="Deep content.",
            )
        )
        assert result["success"] is True
        assert (mock_vault / "test-skill" / "deep" / "nested" / "file.md").exists()

    @pytest.mark.anyio
    async def test_write_path_traversal_blocked(self, mock_vault):
        from src.mcp.augur_core.tools.core.vault_ops import vault_file_write_impl

        result = json.loads(
            await vault_file_write_impl(
                skill="test-skill",
                path="../../evil.md",
                title="Evil",
                body="Bad.",
            )
        )
        assert result["success"] is False

    @pytest.mark.anyio
    async def test_write_overwrites_existing(self, mock_vault):
        from src.mcp.augur_core.tools.core.vault_ops import vault_file_write_impl

        result = json.loads(
            await vault_file_write_impl(
                skill="test-skill",
                path="note.md",
                title="Updated Note",
                body="Updated content.",
            )
        )
        assert result["success"] is True
        assert result["created"] is False
        written = (mock_vault / "test-skill" / "note.md").read_text()
        assert "Updated Note" in written

    @pytest.mark.anyio
    async def test_write_preserves_existing_user_fields_and_routes_system_fields(self, mock_vault):
        from src.lib.frontmatter_utils import parse_frontmatter
        from src.mcp.augur_core.tools.core.vault_ops import vault_file_write_impl

        note = mock_vault / "test-skill" / "note.md"
        note.write_text(
            "---\n" "title: Test Note\n" "type: note\n" "status: active\n" "_checksum: old\n" "---\n\n" "Body.\n",
            encoding="utf-8",
        )

        result = json.loads(
            await vault_file_write_impl(
                skill="test-skill",
                path="note.md",
                title="Updated Note",
                body="Updated content.",
                metadata={"_checksum": "new"},
            )
        )

        assert result["success"] is True
        meta, body = parse_frontmatter(note)
        assert meta["title"] == "Updated Note"
        assert meta["type"] == "note"
        assert meta["status"] == "active"
        assert meta["_checksum"] == "new"
        assert "Updated content." in body


# ---------------------------------------------------------------------------
# save-synthesis tests
# ---------------------------------------------------------------------------


class TestSaveSynthesis:
    @pytest.mark.anyio
    async def test_saves_synthesis_with_frontmatter(self, mock_vault):
        from src.mcp.augur_core.tools.core.vault_ops import save_synthesis_impl

        result = json.loads(
            await save_synthesis_impl(
                query="How does hybrid retrieval work?",
                synthesis="BM25 + ripgrep merged via RRF.",
                sources=["skills/rag/scripts/retrieval.py"],
                tags=["rag", "retrieval"],
            )
        )
        assert result["success"] is True
        assert result["created"] is True
        assert "syntheses/" in result["path"]

        # Verify file was written with correct frontmatter
        written_path = _runtime_knowledge(mock_vault) / result["path"]
        assert written_path.exists()
        content = written_path.read_text()
        assert "type: synthesis" in content
        assert "How does hybrid retrieval work?" in content
        assert "BM25 + ripgrep merged via RRF." in content

    @pytest.mark.anyio
    async def test_slug_generation(self, mock_vault):
        from src.mcp.augur_core.tools.core.vault_ops import save_synthesis_impl

        result = json.loads(
            await save_synthesis_impl(
                query="What's the best approach for RAG?",
                synthesis="Use hybrid retrieval.",
            )
        )
        assert result["success"] is True
        # Slug should be filesystem-safe
        path = result["path"]
        assert "syntheses/" in path
        assert "?" not in path
        assert "'" not in path

    @pytest.mark.anyio
    async def test_creates_parent_dirs(self, mock_vault):
        from src.mcp.augur_core.tools.core.vault_ops import save_synthesis_impl

        # syntheses/ dir doesn't exist yet — should be created
        assert not (_runtime_knowledge(mock_vault) / "syntheses").exists()
        result = json.loads(
            await save_synthesis_impl(
                query="Test query",
                synthesis="Test answer.",
            )
        )
        assert result["success"] is True
        assert (_runtime_knowledge(mock_vault) / "syntheses").is_dir()

    @pytest.mark.anyio
    async def test_optional_fields_omitted(self, mock_vault):
        from src.mcp.augur_core.tools.core.vault_ops import save_synthesis_impl

        result = json.loads(
            await save_synthesis_impl(
                query="Simple question",
                synthesis="Simple answer.",
            )
        )
        assert result["success"] is True
        content = (_runtime_knowledge(mock_vault) / result["path"]).read_text()
        assert "sources" not in content.split("---")[1]  # Not in frontmatter
        assert "tags" not in content.split("---")[1]

    @pytest.mark.anyio
    async def test_save_synthesis_does_not_mutate_wiki(self, mock_vault):
        from src.mcp.augur_core.tools.core.vault_ops import save_synthesis_impl

        wiki_dir = mock_vault / "wiki"
        wiki_dir.mkdir(parents=True)
        (wiki_dir / "overview.md").write_text("---\ntitle: Wiki Overview\n---\n# Wiki Overview\n", encoding="utf-8")

        result = json.loads(
            await save_synthesis_impl(
                query="How should wiki compounding work?",
                synthesis="Persist valuable syntheses as source material, not direct wiki mutations.",
                tags=["wiki"],
                sources=["skills/search/SKILL.md"],
            )
        )

        assert result["success"] is True
        assert "wiki maintenance now happens" in result["note"].lower()
        assert (_runtime_knowledge(mock_vault) / result["path"]).exists()
        assert not (wiki_dir / "index.md").exists()

    @pytest.mark.anyio
    async def test_save_synthesis_persists_ask_shape(self, mock_vault):
        from src.mcp.augur_core.tools.core.vault_ops import save_synthesis_impl

        result = json.loads(
            await save_synthesis_impl(
                query="Work Pattern Insight",
                synthesis="You work best in long morning focus blocks.",
                tags=["ask", "pattern"],
            )
        )

        assert result["success"] is True
        assert result["path"].startswith("syntheses/")

        written_path = _runtime_knowledge(mock_vault) / result["path"]
        content = written_path.read_text()
        frontmatter_block = content.split("---")[1]
        frontmatter = yaml.safe_load(frontmatter_block)

        assert frontmatter["type"] == "synthesis"
        assert frontmatter["query"] == "Work Pattern Insight"
        assert frontmatter["tags"] == ["ask", "pattern"]
        assert "You work best in long morning focus blocks." in content


class TestAskRetain:
    @pytest.mark.anyio
    async def test_retain_logs_memory_saves_synthesis_and_flags_wiki(self, mock_vault, tmp_path, monkeypatch):
        from src.mcp.augur_core.tools.core.ask_retention import retain_ask_outcome_impl

        runtime_dir = tmp_path / "runtime"
        memory_dir = tmp_path / "memory"
        monkeypatch.setattr(
            "src.lib.knowledge.daily_logger.get_runtime_dir",
            lambda: runtime_dir,
        )
        monkeypatch.setattr(
            "src.lib.knowledge.daily_logger.get_memory_dir",
            lambda: memory_dir,
        )
        monkeypatch.setattr(
            "src.mcp.augur_core.tools.core.ask_retention.get_runtime_dir",
            lambda: runtime_dir,
        )

        result = json.loads(
            await retain_ask_outcome_impl(
                question="How do I work best?",
                answer="You work best with long uninterrupted morning blocks.",
                explicit_signals=["I prefer deep work before noon"],
                inferred_signals=["morning focus pattern"],
                retain_mode="default",
                surface_footer=True,
                tags=["pattern"],
                sources=["ask"],
            )
        )

        assert result["success"] is True
        assert result["retained"] is True
        assert result["footer"] == "retained: preference + inferred pattern"

        daily_files = list((runtime_dir / "memory" / "daily").glob("*.md"))
        assert len(daily_files) == 1
        daily_text = daily_files[0].read_text(encoding="utf-8")
        assert "**Preference**: How do I work best?" in daily_text
        assert "**Value**: You work best with long uninterrupted morning blocks." in daily_text

        synthesis_paths = result["persistence"]["syntheses_saved"]
        assert len(synthesis_paths) == 1
        synthesis_text = (_runtime_knowledge(mock_vault) / synthesis_paths[0]).read_text(encoding="utf-8")
        synthesis_frontmatter = yaml.safe_load(synthesis_text.split("---")[1])
        assert set(synthesis_frontmatter["tags"]) >= {"ask", "preference", "inferred-pattern", "pattern"}

        flag_path = Path(result["persistence"]["wiki_update_flag"])
        assert flag_path.exists()
        assert flag_path == runtime_dir / "wiki" / "needs-update.flag"

    @pytest.mark.anyio
    async def test_private_mode_skips_persistence(self, mock_vault, tmp_path, monkeypatch):
        from src.mcp.augur_core.tools.core.ask_retention import retain_ask_outcome_impl

        runtime_dir = tmp_path / "runtime"
        monkeypatch.setattr(
            "src.mcp.augur_core.tools.core.ask_retention.get_runtime_dir",
            lambda: runtime_dir,
        )

        result = json.loads(
            await retain_ask_outcome_impl(
                question="What do I think?",
                answer="You need another day to decide.",
                explicit_signals=["I am still unsure"],
                retain_mode="private",
            )
        )

        assert result["success"] is True
        assert result["retained"] is False
        assert result["skipped"] is True
        assert not (runtime_dir / "wiki" / "needs-update.flag").exists()
        assert not (_runtime_knowledge(mock_vault) / "syntheses").exists()

    @pytest.mark.anyio
    async def test_explicit_project_brain_routes_retention_outputs(
        self,
        mock_vault,
        tmp_path,
        monkeypatch,
    ):
        from src.lib.brain_manifest import (
            BrainManifest,
            ensure_brain_skeleton,
            write_brain_manifest,
        )
        from src.lib.brain_registry_io import save_registry
        from src.lib.brain_registry_models import (
            Brain,
            BrainRegistry,
            BrainType,
            GitArrangement,
            GitConfig,
        )
        from src.mcp.augur_core.tools.core.ask_retention import retain_ask_outcome_impl

        runtime_dir = tmp_path / "runtime"
        personal = tmp_path / "personal"
        project = tmp_path / "repo"
        brain_root = project / "project-brain"
        ensure_brain_skeleton(brain_root)
        write_brain_manifest(
            brain_root,
            BrainManifest(
                schema_version=1,
                id="project-repo",
                type=BrainType.PROJECT,
                root=str(brain_root),
                attached_project=str(project),
            ),
        )
        registry_path = tmp_path / "brains.yaml"
        save_registry(
            BrainRegistry(
                version=1,
                brains={
                    "personal": Brain(
                        id="personal",
                        type=BrainType.PERSONAL,
                        data_root=personal,
                        git=GitConfig(arrangement=GitArrangement.UNTRACKED),
                    ),
                    "project-repo": Brain(
                        id="project-repo",
                        type=BrainType.PROJECT,
                        data_root=brain_root,
                        git=GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project),
                        auto_activate_cwd_under=(project,),
                    ),
                },
            ),
            registry_path,
        )
        monkeypatch.setattr(
            "src.mcp.augur_core.tools.core.ask_retention.get_runtime_dir",
            lambda: runtime_dir,
        )

        result = json.loads(
            await retain_ask_outcome_impl(
                question="What should the project remember?",
                answer="The project should keep write-routing decisions beside project docs.",
                explicit_signals=["you decided to keep project write routing canonical"],
                inferred_signals=["project-local memory should compound beside project docs"],
                retain_mode="default",
                surface_footer=True,
                to="project-repo",
                registry_path=registry_path,
                cwd=project,
            )
        )

        assert result["success"] is True
        assert result["brain"]["id"] == "project-repo"
        assert result["brain"]["reason"] == "explicit"
        daily_files = list((brain_root / "knowledge" / "memory" / "daily").glob("*.md"))
        assert len(daily_files) == 1
        synthesis_paths = result["persistence"]["syntheses_saved"]
        assert len(synthesis_paths) == 1
        assert (brain_root / "knowledge" / synthesis_paths[0]).exists()
        assert not (_runtime_knowledge(mock_vault) / "syntheses").exists()

    @pytest.mark.anyio
    async def test_retain_mode_upgrades_ephemeral_answer_to_synthesis(self, mock_vault, tmp_path, monkeypatch):
        from src.mcp.augur_core.tools.core.ask_retention import retain_ask_outcome_impl

        runtime_dir = tmp_path / "runtime"
        memory_dir = tmp_path / "memory"
        monkeypatch.setattr(
            "src.lib.knowledge.daily_logger.get_runtime_dir",
            lambda: runtime_dir,
        )
        monkeypatch.setattr(
            "src.lib.knowledge.daily_logger.get_memory_dir",
            lambda: memory_dir,
        )
        monkeypatch.setattr(
            "src.mcp.augur_core.tools.core.ask_retention.get_runtime_dir",
            lambda: runtime_dir,
        )

        result = json.loads(
            await retain_ask_outcome_impl(
                question="What should I think about this?",
                answer="You should revisit it after sleeping on it.",
                retain_mode="retain",
                surface_footer=True,
            )
        )

        assert result["retained"] is True
        assert result["kinds"] == ["insight"]
        assert result["footer"] == "retained: synthesis"
        assert result["persistence"]["decisions_logged"] == 0
        assert result["persistence"]["preferences_logged"] == 0
        assert len(result["persistence"]["syntheses_saved"]) == 1
