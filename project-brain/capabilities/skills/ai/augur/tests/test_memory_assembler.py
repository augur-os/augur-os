"""Tests for multi-client memory assembler."""

from __future__ import annotations

# TODO_CLEANUP: This file is 921 lines — consider splitting into smaller modules
import sys
from pathlib import Path

# Ensure assembler module is importable
_scripts_dir = str(Path(__file__).resolve().parent.parent.parent / "scripts" / "ops")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

import pytest
from src.lib.ops_protocol import OpsContext

import memory_assembler as memory_assembler_module
from memory_assembler import (
    _is_noise,
    _normalize,
    _parse_frontmatter,
    _update_gemini_imports,
    assemble,
    assemble_to_vault,
    collect_review_candidates,
    discover_entries,
    generate_claude_index,
    generate_flat_index,
    generate_vault_index,
    merge_vault_index,
    quality_gate,
    resolve_default_client_memory_plan,
    to_review_candidates,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _yaml_val(value: str) -> str:
    """Quote a YAML value if it contains characters that need quoting."""
    if any(ch in value for ch in (":", "#", "{", "}", "[", "]", ",")):
        return f'"{value}"'
    return value


def _write_entry(
    directory: Path,
    filename: str,
    *,
    name: str = "test_entry",
    description: str = "A test entry",
    entry_type: str = "decision",
    written_by: str = "claude-code",
    body: str = "Body content here.\n",
    created: str = "2026-03-15",
    updated: str = "2026-03-16",
) -> Path:
    """Write a .md file with YAML frontmatter to *directory*."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    lines = [
        "---",
        f"name: {_yaml_val(name)}",
        f"description: {_yaml_val(description)}",
        f"type: {_yaml_val(entry_type)}",
        f"written-by: {_yaml_val(written_by)}",
        f"created: {created}",
        f"updated: {updated}",
        "---",
        "",
        body,
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# _parse_frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_valid_frontmatter(self, tmp_path: Path) -> None:
        p = _write_entry(tmp_path, "test.md")
        result = _parse_frontmatter(p)
        assert result is not None
        assert result["name"] == "test_entry"
        assert "_body" in result
        assert "_raw" in result
        assert "Body content" in result["_body"]

    def test_no_frontmatter(self, tmp_path: Path) -> None:
        p = tmp_path / "plain.md"
        p.write_text("Just plain text\n")
        assert _parse_frontmatter(p) is None

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.md"
        p.write_text("---\n: [invalid yaml\n---\nBody\n")
        assert _parse_frontmatter(p) is None

    def test_missing_file(self, tmp_path: Path) -> None:
        p = tmp_path / "nonexistent.md"
        assert _parse_frontmatter(p) is None


# ---------------------------------------------------------------------------
# discover_entries
# ---------------------------------------------------------------------------


class TestDiscoverEntries:
    def test_finds_valid_files(self, tmp_path: Path) -> None:
        _write_entry(tmp_path, "decision_a.md", name="a", written_by="claude-code")
        _write_entry(tmp_path, "decision_b.md", name="b", written_by="claude-code")
        entries = discover_entries(tmp_path, "claude-code")
        assert len(entries) == 2
        names = {e["name"] for e in entries}
        assert names == {"a", "b"}

    def test_skips_wrong_client(self, tmp_path: Path) -> None:
        _write_entry(tmp_path, "mine.md", written_by="claude-code")
        _write_entry(tmp_path, "theirs.md", written_by="gemini")
        entries = discover_entries(tmp_path, "claude-code")
        assert len(entries) == 1
        assert entries[0]["written_by"] == "claude-code"

    def test_skips_memory_md(self, tmp_path: Path) -> None:
        _write_entry(tmp_path, "MEMORY.md")
        _write_entry(tmp_path, "real_entry.md", name="real")
        entries = discover_entries(tmp_path, "claude-code")
        assert len(entries) == 1
        assert entries[0]["name"] == "real"

    def test_skips_stale_report(self, tmp_path: Path) -> None:
        _write_entry(tmp_path, "stale-entries-report.md")
        entries = discover_entries(tmp_path, "claude-code")
        assert len(entries) == 0

    def test_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        fake = tmp_path / "nonexistent"
        entries = discover_entries(fake, "claude-code")
        assert entries == []

    def test_defaults_written_by_to_expected_client(self, tmp_path: Path) -> None:
        """Files without written-by should default to expected_client."""
        d = tmp_path / "mem"
        d.mkdir()
        p = d / "entry.md"
        p.write_text("---\nname: test\ndescription: desc\ntype: decision\n---\nBody\n")
        entries = discover_entries(d, "claude-code")
        assert len(entries) == 1
        assert entries[0]["written_by"] == "claude-code"

    def test_entry_has_all_fields(self, tmp_path: Path) -> None:
        _write_entry(
            tmp_path,
            "full.md",
            name="full_entry",
            description="Full desc",
            entry_type="feedback",
            written_by="claude-code",
            created="2026-01-01",
            updated="2026-02-01",
        )
        entries = discover_entries(tmp_path, "claude-code")
        e = entries[0]
        assert e["name"] == "full_entry"
        assert e["type"] == "feedback"
        assert e["written_by"] == "claude-code"
        assert e["created"] == "2026-01-01"
        assert e["updated"] == "2026-02-01"
        assert e["description"] == "Full desc"
        assert isinstance(e["source_path"], Path)
        assert "body" in e
        assert "raw" in e


# ---------------------------------------------------------------------------
# _normalize / _is_noise
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_strips_commit_hashes(self) -> None:
        assert "fix stuff" in _normalize("fix stuff abc1234def")

    def test_strips_file_counts(self) -> None:
        assert "files" not in _normalize("changed 5 files in refactor")

    def test_collapses_whitespace(self) -> None:
        assert _normalize("  lots   of   spaces  ") == "lots of spaces"

    def test_lowercases(self) -> None:
        assert _normalize("ALL CAPS") == "all caps"


class TestIsNoise:
    def test_chore_sync_regenerate(self) -> None:
        assert _is_noise("chore(sync): regenerate memory files")

    def test_session_checkpoint(self) -> None:
        assert _is_noise("Session checkpoint")

    def test_bare_commit_message(self) -> None:
        assert _is_noise("fix(health): update route (abc1234, 3 files)")

    def test_empty_description(self) -> None:
        assert _is_noise("")
        assert _is_noise("   ")

    def test_good_description_passes(self) -> None:
        assert not _is_noise("Skills sync redesigned to client-native mastering")

    def test_real_feedback_passes(self) -> None:
        assert not _is_noise(
            "Always verify full data pipeline on custom pages"
        )


# ---------------------------------------------------------------------------
# quality_gate
# ---------------------------------------------------------------------------


class TestQualityGate:
    def test_rejects_noise(self) -> None:
        entries = [
            {"name": "noise1", "description": "chore(sync): regenerate"},
            {"name": "good", "description": "Real architectural decision"},
        ]
        result = quality_gate(entries)
        assert len(result) == 1
        assert result[0]["name"] == "good"

    def test_rejects_duplicates(self) -> None:
        entries = [
            {"name": "a", "description": "Implement memory assembler"},
            {"name": "b", "description": "implement  memory  assembler"},
        ]
        result = quality_gate(entries)
        assert len(result) == 1

    def test_passes_good_entries(self) -> None:
        entries = [
            {"name": "a", "description": "First unique entry"},
            {"name": "b", "description": "Second different entry"},
        ]
        result = quality_gate(entries)
        assert len(result) == 2

    def test_empty_input(self) -> None:
        assert quality_gate([]) == []


# ---------------------------------------------------------------------------
# assemble_to_vault
# ---------------------------------------------------------------------------


class TestAssembleToVault:
    def _make_entries(self, src_dir: Path) -> list[dict]:
        _write_entry(src_dir, "entry.md", name="e", written_by="claude-code")
        entries = discover_entries(src_dir, "claude-code")
        return entries

    def test_copies_with_prefix_and_header(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        entries = self._make_entries(src)
        written = assemble_to_vault(entries, vault)
        assert len(written) == 1
        target = vault / "entries" / "claude-code_entry.md"
        assert target.exists()
        content = target.read_text()
        assert content.startswith("---\n")
        assert "<!-- ASSEMBLED by memory_assembler from claude-code -->" in content
        fm_end = content.find("\n---", 4)
        assert fm_end != -1
        comment_index = content.find("<!-- ASSEMBLED by memory_assembler from claude-code -->")
        assert comment_index > fm_end

    def test_skips_unchanged(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        entries = self._make_entries(src)

        written1 = assemble_to_vault(entries, vault)
        assert len(written1) == 1

        written2 = assemble_to_vault(entries, vault)
        assert len(written2) == 0

    def test_updates_changed(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        entries = self._make_entries(src)
        assemble_to_vault(entries, vault)

        # Change the raw content
        entries[0]["raw"] = "---\nname: changed\n---\nNew body\n"
        written = assemble_to_vault(entries, vault)
        assert len(written) == 1

    def test_preserves_existing_graph_system_frontmatter(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        vault = tmp_path / "vault"
        entries = self._make_entries(src)
        assemble_to_vault(entries, vault)

        target = vault / "entries" / "claude-code_entry.md"
        target.write_text(
            "---\n"
            "name: e\n"
            "description: A test entry\n"
            "_mentions:\n"
            "- '[[project-gbrain-borrow-slate]]'\n"
            "_entity_tier: 2\n"
            "---\n"
            "<!-- ASSEMBLED by memory_assembler from claude-code -->\n\n"
            "Old body.\n",
            encoding="utf-8",
        )

        entries[0]["raw"] = (
            "---\n"
            "name: e\n"
            "description: Changed source\n"
            "type: decision\n"
            "written-by: claude-code\n"
            "---\n"
            "New body.\n"
        )
        assemble_to_vault(entries, vault)

        meta = _parse_frontmatter(target)
        assert meta is not None
        assert meta["_mentions"] == ["[[project-gbrain-borrow-slate]]"]
        assert meta["_entity_tier"] == 2
        assert "New body." in target.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# generate_claude_index
# ---------------------------------------------------------------------------


class TestGenerateClaudeIndex:
    def _make_entries(self, tmp_path: Path) -> list[dict]:
        for i, date in enumerate(["2026-03-10", "2026-03-15", "2026-03-12"]):
            _write_entry(
                tmp_path,
                f"entry_{i}.md",
                name=f"entry_{i}",
                description=f"Desc {i}",
                updated=date,
                written_by="claude-code",
            )
        return discover_entries(tmp_path, "claude-code")

    def test_linked_format(self, tmp_path: Path) -> None:
        entries = self._make_entries(tmp_path)
        index = generate_claude_index(entries)
        assert "# Augur Memory" in index
        assert "[entry_" in index
        assert "](entry_" in index

    def test_sorted_by_date_desc(self, tmp_path: Path) -> None:
        entries = self._make_entries(tmp_path)
        index = generate_claude_index(entries)
        lines = [line for line in index.splitlines() if line.startswith("- [")]
        # First entry should be 2026-03-15 (entry_1)
        assert "entry_1" in lines[0]
        # Last should be 2026-03-10 (entry_0)
        assert "entry_0" in lines[-1]

    def test_budget_enforcement(self, tmp_path: Path) -> None:
        # Create more entries than budget
        for i in range(10):
            _write_entry(
                tmp_path,
                f"e{i}.md",
                name=f"e{i}",
                description=f"Desc {i}",
                updated=f"2026-03-{10 + i:02d}",
                written_by="cc",
            )
        entries = discover_entries(tmp_path, "cc")
        index = generate_claude_index(entries, budget=3)
        entry_lines = [line for line in index.splitlines() if line.startswith("- [")]
        assert len(entry_lines) == 3


# ---------------------------------------------------------------------------
# generate_vault_index
# ---------------------------------------------------------------------------


class TestGenerateVaultIndex:
    def test_table_format(self, tmp_path: Path) -> None:
        _write_entry(
            tmp_path,
            "entry.md",
            name="vault_entry",
            description="Vault desc",
            entry_type="project",
            written_by="claude-code",
            updated="2026-03-15",
        )
        entries = discover_entries(tmp_path, "claude-code")
        index = generate_vault_index(entries)

        assert "# Augur Memory Index" in index
        assert "| Date | Client | Type | Name | Description |" in index
        assert "| 2026-03-15 | claude-code | project | vault_entry | Vault desc |" in index

    def test_all_columns_present(self, tmp_path: Path) -> None:
        _write_entry(tmp_path, "e.md", written_by="gemini")
        entries = discover_entries(tmp_path, "gemini")
        index = generate_vault_index(entries)
        # Header + separator + data row
        table_lines = [line for line in index.splitlines() if line.startswith("|")]
        assert len(table_lines) == 3  # header, separator, data

    def test_merge_preserves_existing_curated_sections(self, tmp_path: Path) -> None:
        existing = (
            "# Augur Memory Index\n\n"
            "| Date | Client | Type | Name | Description |\n"
            "|------|--------|------|------|-------------|\n\n"
            "## Decisions\n\n"
            "### General\n"
            "- **Where should wiki outcomes live?**: In the vault.\n"
        )
        _write_entry(
            tmp_path,
            "entry.md",
            name="vault_entry",
            description="Vault desc",
            entry_type="project",
            written_by="claude-code",
            updated="2026-03-15",
        )
        entries = discover_entries(tmp_path, "claude-code")

        merged = merge_vault_index(existing, generate_vault_index(entries))

        assert "<!-- AUGUR-ASSEMBLED-INDEX:BEGIN -->" in merged
        assert "| 2026-03-15 | claude-code | project | vault_entry | Vault desc |" in merged
        assert "## Decisions" in merged
        assert "Where should wiki outcomes live?" in merged

    def test_merge_replaces_existing_managed_block_once(self, tmp_path: Path) -> None:
        existing = (
            "<!-- AUGUR-ASSEMBLED-INDEX:BEGIN -->\n"
            "# Augur Memory Index\n\nold\n"
            "<!-- AUGUR-ASSEMBLED-INDEX:END -->\n\n"
            "## Decisions\n"
            "- Keep me.\n"
        )

        merged = merge_vault_index(existing, "# Augur Memory Index\n\nnew\n")

        assert "old" not in merged
        assert merged.count("<!-- AUGUR-ASSEMBLED-INDEX:BEGIN -->") == 1
        assert "new" in merged
        assert "- Keep me." in merged


# ---------------------------------------------------------------------------
# generate_flat_index
# ---------------------------------------------------------------------------


class TestGenerateFlatIndex:
    def test_inlines_content(self, tmp_path: Path) -> None:
        _write_entry(
            tmp_path,
            "entry.md",
            name="flat_entry",
            description="Flat desc",
            body="Detailed body content.\n",
            written_by="codex",
        )
        entries = discover_entries(tmp_path, "codex")
        index = generate_flat_index(entries)

        assert "# Augur Memory (flat)" in index
        assert "## flat_entry" in index
        assert "*Written by: codex*" in index
        assert "Flat desc" in index
        assert "Detailed body content." in index

    def test_written_by_shown(self, tmp_path: Path) -> None:
        _write_entry(tmp_path, "e.md", written_by="gemini")
        entries = discover_entries(tmp_path, "gemini")
        index = generate_flat_index(entries)
        assert "*Written by: gemini*" in index


# ---------------------------------------------------------------------------
# _update_gemini_imports
# ---------------------------------------------------------------------------


class TestUpdateGeminiImports:
    def test_replaces_section(self, tmp_path: Path) -> None:
        gemini = tmp_path / "GEMINI.md"
        gemini.write_text(
            "# Gemini\n\n## Augur Memories\n\nold stuff\n\n## Other\n\nKeep this\n"
        )
        entries = [
            {"source_path": Path("a.md"), "written_by": "gemini"},
            {"source_path": Path("b.md"), "written_by": "gemini"},
        ]
        _update_gemini_imports(entries, gemini)
        content = gemini.read_text()
        assert "@./memory/a.md" in content
        assert "@./memory/b.md" in content
        assert "old stuff" not in content
        assert "Keep this" in content

    def test_creates_section_if_missing(self, tmp_path: Path) -> None:
        gemini = tmp_path / "GEMINI.md"
        gemini.write_text("# Gemini\n\nSome content.\n")
        entries = [{"source_path": Path("x.md"), "written_by": "gemini"}]
        _update_gemini_imports(entries, gemini)
        content = gemini.read_text()
        assert "## Augur Memories" in content
        assert "@./memory/x.md" in content

    def test_no_crash_missing_file(self, tmp_path: Path) -> None:
        fake = tmp_path / "no_exist.md"
        _update_gemini_imports([], fake)  # should not raise

    def test_materializes_cross_client_files(self, tmp_path: Path) -> None:
        gemini = tmp_path / "GEMINI.md"
        gemini.write_text("# Gemini\n")
        src = tmp_path / "src.md"
        src.write_text("---\nname: feedback_x\n---\nbody\n")
        entries = [
            {
                "source_path": src,
                "written_by": "claude-code",
                "raw": src.read_text(),
            },
        ]
        _update_gemini_imports(entries, gemini)
        materialized = tmp_path / "memory" / "src.md"
        assert materialized.exists(), "cross-client memory must be copied next to GEMINI.md"
        content = materialized.read_text()
        assert content.startswith("<!-- CROSS-CLIENT from claude-code -->")
        assert "body" in content
        assert "@./memory/src.md" in gemini.read_text()

    def test_skips_gemini_native_entries(self, tmp_path: Path) -> None:
        gemini = tmp_path / "GEMINI.md"
        gemini.write_text("# Gemini\n")
        entries = [
            {"source_path": Path("native.md"), "written_by": "gemini", "raw": "x"},
        ]
        _update_gemini_imports(entries, gemini)
        # Gemini-native entries are read from .gemini/memory/ in production; the
        # assembler must not write a stub for them here.
        assert not (tmp_path / "memory" / "native.md").exists()
        assert "@./memory/native.md" in gemini.read_text()


# ---------------------------------------------------------------------------
# assemble (full pipeline)
# ---------------------------------------------------------------------------


class TestAssemble:
    def test_default_plan_discovers_clients_without_claude_requirement(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        home = tmp_path / "home"
        encoded_project = str(project.resolve()).replace("\\", "-").replace("/", "-").replace(":", "-")

        (home / ".claude" / "projects" / encoded_project / "memory").mkdir(parents=True)
        (home / ".codex").mkdir(parents=True)
        (home / ".kimi").mkdir(parents=True)
        (project / ".antigravity" / "memory").mkdir(parents=True)
        (project / ".antigravity" / "ANTIGRAVITY.md").write_text(
            "# Antigravity\n",
            encoding="utf-8",
        )
        (project / ".cursor" / "memory").mkdir(parents=True)
        (project / ".github").mkdir(parents=True)

        plan = resolve_default_client_memory_plan(project_root=project, home=home)

        assert {"claude-code", "codex", "gemini", "cursor"} <= set(plan["sources"])
        output_clients = {output["client"] for output in plan["outputs"]}
        assert {"claude-code", "codex", "gemini", "cursor", "copilot", "kimi"} <= output_clients

    def test_assemble_writes_generic_client_outputs(self, tmp_path: Path) -> None:
        cursor_dir = tmp_path / "cursor_mem"
        vault_dir = tmp_path / "vault"
        codex_out = tmp_path / "codex" / "augur-memory.md"
        cursor_out = tmp_path / "cursor" / "augur-memory.md"

        _write_entry(
            cursor_dir,
            "preference.md",
            name="preference",
            description="Use whichever client the user picked",
            written_by="cursor",
        )

        result = assemble(
            sources={"cursor": cursor_dir},
            vault_memory_dir=vault_dir,
            client_outputs=[
                {"client": "codex", "kind": "flat_index", "path": codex_out},
                {"client": "cursor", "kind": "flat_index", "path": cursor_out},
            ],
        )

        assert result["after_quality_gate"] == 1
        assert "## preference" in codex_out.read_text(encoding="utf-8")
        assert "## preference" in cursor_out.read_text(encoding="utf-8")
        assert str(codex_out) in result["indexes_written"]
        assert str(cursor_out) in result["indexes_written"]

    def test_end_to_end(self, tmp_path: Path) -> None:
        # Set up two client dirs
        claude_dir = tmp_path / "claude_mem"
        codex_dir = tmp_path / "codex_mem"
        vault_dir = tmp_path / "vault"
        claude_out = tmp_path / "claude_out"
        codex_out = tmp_path / "codex_out" / "MEMORY.md"
        gemini_md = tmp_path / "GEMINI.md"
        gemini_md.write_text("# Gemini Config\n")

        _write_entry(
            claude_dir,
            "decision_a.md",
            name="decision_a",
            description="Architecture decision A",
            written_by="claude-code",
            updated="2026-03-15",
        )
        _write_entry(
            claude_dir,
            "noise.md",
            name="noise",
            description="chore(sync): regenerate memory",
            written_by="claude-code",
        )
        _write_entry(
            codex_dir,
            "feedback_b.md",
            name="feedback_b",
            description="Real feedback from codex",
            written_by="codex",
            updated="2026-03-16",
        )

        result = assemble(
            sources={"claude-code": claude_dir, "codex": codex_dir},
            vault_memory_dir=vault_dir,
            claude_native_dir=claude_out,
            gemini_md_path=gemini_md,
            codex_memory_path=codex_out,
        )

        # Discovered all 3, but noise filtered
        assert result["discovered"] == 3
        assert result["after_quality_gate"] == 2

        # Vault entries created
        assert len(result["assembled_paths"]) == 2
        entries_dir = vault_dir / "entries"
        assert entries_dir.is_dir()
        vault_files = list(entries_dir.glob("*.md"))
        assert len(vault_files) == 2

        # Claude MEMORY.md written
        claude_memory = claude_out / "MEMORY.md"
        assert claude_memory.exists()
        claude_content = claude_memory.read_text()
        assert "decision_a" in claude_content
        assert "feedback_b" in claude_content

        # Vault MEMORY.md written
        vault_index = vault_dir / "MEMORY.md"
        assert vault_index.exists()
        assert "| Date |" in vault_index.read_text()

        # Codex flat index written
        assert codex_out.exists()
        codex_content = codex_out.read_text()
        assert "## decision_a" in codex_content
        assert "## feedback_b" in codex_content

        # Gemini updated
        gemini_content = gemini_md.read_text()
        assert "## Augur Memories" in gemini_content

        # Indexes written list
        assert len(result["indexes_written"]) == 4  # vault, claude, gemini, codex

    def test_missing_source_dirs(self, tmp_path: Path) -> None:
        """Pipeline handles missing source dirs gracefully."""
        vault = tmp_path / "vault"
        result = assemble(
            sources={"claude-code": tmp_path / "nonexistent"},
            vault_memory_dir=vault,
        )
        assert result["discovered"] == 0
        assert result["after_quality_gate"] == 0

    def test_zero_discovery_preserves_existing_vault_memory_payload(self, tmp_path: Path) -> None:
        """A transient source miss must not erase durable vault memory indexes."""
        vault = tmp_path / "vault"
        entries = vault / "entries"
        _write_entry(
            entries,
            "claude-code_existing.md",
            name="existing",
            description="Existing durable memory",
            written_by="claude-code",
        )
        memory_index = vault / "MEMORY.md"
        memory_index.write_text(
            "<!-- AUGUR-ASSEMBLED-INDEX:BEGIN -->\n"
            "# Augur Memory Index\n\n"
            "| Date | Client | Type | Name | Description |\n"
            "|------|--------|------|------|-------------|\n"
            "| 2026-03-16 | claude-code | decision | existing | Existing durable memory |\n"
            "<!-- AUGUR-ASSEMBLED-INDEX:END -->\n",
            encoding="utf-8",
        )
        stale_report = vault / "stale-entries-report.md"
        stale_report.write_text("# Stale Memory Entries\n\nKeep until sources return.\n", encoding="utf-8")

        result = assemble(
            sources={"claude-code": tmp_path / "nonexistent"},
            vault_memory_dir=vault,
        )

        assert result["discovered"] == 0
        assert result["after_quality_gate"] == 0
        assert result["indexes_written"] == []
        assert result["skipped"] == "empty-discovery-preserved-existing-vault-memory"
        assert "existing | Existing durable memory" in memory_index.read_text(encoding="utf-8")
        assert stale_report.exists()


class TestOpsProtocol:
    def test_scan_checks_linked_client_outputs_from_plan(self, monkeypatch, tmp_path: Path) -> None:
        linked_dir = tmp_path / "cursor-memory"
        linked_dir.mkdir()
        (linked_dir / "MEMORY.md").write_text("- [missing](missing.md)\n", encoding="utf-8")
        _write_entry(linked_dir, "unindexed.md", written_by="cursor")
        vault = tmp_path / "vault-memory"
        vault.mkdir()

        monkeypatch.setattr(memory_assembler_module, "get_memory_dir", lambda: vault)
        monkeypatch.setattr(
            memory_assembler_module,
            "resolve_default_client_memory_plan",
            lambda *, project_root: {
                "sources": {},
                "outputs": [
                    {"client": "cursor", "kind": "linked_index", "dir": linked_dir},
                ],
            },
        )

        result = memory_assembler_module.scan(OpsContext(project_root=tmp_path))

        actions = {issue["action"] for issue in result.issues}
        assert {"orphaned-index-entry", "unindexed-memory-file"} <= actions

    def test_fix_uses_client_memory_plan_outputs(self, monkeypatch, tmp_path: Path) -> None:
        source_dir = tmp_path / "cursor-source"
        vault = tmp_path / "vault-memory"
        cursor_out = tmp_path / "cursor" / "augur-memory.md"
        _write_entry(
            source_dir,
            "decision.md",
            name="decision",
            description="Client-neutral memory repair",
            written_by="cursor",
        )

        monkeypatch.setattr(memory_assembler_module, "get_memory_dir", lambda: vault)
        monkeypatch.setattr(
            memory_assembler_module,
            "resolve_default_client_memory_plan",
            lambda *, project_root: {
                "sources": {"cursor": source_dir},
                "outputs": [
                    {"client": "cursor", "kind": "flat_index", "path": cursor_out},
                ],
            },
        )

        result = memory_assembler_module.fix(
            OpsContext(project_root=tmp_path, dry_run=False),
            [{"action": "missing-vault-index"}],
        )

        assert result.success is True
        assert "## decision" in cursor_out.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Staleness report
# ---------------------------------------------------------------------------


class TestStalenessReport:
    """Tests for _generate_staleness_report."""

    def test_generates_report_for_old_entries(self, tmp_path: Path) -> None:
        """Entries >90 days old appear in the staleness report."""
        from memory_assembler import _generate_staleness_report

        vault = tmp_path / "vault"
        vault.mkdir()
        entries = [
            {"name": "old", "type": "feedback", "written_by": "claude-code",
             "created": "2025-01-01", "updated": "2025-01-01", "description": "Very old"},
            {"name": "new", "type": "feedback", "written_by": "claude-code",
             "created": "2026-03-17", "updated": "2026-03-17", "description": "Recent"},
        ]
        _generate_staleness_report(entries, vault)
        report = vault / "stale-entries-report.md"
        assert report.exists()
        content = report.read_text()
        assert "old" in content
        assert "new" not in content

    def test_no_report_when_all_fresh(self, tmp_path: Path) -> None:
        """No report generated if all entries are recent."""
        from memory_assembler import _generate_staleness_report

        vault = tmp_path / "vault"
        vault.mkdir()
        entries = [
            {"name": "fresh", "type": "feedback", "written_by": "claude-code",
             "created": "2026-03-17", "updated": "2026-03-17", "description": "Fresh"},
        ]
        _generate_staleness_report(entries, vault)
        assert not (vault / "stale-entries-report.md").exists()

    def test_deletes_stale_report_when_all_fresh(self, tmp_path: Path) -> None:
        """If a stale report exists but all entries are now fresh, delete it."""
        from memory_assembler import _generate_staleness_report

        vault = tmp_path / "vault"
        vault.mkdir()
        report = vault / "stale-entries-report.md"
        report.write_text("# Old stale report")

        entries = [
            {"name": "fresh", "type": "feedback", "written_by": "claude-code",
             "created": "2026-03-17", "updated": "2026-03-17", "description": "Fresh"},
        ]
        _generate_staleness_report(entries, vault)
        assert not report.exists()


# ---------------------------------------------------------------------------
# Cross-client entry copying
# ---------------------------------------------------------------------------


class TestCrossClientCopies:
    """Tests for cross-client entry copies in Claude native dir."""

    def test_cross_client_entries_copied_to_claude_dir(self, tmp_path: Path) -> None:
        """Non-Claude entries are copied into Claude native dir so index links resolve."""
        gemini_dir = tmp_path / "gemini"
        gemini_dir.mkdir()
        raw = (
            "---\nname: gemini-pattern\ntype: feedback\nwritten-by: gemini\n"
            "created: 2026-03-17\nupdated: 2026-03-17\n"
            "description: Gemini found this\n---\n\nGemini content.\n"
        )
        (gemini_dir / "feedback_gemini-pattern.md").write_text(raw)

        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()
        vault = tmp_path / "vault"

        assemble(
            sources={"gemini": gemini_dir},
            vault_memory_dir=vault,
            claude_native_dir=claude_dir,
        )

        # Entry should be copied to Claude dir
        copied = claude_dir / "feedback_gemini-pattern.md"
        assert copied.exists()
        content = copied.read_text()
        assert "CROSS-CLIENT from gemini" in content
        assert "Gemini content." in content

    def test_claude_owned_entries_not_duplicated(self, tmp_path: Path) -> None:
        """Claude-owned entries are NOT re-copied (they already exist)."""
        claude_dir = tmp_path / "claude"
        claude_dir.mkdir()
        raw = (
            "---\nname: my-entry\ntype: feedback\nwritten-by: claude-code\n"
            "created: 2026-03-17\nupdated: 2026-03-17\n"
            "description: Claude wrote this\n---\n\nClaude content.\n"
        )
        original = claude_dir / "feedback_my-entry.md"
        original.write_text(raw)

        vault = tmp_path / "vault"
        assemble(
            sources={"claude-code": claude_dir},
            vault_memory_dir=vault,
            claude_native_dir=claude_dir,
        )

        # Original should be unchanged (no CROSS-CLIENT header)
        content = original.read_text()
        assert "CROSS-CLIENT" not in content


# ---------------------------------------------------------------------------
# ADR-772: review candidates (client memory is input, not auto-promoted)
# ---------------------------------------------------------------------------


class TestReviewCandidates:
    def test_to_review_candidates_uses_canonical_filename(self, tmp_path: Path) -> None:
        _write_entry(tmp_path, "feedback_foo.md", name="Foo", written_by="claude-code")
        entries = discover_entries(tmp_path, "claude-code")
        candidates = to_review_candidates(entries)
        assert len(candidates) == 1
        cand = candidates[0]
        # Canonical naming matches the legacy assemble_to_vault convention so
        # already-promoted entries are detected.
        assert cand.target_filename == "claude-code_feedback_foo.md"
        assert cand.client == "claude-code"
        assert cand.name == "Foo"

    def test_collect_review_candidates_does_not_write_canonical_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ADR-772: surfacing candidates must never write to the brain vault."""
        client_dir = tmp_path / "client_memory"
        _write_entry(client_dir, "feedback_bar.md", name="Bar", written_by="claude-code")

        project_root = tmp_path / "repo"
        project_root.mkdir()

        def _fake_plan(*, project_root, home=None, env=None):  # noqa: ANN001
            return {"sources": {"claude-code": client_dir}, "outputs": []}

        monkeypatch.setattr(
            memory_assembler_module,
            "resolve_default_client_memory_plan",
            _fake_plan,
        )

        # A vault dir that must remain untouched.
        vault_entries = tmp_path / "vault" / "memory" / "entries"
        vault_entries.mkdir(parents=True)

        candidates = collect_review_candidates([project_root])
        assert len(candidates) == 1
        assert candidates[0].name == "Bar"
        # Critical: no canonical entry was written anywhere.
        assert list(vault_entries.glob("*.md")) == []

    def test_collect_review_candidates_dedupes_across_roots(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client_dir = tmp_path / "client_memory"
        _write_entry(client_dir, "feedback_baz.md", name="Baz", written_by="claude-code")

        def _fake_plan(*, project_root, home=None, env=None):  # noqa: ANN001
            return {"sources": {"claude-code": client_dir}, "outputs": []}

        monkeypatch.setattr(
            memory_assembler_module,
            "resolve_default_client_memory_plan",
            _fake_plan,
        )
        # Same source resolved from two roots -> one candidate.
        candidates = collect_review_candidates([tmp_path / "a", tmp_path / "b"])
        assert len(candidates) == 1


class TestReindexBrainMemory:
    def test_rebuilds_index_table_from_entries_dir(self, tmp_path: Path) -> None:
        from memory_assembler import reindex_brain_memory

        memory_dir = tmp_path / "brain" / "memory"
        entries_dir = memory_dir / "entries"
        _write_entry(
            entries_dir, "claude-code_foo.md", name="Foo fact",
            description="something useful", written_by="claude-code",
        )
        _write_entry(
            entries_dir, "agent_bar.md", name="Bar fact",
            description="agent observation", written_by="claude-code",
        )

        index_path = reindex_brain_memory(memory_dir)
        assert index_path == memory_dir / "MEMORY.md"
        content = index_path.read_text(encoding="utf-8")
        # Managed block + both entries present in the table.
        assert "AUGUR-ASSEMBLED-INDEX:BEGIN" in content
        assert "Foo fact" in content
        assert "Bar fact" in content
        # agent_ prefix is not a known client -> attributed to user.
        assert "| user |" in content or "| agent |" in content

    def test_no_entries_dir_returns_none(self, tmp_path: Path) -> None:
        from memory_assembler import reindex_brain_memory

        assert reindex_brain_memory(tmp_path / "empty" / "memory") is None

    def test_preserves_curated_content_outside_managed_block(self, tmp_path: Path) -> None:
        from memory_assembler import reindex_brain_memory

        memory_dir = tmp_path / "brain" / "memory"
        entries_dir = memory_dir / "entries"
        _write_entry(entries_dir, "claude-code_x.md", name="X", written_by="claude-code")
        index_path = memory_dir / "MEMORY.md"
        memory_dir.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            "<!-- AUGUR-ASSEMBLED-INDEX:BEGIN -->\nold\n<!-- AUGUR-ASSEMBLED-INDEX:END -->\n\n## My curated notes\n- keep me\n",
            encoding="utf-8",
        )
        reindex_brain_memory(memory_dir)
        content = index_path.read_text(encoding="utf-8")
        assert "My curated notes" in content
        assert "keep me" in content
        assert "X" in content
