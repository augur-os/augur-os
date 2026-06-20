"""Tests for the client-memory sweep module (ADR-811).

Verifies sweep_client_memory, render_memory_index, and claude_project_memory_dir
using the established test bootstrap and real src.lib APIs.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = next(
    (
        p
        for p in Path(__file__).resolve().parents
        if (p / "pyproject.toml").exists() and (p / ".git").exists()
    ),
    Path(__file__).resolve().parents[-1],
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from src.lib.brain_registry_models import BrainType
from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter


def _client_entry(directory: Path, name: str, mem_type: str, body: str) -> Path:
    path = directory / f"{name}.md"
    write_frontmatter(
        path,
        {"name": name, "description": f"{name} description", "metadata": {"type": mem_type}},
        body,
    )
    return path


def _brains(tmp_path: Path):
    """
    Build minimal brain-like namespaces for the sweep tests.

    IMPORTANT: memory_dir_for_brain resolves differently by BrainType:
      - PROJECT  → <root>/knowledge/memory  (root/knowledge must be a dir)
      - PERSONAL → <root>/memory            (PERSONAL never uses knowledge subdir)
      - GLOBAL   → <root>/knowledge/memory  iff root/knowledge is_dir(), else root/memory

    So the personal brain's entries land at vault/memory/entries, NOT
    vault/knowledge/memory/entries.  Tests must match this layout.
    """
    project_root = tmp_path / "brain"
    personal_root = tmp_path / "vault"
    (project_root / "knowledge" / "memory" / "entries").mkdir(parents=True)
    (personal_root / "memory" / "entries").mkdir(parents=True)
    project = SimpleNamespace(id="proj", type=BrainType.PROJECT, data_root=str(project_root))
    personal = SimpleNamespace(id="pers", type=BrainType.PERSONAL, data_root=str(personal_root))
    return project, personal


def test_sweep_routes_project_and_personal_entries(tmp_path):
    from src.lib.client_memory_sweep import sweep_client_memory

    source = tmp_path / "client-mem"
    source.mkdir()
    _client_entry(source, "proj-fact", "project", "A project fact.")
    _client_entry(source, "user-pref", "user", "A user preference.")
    project, personal = _brains(tmp_path)

    result = sweep_client_memory(
        source,
        project_brain=project,
        personal_brain=personal,
        source_client="claude-code",
    )

    proj_entry = (
        Path(project.data_root) / "knowledge" / "memory" / "entries" / "proj-fact.md"
    )
    pers_entry = (
        Path(personal.data_root) / "memory" / "entries" / "user-pref.md"
    )
    assert proj_entry.is_file() and pers_entry.is_file()
    assert sorted(result.swept) == ["proj-fact", "user-pref"]

    meta, body = parse_frontmatter(proj_entry, include_sidecar_config=False)
    assert meta["name"] == "proj-fact"
    assert meta["source_client"] == "claude-code"
    assert meta["brain_scope"] == "project"
    # ADR-814: provenance stores filename, not machine path
    assert meta["source_file"] == "proj-fact.md"
    assert "source_path" not in meta
    assert "/Users/" not in str(meta)
    assert "A project fact." in body


def test_sweep_is_idempotent_and_skips_unchanged(tmp_path):
    from src.lib.client_memory_sweep import sweep_client_memory

    source = tmp_path / "client-mem"
    source.mkdir()
    _client_entry(source, "proj-fact", "project", "A project fact.")
    project, personal = _brains(tmp_path)

    first = sweep_client_memory(
        source,
        project_brain=project,
        personal_brain=personal,
        source_client="claude-code",
    )
    second = sweep_client_memory(
        source,
        project_brain=project,
        personal_brain=personal,
        source_client="claude-code",
    )
    assert first.swept == ["proj-fact"]
    assert second.swept == []
    assert second.skipped == ["proj-fact"]


def test_sweep_skips_memory_md_and_malformed(tmp_path):
    from src.lib.client_memory_sweep import sweep_client_memory

    source = tmp_path / "client-mem"
    source.mkdir()
    # MEMORY.md is explicitly excluded by name
    (source / "MEMORY.md").write_text("# index, not an entry", encoding="utf-8")
    # no-frontmatter file: parse_frontmatter returns ({}, content) → empty meta → skip
    (source / "broken.md").write_text("no frontmatter here, just plain text", encoding="utf-8")
    project, personal = _brains(tmp_path)

    result = sweep_client_memory(
        source,
        project_brain=project,
        personal_brain=personal,
        source_client="claude-code",
    )
    assert result.swept == []
    assert (source / "MEMORY.md").exists()  # source never modified


def test_render_memory_index_lists_entries(tmp_path):
    from src.lib.client_memory_sweep import render_memory_index

    project, _ = _brains(tmp_path)
    entries = Path(project.data_root) / "knowledge" / "memory" / "entries"
    write_frontmatter(
        entries / "proj-fact.md",
        {"name": "proj-fact", "description": "A swept fact"},
        "Body.",
    )
    (entries / "README.md").write_text("# Folder stub\n", encoding="utf-8")

    rendered = render_memory_index(project)
    assert "proj-fact" in rendered
    assert "A swept fact" in rendered
    assert "knowledge/memory/entries/proj-fact.md" in rendered
    assert "Do not hand-edit" in rendered
    assert "README" not in rendered


def test_claude_project_memory_dir_slug():
    from src.lib.client_memory_sweep import claude_project_memory_dir

    out = claude_project_memory_dir(Path("/Users/u/Projects/Augur"), home=Path("/Users/u"))
    assert out == Path("/Users/u/.claude/projects/-Users-u-Projects-Augur/memory")


def test_private_subject_overrides_declared_project_type():
    """resume-tailor regression: type:project but subject is a private-vault skill."""
    from src.lib.client_memory_sweep import effective_memory_brain_type

    meta = {"type": "project", "brain_scope": "project"}
    body = ("Built a private-vault skill at `Au-vault/capabilities/skills/resume-tailor/` "
            "that tailors Gur's resume and writes `Au-docs/career/`.")
    assert effective_memory_brain_type(meta, body) == "personal"


def test_real_project_entry_stays_project():
    from src.lib.client_memory_sweep import effective_memory_brain_type

    meta = {"type": "project"}
    body = "augur_core MCP server in `src/mcp/augur_core/`; see ADR-781."
    assert effective_memory_brain_type(meta, body) == "project"
