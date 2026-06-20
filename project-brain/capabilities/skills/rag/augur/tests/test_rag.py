from pathlib import Path
import sys
from unittest.mock import patch

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent.parent))
from src.lib.index.unified_indexer import reindex_all
from src.lib.index.unified_search import iterative_search


def _mock_discover_plugins(tmp_path):
    """Scan tmp_path/plugins/*/skills/* for test skill dirs."""
    results = []
    plugins_root = tmp_path / "plugins"
    if plugins_root.is_dir():
        for bundle_dir in sorted(plugins_root.iterdir()):
            if not bundle_dir.is_dir():
                continue
            skills_dir = bundle_dir / "skills"
            if not skills_dir.is_dir():
                continue
            for skill_dir in sorted(skills_dir.iterdir()):
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").is_file():
                    results.append((bundle_dir.name, skill_dir))
    return results

# NOTE: test_rag_indexing was removed — it tested old rag_indexer.run_indexer()
# chunk/symbol behavior (symbols.yaml, root_index.md, chunks/*.md) which no
# longer exists in the pointer-based unified_indexer system. Equivalent
# coverage is now provided by test_unified_indexer.py.


def test_rag_reindex_creates_manifest(tmp_path):
    """Smoke-test that reindex_all produces a manifest for a minimal project."""
    skill_dir = tmp_path / "plugins" / "test" / "skills" / "myskill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: myskill\ndescription: Test skill\nvisibility: dev\n---\n# My Skill\n"
    )

    adr_dir = tmp_path / "docs" / "decisions"
    adr_dir.mkdir(parents=True)
    (adr_dir / "ADR-001-test.md").write_text(
        "---\nstatus: Proposed\ndate: '2026-01-01'\nhub: null\n---\n# ADR-001: Test\n"
    )

    rag_dir = tmp_path / "rag"
    with patch("src.lib.index._scanners_knowledge._discover_skill_dirs", return_value=_mock_discover_plugins(tmp_path)), \
         patch("src.lib.index._scanners_structural._discover_skill_dirs", return_value=_mock_discover_plugins(tmp_path)):
        stats = reindex_all(tmp_path, rag_dir, vault_dir=None)

    # Manifest must exist
    manifest = rag_dir / "_meta" / "manifest.yaml"
    assert manifest.exists(), "manifest.yaml was not created"

    # At least one skill and one ADR indexed
    assert stats["skills"] >= 1, f"Expected >=1 skills, got {stats['skills']}"
    assert stats["adrs"] >= 1, f"Expected >=1 adrs, got {stats['adrs']}"

    # Pointer entry must exist
    entry = rag_dir / "skills" / "test" / "external" / "myskill.md"
    assert entry.exists(), "Skill pointer entry was not created"
    content = entry.read_text()
    assert "type: skill" in content
    assert "myskill" in content


def test_rag_iterative_search(tmp_path):
    """Verify iterative_search finds content indexed by reindex_all."""
    skill_dir = tmp_path / "plugins" / "ai" / "skills" / "rag"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: rag\ndescription: RAG search engine\nvisibility: auto\n---\n# RAG Skill\n"
    )

    rag_dir = tmp_path / "rag"
    with patch("src.lib.index._scanners_knowledge._discover_skill_dirs", return_value=_mock_discover_plugins(tmp_path)), \
         patch("src.lib.index._scanners_structural._discover_skill_dirs", return_value=_mock_discover_plugins(tmp_path)):
        reindex_all(tmp_path, rag_dir, vault_dir=None)

    # Iterative search falls back to fulltext when no symbols.yaml is present
    results = iterative_search("RAG search engine", [tmp_path], [], [rag_dir])
    all_hits = [hit for group in results for hit in group.get("hits", [])]
    assert len(all_hits) > 0, "iterative_search returned no results"
