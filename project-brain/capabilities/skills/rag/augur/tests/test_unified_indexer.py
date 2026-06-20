# TODO_CLEANUP: This file is 937 lines — consider splitting into smaller modules
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config.paths import get_project_root


def _make_skill(tmp_path, bundle, skill_name, content):
    """Helper: create a minimal SKILL.md under plugins/ layout."""
    skill_dir = tmp_path / "plugins" / bundle / "skills" / skill_name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(content)
    return skill_dir


def _mock_discover(tmp_path):
    """Build a mock for _discover_skill_dirs that scans tmp_path/plugins/*/skills/*.

    Returns a list of (bundle_name, skill_dir) tuples mirroring what the
    real discover_all_skills() returns, but scanning tmp_path instead of
    the real project root.
    """
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


def _resolve_unified_indexer_script() -> Path:
    """Locate the canonical unified_indexer CLI under src/lib/index/."""
    return get_project_root() / "src" / "lib" / "index" / "unified_indexer.py"


def _fixture_document_sources(documents_dir: Path):
    from src.lib.index.document_sources import DocumentSource

    return [
        DocumentSource(
            "documents",
            "Au-docs",
            documents_dir,
            preserve_legacy_output=True,
        )
    ]


def test_unified_indexer_cli_help_bootstraps_imports():
    script_path = _resolve_unified_indexer_script()
    result = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        capture_output=True,
        text=True,
        cwd=script_path.parents[3],
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "Unified RAG indexer" in result.stdout


def test_unified_indexer_cli_category_documents_uses_documents_dir(tmp_path):
    script_path = _resolve_unified_indexer_script()
    root = tmp_path / "project"
    docs_dir = tmp_path / "documents"
    home_dir = tmp_path / "home"
    desktop_dir = home_dir / "Desktop"
    downloads_dir = home_dir / "Downloads"
    rag_dir = tmp_path / "rag"

    root.mkdir(parents=True)
    docs_dir.mkdir(parents=True)
    desktop_dir.mkdir(parents=True)
    downloads_dir.mkdir(parents=True)
    (root / "repo-only.md").write_text("repo file", encoding="utf-8")
    (docs_dir / "brain").mkdir(parents=True)
    (docs_dir / "brain" / "live.md").write_text("# Live\n\nbody", encoding="utf-8")
    (desktop_dir / "loose.txt").write_text("desktop note", encoding="utf-8")
    (downloads_dir / "invoice.txt").write_text("download invoice", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--category",
            "documents",
            "--root",
            str(root),
            "--rag-dir",
            str(rag_dir),
            "--documents-dir",
            str(docs_dir),
        ],
        capture_output=True,
        text=True,
        cwd=script_path.parents[3],
        env={**os.environ, "HOME": str(home_dir)},
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "Indexed 3 documents entries" in result.stdout
    assert (rag_dir / "documents" / "brain" / "live.md").exists()
    assert (rag_dir / "documents" / "_sources" / "desktop" / "loose.md").exists()
    assert (rag_dir / "documents" / "_sources" / "downloads" / "invoice.md").exists()
    assert not (rag_dir / "documents" / "_root" / "repo-only.md").exists()


def test_reindex_category_documents_uses_documents_dir(tmp_path, monkeypatch):
    from src.lib.index.unified_indexer import reindex_category
    from src.lib.index import unified_indexer

    root = tmp_path / "project"
    documents_dir = tmp_path / "documents"
    rag_dir = tmp_path / "rag"

    root.mkdir(parents=True)
    documents_dir.mkdir(parents=True)
    (documents_dir / "brain").mkdir(parents=True, exist_ok=True)
    (documents_dir / "brain" / "founder-story.md").write_text(
        "# Founder Story\n\nbody",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        unified_indexer,
        "_extract_document",
        lambda path: {
            "format": "markdown",
            "size_bytes": path.stat().st_size,
            "created": "2026-04-15T10:00:00+00:00",
            "body": path.read_text(encoding="utf-8"),
            "extraction_error": None,
        },
    )
    monkeypatch.setattr(unified_indexer, "_load_mtime_cache", lambda: {})
    monkeypatch.setattr(unified_indexer, "_save_mtime_cache", lambda cache: None)

    count = reindex_category(
        "documents",
        root,
        rag_dir,
        document_sources=_fixture_document_sources(documents_dir),
    )

    assert count == 1
    assert (rag_dir / "documents" / "brain" / "founder-story.md").exists()


def test_index_mcp_servers_reads_system_manifest(tmp_path):
    from src.lib.index._scanners_structural import index_mcp_servers
    from src.lib.index.unified_indexer import reindex_category

    root = tmp_path / "repo"
    rag_dir = tmp_path / "rag"
    manifest = root / "config" / "system" / "mcp_servers.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        "project_tier:\n"
        "  - id: augur-core\n"
        "    description: Core registry\n"
        "    command: python\n"
        "    args: [-m, augur_core]\n"
        "vault_tier:\n"
        "  - id: augur-gmail\n"
        "    description: Gmail bundle\n"
        "    command: python\n"
        "    args: [-m, augur_shared.bundle_server, gmail]\n"
        "    bundle: gmail\n"
        "    bundle_path: ~/Projects/Au-vault/capabilities/skills/gmail\n",
        encoding="utf-8",
    )

    assert index_mcp_servers(root, rag_dir) == 2
    core = (rag_dir / "mcp-servers" / "augur-core.md").read_text(encoding="utf-8")
    gmail = (rag_dir / "mcp-servers" / "augur-gmail.md").read_text(encoding="utf-8")
    assert "tier: project-tier" in core
    assert "command: python" in core
    assert "bundle: gmail" in gmail
    assert "tier: vault-tier" in gmail

    assert reindex_category("mcp-servers", root, rag_dir) == 2


def test_index_mcp_servers_malformed_manifest_preserves_existing_output(tmp_path):
    from src.lib.index._scanners_structural import index_mcp_servers

    root = tmp_path / "repo"
    rag_dir = tmp_path / "rag"
    manifest = root / "config" / "system" / "mcp_servers.yaml"
    existing = rag_dir / "mcp-servers" / "existing.md"
    manifest.parent.mkdir(parents=True)
    existing.parent.mkdir(parents=True)
    manifest.write_text("project_tier:\n  - id: [broken\n", encoding="utf-8")
    existing.write_text("---\nid: existing\n---\n# Existing\n", encoding="utf-8")

    assert index_mcp_servers(root, rag_dir) == 0
    assert existing.exists()
    existing_text = existing.read_text(encoding="utf-8")
    assert "status: stale" in existing_text
    assert "index_status: error" in existing_text
    assert "source_error:" in existing_text
    error_entry = rag_dir / "mcp-servers" / "__manifest-error.md"
    assert error_entry.exists()
    assert "status: error" in error_entry.read_text(encoding="utf-8")


def test_index_mcp_servers_empty_manifest_preserves_existing_output(tmp_path):
    from src.lib.index._scanners_structural import index_mcp_servers

    root = tmp_path / "repo"
    rag_dir = tmp_path / "rag"
    manifest = root / "config" / "system" / "mcp_servers.yaml"
    existing = rag_dir / "mcp-servers" / "existing.md"
    manifest.parent.mkdir(parents=True)
    existing.parent.mkdir(parents=True)
    manifest.write_text("", encoding="utf-8")
    existing.write_text("---\nid: existing\n---\n# Existing\n", encoding="utf-8")

    assert index_mcp_servers(root, rag_dir) == 0
    assert existing.exists()
    existing_text = existing.read_text(encoding="utf-8")
    assert "status: stale" in existing_text
    assert "index_status: error" in existing_text
    assert (rag_dir / "mcp-servers" / "__manifest-error.md").exists()


def test_index_mcp_servers_schema_invalid_manifest_preserves_existing_output(tmp_path):
    from src.lib.index._scanners_structural import index_mcp_servers

    root = tmp_path / "repo"
    rag_dir = tmp_path / "rag"
    manifest = root / "config" / "system" / "mcp_servers.yaml"
    existing = rag_dir / "mcp-servers" / "existing.md"
    manifest.parent.mkdir(parents=True)
    existing.parent.mkdir(parents=True)
    manifest.write_text("project_tier:\n  id: augur-core\n", encoding="utf-8")
    existing.write_text("---\nid: existing\n---\n# Existing\n", encoding="utf-8")

    assert index_mcp_servers(root, rag_dir) == 0
    assert existing.exists()
    existing_text = existing.read_text(encoding="utf-8")
    assert "status: stale" in existing_text
    assert "index_status: error" in existing_text
    assert (rag_dir / "mcp-servers" / "__manifest-error.md").exists()


def test_index_mcp_servers_blank_id_marks_existing_output_stale(tmp_path):
    from src.lib.index._scanners_structural import index_mcp_servers

    root = tmp_path / "repo"
    rag_dir = tmp_path / "rag"
    manifest = root / "config" / "system" / "mcp_servers.yaml"
    existing = rag_dir / "mcp-servers" / "existing.md"
    manifest.parent.mkdir(parents=True)
    existing.parent.mkdir(parents=True)
    manifest.write_text(
        "project_tier:\n"
        "  - id: ''\n"
        "    command: python\n"
        "    args: []\n",
        encoding="utf-8",
    )
    existing.write_text(
        "---\nid: existing\nstatus: configured\n---\n# Existing\n",
        encoding="utf-8",
    )

    assert index_mcp_servers(root, rag_dir) == 0
    existing_text = existing.read_text(encoding="utf-8")
    assert "status: stale" in existing_text
    assert "index_status: error" in existing_text
    assert (rag_dir / "mcp-servers" / "__manifest-error.md").exists()


def test_index_mcp_servers_sanitized_filename_collisions_write_distinct_entries(tmp_path):
    from src.lib.index._scanners_structural import index_mcp_servers

    root = tmp_path / "repo"
    rag_dir = tmp_path / "rag"
    manifest = root / "config" / "system" / "mcp_servers.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        "project_tier:\n"
        "  - id: a/b\n"
        "    description: Slash ID\n"
        "    command: python\n"
        "    args: []\n"
        "  - id: a:b\n"
        "    description: Colon ID\n"
        "    command: python\n"
        "    args: []\n",
        encoding="utf-8",
    )

    assert index_mcp_servers(root, rag_dir) == 2
    entries = sorted((rag_dir / "mcp-servers").glob("*.md"))
    assert len(entries) == 2
    contents = [entry.read_text(encoding="utf-8") for entry in entries]
    assert any("id: a/b" in content for content in contents)
    assert any("id: a:b" in content for content in contents)


def test_index_mcp_servers_sanitized_suffix_collisions_write_distinct_entries(tmp_path):
    from src.lib.index._scanners_structural import index_mcp_servers

    root = tmp_path / "repo"
    rag_dir = tmp_path / "rag"
    manifest = root / "config" / "system" / "mcp_servers.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        "project_tier:\n"
        "  - id: a/b\n"
        "    command: python\n"
        "    args: []\n"
        "  - id: a:b\n"
        "    command: python\n"
        "    args: []\n"
        "  - id: a:b-2\n"
        "    command: python\n"
        "    args: []\n",
        encoding="utf-8",
    )

    assert index_mcp_servers(root, rag_dir) == 3
    entries = sorted((rag_dir / "mcp-servers").glob("*.md"))
    assert len(entries) == 3
    contents = [entry.read_text(encoding="utf-8") for entry in entries]
    assert any("id: a/b" in content for content in contents)
    assert any("id: a:b" in content for content in contents)
    assert any("id: a:b-2" in content for content in contents)


def test_unified_indexer_cli_category_vault_uses_vault_dir(tmp_path):
    script_path = _resolve_unified_indexer_script()
    root = tmp_path / "project"
    vault_dir = tmp_path / "vault"
    rag_dir = tmp_path / "rag"

    root.mkdir(parents=True)
    vault_dir.mkdir(parents=True)
    (root / "project-brain" / "notes").mkdir(parents=True)
    (root / "repo-only.md").write_text("repo file", encoding="utf-8")
    (root / "project-brain" / "notes" / "shared-note.md").write_text(
        "---\ntitle: Shared Note\n---\nshared",
        encoding="utf-8",
    )
    (vault_dir / "note.md").write_text("---\ntitle: Note\n---\nbody", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--category",
            "vault",
            "--root",
            str(root),
            "--rag-dir",
            str(rag_dir),
            "--vault-dir",
            str(vault_dir),
        ],
        capture_output=True,
        text=True,
        cwd=script_path.parents[3],
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "Indexed 1 vault entries" in result.stdout
    assert (rag_dir / "vault" / "private" / "note.md").exists()
    assert not (rag_dir / "vault" / "notes" / "shared" / "shared-note.md").exists()
    assert not (rag_dir / "vault" / "repo-only.md").exists()


