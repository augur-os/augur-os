"""Tests for archive_index — Browse entries for Sweep archives."""
from __future__ import annotations

# TODO_CLEANUP: This file is 1031 lines — consider splitting into smaller modules
import importlib.util
import json
import os
import sys
from pathlib import Path

from src.lib.frontmatter_utils import write_frontmatter

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "archive_index.py"
_SPEC = importlib.util.spec_from_file_location("archive_index_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
sys.modules["archive_index_under_test"] = mod
_SPEC.loader.exec_module(mod)


def _write_valid_ledger_record(ledger: Path, repo: Path) -> None:
    ledger.write_text(
        json.dumps(
            {
                "archive_source": "sweep",
                "source_tab": "notes",
                "archive_mode": "git-aware",
                "original_path": str(repo / "notes/topic/page.md"),
                "archived_path": "archive/sweep/notes/2026-05-13/notes/topic/page.md",
                "repository_root": str(repo),
                "git_action": "mv",
                "reason": "superseded",
                "apply_run_id": "run-safe",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _bump_mtime(path: Path) -> None:
    bumped = path.stat().st_mtime_ns + 10_000_000_000
    os.utime(path, ns=(bumped, bumped))


def test_reads_docs_archive_manifest(tmp_path):
    docs = tmp_path / "docs"
    archive = docs / "venture" / ".archive"
    archived = archive / "old.pdf"
    archive.mkdir(parents=True)
    archived.write_bytes(b"pdf")
    (archive / "_manifest.jsonl").write_text(
        json.dumps(
            {
                "archived_at": "2026-05-13T10:00:00Z",
                "from": "venture/old.pdf",
                "to": "venture/.archive/old.pdf",
                "reason": "superseded",
                "artifact_group": "deck",
                "apply_run_id": "run1",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    entries = mod.docs_archive_entries(docs)

    assert entries == [
        {
            "id": "sweep:docs:run1:venture/old.pdf",
            "type": "vault",
            "name": "old.pdf",
            "title": "old.pdf",
            "description": "superseded",
            "hub": "system",
            "source_path": str(archived.resolve()),
            "journey_category": "archive",
            "archive_source": "sweep",
            "archive_mode": "docs-archive",
            "source_tab": "sources",
            "original_path": str((docs / "venture" / "old.pdf").resolve()),
            "archived_path": str(archived.resolve()),
            "reason": "superseded",
            "artifact_group": "deck",
            "apply_run_id": "run1",
            "archived_at": "2026-05-13T10:00:00Z",
            "recovery_hint": "Move the file out of its .archive folder to restore it.",
        }
    ]


def test_skips_malformed_manifest_lines_with_warning(tmp_path):
    docs = tmp_path / "docs"
    archive = docs / "x" / ".archive"
    archive.mkdir(parents=True)
    (archive / "_manifest.jsonl").write_text("{bad json}\n", encoding="utf-8")

    result = mod.collect_sweep_archive_entries(documents_dir=docs, ledger_roots=[])

    assert result["entries"] == []
    assert result["warning_count"] == 1
    assert result["warnings"][0]["kind"] == "malformed_json"
    assert result["warnings"][0]["path"] == str(archive / "_manifest.jsonl")
    assert result["warnings"][0]["line"] == 1


def test_skips_docs_manifest_paths_that_escape_documents_root(tmp_path):
    docs = tmp_path / "docs"
    archive = docs / "x" / ".archive"
    archive.mkdir(parents=True)
    (archive / "_manifest.jsonl").write_text(
        json.dumps(
            {
                "from": "../outside.txt",
                "to": "x/.archive/outside.txt",
                "reason": "unsafe",
                "apply_run_id": "run-unsafe",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = mod.collect_sweep_archive_entries(documents_dir=docs, ledger_roots=[])

    assert result["entries"] == []
    assert result["warning_count"] == 1
    assert result["warnings"][0]["kind"] == "unsafe_path"
    assert result["warnings"][0]["field"] == "from"


def test_skips_docs_manifest_paths_through_archive_symlink(tmp_path):
    docs = tmp_path / "docs"
    outside = tmp_path / "outside"
    outside.mkdir()
    archive_parent = docs / "x"
    archive_parent.mkdir(parents=True)
    archive = archive_parent / ".archive"
    archive.symlink_to(outside, target_is_directory=True)
    (outside / "_manifest.jsonl").write_text(
        json.dumps(
            {
                "from": "x/old.pdf",
                "to": "x/.archive/old.pdf",
                "reason": "unsafe symlink",
                "apply_run_id": "run-symlink",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = mod.collect_sweep_archive_entries(documents_dir=docs, ledger_roots=[])

    assert result["entries"] == []
    assert result["warning_count"] == 1
    assert result["warnings"][0]["kind"] == "unsafe_manifest"


def test_reads_git_aware_sweep_ledgers(tmp_path):
    repo = tmp_path / "repo"
    ledger_root = repo / "archive" / "sweep"
    ledger_root.mkdir(parents=True)
    ledger = ledger_root / "sweep-ledger.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "archive_source": "sweep",
                "selection_id": "browse-sweep-20260513-120002-abcdef12",
                "source_id": "note1",
                "source_tab": "notes",
                "kind": "vault-notes",
                "archive_mode": "git-aware",
                "original_path": str(repo / "notes/topic/page.md"),
                "relative_path": "notes/topic/page.md",
                "archived_path": "archive/sweep/notes/2026-05-13/notes/topic/page.md",
                "repository_root": str(repo),
                "git_action": "mv",
                "reason": "superseded",
                "artifact_group": "topic",
                "apply_run_id": "run-git",
                "archived_at": "2026-05-13T12:00:00Z",
                "recovery_hint": "Use git restore.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = mod.collect_sweep_archive_entries(
        documents_dir=tmp_path / "docs",
        ledger_roots=[ledger_root, tmp_path / "missing-ledgers"],
    )

    assert result["warning_count"] == 0
    assert result["entries"] == [
        {
            "id": "sweep:git-aware:run-git:notes/topic/page.md",
            "type": "vault",
            "name": "page.md",
            "title": "page.md",
            "description": "superseded",
            "hub": "system",
            "source_path": str(repo / "archive/sweep/notes/2026-05-13/notes/topic/page.md"),
            "journey_category": "archive",
            "archive_source": "sweep",
            "archive_mode": "git-aware",
            "source_tab": "notes",
            "original_path": str(repo / "notes/topic/page.md"),
            "archived_path": str(repo / "archive/sweep/notes/2026-05-13/notes/topic/page.md"),
            "repo_root": str(repo),
            "repository_root": str(repo),
            "git_action": "mv",
            "reason": "superseded",
            "artifact_group": "topic",
            "apply_run_id": "run-git",
            "archived_at": "2026-05-13T12:00:00Z",
            "recovery_hint": "Use git restore.",
        }
    ]


def test_git_aware_sweep_ledgers_infer_recovery_metadata(tmp_path):
    repo = tmp_path / "repo"
    ledger_root = repo / "archive" / "sweep"
    ledger_root.mkdir(parents=True)
    ledger = ledger_root / "sweep-ledger.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "archive_source": "sweep",
                "source_tab": "notes",
                "archive_mode": "git-aware",
                "relative_path": "notes/topic/page.md",
                "archived_path": "archive/sweep/notes/2026-05-13/notes/topic/page.md",
                "reason": "superseded",
                "apply_run_id": "run-infer",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = mod.collect_sweep_archive_entries(
        documents_dir=tmp_path / "docs",
        ledger_roots=[ledger_root],
    )

    assert result["warning_count"] == 0
    assert result["entries"][0]["repo_root"] == str(repo)
    assert result["entries"][0]["repository_root"] == str(repo)
    assert result["entries"][0]["git_action"] == "mv"


def test_reads_git_history_purge_ledger_events(tmp_path):
    repo = tmp_path / "brain"
    repo.mkdir()
    ledger = repo / "archive" / "_ledger" / "sweep.jsonl"
    ledger.parent.mkdir(parents=True)
    archived_rel = "archive/sweep/notes/2026-05-14/notes/page.md"
    ledger.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "archive_prepared",
                        "archive_record_id": "run-1-notes-page",
                        "brain_id": "private",
                        "source_kind": "vault-notes",
                        "source_tab": "notes",
                        "original_path": "notes/page.md",
                        "archived_path": archived_rel,
                        "reason": "superseded",
                        "artifact_group": "firmware",
                        "apply_run_id": "run-1",
                        "archived_at": "2026-05-14T10:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "event": "purged",
                        "archive_record_id": "run-1-notes-page",
                        "brain_id": "private",
                        "archived_path": archived_rel,
                        "archive_commit": "abc123",
                        "archive_pushed": True,
                        "purged_at": "2026-05-14T10:02:00Z",
                        "recovery_hint": "git restore --source=abc123 -- " + archived_rel,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = mod.collect_sweep_archive_entries(
        documents_dir=tmp_path / "docs",
        ledger_roots=[repo / "archive"],
    )

    assert result["warnings"] == []
    entries = result["entries"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["archive_mode"] == "git-history-purge"
    assert entry["archive_record_id"] == "run-1-notes-page"
    assert entry["brain_id"] == "private"
    assert entry["source_kind"] == "vault-notes"
    assert entry["original_path"] == str(repo / "notes/page.md")
    assert entry["archived_path"] == str(repo / archived_rel)
    assert entry["source_path"] == str(repo / archived_rel)
    assert entry["git_action"] == "mv+purge"
    assert entry["purged"] is True
    assert entry["archive_commit"] == "abc123"
    assert entry["archive_pushed"] is True
    assert entry["purged_at"] == "2026-05-14T10:02:00Z"
    assert entry["recovery_hint"].startswith("git restore --source=abc123")


def test_skips_symlinked_git_aware_ledger_roots_with_warning(tmp_path):
    repo = tmp_path / "repo"
    real_ledger_root = tmp_path / "real-ledgers"
    real_ledger_root.mkdir()
    _write_valid_ledger_record(real_ledger_root / "sweep-ledger.jsonl", repo)
    symlinked_ledger_root = repo / "archive" / "sweep"
    symlinked_ledger_root.parent.mkdir(parents=True)
    symlinked_ledger_root.symlink_to(real_ledger_root, target_is_directory=True)

    result = mod.collect_sweep_archive_entries(
        documents_dir=tmp_path / "docs",
        ledger_roots=[symlinked_ledger_root],
    )

    assert result["entries"] == []
    assert result["warning_count"] == 1
    assert result["warnings"][0]["kind"] == "unsafe_ledger"
    assert result["warnings"][0]["path"] == str(symlinked_ledger_root)


def test_skips_symlinked_git_aware_ledger_files_with_warning(tmp_path):
    repo = tmp_path / "repo"
    ledger_root = repo / "archive" / "sweep"
    ledger_root.mkdir(parents=True)
    outside_ledger = tmp_path / "outside-ledger.jsonl"
    _write_valid_ledger_record(outside_ledger, repo)
    symlinked_ledger = ledger_root / "sweep-ledger.jsonl"
    symlinked_ledger.symlink_to(outside_ledger)

    result = mod.collect_sweep_archive_entries(
        documents_dir=tmp_path / "docs",
        ledger_roots=[ledger_root],
    )

    assert result["entries"] == []
    assert result["warning_count"] == 1
    assert result["warnings"][0]["kind"] == "unsafe_ledger"
    assert result["warnings"][0]["path"] == str(symlinked_ledger)


def test_skips_git_aware_ledger_paths_that_escape_repository_root(tmp_path):
    repo = tmp_path / "repo"
    ledger_root = repo / "archive" / "sweep"
    ledger_root.mkdir(parents=True)
    ledger = ledger_root / "sweep-ledger.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "archive_source": "sweep",
                "source_tab": "notes",
                "archive_mode": "git-aware",
                "original_path": "/etc/passwd",
                "archived_path": "archive/sweep/notes/2026-05-13/notes/topic/page.md",
                "repository_root": str(repo),
                "git_action": "mv",
                "reason": "absolute outside repo",
                "apply_run_id": "run-outside",
            }
        )
        + "\n"
        + json.dumps(
            {
                "archive_source": "sweep",
                "source_tab": "notes",
                "archive_mode": "git-aware",
                "original_path": "notes/topic/page.md",
                "archived_path": "../escape.md",
                "repository_root": str(repo),
                "git_action": "mv",
                "reason": "relative escape",
                "apply_run_id": "run-dotdot",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = mod.collect_sweep_archive_entries(
        documents_dir=tmp_path / "docs",
        ledger_roots=[ledger_root],
    )

    assert result["entries"] == []
    assert result["warning_count"] == 2
    assert [warning["kind"] for warning in result["warnings"]] == ["unsafe_path", "unsafe_path"]
    assert [warning["field"] for warning in result["warnings"]] == ["original_path", "archived_path"]
    assert "/etc/passwd" not in json.dumps(result["entries"])


def test_skips_semantically_malformed_ledger_records_with_warning(tmp_path):
    repo = tmp_path / "repo"
    ledger_root = repo / "archive" / "sweep"
    ledger_root.mkdir(parents=True)
    ledger = ledger_root / "sweep-ledger.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "archive_source": "sweep",
                "archive_mode": "git-aware",
                "relative_path": "notes/topic/page.md",
                "repository_root": str(repo),
                "git_action": "mv",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = mod.collect_sweep_archive_entries(
        documents_dir=tmp_path / "docs",
        ledger_roots=[ledger_root],
    )

    assert result["entries"] == []
    assert result["warning_count"] == 1
    assert result["warnings"][0]["kind"] == "malformed_record"
    assert result["warnings"][0]["path"] == str(ledger)
    assert result["warnings"][0]["line"] == 1
    assert result["warnings"][0]["field"] == "archived_path"


def test_skips_git_aware_ledger_missing_recovery_source_fields_with_warning(tmp_path):
    repo = tmp_path / "repo"
    ledger_root = repo / "archive" / "sweep"
    ledger_root.mkdir(parents=True)
    ledger = ledger_root / "sweep-ledger.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "archive_source": "sweep",
                "source_tab": "notes",
                "archive_mode": "git-aware",
                "archived_path": "archive/sweep/notes/2026-05-13/notes/topic/page.md",
                "repository_root": str(repo),
                "git_action": "mv",
                "reason": "missing source provenance",
                "apply_run_id": "run-missing-source",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = mod.collect_sweep_archive_entries(
        documents_dir=tmp_path / "docs",
        ledger_roots=[ledger_root],
    )

    assert result["entries"] == []
    assert result["warning_count"] == 1
    assert result["warnings"][0]["kind"] == "malformed_record"
    assert result["warnings"][0]["path"] == str(ledger)
    assert result["warnings"][0]["line"] == 1
    assert result["warnings"][0]["field"] == "original_path"
    assert '"original_path": ""' not in json.dumps(result["entries"])


def test_browse_archive_synthetic_entries_use_file_path_loader(tmp_path, monkeypatch):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    project = tmp_path / "project"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    module_dir = project / "project-brain" / "capabilities" / "skills" / "routine-vault" / "scripts"
    module_dir.mkdir(parents=True)
    docs.mkdir()
    vault.mkdir()
    (module_dir / "archive_index.py").write_text(
        "def collect_sweep_archive_entries(*, documents_dir, ledger_roots):\n"
        "    return {'entries': [{\n"
        "        'id': 'sweep:test',\n"
        "        'type': 'vault',\n"
        "        'name': 'old.md',\n"
        "        'title': 'old.md',\n"
        "        'description': 'archived',\n"
        "        'hub': 'system',\n"
        "        'source_path': str(documents_dir / 'old.md'),\n"
        "        'journey_category': 'archive',\n"
        "        'archive_source': 'sweep',\n"
        "        'archive_mode': 'docs-archive',\n"
        "        'source_tab': 'sources',\n"
        "        'original_path': str(documents_dir / 'original.md'),\n"
        "        'archived_path': str(documents_dir / 'old.md'),\n"
        "        'reason': 'archived',\n"
        "        'artifact_group': '',\n"
        "        'apply_run_id': 'run1',\n"
        "        'archived_at': '',\n"
        "        'recovery_hint': 'restore',\n"
        "        'ledger_root_count': str(len(ledger_roots)),\n"
        "    }]}\n",
        encoding="utf-8",
    )
    sys.modules.pop("loop_hygiene_archive_index", None)
    monkeypatch.setattr(browse_index, "get_project_root", lambda: project)
    monkeypatch.setattr(browse_index, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(browse_index, "get_vault_dir", lambda: vault)

    entries = browse_index._synthetic_entries_for_category("vault", "archive")

    assert entries[0]["id"] == "sweep:test"
    assert entries[0]["source_path"] == str(docs / "old.md")
    assert entries[0]["ledger_root_count"] == "2"
    assert browse_index._synthetic_entries_for_category("vault", "notes") == []


def test_browse_archive_exposes_collector_warning_status_entry(tmp_path, monkeypatch):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    project = tmp_path / "project"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    module_dir = project / "project-brain" / "capabilities" / "skills" / "routine-vault" / "scripts"
    module_dir.mkdir(parents=True)
    docs.mkdir()
    vault.mkdir()
    (module_dir / "archive_index.py").write_text(
        "def collect_sweep_archive_entries(*, documents_dir, ledger_roots):\n"
        "    return {\n"
        "        'entries': [{\n"
        "            'id': 'sweep:valid',\n"
        "            'type': 'vault',\n"
        "            'name': 'valid.md',\n"
        "            'title': 'valid.md',\n"
        "            'description': 'archived',\n"
        "            'hub': 'system',\n"
        "            'source_path': str(documents_dir / 'valid.md'),\n"
        "            'journey_category': 'archive',\n"
        "        }],\n"
        "        'warning_count': 2,\n"
        "        'warnings': [\n"
        "            {'kind': 'malformed_record', 'field': 'original_path'},\n"
        "            {'kind': 'unsafe_path', 'field': 'archived_path'},\n"
        "        ],\n"
        "    }\n",
        encoding="utf-8",
    )
    sys.modules.pop("loop_hygiene_archive_index", None)
    monkeypatch.setattr(browse_index, "get_project_root", lambda: project)
    monkeypatch.setattr(browse_index, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(browse_index, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(browse_index, "_sweep_archive_cache_key", None, raising=False)
    monkeypatch.setattr(browse_index, "_sweep_archive_cache_entries", [], raising=False)
    monkeypatch.setattr(browse_index, "_sweep_archive_cache_ts", 0.0, raising=False)

    import src.config.paths as paths

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: tmp_path / "rag" / category)

    result = json.loads(browse_index.browse_index_impl("vault", journey_category="archive"))

    assert [item["id"] for item in result["items"]] == [
        "sweep:valid",
        "sweep:archive-status:warnings",
    ]
    warning_item = result["items"][1]
    assert warning_item["metadata"]["warning_count"] == "2"
    assert warning_item["metadata"]["warning_kinds"] == "malformed_record,unsafe_path"
    assert warning_item["metadata"]["status"] == "warning"


def test_browse_archive_synthetic_entries_fail_closed(tmp_path, monkeypatch):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    sys.modules.pop("loop_hygiene_archive_index", None)
    monkeypatch.setattr(browse_index, "get_project_root", lambda: tmp_path / "missing-project")
    monkeypatch.setattr(browse_index, "get_documents_dir", lambda: tmp_path / "docs")
    monkeypatch.setattr(browse_index, "get_vault_dir", lambda: tmp_path / "vault")

    assert browse_index._synthetic_entries_for_category("vault", "archive") == []


def test_browse_archive_search_matches_sweep_metadata(tmp_path, monkeypatch):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    category_dir = tmp_path / "rag" / "vault"
    repo = tmp_path / "repo"
    archived_path = repo / "archive/sweep/notes/2026-05-13/notes/topic/page.md"
    write_frontmatter(
        category_dir / "archive" / "page.md",
        {
            "id": "sweep:git-aware:run-meta:notes/topic/page.md",
            "type": "vault",
            "name": "page.md",
            "title": "Page",
            "description": "Archived by Sweep",
            "hub": "system",
            "source_path": str(archived_path),
            "journey_category": "archive",
            "archive_source": "sweep",
            "archive_mode": "git-aware",
            "source_tab": "notes",
            "original_path": str(repo / "notes/topic/page.md"),
            "archived_path": str(archived_path),
            "repo_root": str(repo),
            "repository_root": str(repo),
            "git_action": "mv",
            "apply_run_id": "run-meta-123",
        },
        "",
    )

    import src.config.paths as paths

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: category_dir)
    monkeypatch.setattr(browse_index, "_sweep_archive_entries", lambda: [])

    for query in (
        "sweep",
        "git-aware",
        "notes",
        "run-meta-123",
        str(repo),
        "mv",
        str(archived_path),
    ):
        result = json.loads(
            browse_index.browse_index_impl("vault", journey_category="archive", search=query)
        )
        assert [item["id"] for item in result["items"]] == [
            "sweep:git-aware:run-meta:notes/topic/page.md"
        ]


def test_browse_archive_applies_hub_filter_after_synthetic_entries(tmp_path, monkeypatch):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    category_dir = tmp_path / "rag" / "vault"
    write_frontmatter(
        category_dir / "archive" / "brain.md",
        {
            "id": "vault:brain:archive/brain",
            "type": "vault",
            "name": "brain",
            "title": "Brain Archive",
            "description": "Brain-owned archive row",
            "hub": "brain",
            "source_path": str(tmp_path / "vault/archive/brain.md"),
            "journey_category": "archive",
        },
        "",
    )

    import src.config.paths as paths

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: category_dir)
    monkeypatch.setattr(
        browse_index,
        "_sweep_archive_entries",
        lambda: [
            {
                "id": "sweep:system",
                "type": "vault",
                "name": "system",
                "title": "System Archive",
                "description": "Synthetic Sweep archive row",
                "hub": "system",
                "source_path": str(tmp_path / "vault/archive/system.md"),
                "journey_category": "archive",
            }
        ],
    )

    result = json.loads(browse_index.browse_index_impl("vault", hub="brain", journey_category="archive"))

    assert [item["id"] for item in result["items"]] == ["vault:brain:archive/brain"]
    assert result["count"] == 1
    assert "total_count" not in result


def test_browse_archive_applies_limit_after_synthetic_entries(tmp_path, monkeypatch):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    category_dir = tmp_path / "rag" / "vault"
    write_frontmatter(
        category_dir / "archive" / "rag.md",
        {
            "id": "vault:system:archive/rag",
            "type": "vault",
            "name": "rag",
            "title": "RAG Archive",
            "description": "Indexed archive row",
            "hub": "system",
            "source_path": str(tmp_path / "vault/archive/rag.md"),
            "journey_category": "archive",
        },
        "",
    )

    import src.config.paths as paths

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: category_dir)
    monkeypatch.setattr(
        browse_index,
        "_sweep_archive_entries",
        lambda: [
            {
                "id": "sweep:system",
                "type": "vault",
                "name": "synthetic",
                "title": "Synthetic Archive",
                "description": "Synthetic Sweep archive row",
                "hub": "system",
                "source_path": str(tmp_path / "vault/archive/synthetic.md"),
                "journey_category": "archive",
            }
        ],
    )

    result = json.loads(browse_index.browse_index_impl("vault", journey_category="archive", limit=1))

    assert [item["id"] for item in result["items"]] == ["vault:system:archive/rag"]
    assert result["count"] == 1
    assert result["total_count"] == 2
    assert result["truncated"] is True


def test_browse_archive_repeated_calls_reuse_sweep_collector_cache(tmp_path, monkeypatch):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    project = tmp_path / "project"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    module_dir = project / "project-brain" / "capabilities" / "skills" / "routine-vault" / "scripts"
    module_dir.mkdir(parents=True)
    docs.mkdir()
    vault.mkdir()
    (module_dir / "archive_index.py").write_text(
        "CALLS = 0\n"
        "def collect_sweep_archive_entries(*, documents_dir, ledger_roots):\n"
        "    global CALLS\n"
        "    CALLS += 1\n"
        "    return {'entries': [{\n"
        "        'id': 'sweep:cached',\n"
        "        'type': 'vault',\n"
        "        'name': 'cached.md',\n"
        "        'title': 'cached.md',\n"
        "        'description': 'archived',\n"
        "        'hub': 'system',\n"
        "        'source_path': str(documents_dir / 'cached.md'),\n"
        "        'journey_category': 'archive',\n"
        "        'calls': str(CALLS),\n"
        "    }]}\n",
        encoding="utf-8",
    )
    sys.modules.pop("loop_hygiene_archive_index", None)
    monkeypatch.setattr(browse_index, "get_project_root", lambda: project)
    monkeypatch.setattr(browse_index, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(browse_index, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(browse_index, "_SWEEP_ARCHIVE_CACHE_TTL", 60.0, raising=False)
    monkeypatch.setattr(browse_index, "_sweep_archive_cache_key", None, raising=False)
    monkeypatch.setattr(browse_index, "_sweep_archive_cache_entries", [], raising=False)
    monkeypatch.setattr(browse_index, "_sweep_archive_cache_ts", 0.0, raising=False)

    import src.config.paths as paths

    monkeypatch.setattr(paths, "get_rag_category_dir", lambda category: tmp_path / "rag" / category)

    first = json.loads(browse_index.browse_index_impl("vault", journey_category="archive"))
    second = json.loads(browse_index.browse_index_impl("vault", journey_category="archive"))

    assert first["items"][0]["metadata"]["calls"] == "1"
    assert second["items"][0]["metadata"]["calls"] == "1"


def test_browse_archive_cache_invalidates_on_manifest_and_ledger_mtime_changes(
    tmp_path, monkeypatch
):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    project = tmp_path / "project"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    module_dir = project / "project-brain" / "capabilities" / "skills" / "routine-vault" / "scripts"
    module_dir.mkdir(parents=True)
    manifest = docs / "sources" / ".archive" / "_manifest.jsonl"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("manifest-one\n", encoding="utf-8")
    ledger = project / "archive" / "sweep" / "sweep-ledger.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text("ledger-one\n", encoding="utf-8")
    vault.mkdir()
    (module_dir / "archive_index.py").write_text(
        "CALLS = 0\n"
        "def collect_sweep_archive_entries(*, documents_dir, ledger_roots):\n"
        "    global CALLS\n"
        "    CALLS += 1\n"
        "    manifests = sorted(documents_dir.rglob('_manifest.jsonl'))\n"
        "    ledgers = []\n"
        "    for root in ledger_roots:\n"
        "        if root.is_file():\n"
        "            ledgers.append(root)\n"
        "        elif root.is_dir():\n"
        "            ledgers.extend(sorted(root.rglob('sweep-ledger.jsonl')))\n"
        "    manifest_text = '|'.join(path.read_text(encoding='utf-8') for path in manifests)\n"
        "    ledger_text = '|'.join(path.read_text(encoding='utf-8') for path in ledgers)\n"
        "    return {'entries': [{\n"
        "        'id': 'sweep:fresh',\n"
        "        'type': 'vault',\n"
        "        'name': 'fresh.md',\n"
        "        'title': 'fresh.md',\n"
        "        'description': 'archived',\n"
        "        'hub': 'system',\n"
        "        'source_path': str(documents_dir / 'fresh.md'),\n"
        "        'journey_category': 'archive',\n"
        "        'calls': str(CALLS),\n"
        "        'manifest_text': manifest_text,\n"
        "        'ledger_text': ledger_text,\n"
        "    }]}\n",
        encoding="utf-8",
    )
    sys.modules.pop("loop_hygiene_archive_index", None)
    monkeypatch.setattr(browse_index, "get_project_root", lambda: project)
    monkeypatch.setattr(browse_index, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(browse_index, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(browse_index, "_SWEEP_ARCHIVE_CACHE_TTL", 60.0, raising=False)
    monkeypatch.setattr(browse_index, "_sweep_archive_cache_key", None, raising=False)
    monkeypatch.setattr(browse_index, "_sweep_archive_cache_entries", [], raising=False)
    monkeypatch.setattr(browse_index, "_sweep_archive_cache_ts", 0.0, raising=False)

    first = browse_index._sweep_archive_entries()[0]
    cached = browse_index._sweep_archive_entries()[0]
    manifest.write_text("manifest-two\n", encoding="utf-8")
    _bump_mtime(manifest)
    after_manifest_change = browse_index._sweep_archive_entries()[0]
    ledger.write_text("ledger-two\n", encoding="utf-8")
    _bump_mtime(ledger)
    after_ledger_change = browse_index._sweep_archive_entries()[0]

    assert first["calls"] == "1"
    assert cached["calls"] == "1"
    assert after_manifest_change["calls"] == "2"
    assert after_manifest_change["manifest_text"] == "manifest-two\n"
    assert after_ledger_change["calls"] == "3"
    assert after_ledger_change["ledger_text"] == "ledger-two\n"


def test_browse_sweep_ledger_signature_includes_new_archive_ledger(tmp_path):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    archive_root = tmp_path / "archive"
    ledger = archive_root / "_ledger" / "sweep.jsonl"
    ledger.parent.mkdir(parents=True)
    ledger.write_text("{}\n", encoding="utf-8")

    signature = browse_index._sweep_ledger_file_signature(archive_root)

    assert len(signature) == 1
    assert signature[0][0].endswith("archive/_ledger/sweep.jsonl")


def test_browse_archive_cache_reload_reexecutes_changed_collector_module(
    tmp_path, monkeypatch
):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    project = tmp_path / "project"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    module_dir = project / "project-brain" / "capabilities" / "skills" / "routine-vault" / "scripts"
    module_path = module_dir / "archive_index.py"
    module_dir.mkdir(parents=True)
    docs.mkdir()
    vault.mkdir()

    def write_collector(version: str) -> None:
        module_path.write_text(
            "def collect_sweep_archive_entries(*, documents_dir, ledger_roots):\n"
            "    return {'entries': [{\n"
            f"        'id': 'sweep:{version}',\n"
            "        'type': 'vault',\n"
            f"        'name': '{version}.md',\n"
            f"        'title': '{version}.md',\n"
            "        'description': 'archived',\n"
            "        'hub': 'system',\n"
            "        'source_path': str(documents_dir / 'archived.md'),\n"
            "        'journey_category': 'archive',\n"
            f"        'collector_version': '{version}',\n"
            "    }]}\n",
            encoding="utf-8",
        )

    write_collector("one")
    sys.modules.pop("loop_hygiene_archive_index", None)
    monkeypatch.setattr(browse_index, "get_project_root", lambda: project)
    monkeypatch.setattr(browse_index, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(browse_index, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(browse_index, "_SWEEP_ARCHIVE_CACHE_TTL", 60.0, raising=False)
    monkeypatch.setattr(browse_index, "_sweep_archive_cache_key", None, raising=False)
    monkeypatch.setattr(browse_index, "_sweep_archive_cache_entries", [], raising=False)
    monkeypatch.setattr(browse_index, "_sweep_archive_cache_ts", 0.0, raising=False)

    first = browse_index._sweep_archive_entries()[0]
    write_collector("two")
    _bump_mtime(module_path)
    second = browse_index._sweep_archive_entries()[0]

    assert first["collector_version"] == "one"
    assert second["collector_version"] == "two"


def test_browse_archive_reload_uses_source_when_pyc_timestamp_is_stale(
    tmp_path, monkeypatch
):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    project = tmp_path / "project"
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    module_dir = project / "project-brain" / "capabilities" / "skills" / "routine-vault" / "scripts"
    module_path = module_dir / "archive_index.py"
    module_dir.mkdir(parents=True)
    docs.mkdir()
    vault.mkdir()

    def collector_source(version: str) -> str:
        return (
            "def collect_sweep_archive_entries(*, documents_dir, ledger_roots):\n"
            "    return {'entries': [{\n"
            f"        'id': 'sweep:{version}',\n"
            "        'type': 'vault',\n"
            f"        'name': '{version}.md',\n"
            f"        'title': '{version}.md',\n"
            "        'description': 'archived',\n"
            "        'hub': 'system',\n"
            "        'source_path': str(documents_dir / 'archived.md'),\n"
            "        'journey_category': 'archive',\n"
            f"        'collector_version': '{version}',\n"
            "    }]}\n"
        )

    first_source = collector_source("one")
    second_source = collector_source("two")
    assert len(first_source) == len(second_source)

    base_ns = 1_800_000_000_100_000_000
    module_path.write_text(first_source, encoding="utf-8")
    os.utime(module_path, ns=(base_ns, base_ns))
    sys.modules.pop("loop_hygiene_archive_index", None)
    monkeypatch.setattr(browse_index, "get_project_root", lambda: project)
    monkeypatch.setattr(browse_index, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(browse_index, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(browse_index, "_SWEEP_ARCHIVE_CACHE_TTL", 60.0, raising=False)
    monkeypatch.setattr(browse_index, "_sweep_archive_cache_key", None, raising=False)
    monkeypatch.setattr(browse_index, "_sweep_archive_cache_entries", [], raising=False)
    monkeypatch.setattr(browse_index, "_sweep_archive_cache_ts", 0.0, raising=False)

    first = browse_index._sweep_archive_entries()[0]
    module_path.write_text(second_source, encoding="utf-8")
    same_second_later_ns = base_ns + 500_000_000
    os.utime(module_path, ns=(same_second_later_ns, same_second_later_ns))
    second = browse_index._sweep_archive_entries()[0]

    assert first["collector_version"] == "one"
    assert second["collector_version"] == "two"


def test_browse_ledger_signature_skips_symlinked_root_without_external_entries(tmp_path):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    repo = tmp_path / "repo"
    external = tmp_path / "external-ledgers"
    external.mkdir()
    external_ledger = external / "sweep-ledger.jsonl"
    external_ledger.write_text("external\n", encoding="utf-8")
    symlinked_ledger_root = repo / "archive" / "sweep"
    symlinked_ledger_root.parent.mkdir(parents=True)
    symlinked_ledger_root.symlink_to(external, target_is_directory=True)

    signature = browse_index._sweep_ledger_file_signature(symlinked_ledger_root)

    assert signature == ()
    assert str(external_ledger) not in json.dumps(signature)


def test_browse_archive_cache_signature_skips_external_target_for_symlinked_ledger_root(
    tmp_path,
):
    from src.mcp.augur_framework.tools.infrastructure.browse import index as browse_index

    module_path = (
        tmp_path
        / "project"
        / "project-brain"
        / "capabilities"
        / "skills"
        / "routine-vault"
        / "scripts"
        / "archive_index.py"
    )
    module_path.parent.mkdir(parents=True)
    module_path.write_text("", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    repo = tmp_path / "repo"
    external = tmp_path / "external-ledgers"
    external.mkdir()
    external_ledger = external / "sweep-ledger.jsonl"
    external_ledger.write_text("external\n", encoding="utf-8")
    symlinked_ledger_root = repo / "archive" / "sweep"
    symlinked_ledger_root.parent.mkdir(parents=True)
    symlinked_ledger_root.symlink_to(external, target_is_directory=True)

    signature = browse_index._sweep_archive_cache_signature(
        module_path,
        docs,
        [symlinked_ledger_root],
    )
    serialized = json.dumps(signature)

    assert str(symlinked_ledger_root) in serialized
    assert str(external) not in serialized
    assert str(external_ledger) not in serialized