def test_unified_indexer_cli_category_wiki_uses_wiki_dir(tmp_path):
    script_path = _resolve_unified_indexer_script()
    root = tmp_path / "project"
    wiki_dir = tmp_path / "wiki"
    rag_dir = tmp_path / "rag"

    root.mkdir(parents=True)
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "dev").mkdir(parents=True, exist_ok=True)
    (root / "project-brain" / "wiki" / "concepts").mkdir(parents=True)
    (root / "repo-only.md").write_text("repo file", encoding="utf-8")
    (root / "project-brain" / "wiki" / "concepts" / "shared-article.md").write_text(
        "---\ntitle: Shared Article\n---\nshared",
        encoding="utf-8",
    )
    (wiki_dir / "dev" / "architecture.md").write_text(
        "---\ntitle: Architecture\ntype: wiki-page\nhub: dev\n---\nbody",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--category",
            "wiki",
            "--root",
            str(root),
            "--rag-dir",
            str(rag_dir),
            "--wiki-dir",
            str(wiki_dir),
        ],
        capture_output=True,
        text=True,
        cwd=script_path.parents[3],
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "Indexed 1 wiki entries" in result.stdout
    assert (rag_dir / "wiki" / "private" / "dev" / "architecture.md").exists()
    assert not (rag_dir / "wiki" / "shared" / "concepts" / "shared-article.md").exists()
    assert not (rag_dir / "wiki" / "repo-only.md").exists()


def test_bulk_index_loads_canonical_unified_indexer():
    script_path = get_project_root() / "scripts" / "bulk_index.py"
    spec = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib.util; "
                f"p={str(script_path)!r}; "
                "spec=importlib.util.spec_from_file_location('bulk_index', p); "
                "mod=importlib.util.module_from_spec(spec); "
                "spec.loader.exec_module(mod); "
                "loaded=mod._load_unified_indexer(); "
                "print(hasattr(loaded, 'reindex_all'))"
            ),
        ],
        capture_output=True,
        text=True,
        cwd=script_path.parents[1],
        timeout=30,
    )

    assert spec.returncode == 0, spec.stderr
    assert spec.stdout.strip() == "True"


def test_index_skills_creates_pointer_files(tmp_path):
    from src.lib.index.unified_indexer import index_skills

    _make_skill(tmp_path, "career", "career",
        "---\nname: career\ndescription: Job tracking\n"
        "visibility: app\n---\n# Career Skill\n")

    rag_dir = tmp_path / "rag"
    with patch("src.lib.index._scanners_knowledge._discover_skill_dirs", return_value=_mock_discover(tmp_path)):
        index_skills(tmp_path, rag_dir)

    entry = rag_dir / "skills" / "career" / "external" / "career.md"
    assert entry.exists()
    content = entry.read_text()
    assert "type: skill" in content
    assert "hub: career" in content
    assert "source_path:" in content


def test_index_skills_extracts_description(tmp_path):
    from src.lib.index.unified_indexer import index_skills

    _make_skill(tmp_path, "ai", "rag",
        "---\nname: rag\ndescription: RAG indexing and search\n"
        "visibility: auto\n---\n# RAG\n")

    rag_dir = tmp_path / "rag"
    with patch("src.lib.index._scanners_knowledge._discover_skill_dirs", return_value=_mock_discover(tmp_path)):
        index_skills(tmp_path, rag_dir)

    entry = rag_dir / "skills" / "ai" / "external" / "rag.md"
    content = entry.read_text()
    assert "RAG indexing and search" in content


def test_discover_skill_dirs_skips_generated_client_duplicates(tmp_path, monkeypatch):
    from src.lib.index import _indexer_helpers

    canonical_skill = tmp_path / "project-brain" / "capabilities" / "skills" / "rag"
    canonical_skill.mkdir(parents=True)
    (canonical_skill / "SKILL.md").write_text(
        "---\nname: rag\nx-augur-hub: adaptive\n---\n# Canonical\n",
        encoding="utf-8",
    )

    generated_duplicate = tmp_path / ".opencode" / "skills" / "rag"
    generated_duplicate.mkdir(parents=True)
    (generated_duplicate / "SKILL.md").write_text(
        "---\nname: rag\nx-augur-hub: adaptive\n---\n# Generated Duplicate\n",
        encoding="utf-8",
    )

    unique_client_skill = tmp_path / ".opencode" / "skills" / "custom-helper"
    unique_client_skill.mkdir(parents=True)
    (unique_client_skill / "SKILL.md").write_text(
        "---\nname: custom-helper\nx-augur-hub: brain\n---\n# Unique Client Skill\n",
        encoding="utf-8",
    )

    class _Record:
        def __init__(self, hub, path, name):
            self.hub = hub
            self.path = path
            self.name = name

    monkeypatch.setattr(_indexer_helpers, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        "src.plugins.skill_discovery.discover_all_skills",
        lambda: [
            _Record("adaptive", canonical_skill, "rag"),
            _Record("adaptive", generated_duplicate, "rag"),
            _Record("brain", unique_client_skill, "custom-helper"),
        ],
    )

    discovered = _indexer_helpers._discover_skill_dirs(tmp_path)

    assert discovered == [
        ("adaptive", canonical_skill),
        ("brain", unique_client_skill),
    ]


def test_discover_skill_dirs_includes_global_external_records_for_project_root(tmp_path, monkeypatch):
    from src.lib.index import _indexer_helpers

    root = tmp_path / "project"
    root.mkdir()
    canonical_skill = root / "project-brain" / "capabilities" / "skills" / "rag"
    canonical_skill.mkdir(parents=True)
    (canonical_skill / "SKILL.md").write_text(
        "---\nname: rag\n---\n# RAG\n",
        encoding="utf-8",
    )

    global_skill = tmp_path / "home" / ".claude" / "skills" / "systematic-debugging"
    global_skill.mkdir(parents=True)
    (global_skill / "SKILL.md").write_text(
        "---\nname: systematic-debugging\ndescription: Debug systematically\n---\n# Debug\n",
        encoding="utf-8",
    )

    class _Record:
        def __init__(self, hub, path, name):
            self.hub = hub
            self.path = path
            self.name = name

    monkeypatch.setattr(_indexer_helpers, "get_project_root", lambda: root)
    monkeypatch.setattr(
        "src.plugins.skill_discovery.discover_all_skills",
        lambda: [
            _Record("brain", canonical_skill, "rag"),
            _Record("external", global_skill, "systematic-debugging"),
        ],
    )

    discovered = _indexer_helpers._discover_skill_dirs(root)

    assert ("brain", canonical_skill) in discovered
    assert ("external", global_skill) in discovered


def test_discover_skill_dirs_for_temp_root_includes_managed_vault_roots(tmp_path, monkeypatch):
    from src.lib.index import _indexer_helpers

    root = tmp_path / "project"
    root.mkdir()
    repo_skill = root / "project-brain" / "capabilities" / "skills" / "rag"
    repo_skill.mkdir(parents=True)
    (repo_skill / "SKILL.md").write_text(
        "---\nname: rag\n---\n# RAG\n",
        encoding="utf-8",
    )

    vault_skills_dir = tmp_path / "vault" / "skills"
    vault_skill = vault_skills_dir / "career-ops"
    vault_skill.mkdir(parents=True)
    (vault_skill / "SKILL.md").write_text(
        "---\nname: career-ops\n---\n# Career Ops\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(_indexer_helpers, "get_project_root", lambda: tmp_path / "live-project")
    monkeypatch.setattr(
        _indexer_helpers,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [root / "project-brain" / "capabilities" / "skills", vault_skills_dir],
    )
    monkeypatch.setattr(
        _indexer_helpers,
        "get_project_brain_skills_dir",
        lambda project_root=None: root / "project-brain" / "capabilities" / "skills",
    )
    monkeypatch.setattr(
        _indexer_helpers,
        "get_configured_vault_skills_dir",
        lambda project_root=None: vault_skills_dir,
    )
    monkeypatch.setattr(_indexer_helpers, "get_client_skill_dirs", lambda: {})
    monkeypatch.setattr(_indexer_helpers, "get_claude_plugin_skill_dirs", lambda: [])

    discovered = _indexer_helpers._discover_skill_dirs(root)

    # ADR-802 hub teardown: labels partition by source root and resolve to
    # "unknown" for temp fixture roots; the contract under test is inclusion.
    assert discovered == [
        ("unknown", repo_skill),
        ("unknown", vault_skill),
    ]


def test_discover_skill_dirs_ignores_stale_repo_root_managed_dir(tmp_path, monkeypatch):
    from src.lib.index import _indexer_helpers

    root = tmp_path / "project"
    stale_skill = root.joinpath("skills", "legacy")
    shared_skill = root / "project-brain" / "capabilities" / "skills" / "rag"
    for skill_dir, name in ((stale_skill, "legacy"), (shared_skill, "rag")):
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\nx-augur-hub: brain\n---\n# {name}\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(_indexer_helpers, "get_project_root", lambda: tmp_path / "live-project")
    monkeypatch.setattr(
        _indexer_helpers,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [root.joinpath("skills"), root / "project-brain" / "capabilities" / "skills"],
    )
    monkeypatch.setattr(
        _indexer_helpers,
        "get_project_brain_skills_dir",
        lambda project_root=None: root / "project-brain" / "capabilities" / "skills",
    )
    monkeypatch.setattr(
        _indexer_helpers,
        "get_configured_vault_skills_dir",
        lambda project_root=None: tmp_path / "vault" / "skills",
    )
    monkeypatch.setattr(_indexer_helpers, "get_vault_skills_dir", lambda: tmp_path / "vault" / "skills")
    monkeypatch.setattr(_indexer_helpers, "get_client_skill_dirs", lambda: {})
    monkeypatch.setattr(_indexer_helpers, "get_claude_plugin_skill_dirs", lambda: [])

    discovered = _indexer_helpers._discover_skill_dirs(root)

    # ADR-802 hub teardown: temp fixture roots resolve to "unknown".
    assert discovered == [("unknown", shared_skill)]


def test_index_skills_writes_client_metadata(tmp_path):
    from src.lib.index.unified_indexer import index_skills

    canonical_skill = tmp_path / "project-brain" / "capabilities" / "skills" / "rag"
    canonical_skill.mkdir(parents=True)
    (canonical_skill / "SKILL.md").write_text(
        "---\nname: rag\ndescription: Canonical skill\nx-augur-hub: adaptive\n---\n# Canonical\n",
        encoding="utf-8",
    )

    unique_client_skill = tmp_path / ".opencode" / "skills" / "custom-helper"
    unique_client_skill.mkdir(parents=True)
    (unique_client_skill / "SKILL.md").write_text(
        "---\nname: custom-helper\ndescription: Client-only skill\nx-augur-hub: brain\n---\n# Client Skill\n",
        encoding="utf-8",
    )

    rag_dir = tmp_path / "rag"
    with patch(
        "src.lib.index._scanners_knowledge._discover_skill_dirs",
        return_value=[
            ("adaptive", canonical_skill),
            ("brain", unique_client_skill),
        ],
    ):
        index_skills(tmp_path, rag_dir)

    canonical_entry = (rag_dir / "skills" / "adaptive" / "project-brain" / "rag.md").read_text(
        encoding="utf-8"
    )
    assert "skill_client: augur" in canonical_entry
    assert "skill_origin: canonical" in canonical_entry
    assert "source: project-brain" in canonical_entry

    client_entry = (rag_dir / "skills" / "brain" / "external-client" / "custom-helper.md").read_text(
        encoding="utf-8"
    )
    assert "skill_client: opencode" in client_entry
    assert "skill_origin: client-local" in client_entry
    assert "source: opencode-local" in client_entry


def test_index_skills_writes_global_client_metadata(tmp_path, monkeypatch):
    from src.lib.index import _indexer_helpers
    from src.lib.index.unified_indexer import index_skills

    root = tmp_path / "project"
    root.mkdir()
    codex_global = tmp_path / "home" / ".codex" / "skills"
    global_skill = codex_global / ".system" / "imagegen"
    global_skill.mkdir(parents=True)
    (global_skill / "SKILL.md").write_text(
        "---\nname: imagegen\ndescription: Generate bitmap assets\n---\n# Imagegen\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        _indexer_helpers,
        "get_client_skill_dirs",
        lambda: {"codex-global": codex_global},
    )

    rag_dir = tmp_path / "rag"
    with patch(
        "src.lib.index._scanners_knowledge._discover_skill_dirs",
        return_value=[("external", global_skill)],
    ):
        index_skills(root, rag_dir)

    entry = (rag_dir / "skills" / "external" / "external-client" / "imagegen.md").read_text(encoding="utf-8")
    assert "skill_client: codex" in entry
    assert "skill_origin: client-global" in entry
    assert "source: codex-global" in entry
    assert "ownership: external" in entry


def test_index_skills_preserves_discovery_record_ownership_for_vault_skill(tmp_path, monkeypatch):
    from src.lib.index.unified_indexer import index_skills

    root = tmp_path / "project"
    root.mkdir()
    vault_skill = tmp_path / "vault" / "skills" / "career-ops"
    vault_skill.mkdir(parents=True)
    (vault_skill / "SKILL.md").write_text(
        "---\nname: career-ops\ndescription: Vault skill\nx-augur-hub: career\n---\n# Vault Skill\n",
        encoding="utf-8",
    )

    class _Record:
        def __init__(self):
            self.hub = "career"
            self.path = vault_skill
            self.name = "career-ops"
            self.source = "vault"
            self.ownership = "user"
            self.source_root = "vault"
            self.client_sources = ("vault",)

    monkeypatch.setattr("src.plugins.skill_discovery.discover_all_skills", lambda: [_Record()])

    rag_dir = tmp_path / "rag"
    with patch(
        "src.lib.index._scanners_knowledge._discover_skill_dirs",
        return_value=[("career", vault_skill)],
    ):
        index_skills(root, rag_dir)

    entry = (rag_dir / "skills" / "career" / "vault" / "career-ops.md").read_text(encoding="utf-8")
    assert "source: vault" in entry
    assert "ownership: user" in entry
    assert "source_root: vault" in entry


def test_index_skills_fallback_vault_user_ownership_for_managed_root(tmp_path, monkeypatch):
    from src.lib.index import _indexer_helpers
    from src.lib.index.unified_indexer import index_skills

    root = tmp_path / "project"
    root.mkdir()
    vault_skills_dir = tmp_path / "vault" / "skills"
    vault_skill = vault_skills_dir / "career-ops"
    vault_skill.mkdir(parents=True)
    (vault_skill / "SKILL.md").write_text(
        "---\nname: career-ops\ndescription: Vault skill\nx-augur-hub: career\n---\n# Vault Skill\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        _indexer_helpers,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [root / "project-brain" / "capabilities" / "skills", vault_skills_dir],
        raising=False,
    )
    monkeypatch.setattr(
        _indexer_helpers,
        "get_configured_vault_skills_dir",
        lambda project_root=None: vault_skills_dir,
        raising=False,
    )
    monkeypatch.setattr("src.plugins.skill_discovery.discover_all_skills", lambda: [])

    rag_dir = tmp_path / "rag"
    with patch(
        "src.lib.index._scanners_knowledge._discover_skill_dirs",
        return_value=[("career", vault_skill)],
    ):
        index_skills(root, rag_dir)

    entry = (rag_dir / "skills" / "career" / "private-vault" / "career-ops.md").read_text(encoding="utf-8")
    assert "source: private-vault" in entry
    assert "ownership: user" in entry
    assert "source_root: private-vault" in entry


def test_index_skills_keeps_shared_and_private_duplicate_skills_distinct(tmp_path, monkeypatch):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index import _indexer_helpers
    from src.lib.index.unified_indexer import index_skills

    root = tmp_path / "project"
    stale_root_skill = root.joinpath("skills", "assistant")
    shared_skill = root / "project-brain" / "capabilities" / "skills" / "assistant"
    private_skill = tmp_path / "private-vault" / "skills" / "assistant"
    for skill_dir, description in (
        (stale_root_skill, "Stale root skill"),
        (shared_skill, "Shared skill"),
        (private_skill, "Private skill"),
    ):
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: assistant\ndescription: {description}\nx-augur-hub: brain\n---\n# Assistant\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        _indexer_helpers,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [root.joinpath("skills"), root / "project-brain" / "capabilities" / "skills", private_skill.parent],
        raising=False,
    )
    monkeypatch.setattr(
        _indexer_helpers,
        "get_project_brain_skills_dir",
        lambda project_root=None: root / "project-brain" / "capabilities" / "skills",
        raising=False,
    )
    monkeypatch.setattr(
        _indexer_helpers,
        "get_configured_vault_skills_dir",
        lambda project_root=None: private_skill.parent,
        raising=False,
    )
    monkeypatch.setattr("src.plugins.skill_discovery.discover_all_skills", lambda: [])

    rag_dir = tmp_path / "rag"
    count = index_skills(root, rag_dir)

    assert count == 2
    entries = [parse_frontmatter(path)[0] for path in sorted((rag_dir / "skills").rglob("*.md"))]
    assert {entry["id"] for entry in entries} == {
        "skill:project-brain:assistant",
        "skill:private-vault:assistant",
    }
    assert {entry["vault_scope"] for entry in entries} == {"shared", "private"}
    assert {entry["source_root"] for entry in entries} == {"project-brain", "private-vault"}
    entries_by_id = {entry["id"]: entry for entry in entries}
    assert entries_by_id["skill:project-brain:assistant"]["skill_clients"] == ["augur"]
    assert entries_by_id["skill:private-vault:assistant"]["skill_clients"] == ["vault"]
    assert not (rag_dir / "skills" / "unknown" / "repo" / "assistant.md").exists()
    assert (rag_dir / "skills" / "unknown" / "project-brain" / "assistant.md").is_file()
    assert (rag_dir / "skills" / "unknown" / "private-vault" / "assistant.md").is_file()


def test_index_skills_live_root_appends_managed_overlay_skills_after_discovery_without_stale_root(tmp_path, monkeypatch):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index import _indexer_helpers
    from src.lib.index.unified_indexer import index_skills

    root = tmp_path / "project"
    stale_root_skill = root.joinpath("skills", "assistant")
    shared_skill = root / "project-brain" / "capabilities" / "skills" / "assistant"
    private_skill = tmp_path / "private-vault" / "skills" / "assistant"
    for skill_dir, description in (
        (stale_root_skill, "Stale root skill"),
        (shared_skill, "Shared skill"),
        (private_skill, "Private skill"),
    ):
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: assistant\ndescription: {description}\nx-augur-hub: brain\n---\n# Assistant\n",
            encoding="utf-8",
        )

    class _Record:
        def __init__(self):
            self.hub = "brain"
            self.path = stale_root_skill
            self.name = "assistant"
            self.source = "augur"
            self.ownership = "augur"
            self.source_root = "repo"
            self.client_sources = ("augur", "codex-local", "gemini-local")

    monkeypatch.setattr(_indexer_helpers, "get_project_root", lambda: root)
    monkeypatch.setattr(
        _indexer_helpers,
        "get_managed_skill_source_dirs",
        lambda project_root=None: [root.joinpath("skills"), root / "project-brain" / "capabilities" / "skills", private_skill.parent],
        raising=False,
    )
    monkeypatch.setattr(
        _indexer_helpers,
        "get_project_brain_skills_dir",
        lambda project_root=None: root / "project-brain" / "capabilities" / "skills",
        raising=False,
    )
    monkeypatch.setattr(
        _indexer_helpers,
        "get_configured_vault_skills_dir",
        lambda project_root=None: private_skill.parent,
        raising=False,
    )
    monkeypatch.setattr("src.plugins.skill_discovery.discover_all_skills", lambda: [_Record()])

    rag_dir = tmp_path / "rag"
    count = index_skills(root, rag_dir)

    assert count == 2
    entries = [parse_frontmatter(path)[0] for path in sorted((rag_dir / "skills").rglob("*.md"))]
    assert {entry["id"] for entry in entries} == {
        "skill:project-brain:assistant",
        "skill:private-vault:assistant",
    }
    entries_by_id = {entry["id"]: entry for entry in entries}
    assert entries_by_id["skill:project-brain:assistant"]["skill_clients"] == ["augur"]
    assert entries_by_id["skill:private-vault:assistant"]["skill_clients"] == ["vault"]
    for entry in entries:
        assert "shared" not in entry["skill_clients"]
        assert "private" not in entry["skill_clients"]
    assert not (rag_dir / "skills" / "unknown" / "repo" / "assistant.md").exists()
    assert (rag_dir / "skills" / "unknown" / "project-brain" / "assistant.md").is_file()
    assert (rag_dir / "skills" / "unknown" / "private-vault" / "assistant.md").is_file()


# ---------------------------------------------------------------------------
# ADR scanner tests
# ---------------------------------------------------------------------------


def _make_adr(tmp_path, name, content):
    """Helper: create an ADR file."""
    adr_dir = tmp_path / "docs" / "decisions"
    adr_dir.mkdir(parents=True, exist_ok=True)
    (adr_dir / f"{name}.md").write_text(content)


def test_index_adrs_creates_pointer_files(tmp_path):
    from src.lib.index.unified_indexer import index_adrs

    _make_adr(tmp_path, "ADR-004-markdown-rag",
        "---\nstatus: Implemented\ndate: '2026-01-15'\nhub: null\n"
        "tags:\n  - rag\n---\n# ADR-004: Markdown RAG\n\nDecision text.\n")

    rag_dir = tmp_path / "rag"
    index_adrs(tmp_path, rag_dir)

    entry = rag_dir / "adrs" / "adr-004-markdown-rag.md"
    assert entry.exists()
    content = entry.read_text()
    assert "type: adr" in content
    assert "status: Implemented" in content


def test_index_adrs_includes_archived_ledger_records(tmp_path, monkeypatch):
    from src.lib.index.unified_indexer import index_adrs
    from src.lib.adr_utils import archive_eligible_adrs
    from src.lib.frontmatter_utils import write_frontmatter

    adr_dir = tmp_path / "adrs"
    adr_dir.mkdir()
    write_frontmatter(
        adr_dir / "ADR-055-archived-rag.md",
        {"status": "Implemented", "date": "2026-04-19", "hub": "brain"},
        "# ADR-055: Archived RAG\n\n## Context\n\nArchived RAG decision body.\n",
    )
    archive_eligible_adrs(adr_dir, range_size=100)

    import src.lib.adr_utils as adr_utils

    monkeypatch.setattr(adr_utils, "get_adr_dir", lambda: adr_dir)

    rag_dir = tmp_path / "rag"
    count = index_adrs(tmp_path, rag_dir)

    assert count == 1
    entry = rag_dir / "adrs" / "adr-055-archived-rag.md"
    content = entry.read_text(encoding="utf-8")
    assert "type: adr" in content
    assert "archived: true" in content
    assert "source_path: archive://ADR-055" in content
    # ADR-642: index_path now points at the central adrs-index.json.
    assert "adrs-index.json" in content
    assert "archive_member: ADR-055-archived-rag.md" in content


def test_index_adrs_includes_live_central_index_records(tmp_path, monkeypatch):
    """ADR-642: live entries in the central JSON index get indexed with index:// path."""
    from src.lib.index.unified_indexer import index_adrs
    from src.lib.adr_utils import upsert_adr_entry

    adr_dir = tmp_path / "adrs"
    adr_dir.mkdir()
    upsert_adr_entry(
        adr_dir,
        {
            "adr_number": "ADR-099",
            "title": "Live Central Entry",
            "state": "live",
            "status": "Proposed",
            "date": "2026-05-10",
            "deciders": [],
            "related": [],
            "hub": "dev",
            "tags": ["live"],
            "decision_summary": "Live entry indexed from JSON.",
            "status_notes": "",
            "impact": {
                "paths_renamed": [],
                "apis_changed": [],
                "patterns_deprecated": [],
                "files_affected": [],
            },
            "spec_file": None,
            "plan_file": None,
            "superseded_by": None,
        },
    )

    import src.lib.adr_utils as adr_utils

    monkeypatch.setattr(adr_utils, "get_adr_dir", lambda: adr_dir)

    rag_dir = tmp_path / "rag"
    count = index_adrs(tmp_path, rag_dir)

    assert count == 1
    entry = rag_dir / "adrs" / "adr-099.md"
    content = entry.read_text(encoding="utf-8")
    assert "type: adr" in content
    assert "source_path: index://ADR-099" in content
    assert "adrs-index.json" in content
    assert "archived: false" in content
    assert "Live entry indexed from JSON." in content


def test_index_wiki_creates_pointer_files(tmp_path):
    from src.lib.index.unified_indexer import index_wiki

    vault_dir = tmp_path / "vault"
    wiki_dir = vault_dir / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / "dev").mkdir(parents=True, exist_ok=True)
    (wiki_dir / "dev" / "architecture.md").write_text(
        "---\ntitle: Architecture\ntype: wiki-page\nhub: dev\nmentors: '[[Ada Lovelace|Ada]]'\n---\n"
        "# Architecture\n\nCompiled knowledge.\n",
        encoding="utf-8",
    )

    rag_dir = tmp_path / "rag"
    with patch("src.config.paths.get_vault_dir", return_value=vault_dir):
        count = index_wiki(wiki_dir, rag_dir)

    assert count == 1
    entry = rag_dir / "wiki" / "private" / "dev" / "architecture.md"
    assert entry.exists()
    content = entry.read_text(encoding="utf-8")
    assert "type: wiki" in content
    assert f"source_path: {wiki_dir / 'dev' / 'architecture.md'}" in content
    assert "relationships:" in content
    assert "Ada Lovelace" in content


def test_index_wiki_scans_shared_and_private_duplicates_with_distinct_ids(tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index.unified_indexer import index_wiki

    shared_wiki = tmp_path / "project" / "project-brain" / "wiki"
    private_wiki = tmp_path / "private-vault" / "wiki"
    (shared_wiki / "concepts").mkdir(parents=True)
    (private_wiki / "concepts").mkdir(parents=True)
    (shared_wiki / "concepts" / "agent-memory.md").write_text(
        "---\ntitle: Agent Memory\n---\nShared article\n",
        encoding="utf-8",
    )
    (private_wiki / "concepts" / "agent-memory.md").write_text(
        "---\ntitle: Agent Memory\n---\nPrivate article\n",
        encoding="utf-8",
    )

    rag_dir = tmp_path / "rag"
    count = index_wiki(private_wiki, rag_dir, shared_wiki_dir=shared_wiki)

    assert count == 2
    entries = [parse_frontmatter(path)[0] for path in sorted((rag_dir / "wiki").rglob("*.md"))]
    assert {entry["id"] for entry in entries} == {
        "wiki:shared:concepts/agent-memory",
        "wiki:private:concepts/agent-memory",
    }
    assert {entry["vault_scope"] for entry in entries} == {"shared", "private"}
    assert {entry["promotion_state"] for entry in entries} == {"integrated", "private"}
    assert (rag_dir / "wiki" / "shared" / "concepts" / "agent-memory.md").is_file()
    assert (rag_dir / "wiki" / "private" / "concepts" / "agent-memory.md").is_file()


def test_index_document_sources_indexes_docs_desktop_downloads(monkeypatch, tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index import unified_indexer
    from src.lib.index.document_sources import DocumentSource

    docs = tmp_path / "Au-docs"
    desktop = tmp_path / "Desktop"
    downloads = tmp_path / "Downloads"
    rag = tmp_path / "rag"
    for root in (docs, desktop, downloads):
        root.mkdir()
    (docs / "career").mkdir()
    (docs / "career" / "resume.pdf").write_bytes(b"%PDF-1.4")
    (desktop / "loose.txt").write_text("desktop note", encoding="utf-8")
    (downloads / "invoice.pdf").write_bytes(b"%PDF-1.4")

    def fake_extract(path: Path) -> dict[str, object]:
        return {
            "format": path.suffix.lstrip("."),
            "size_bytes": path.stat().st_size,
            "created": "2026-05-24T00:00:00+00:00",
            "body": f"body for {path.name}",
            "document_title": path.stem,
            "document_kind": "document",
            "document_summary": f"summary for {path.name}",
            "document_key_insights": [],
            "document_sections": [],
            "document_extraction_method": "test",
            "document_visual_structure_used": False,
            "document_understanding_version": "v2",
            "document_action_candidates": [],
            "document_extraction_confidence": "high",
            "document_low_signal_warnings": [],
            "document_llm_assisted": False,
        }

    monkeypatch.setattr(unified_indexer, "_extract_document", fake_extract)
    monkeypatch.setattr("src.config.paths.get_runtime_dir", lambda: tmp_path / "runtime")

    count = unified_indexer.index_document_sources(
        [
            DocumentSource("documents", "Au-docs", docs, preserve_legacy_output=True),
            DocumentSource("desktop", "Desktop", desktop),
            DocumentSource("downloads", "Downloads", downloads),
        ],
        rag,
    )

    assert count == 3
    legacy_entry = rag / "documents" / "career" / "resume.md"
    assert legacy_entry.exists()
    legacy_meta, _ = parse_frontmatter(legacy_entry)
    assert legacy_meta["hub"] == "career"
    assert legacy_meta["source_root"] == "documents"
    assert legacy_meta["source_root_name"] == "Au-docs"
    assert legacy_meta["source_relative_path"] == "career/resume.pdf"
    assert legacy_meta["file_ext"] == "pdf"
    desktop_entry = rag / "documents" / "_sources" / "desktop" / "loose.md"
    downloads_entry = rag / "documents" / "_sources" / "downloads" / "invoice.md"
    assert desktop_entry.exists()
    assert downloads_entry.exists()
    desktop_meta, _ = parse_frontmatter(desktop_entry)
    assert desktop_meta["source_root"] == "desktop"
    assert desktop_meta["source_root_name"] == "Desktop"
    assert desktop_meta["source_root_path"] == str(desktop.resolve())
    assert desktop_meta["source_relative_path"] == "loose.txt"
    assert desktop_meta["file_ext"] == "txt"
    assert desktop_meta["hub"] == "desktop"


def test_index_document_sources_writes_media_stub_without_transcribing(monkeypatch, tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index import unified_indexer
    from src.lib.index.document_sources import DocumentSource

    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    audio = downloads / "meeting.m4a"
    video = downloads / "demo.mp4"
    image = downloads / "scan.png"
    for path in (audio, video, image):
        path.write_bytes(b"media")

    def unexpected_extract(path: Path):
        raise AssertionError(f"nightly index should not extract media: {path}")

    monkeypatch.setattr(unified_indexer, "_extract_document", unexpected_extract)
    monkeypatch.setattr("src.config.paths.get_runtime_dir", lambda: tmp_path / "runtime")

    count = unified_indexer.index_document_sources(
        [DocumentSource("downloads", "Downloads", downloads)],
        tmp_path / "rag",
    )

    # Media exclusion (01ff47b0e): media files produce NO documents-category
    # entry; the property that survives is that indexing never extracts them.
    assert count == 0
    source_dir = tmp_path / "rag" / "documents" / "_sources" / "downloads"
    assert not source_dir.exists() or not list(source_dir.glob("*.md"))


def test_index_document_sources_skips_symlink_candidates(monkeypatch, tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index import unified_indexer
    from src.lib.index.document_sources import DocumentSource

    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    report = downloads / "report.pdf"
    audio = downloads / "meeting.m4a"
    report.write_bytes(b"%PDF-1.4")
    audio.write_bytes(b"audio")
    (downloads / "report-link").symlink_to(report)
    (downloads / "meeting-link").symlink_to(audio)

    extracted: list[str] = []

    def fake_extract(path: Path) -> dict[str, object]:
        extracted.append(path.name)
        return {
            "format": path.suffix.lstrip("."),
            "size_bytes": path.stat().st_size,
            "created": "2026-05-24T00:00:00+00:00",
            "body": f"body for {path.name}",
        }

    monkeypatch.setattr(unified_indexer, "_extract_document", fake_extract)
    monkeypatch.setattr("src.config.paths.get_runtime_dir", lambda: tmp_path / "runtime")

    count = unified_indexer.index_document_sources(
        [DocumentSource("downloads", "Downloads", downloads)],
        tmp_path / "rag",
    )

    # Media exclusion (01ff47b0e): the audio file gets no entry; symlinks are
    # still skipped, so only the real report is extracted and indexed.
    assert count == 1
    assert extracted == ["report.pdf"]
    source_entries = sorted(
        (tmp_path / "rag" / "documents" / "_sources" / "downloads").glob("*.md"),
    )
    assert [entry.name for entry in source_entries] == ["report.md"]


def test_index_document_sources_escapes_legacy_reserved_sources_namespace(monkeypatch, tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index import unified_indexer
    from src.lib.index.document_sources import DocumentSource

    docs = tmp_path / "Au-docs"
    desktop = tmp_path / "Desktop"
    legacy_file = docs / "_sources" / "desktop" / "loose.pdf"
    desktop_file = desktop / "loose.txt"
    legacy_file.parent.mkdir(parents=True)
    desktop.mkdir()
    legacy_file.write_bytes(b"%PDF-1.4")
    desktop_file.write_text("desktop note", encoding="utf-8")

    def fake_extract(path: Path) -> dict[str, object]:
        return {
            "format": path.suffix.lstrip("."),
            "size_bytes": path.stat().st_size,
            "created": "2026-05-24T00:00:00+00:00",
            "body": f"body for {path.name}",
        }

    monkeypatch.setattr(unified_indexer, "_extract_document", fake_extract)
    monkeypatch.setattr("src.config.paths.get_runtime_dir", lambda: tmp_path / "runtime")

    count = unified_indexer.index_document_sources(
        [
            DocumentSource("documents", "Au-docs", docs, preserve_legacy_output=True),
            DocumentSource("desktop", "Desktop", desktop),
        ],
        tmp_path / "rag",
    )

    assert count == 2
    legacy_entry = tmp_path / "rag" / "documents" / "_legacy_sources" / "desktop" / "loose.md"
    desktop_entry = tmp_path / "rag" / "documents" / "_sources" / "desktop" / "loose.md"
    assert legacy_entry.exists()
    assert desktop_entry.exists()
    legacy_meta, _ = parse_frontmatter(legacy_entry)
    desktop_meta, _ = parse_frontmatter(desktop_entry)
    assert legacy_meta["source_root"] == "documents"
    assert desktop_meta["source_root"] == "desktop"
    assert legacy_meta["source_root_path"] == str(docs.resolve())
    assert desktop_meta["source_root_path"] == str(desktop.resolve())
    assert legacy_meta["source_path"] != desktop_meta["source_path"]


def test_index_documents_legacy_reindex_preserves_source_entries(monkeypatch, tmp_path):
    from src.lib.index import unified_indexer
    from src.lib.index.unified_indexer import index_documents

    documents_dir = tmp_path / "Au-docs"
    (documents_dir / "brain").mkdir(parents=True, exist_ok=True)
    (documents_dir / "brain" / "live.pdf").write_bytes(b"%PDF-1.4")

    desktop_file = tmp_path / "Desktop" / "loose.txt"
    desktop_file.parent.mkdir()
    desktop_file.write_text("desktop note", encoding="utf-8")

    rag_dir = tmp_path / "rag"
    desktop_entry = rag_dir / "documents" / "_sources" / "desktop" / "loose.md"
    desktop_entry.parent.mkdir(parents=True, exist_ok=True)
    desktop_entry.write_text(
        "---\n"
        "type: document\n"
        f"source_path: {desktop_file.resolve()}\n"
        "source_root: desktop\n"
        "---\n"
        "desktop body\n",
        encoding="utf-8",
    )

    def fake_extract(path: Path) -> dict[str, object]:
        return {
            "format": path.suffix.lstrip("."),
            "size_bytes": path.stat().st_size,
            "created": "2026-05-24T00:00:00+00:00",
            "body": "body",
        }

    monkeypatch.setattr(unified_indexer, "_extract_document", fake_extract)
    monkeypatch.setattr("src.config.paths.get_runtime_dir", lambda: tmp_path / "runtime")

    count = index_documents(documents_dir, rag_dir)

    assert count == 1
    assert (rag_dir / "documents" / "brain" / "live.md").exists()
    assert desktop_entry.exists()


def test_index_documents_indexes_unsupported_media_assets_as_stubs(tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index.unified_indexer import index_documents

    documents_dir = tmp_path / "documents"
    (documents_dir / "brain").mkdir(parents=True, exist_ok=True)
    (documents_dir / "brain" / "keep.md").write_text("# Keep\n\nbody", encoding="utf-8")
    (documents_dir / "brain" / "skip.mp4").write_bytes(b"binary video")

    rag_dir = tmp_path / "rag"
    runtime_dir = tmp_path / "runtime"

    seen: list[str] = []

    def _fake_extract(path: Path) -> dict[str, str | int]:
        seen.append(Path(path).name)
        return {
            "format": "md",
            "size_bytes": 10,
            "created": "2026-04-12T00:00:00+00:00",
            "body": "body",
        }

    with patch(
        "src.lib.index.unified_indexer._extract_document",
        side_effect=_fake_extract,
    ), patch(
        "src.config.paths.get_runtime_dir",
        return_value=runtime_dir,
    ):
        count = index_documents(documents_dir, rag_dir)

    # Media exclusion (01ff47b0e): the video gets no entry; the markdown
    # sibling is still extracted and indexed normally.
    assert count == 1
    assert seen == ["keep.md"]
    assert (rag_dir / "documents" / "brain" / "keep.md").exists()
    assert not (rag_dir / "documents" / "brain" / "skip.md").exists()


def test_index_documents_indexes_raster_images_as_media_stubs(monkeypatch, tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index import unified_indexer
    from src.lib.index.unified_indexer import index_documents

    documents_dir = tmp_path / "documents"
    (documents_dir / "brain").mkdir(parents=True, exist_ok=True)
    (documents_dir / "brain" / "keep.pdf").write_bytes(b"%PDF-1.4")
    (documents_dir / "brain" / "scan.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    rag_dir = tmp_path / "rag"

    def fake_extract(path: Path) -> dict[str, object]:
        return {
            "format": Path(path).suffix.lstrip("."),
            "size_bytes": path.stat().st_size,
            "created": "2026-04-12T00:00:00+00:00",
            "body": "body",
        }

    monkeypatch.setattr(unified_indexer, "_extract_document", fake_extract)
    monkeypatch.setattr("src.config.paths.get_runtime_dir", lambda: tmp_path / "runtime")

    count = index_documents(documents_dir, rag_dir)

    # Media exclusion (01ff47b0e): the raster image gets no entry; the PDF
    # sibling is still indexed.
    assert count == 1
    assert (rag_dir / "documents" / "brain" / "keep.md").exists()
    assert not (rag_dir / "documents" / "brain" / "scan.md").exists()


def test_index_documents_prunes_existing_entries_for_deleted_media(tmp_path):
    from src.lib.index.unified_indexer import index_documents

    documents_dir = tmp_path / "documents"
    (documents_dir / "brain").mkdir(parents=True, exist_ok=True)
    deleted_source = documents_dir / "brain" / "deleted.mp4"

    rag_dir = tmp_path / "rag"
    stale_entry = rag_dir / "documents" / "brain" / "deleted.md"
    stale_entry.parent.mkdir(parents=True, exist_ok=True)
    stale_entry.write_text(
        "---\n"
        f"source_path: {deleted_source}\n"
        "type: document\n"
        "---\n"
        "stale body\n",
        encoding="utf-8",
    )

    with patch("src.config.paths.get_runtime_dir", return_value=tmp_path / "runtime"):
        count = index_documents(documents_dir, rag_dir)

    assert count == 0
    assert not stale_entry.exists()


def test_index_documents_drops_legacy_wiki_compile_metadata_on_rewrite(tmp_path):
    from src.lib.index.unified_indexer import index_documents
    from src.lib.frontmatter_utils import parse_frontmatter

    documents_dir = tmp_path / "documents"
    (documents_dir / "brain").mkdir(parents=True, exist_ok=True)
    source_file = documents_dir / "brain" / "live.md"
    source_file.write_text("# Live\n\n" + ("content " * 60), encoding="utf-8")

    rag_dir = tmp_path / "rag"
    entry = rag_dir / "documents" / "brain" / "live.md"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(
        "---\n"
        f"source_path: {source_file.resolve()}\n"
        "type: document\n"
        "wiki_compile_status: compiled\n"
        "wiki_compiled_checksum: old-checksum\n"
        "wiki_compiled_at: 2026-04-14T09:00:00+00:00\n"
        "wiki_targets:\n"
        "  - brain/live\n"
        "manual_related:\n"
        "  - brain/reference\n"
        "---\n"
        "old body\n",
        encoding="utf-8",
    )

    def _fake_extract(path: Path) -> dict[str, str | int]:
        return {
            "format": "md",
            "size_bytes": len(path.read_bytes()),
            "created": "2026-04-14T10:00:00+00:00",
            "body": "fresh body",
        }

    with patch(
        "src.lib.index.unified_indexer._extract_document",
        side_effect=_fake_extract,
    ), patch(
        "src.config.paths.get_runtime_dir",
        return_value=tmp_path / "runtime",
    ):
        count = index_documents(documents_dir, rag_dir)

    assert count == 1
    meta, _ = parse_frontmatter(entry)
    assert meta["manual_related"] == ["brain/reference"]
    assert "wiki_compile_status" not in meta
    assert "wiki_compiled_checksum" not in meta
    assert "wiki_compiled_at" not in meta
    assert "wiki_targets" not in meta


def test_index_documents_scrubs_legacy_wiki_compile_metadata_on_cached_hit(tmp_path, monkeypatch):
    from src.lib.index import unified_indexer
    from src.lib.index.unified_indexer import index_documents
    from src.lib.frontmatter_utils import parse_frontmatter

    documents_dir = tmp_path / "documents"
    (documents_dir / "brain").mkdir(parents=True, exist_ok=True)
    source_file = documents_dir / "brain" / "live.md"
    source_file.write_text("# Live\n\ncached body", encoding="utf-8")
    source_mtime = source_file.stat().st_mtime

    rag_dir = tmp_path / "rag"
    entry = rag_dir / "documents" / "brain" / "live.md"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(
        "---\n"
        f"source_path: {source_file.resolve()}\n"
        "type: document\n"
        "manual_related:\n"
        "  - brain/reference\n"
        "wiki_compile_status: compiled\n"
        "wiki_compiled_checksum: old-checksum\n"
        "wiki_compiled_at: 2026-04-14T09:00:00+00:00\n"
        "wiki_targets:\n"
        "  - brain/live\n"
        "document_action_candidates: []\n"
        "document_extraction_confidence: medium\n"
        "document_low_signal_warnings: []\n"
        "document_llm_assisted: false\n"
        "document_understanding_version: v2\n"
        "---\n"
        "cached body\n",
        encoding="utf-8",
    )

    def _load_cached_mtime():
        return {str(source_file.resolve()): source_mtime}

    def _unexpected_extract(*_args, **_kwargs):
        raise AssertionError("unexpected extraction")

    monkeypatch.setattr(unified_indexer, "_load_mtime_cache", _load_cached_mtime)
    monkeypatch.setattr(unified_indexer, "_save_mtime_cache", lambda cache: None)
    monkeypatch.setattr(unified_indexer, "_extract_document", _unexpected_extract)

    count = index_documents(documents_dir, rag_dir)

    assert count == 1
    meta, body = parse_frontmatter(entry)
    assert meta["manual_related"] == ["brain/reference"]
    assert "wiki_compile_status" not in meta
    assert "wiki_compiled_checksum" not in meta
    assert "wiki_compiled_at" not in meta
    assert "wiki_targets" not in meta
    assert body.strip() == "cached body"


def test_index_documents_persists_structured_document_metadata(monkeypatch, tmp_path):
    from src.lib.index import unified_indexer
    from src.lib.index.unified_indexer import index_documents

    documents_dir = tmp_path / "documents"
    rag_dir = tmp_path / "rag"
    pdf = documents_dir / "sources" / "guide.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4 fake")

    def _fake_extract(path: Path) -> dict[str, str | int | list[str] | bool | None]:
        return {
            "format": "pdf",
            "size_bytes": 123,
            "created": "2026-04-15T00:00:00+00:00",
            "body": "Skills are the knowledge layer on top of MCP.",
            "extraction_error": None,
            "document_title": "The Complete Guide to Building Skills for Claude",
            "document_kind": "pdf",
            "document_summary": "Skills are the knowledge layer on top of MCP.",
            "document_key_insights": [
                "Skills are the knowledge layer on top of MCP.",
                "Progressive disclosure minimizes token usage.",
            ],
            "document_sections": ["Introduction", "Fundamentals"],
            "document_extraction_method": "pymupdf",
            "document_visual_structure_used": False,
            "document_understanding_version": "v1",
        }

    monkeypatch.setattr(unified_indexer, "_extract_document", _fake_extract)
    monkeypatch.setattr("src.config.paths.get_runtime_dir", lambda: tmp_path / "runtime")

    count = index_documents(documents_dir, rag_dir)

    assert count == 1
    entry = rag_dir / "documents" / "sources" / "guide.md"
    text = entry.read_text(encoding="utf-8")
    assert "document_title: The Complete Guide to Building Skills for Claude" in text
    assert "document_kind: pdf" in text
    assert "document_extraction_method: pymupdf" in text
    # The understood title becomes the display title (Browse shows it, not the stem).
    assert "title: The Complete Guide to Building Skills for Claude" in text


def test_backfill_document_title_uses_frontmatter_body():
    from src.lib.index.unified_indexer import _backfill_document_title

    meta = {"document_title": "L28", "name": "L28"}
    body = "---\ntitle: L28 — Pitch Deck Review\n---\n\n# L28 — Pitch Deck Review\n\nbody"
    _backfill_document_title(meta, body, "L28")
    assert meta["title"] == "L28 — Pitch Deck Review"
    assert meta["document_title"] == "L28 — Pitch Deck Review"


def test_backfill_document_title_keeps_existing_title():
    from src.lib.index.unified_indexer import _backfill_document_title

    meta = {"title": "Catalog Title", "document_title": "L28"}
    _backfill_document_title(meta, "# Heading Text\n\nbody", "L28")
    assert meta["title"] == "Catalog Title"


def test_backfill_document_title_noop_when_only_stem_available():
    from src.lib.index.unified_indexer import _backfill_document_title

    meta = {"document_title": "doc"}
    _backfill_document_title(meta, "doc\n", "doc")
    assert "title" not in meta


def test_backfill_document_title_replaces_noise_title():
    from src.lib.index.unified_indexer import _backfill_document_title

    meta = {"title": "<!-- Slide number: 1 -->", "document_title": "<!-- Slide number: 1 -->"}
    body = "<!-- Slide number: 1 -->\n\nAugur Investor Deck Overview\n\nbody"
    _backfill_document_title(meta, body, "augur-deck-pc-ai-final")
    assert meta["title"] == "Augur Investor Deck Overview"


def test_backfill_document_title_drops_unfixable_noise_title():
    from src.lib.index.unified_indexer import _backfill_document_title

    meta = {"title": "<!-- Slide number: 1 -->", "document_title": "<!-- Slide number: 1 -->"}
    _backfill_document_title(meta, "<!-- Slide number: 1 -->\n", "deck")
    assert "title" not in meta
    assert meta["document_title"] == "deck"


def test_index_documents_keeps_same_stem_collisions_separate(monkeypatch, tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index import unified_indexer
    from src.lib.index.unified_indexer import index_documents

    documents_dir = tmp_path / "documents"
    rag_dir = tmp_path / "rag"
    folder = documents_dir / "career" / "resumes"
    folder.mkdir(parents=True, exist_ok=True)
    pdf = folder / "offer.pdf"
    docx = folder / "offer.docx"
    markdown = folder / "offer.md"
    pdf.write_bytes(b"%PDF-1.4 fake")
    docx.write_bytes(b"PK fake docx")
    markdown.write_text("# Offer\n\nmarkdown body", encoding="utf-8")

    def _fake_extract(path: Path) -> dict[str, str | int | list[str] | bool | None]:
        return {
            "format": path.suffix.lstrip("."),
            "size_bytes": path.stat().st_size,
            "created": None,
            "body": f"Extracted body for {path.name}",
            "extraction_error": None,
            "document_title": path.name,
            "document_kind": path.suffix.lstrip("."),
            "document_summary": f"Summary for {path.name}",
            "document_key_insights": [],
            "document_sections": [],
            "document_extraction_method": "test",
            "document_visual_structure_used": False,
            "document_understanding_version": "v1",
        }

    monkeypatch.setattr(unified_indexer, "_extract_document", _fake_extract)
    monkeypatch.setattr("src.config.paths.get_runtime_dir", lambda: tmp_path / "runtime")

    count = index_documents(documents_dir, rag_dir)

    assert count == 3
    entries = sorted((rag_dir / "documents" / "career" / "resumes").glob("offer*.md"))
    assert len(entries) == 3
    source_paths = {
        Path(str(parse_frontmatter(entry)[0]["source_path"])).name
        for entry in entries
    }
    assert source_paths == {"offer.pdf", "offer.docx", "offer.md"}


def test_index_documents_stale_same_stem_cache_does_not_delete_current_export(monkeypatch, tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index import unified_indexer
    from src.lib.index.unified_indexer import index_documents

    documents_dir = tmp_path / "documents"
    rag_dir = tmp_path / "rag"
    folder = documents_dir / "venture" / "presentations"
    folder.mkdir(parents=True, exist_ok=True)
    current_pdf = folder / "deck.pdf"
    stale_pptx = folder / "deck.pptx"
    current_pdf.write_bytes(b"%PDF-1.4 fake")

    stale_entry = rag_dir / "documents" / "venture" / "presentations" / "deck__pptx-old.md"
    stale_entry.parent.mkdir(parents=True, exist_ok=True)
    stale_entry.write_text(
        f"---\ntype: document\nsource_path: {stale_pptx.resolve()}\n---\nstale",
        encoding="utf-8",
    )

    def _fake_extract(path: Path) -> dict[str, str | int | list[str] | bool | None]:
        return {
            "format": path.suffix.lstrip("."),
            "size_bytes": path.stat().st_size,
            "created": None,
            "body": f"Extracted body for {path.name}",
            "extraction_error": None,
            "document_title": path.name,
            "document_kind": path.suffix.lstrip("."),
            "document_summary": f"Summary for {path.name}",
            "document_key_insights": [],
            "document_sections": [],
            "document_extraction_method": "test",
            "document_visual_structure_used": False,
            "document_understanding_version": "v1",
        }

    monkeypatch.setattr(unified_indexer, "_extract_document", _fake_extract)
    monkeypatch.setattr(unified_indexer, "_load_mtime_cache", lambda: {str(stale_pptx.resolve()): 1.0})
    monkeypatch.setattr(unified_indexer, "_save_mtime_cache", lambda _cache: None)
    monkeypatch.setattr("src.config.paths.get_runtime_dir", lambda: tmp_path / "runtime")

    count = index_documents(documents_dir, rag_dir)

    current_entry = rag_dir / "documents" / "venture" / "presentations" / "deck.md"
    assert count == 1
    assert current_entry.exists()
    assert not stale_entry.exists()
    meta, _ = parse_frontmatter(current_entry)
    assert Path(str(meta["source_path"])).name == "deck.pdf"


def test_reindex_all_prunes_stale_document_chunks(tmp_path):
    from src.lib.index.unified_indexer import reindex_all

    rag_dir = tmp_path / "rag"
    stale_chunk = rag_dir / "chunks" / "documents" / "old-doc" / "stale.md"
    stale_chunk.parent.mkdir(parents=True, exist_ok=True)
    stale_chunk.write_text("stale", encoding="utf-8")

    documents_dir = tmp_path / "documents"
    (documents_dir / "brain").mkdir(parents=True, exist_ok=True)
    (documents_dir / "brain" / "fresh.md").write_text(
        "# Fresh\n\n" + ("content " * 200),
        encoding="utf-8",
    )

    with patch("src.config.paths.get_runtime_dir", return_value=tmp_path / "runtime"):
        reindex_all(
            tmp_path,
            rag_dir,
            vault_dir=None,
            document_sources=_fixture_document_sources(documents_dir),
        )

    assert not stale_chunk.exists()


def test_reindex_all_drops_legacy_wiki_compile_metadata_on_documents_rebuild(tmp_path):
    from src.lib.index.unified_indexer import reindex_all
    from src.lib.frontmatter_utils import parse_frontmatter

    documents_dir = tmp_path / "documents"
    (documents_dir / "brain").mkdir(parents=True, exist_ok=True)
    source_file = documents_dir / "brain" / "live.md"
    source_file.write_text("# Live\n\n" + ("content " * 60), encoding="utf-8")

    rag_dir = tmp_path / "rag"
    entry = rag_dir / "documents" / "brain" / "live.md"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(
        "---\n"
        f"source_path: {source_file.resolve()}\n"
        "type: document\n"
        "wiki_compile_status: compiled\n"
        "wiki_compiled_checksum: old-checksum\n"
        "wiki_compiled_at: 2026-04-14T09:00:00+00:00\n"
        "wiki_targets:\n"
        "  - brain/live\n"
        "---\n"
        "old body\n",
        encoding="utf-8",
    )

    def _fake_extract(path: Path) -> dict[str, str | int]:
        return {
            "format": "md",
            "size_bytes": len(path.read_bytes()),
            "created": "2026-04-14T10:00:00+00:00",
            "body": "fresh body",
        }

    with patch(
        "src.lib.index.unified_indexer._extract_document",
        side_effect=_fake_extract,
    ), patch(
        "src.config.paths.get_runtime_dir",
        return_value=tmp_path / "runtime",
    ):
        stats = reindex_all(
            tmp_path,
            rag_dir,
            vault_dir=None,
            document_sources=_fixture_document_sources(documents_dir),
        )

    assert stats["documents"] == 1
    meta, _ = parse_frontmatter(entry)
    assert "wiki_compile_status" not in meta
    assert "wiki_compiled_checksum" not in meta
    assert "wiki_compiled_at" not in meta
    assert "wiki_targets" not in meta


def test_reindex_all_keeps_same_stem_documents_separate(tmp_path):
    from src.lib.index.unified_indexer import reindex_all

    rag_dir = tmp_path / "rag"
    documents_dir = tmp_path / "documents"
    (documents_dir / "brain" / "alpha").mkdir(parents=True, exist_ok=True)
    (documents_dir / "brain" / "beta").mkdir(parents=True, exist_ok=True)
    body = "# Shared\n\n" + ("content " * 200)
    (documents_dir / "brain" / "alpha" / "overview.md").write_text(body, encoding="utf-8")
    (documents_dir / "brain" / "beta" / "overview.md").write_text(body, encoding="utf-8")

    with patch("src.config.paths.get_runtime_dir", return_value=tmp_path / "runtime"):
        reindex_all(
            tmp_path,
            rag_dir,
            vault_dir=None,
            document_sources=_fixture_document_sources(documents_dir),
        )

    assert (rag_dir / "chunks" / "documents" / "brain" / "alpha" / "overview").exists()
    assert (rag_dir / "chunks" / "documents" / "brain" / "beta" / "overview").exists()


# ---------------------------------------------------------------------------
# Prompts scanner tests
# ---------------------------------------------------------------------------


def _make_prompt(tmp_path, bundle, skill_name, prompt_id, content):
    # Scanner looks at skill_dir/assets/seeds/prompts/
    prompt_dir = tmp_path / "plugins" / bundle / "skills" / skill_name / "assets" / "seeds" / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / f"{prompt_id}.md").write_text(content)


def _make_root_prompt(tmp_path, bundle, skill_name, prompt_id, content):
    prompt_dir = tmp_path / "plugins" / bundle / "skills" / skill_name / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    (prompt_dir / f"{prompt_id}.md").write_text(content)


def test_index_prompts_creates_pointer_files(tmp_path):
    from src.lib.index.unified_indexer import index_prompts

    # Need SKILL.md for discovery
    skill_dir = tmp_path / "plugins" / "ai" / "skills" / "knowledge"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("---\nname: knowledge\n---\n")
    _make_prompt(tmp_path, "ai", "knowledge", "search-prompt",
        "---\nid: search-prompt\n---\nSearch across knowledge.\n")

    rag_dir = tmp_path / "rag"
    with patch("src.lib.index._scanners_knowledge._discover_skill_dirs", return_value=_mock_discover(tmp_path)):
        index_prompts(tmp_path, rag_dir)

    entry = rag_dir / "prompts" / "ai" / "search-prompt.md"
    assert entry.exists()


def test_index_prompts_includes_agent_skills_prompt_directory(tmp_path):
    from src.lib.index.unified_indexer import index_prompts

    skill_dir = tmp_path / "plugins" / "ai" / "skills" / "ingest"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("---\nname: ingest\n---\n")
    _make_root_prompt(
        tmp_path,
        "ai",
        "ingest",
        "ingest-content",
        "---\nid: ingest-content\ndescription: Process dropped content\n---\nProcess dropped content.\n",
    )

    rag_dir = tmp_path / "rag"
    with patch("src.lib.index._scanners_knowledge._discover_skill_dirs", return_value=_mock_discover(tmp_path)):
        index_prompts(tmp_path, rag_dir)

    entry = rag_dir / "prompts" / "ai" / "ingest-content.md"
    assert entry.exists()
    assert "source_path: plugins/ai/skills/ingest/prompts/ingest-content.md" in entry.read_text()


# ---------------------------------------------------------------------------
# Agents scanner tests
# ---------------------------------------------------------------------------


def test_index_agents_from_config_dir(tmp_path):
    from src.lib.index.unified_indexer import index_agents

    # index_agents scans root/plugins/agents/*.md (not config/agents/)
    agents_dir = tmp_path / "plugins" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "researcher.md").write_text(
        "---\nname: researcher\ndescription: Research and analysis agent\n"
        "mode: auto\n---\n"
    )

    rag_dir = tmp_path / "rag"
    index_agents(tmp_path, rag_dir)

    entry = rag_dir / "agents" / "researcher.md"
    assert entry.exists()
    content = entry.read_text()
    assert "type: agent" in content


def test_index_agents_adds_client_projection_models(tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index.unified_indexer import index_agents

    agents_dir = tmp_path / "plugins" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "researcher.md").write_text(
        "---\n"
        "name: researcher\n"
        "description: Research and analysis agent\n"
        "mode: act\n"
        "model: sonnet\n"
        "x-augur-master: claude-code\n"
        "---\n"
        "# Researcher\n",
        encoding="utf-8",
    )
    (tmp_path / "config" / "agents").mkdir(parents=True)
    (tmp_path / "config" / "agents" / "model_mapping.yaml").write_text(
        "tiers:\n"
        "  standard:\n"
        "    clients:\n"
        "      claude-code: sonnet\n"
        "      codex: gpt-5.4\n"
        "      gemini: gemini-3-flash-preview\n"
        "reverse_lookup:\n"
        "  sonnet: standard\n",
        encoding="utf-8",
    )
    codex_agent = tmp_path / ".codex" / "agents" / "researcher.md"
    codex_agent.parent.mkdir(parents=True)
    codex_agent.write_text("---\ndescription: researcher\n---\n# Researcher\n", encoding="utf-8")

    rag_dir = tmp_path / "rag"
    index_agents(tmp_path, rag_dir)

    metadata, _body = parse_frontmatter(rag_dir / "agents" / "researcher.md")
    assert metadata["master_client"] == "claude-code"
    assert metadata["source_model"] == "sonnet"
    assert metadata["source_tier"] == "standard"
    assert metadata["codex_model"] == "gpt-5.4"
    assert metadata["codex_profile_path"] == ".codex/agents/researcher.md"
    assert metadata["codex_sync_status"] == "synced"
    assert metadata["gemini_model"] == "gemini-3-flash-preview"


# ---------------------------------------------------------------------------
# Integrations scanner tests
# ---------------------------------------------------------------------------


def test_index_integrations(tmp_path):
    from src.lib.index.unified_indexer import index_integrations

    # index_integrations checks SKILL.md frontmatter for x-augur-cli-integrations
    skill_dir = tmp_path / "plugins" / "productivity" / "skills" / "notion"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: notion\ndescription: Notion integration\n"
        "x-augur-integration-type: api\n"
        "x-augur-cli-integrations:\n  - notion\n---\n# Notion\n")

    rag_dir = tmp_path / "rag"
    with patch("src.lib.index._scanners_knowledge._discover_skill_dirs", return_value=_mock_discover(tmp_path)):
        index_integrations(tmp_path, rag_dir)

    entry = rag_dir / "integrations" / "productivity" / "notion.md"
    assert entry.exists()


# ---------------------------------------------------------------------------
# Commands scanner tests
# ---------------------------------------------------------------------------


def test_index_commands(tmp_path):
    from src.lib.index.unified_indexer import index_commands

    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "dev-debug"
    command_dir = skill_dir / "commands"
    command_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: dev-debug\ndescription: Debug issues\n"
        "x-augur-hub: dev\n---\n# Debug\n")
    (command_dir / "dev-debug.md").write_text(
        "---\ndescription: Debug issues\nvisibility: dev\n---\n# /dev-debug\n")

    rag_dir = tmp_path / "rag"
    index_commands(tmp_path, rag_dir)

    entry = rag_dir / "commands" / "dev-debug.md"
    assert entry.exists()
    content = entry.read_text()
    assert "type: command" in content
    assert "category: DEV" in content


def test_index_logs(tmp_path):
    from src.lib.index.unified_indexer import index_logs

    logs_dir = tmp_path / "runtime-logs"
    (logs_dir / "llm").mkdir(parents=True)
    (logs_dir / "llm" / "events.jsonl").write_text("INFO booted\n", encoding="utf-8")
    (logs_dir / "daemon").mkdir(parents=True)
    (logs_dir / "daemon" / "stderr.log").write_text("ERROR failed\n", encoding="utf-8")

    rag_dir = tmp_path / "rag"
    with patch("src.lib.index._scanners_structural.get_logs_dir", return_value=logs_dir):
        index_logs(tmp_path, rag_dir)

    entry = rag_dir / "logs" / "llm.md"
    assert entry.exists()
    content = entry.read_text()
    assert "type: log" in content
    assert "title: LLM" in content
    assert "file_count: '1'" in content
    assert "latest_relative_path: llm/events.jsonl" in content


# ---------------------------------------------------------------------------
# Vault scanner tests
# ---------------------------------------------------------------------------


def test_vault_journey_category_from_relative_path(tmp_path):
    from src.lib.index._scanners_structural import _vault_journey_category

    assert _vault_journey_category(tmp_path / "vault" / "inbox" / "capture.md", tmp_path / "vault") == "inbox"
    assert _vault_journey_category(tmp_path / "vault" / "notes" / "career" / "plan.md", tmp_path / "vault") == "notes"
    assert _vault_journey_category(tmp_path / "vault" / "sources" / "web" / "source.md", tmp_path / "vault") == "sources"
    assert _vault_journey_category(tmp_path / "vault" / "wiki" / "overview.md", tmp_path / "vault") == "wiki"
    assert _vault_journey_category(tmp_path / "vault" / "drafts" / "staging" / "item.md", tmp_path / "vault") == "drafts"
    assert _vault_journey_category(tmp_path / "vault" / "_drafts" / "staging" / "item.md", tmp_path / "vault") == "other"
    assert _vault_journey_category(tmp_path / "vault" / "archive" / "old.md", tmp_path / "vault") == "archive"
    assert _vault_journey_category(tmp_path / "vault" / "_system" / "migrations" / "ledger.md", tmp_path / "vault") == "other"
    assert _vault_journey_category(tmp_path / "vault" / "skills" / "apple" / "SKILL.md", tmp_path / "vault") == "skills"
    assert _vault_journey_category(tmp_path / "vault" / "memory" / "index.md", tmp_path / "vault") == "memory"
    assert _vault_journey_category(tmp_path / "outside" / "note.md", tmp_path / "vault") == "other"
    assert _vault_journey_category(tmp_path / "vault" / "random" / "note.md", tmp_path / "vault") == "other"
    assert _vault_journey_category(tmp_path / "vault", tmp_path / "vault") == "other"


def test_index_vault(tmp_path):
    from src.lib.index.unified_indexer import index_vault
    from src.lib.frontmatter_utils import parse_frontmatter

    vault_dir = tmp_path / "vault"
    (vault_dir / "notes" / "career").mkdir(parents=True)
    (vault_dir / "notes" / "career" / "interview-prep.md").write_text(
        "---\ntitle: Interview Prep\nrelated_topics: '[[Hiring]]'\nx-augur-note-type: url\nurl: https://example.com/prep\ndomain: example.com\n---\n# Interview Prep Notes\n")

    rag_dir = tmp_path / "rag"
    index_vault(vault_dir, rag_dir)

    entries = list((rag_dir / "vault").rglob("*.md"))
    assert len(entries) == 1
    content = entries[0].read_text()
    assert "type: vault" in content
    meta, _body = parse_frontmatter(entries[0])
    assert meta["relationships"] == {"related_topics": ["Hiring"]}
    assert meta["x-augur-note-type"] == "url"
    assert meta["source_domain"] == "example.com"
    assert meta["canonical_url"] == "https://example.com/prep"
    assert "journey_category: notes" in content


def test_index_vault_uses_summary_callout_for_card_description(tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index.unified_indexer import index_vault

    vault_dir = tmp_path / "vault"
    (vault_dir / "notes").mkdir(parents=True)
    (vault_dir / "notes" / "2026-05-30-demo-hard-photo.md").write_text(
        "---\n"
        "title: demo-hard-photo\n"
        "x-augur-note-type: file\n"
        "---\n\n"
        "# demo-hard-photo\n\n"
        "> [!summary]\n"
        "> NORTHWIND LABS PHOTO INVOICE\n"
        ">\n"
        "> Invoice: AI-PC-1842\n"
        ">\n"
        "> Total Due: $1,842.25\n\n"
        "## Routing\n\n"
        "- Destination: `finance`\n",
        encoding="utf-8",
    )

    rag_dir = tmp_path / "rag"
    index_vault(vault_dir, rag_dir)

    entries = list((rag_dir / "vault").rglob("*.md"))
    assert len(entries) == 1
    meta, _body = parse_frontmatter(entries[0])
    assert meta["description"] == (
        "NORTHWIND LABS PHOTO INVOICE Invoice: AI-PC-1842 Total Due: $1,842.25"
    )


def test_index_vault_scans_shared_private_notes_and_promotion_packets(tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index.unified_indexer import index_vault

    shared_vault = tmp_path / "project" / "project-brain"
    private_vault = tmp_path / "private-vault"
    (shared_vault / "notes" / "career").mkdir(parents=True)
    (private_vault / "notes" / "career").mkdir(parents=True)
    (shared_vault / "inbox" / "promotions" / "packet-a").mkdir(parents=True)

    (shared_vault / "notes" / "career" / "strategy.md").write_text(
        "---\ntitle: Team Strategy\n---\nShared plan\n",
        encoding="utf-8",
    )
    (private_vault / "notes" / "career" / "strategy.md").write_text(
        "---\ntitle: Private Strategy\n---\nPrivate plan\n",
        encoding="utf-8",
    )
    (shared_vault / "inbox" / "promotions" / "packet-a" / "synthesis.md").write_text(
        "---\ntitle: Strategy Packet\nvault_scope: shared\npromotion_state: packet\n---\nPacket\n",
        encoding="utf-8",
    )

    rag_dir = tmp_path / "rag"
    count = index_vault(private_vault, rag_dir, shared_vault_dir=shared_vault)

    assert count == 3
    entries = [parse_frontmatter(path)[0] for path in sorted((rag_dir / "vault").rglob("*.md"))]
    assert {entry["id"] for entry in entries} == {
        "vault:shared:notes/career/strategy",
        "vault:private:notes/career/strategy",
        "vault:shared:inbox/promotions/packet-a/synthesis",
    }
    assert {entry["vault_scope"] for entry in entries} == {"shared", "private"}
    assert {entry["promotion_state"] for entry in entries} == {"integrated", "private", "packet"}
    assert (rag_dir / "vault" / "notes" / "shared" / "career" / "strategy.md").is_file()
    assert (rag_dir / "vault" / "notes" / "private" / "career" / "strategy.md").is_file()
    assert (rag_dir / "vault" / "inbox" / "promotions" / "packet-a" / "synthesis.md").is_file()


def test_index_vault_keeps_shared_and_private_promotion_paths_distinct(tmp_path):
    from src.lib.frontmatter_utils import parse_frontmatter
    from src.lib.index.unified_indexer import index_vault

    shared_vault = tmp_path / "project" / "project-brain"
    private_vault = tmp_path / "private-vault"
    shared_packet = shared_vault / "inbox" / "promotions" / "packet-a" / "synthesis.md"
    private_packet = private_vault / "inbox" / "promotions" / "packet-a" / "synthesis.md"
    shared_packet.parent.mkdir(parents=True)
    private_packet.parent.mkdir(parents=True)
    shared_packet.write_text(
        "---\ntitle: Shared Packet\n---\nShared packet\n",
        encoding="utf-8",
    )
    private_packet.write_text(
        "---\ntitle: Private Packet\n---\nPrivate packet\n",
        encoding="utf-8",
    )

    rag_dir = tmp_path / "rag"
    count = index_vault(private_vault, rag_dir, shared_vault_dir=shared_vault)

    assert count == 2
    entry_paths = sorted((rag_dir / "vault").rglob("*.md"))
    assert len(entry_paths) == 2
    entries = [parse_frontmatter(path)[0] for path in entry_paths]
    assert {entry["id"] for entry in entries} == {
        "vault:shared:inbox/promotions/packet-a/synthesis",
        "vault:private:inbox/promotions/packet-a/synthesis",
    }
    assert {entry["vault_scope"] for entry in entries} == {"shared", "private"}
    assert {entry["promotion_state"] for entry in entries} == {"packet", "private"}
    assert (rag_dir / "vault" / "inbox" / "promotions" / "packet-a" / "synthesis.md").is_file()
    assert (rag_dir / "vault" / "inbox" / "private" / "promotions" / "packet-a" / "synthesis.md").is_file()


# ---------------------------------------------------------------------------
# Scripts scanner tests
# ---------------------------------------------------------------------------


def test_index_scripts(tmp_path):
    from src.lib.index.unified_indexer import index_scripts

    script_dir = tmp_path / "plugins" / "ai" / "skills" / "rag" / "scripts"
    script_dir.mkdir(parents=True)
    (script_dir / "rag_indexer.py").write_text("# RAG indexer\ndef run(): pass\n")
    (script_dir.parent / "SKILL.md").write_text("---\nname: rag\n---\n")

    rag_dir = tmp_path / "rag"
    index_scripts(tmp_path, rag_dir)

    entries = list((rag_dir / "scripts").rglob("*.md"))
    assert len(entries) >= 1


# ---------------------------------------------------------------------------
# API routes scanner tests
# ---------------------------------------------------------------------------


def test_index_api_routes(tmp_path):
    from src.lib.index.unified_indexer import index_api_routes

    route = tmp_path / "apps" / "dashboard" / "app" / "api" / "browse" / "actions" / "route.ts"
    route.parent.mkdir(parents=True)
    route.write_text("export async function GET() { return Response.json({}); }\n")

    rag_dir = tmp_path / "rag"
    index_api_routes(tmp_path, rag_dir)

    entries = list((rag_dir / "api-routes").rglob("*.md"))
    assert len(entries) >= 1


# ---------------------------------------------------------------------------
# Tests scanner tests
# ---------------------------------------------------------------------------


def test_index_tests_finds_pytest_files(tmp_path):
    from src.lib.index.unified_indexer import index_tests

    skill_dir = tmp_path / "plugins" / "ai" / "skills" / "rag"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: rag\n---\n")
    test_file = tmp_path / "plugins" / "ai" / "skills" / "rag" / "augur" / "tests" / "test_rag.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_example(): assert True\n")

    rag_dir = tmp_path / "rag"
    index_tests(tmp_path, rag_dir)

    entries = list((rag_dir / "tests").rglob("*.md"))
    assert len(entries) >= 1


# ---------------------------------------------------------------------------
# Blocks scanner tests
# ---------------------------------------------------------------------------


def test_index_blocks_from_skill_metadata(tmp_path):
    from src.lib.index.unified_indexer import index_blocks

    # index_blocks reads x-augur-config from SKILL.md frontmatter (or x-augur-config-file sidecar)
    skill_dir = tmp_path / "plugins" / "core" / "skills" / "page-builder"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: page-builder\n"
        "x-augur-config:\n"
        "  contributions:\n"
        "    blocks:\n"
        "      - id: stat-card\n"
        "        title: Stat Card\n"
        "        type: display\n"
        "---\n# Page Builder\n"
    )

    rag_dir = tmp_path / "rag"
    with patch("src.lib.index._scanners_structural._discover_skill_dirs", return_value=_mock_discover(tmp_path)):
        index_blocks(tmp_path, rag_dir)

    entry = rag_dir / "blocks" / "stat-card.md"
    assert entry.exists()
    content = entry.read_text()
    assert "type: block" in content


# ---------------------------------------------------------------------------
# Pages scanner tests
# ---------------------------------------------------------------------------


def test_index_pages_from_skill_metadata(tmp_path):
    from src.lib.index.unified_indexer import index_pages

    skill_md = tmp_path / "plugins" / "career" / "skills" / "career" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text(
        "---\n"
        "name: career\n"
        "x-augur-hub: career\n"
        "x-augur-config:\n"
        "  contributions:\n"
        "    pages:\n"
        "      - id: career-pipeline\n"
        "        title: Pipeline\n"
        "        route: /career/career/pipeline\n"
        "        state: mature\n"
        "---\n"
    )

    rag_dir = tmp_path / "rag"
    index_pages(tmp_path, rag_dir)

    entries = list((rag_dir / "pages").rglob("*.md"))
    assert len(entries) >= 1
    content = entries[0].read_text()
    assert "type: page" in content


# ---------------------------------------------------------------------------
# reindex_all orchestrator tests
# ---------------------------------------------------------------------------


def test_reindex_all_creates_manifest(tmp_path):
    from src.lib.index.unified_indexer import reindex_all

    # Create a minimal skill
    skill_dir = tmp_path / "plugins" / "career" / "skills" / "career"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: career\ndescription: Job tracking\n---\n")

    # Create a minimal ADR
    adr_dir = tmp_path / "docs" / "decisions"
    adr_dir.mkdir(parents=True)
    (adr_dir / "ADR-001-test.md").write_text(
        "---\nstatus: Proposed\ndate: '2026-01-01'\nhub: null\n---\n# ADR-001\n")

    rag_dir = tmp_path / "rag"
    stats = reindex_all(tmp_path, rag_dir, vault_dir=None)

    assert stats["skills"] >= 1
    assert stats["adrs"] >= 1

    manifest = rag_dir / "_meta" / "manifest.yaml"
    assert manifest.exists()


def test_reindex_all_writes_per_category_checksums(tmp_path):
    from src.lib.index.unified_indexer import reindex_all

    skill_dir = tmp_path / "plugins" / "ai" / "skills" / "rag"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: rag\ndescription: RAG\n---\n")

    rag_dir = tmp_path / "rag"
    reindex_all(tmp_path, rag_dir, vault_dir=None)

    checksums_dir = rag_dir / "_meta" / "checksums"
    assert checksums_dir.exists()
    assert (checksums_dir / "skills.yaml").exists()


# ---------------------------------------------------------------------------
# New chunking pipeline tests
# ---------------------------------------------------------------------------


def test_reindex_all_runs_chunking_phase(tmp_path):
    """reindex_all should only chunk document entries, not source markdown skills."""
    from src.lib.index.unified_indexer import reindex_all

    skill_dir = tmp_path / "skills" / "rag"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: rag\ndescription: RAG\nx-augur-hub: ai\n---\n"
        "# RAG Skill\n\n" + ("Content paragraph. " * 200) + "\n\n"
        "## Configuration\n\n" + ("Config detail. " * 200)
    )

    rag_dir = tmp_path / "rag"
    stats = reindex_all(tmp_path, rag_dir, vault_dir=None)

    assert stats["chunks"] == 0
    assert not (rag_dir / "chunks").exists()


def test_reindex_all_builds_bm25_index(tmp_path, monkeypatch):
    """reindex_all should create BM25 index files when documents are present."""
    pytest.importorskip("rank_bm25", reason="rank_bm25 not installed")
    from src.lib.index import unified_indexer

    monkeypatch.setattr(unified_indexer, "_load_mtime_cache", lambda: {})
    monkeypatch.setattr(unified_indexer, "_save_mtime_cache", lambda _cache: None)

    documents_dir = tmp_path / "documents"
    documents_dir.mkdir(parents=True)
    (documents_dir / "policy.md").write_text(
        "---\nname: policy\nsource_path: /tmp/policy.pdf\nhub: brain\n---\n# Policy\n\n" + ("Document text. " * 40),
        encoding="utf-8",
    )

    rag_dir = tmp_path / "rag"
    unified_indexer.reindex_all(
        tmp_path,
        rag_dir,
        vault_dir=None,
        document_sources=_fixture_document_sources(documents_dir),
    )

    assert (rag_dir / "_meta" / "bm25_index.json").exists()
    assert (rag_dir / "_meta" / "bm25_chunk_map.json").exists()
    assert (rag_dir / "chunks" / "documents").exists()


def test_reindex_all_progress_uses_stderr(tmp_path, capsys, monkeypatch):
    """Library progress output must stay off stdout for MCP stdio safety."""
    from src.lib.index import unified_indexer

    monkeypatch.setattr(unified_indexer, "_load_mtime_cache", lambda: {})
    monkeypatch.setattr(unified_indexer, "_save_mtime_cache", lambda _cache: None)

    documents_dir = tmp_path / "documents"
    documents_dir.mkdir(parents=True)
    (documents_dir / "policy.md").write_text(
        "---\nname: policy\nsource_path: /tmp/policy.pdf\nhub: brain\n---\n# Policy\n\n" + ("Document text. " * 40),
        encoding="utf-8",
    )

    rag_dir = tmp_path / "rag"
    unified_indexer.reindex_all(
        tmp_path,
        rag_dir,
        vault_dir=None,
        document_sources=_fixture_document_sources(documents_dir),
    )

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Generated index.md" in captured.err


def test_chunk_all_only_chunks_document_entries(tmp_path):
    """_chunk_all should only produce chunks for documents, not ADRs or vault entries."""
    from src.lib.index.unified_indexer import _chunk_all

    rag_dir = tmp_path / "rag"
    docs_dir = rag_dir / "documents"
    docs_dir.mkdir(parents=True)
    adrs_dir = rag_dir / "adrs"
    adrs_dir.mkdir(parents=True)
    vault_dir = rag_dir / "vault"
    vault_dir.mkdir(parents=True)

    (docs_dir / "invoice.md").write_text(
        "---\n"
        "name: invoice\n"
        "hub: brain\n"
        "source_path: /tmp/invoice.pdf\n"
        "---\n"
        + ("Invoice document body. " * 30)
    )
    (adrs_dir / "ADR-001.md").write_text(
        "---\nname: ADR-001\nsource_path: /tmp/ADR-001.md\n---\n" + ("ADR body. " * 30)
    )
    (vault_dir / "note.md").write_text(
        "---\nname: note\nsource_path: /tmp/note.md\n---\n" + ("Vault body. " * 30)
    )

    count, bm25_chunks = _chunk_all(rag_dir, tmp_path)

    assert count > 0
    assert list((rag_dir / "chunks" / "documents").rglob("*.md"))
    assert not (rag_dir / "chunks" / "adrs").exists()
    assert not (rag_dir / "chunks" / "vault").exists()
    assert all(chunk["meta"].get("category") == "documents" for chunk in bm25_chunks)


def test_chunk_all_skips_short_document_entries(tmp_path):
    """_chunk_all should skip document entries with body shorter than 200 chars."""
    from src.lib.index.unified_indexer import _chunk_all

    rag_dir = tmp_path / "rag"
    docs_dir = rag_dir / "documents"
    docs_dir.mkdir(parents=True)

    entry_content = (
        "---\n"
        "name: short-doc\n"
        "hub: brain\n"
        "source_path: /tmp/short.pdf\n"
        "---\n"
        "Too short.\n"
    )
    (docs_dir / "short-doc.md").write_text(entry_content)

    count, bm25_chunks = _chunk_all(rag_dir, tmp_path)

    assert count == 0
    assert bm25_chunks == []
    assert not (rag_dir / "chunks" / "documents").exists()


# ---------------------------------------------------------------------------
# Content-oriented index.md tests (ADR-532)
# ---------------------------------------------------------------------------


def test_generate_index_md_creates_file(tmp_path):
    """_generate_index_md should write an index.md with hub-organized entries."""
    from src.lib.index.unified_indexer import _generate_index_md

    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()

    entries = [
        {"name": "career", "category": "skills", "hub": "career", "description": "Job tracking"},
        {"name": "rag", "category": "skills", "hub": "adaptive", "description": "RAG indexing and search"},
        {"name": "ADR-004", "category": "adrs", "hub": "", "description": "Markdown RAG over Vector Databases"},
    ]
    stats = {"skills": 2, "adrs": 1, "chunks": 10}

    _generate_index_md(rag_dir, entries, stats, "2026-04-05T00:00:00+00:00")

    index_file = rag_dir / "index.md"
    assert index_file.exists()
    content = index_file.read_text()
    assert "# Knowledge Base Index" in content
    assert "**career**" in content
    assert "**rag**" in content
    assert "Adaptive Engine" in content or "Career" in content


def test_generate_index_md_groups_by_hub(tmp_path):
    """Entries should be grouped under their hub headings."""
    from src.lib.index.unified_indexer import _generate_index_md

    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()

    entries = [
        {"name": "skill-a", "category": "skills", "hub": "brain", "description": "Skill A"},
        {"name": "skill-b", "category": "skills", "hub": "brain", "description": "Skill B"},
        {"name": "skill-c", "category": "skills", "hub": "career", "description": "Skill C"},
    ]
    stats = {"skills": 3, "chunks": 0}

    _generate_index_md(rag_dir, entries, stats, "2026-04-05T00:00:00+00:00")

    content = (rag_dir / "index.md").read_text()
    assert "## Brain" in content
    assert "## Career" in content


def test_generate_index_md_truncates_long_descriptions(tmp_path):
    """Descriptions longer than 120 chars should be truncated with ellipsis."""
    from src.lib.index.unified_indexer import _generate_index_md

    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()

    long_desc = "A" * 200
    entries = [
        {"name": "verbose-skill", "category": "skills", "hub": "brain", "description": long_desc},
    ]
    stats = {"skills": 1, "chunks": 0}

    _generate_index_md(rag_dir, entries, stats, "2026-04-05T00:00:00+00:00")

    content = (rag_dir / "index.md").read_text()
    assert "..." in content
    assert long_desc not in content  # Full desc should NOT appear


def test_generate_index_md_handles_no_hub(tmp_path):
    """Entries with no hub should appear under Cross-Cutting."""
    from src.lib.index.unified_indexer import _generate_index_md

    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()

    entries = [
        {"name": "ADR-004", "category": "adrs", "hub": "", "description": "Markdown RAG"},
        {"name": "ADR-085", "category": "adrs", "hub": "", "description": "Three-Tier Index"},
    ]
    stats = {"adrs": 2, "chunks": 0}

    _generate_index_md(rag_dir, entries, stats, "2026-04-05T00:00:00+00:00")

    content = (rag_dir / "index.md").read_text()
    assert "Cross-Cutting" in content
    assert "**ADR-004**" in content


def test_generate_index_md_skips_non_navigable_categories(tmp_path):
    """Categories like 'chunks', 'tests', 'agents' should not appear in index."""
    from src.lib.index.unified_indexer import _generate_index_md

    rag_dir = tmp_path / "rag"
    rag_dir.mkdir()

    entries = [
        {"name": "chunk-1", "category": "chunks", "hub": "brain", "description": "A chunk"},
        {"name": "test-1", "category": "tests", "hub": "brain", "description": "A test"},
        {"name": "agent-1", "category": "agents", "hub": "brain", "description": "An agent"},
        {"name": "real-skill", "category": "skills", "hub": "brain", "description": "Real"},
    ]
    stats = {"chunks": 1, "tests": 1, "agents": 1, "skills": 1}

    _generate_index_md(rag_dir, entries, stats, "2026-04-05T00:00:00+00:00")

    content = (rag_dir / "index.md").read_text()
    assert "**chunk-1**" not in content
    assert "**test-1**" not in content
    assert "**agent-1**" not in content
    assert "**real-skill**" in content


def test_reindex_all_generates_index_md(tmp_path):
    """reindex_all should produce index.md alongside manifest.yaml."""
    from src.lib.index.unified_indexer import reindex_all

    skill_dir = tmp_path / "skills" / "rag"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: rag\ndescription: RAG search\nx-augur-hub: adaptive\n---\n# RAG\n"
    )

    rag_dir = tmp_path / "rag"
    reindex_all(tmp_path, rag_dir, vault_dir=None)

    assert (rag_dir / "index.md").exists()
    assert (rag_dir / "_meta" / "manifest.yaml").exists()
    content = (rag_dir / "index.md").read_text()
    assert "Knowledge Base Index" in content


def test_reindex_category_drops_legacy_wiki_compile_metadata(tmp_path):
    from src.lib.index.unified_indexer import reindex_category
    from src.lib.index import _scanners_knowledge
    from src.lib.frontmatter_utils import parse_frontmatter

    skill_dir = _make_skill(
        tmp_path,
        "brain",
        "ideas",
        "---\nname: ideas\ndescription: Ideas skill\nx-augur-hub: brain\n---\n"
        "# Ideas\n\nCurrent body that should generate a new checksum.\n",
    )

    output = tmp_path / "rag" / "skills" / "brain" / "external" / "ideas.md"
    output.parent.mkdir(parents=True)
    output.write_text(
        "---\n"
        "type: skill\n"
        "hub: brain\n"
        "name: ideas\n"
        "source_path: plugins/brain/skills/ideas/SKILL.md\n"
        "checksum: old-checksum\n"
        "wiki_compile_status: compiled\n"
        "wiki_compiled_checksum: old-checksum\n"
        "wiki_compiled_at: 2026-04-14T09:00:00+00:00\n"
        "wiki_targets:\n"
        "  - startup-ideas\n"
        "manual_related:\n"
        "  - vault/career/notes.md\n"
        "---\n",
        encoding="utf-8",
    )

    with patch.object(
        _scanners_knowledge,
        "_discover_skill_dirs",
        return_value=[("brain", skill_dir)],
    ):
        reindex_category("skills", tmp_path, tmp_path / "rag")

    meta, _ = parse_frontmatter(output)
    assert meta["checksum"] != "old-checksum"
    assert meta["manual_related"] == ["vault/career/notes.md"]
    assert "wiki_compile_status" not in meta
    assert "wiki_compiled_at" not in meta
    assert "wiki_compiled_checksum" not in meta
    assert "wiki_targets" not in meta


def test_index_documents_removes_empty_dirs_after_prune(tmp_path):
    """Moving a source out leaves no empty entry-dir shell behind (RC fix 2026-06-13)."""
    from src.lib.index.unified_indexer import index_documents

    documents_dir = tmp_path / "documents"
    (documents_dir / "brain").mkdir(parents=True, exist_ok=True)
    (documents_dir / "brain" / "live.md").write_text(
        "# Live\n\n" + ("content " * 60), encoding="utf-8"
    )
    rag_dir = tmp_path / "rag"
    # a stale entry in its own subdir whose source no longer exists (simulates a move)
    stale = rag_dir / "documents" / "gone-folder" / "old.md"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text(
        "---\n"
        f"source_path: {documents_dir / 'gone-folder' / 'old.pdf'}\n"
        "type: document\n"
        "---\nstale\n",
        encoding="utf-8",
    )

    with patch("src.config.paths.get_runtime_dir", return_value=tmp_path / "runtime"):
        index_documents(documents_dir, rag_dir)

    assert not stale.exists()  # orphan entry pruned
    assert not (rag_dir / "documents" / "gone-folder").exists()  # empty shell removed too
