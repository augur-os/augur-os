"""Tests for Browse sweep selection validation and persistence."""
from __future__ import annotations

# TODO_CLEANUP: This file is 870 lines — consider splitting into smaller modules
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "sweep_selection.py"
_SPEC = importlib.util.spec_from_file_location("sweep_selection_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
sys.modules["sweep_selection_under_test"] = mod
_SPEC.loader.exec_module(mod)


def _roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project = tmp_path / "Augur"
    docs = tmp_path / "Au-docs"
    vault = tmp_path / "Au-vault"
    runtime = tmp_path / "runtime"
    for path in (project, docs, vault, runtime):
        path.mkdir(parents=True)
    monkeypatch.setattr(mod, "get_project_root", lambda: project)
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)
    monkeypatch.setattr(mod, "get_runtime_dir", lambda: runtime)
    return project, docs, vault, runtime


def test_create_selection_persists_valid_docs_target(tmp_path, monkeypatch):
    _project, docs, _vault, runtime = _roots(tmp_path, monkeypatch)
    source = docs / "venture-augur" / "deck-v1.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"pdf")

    result = mod.create_selection(
        source_tab="sources",
        filter_summary={"search": "venture", "scope": "all"},
        targets=[
            {
                "kind": "docs",
                "source_path": str(source),
                "source_id": "doc:deck-v1",
                "archive_mode": "docs-archive",
                "title": "Deck v1",
                "metadata": {"format": "pdf"},
            }
        ],
    )

    assert result["success"] is True
    assert result["target_count"] == 1
    selection_path = Path(result["selection_path"])
    assert selection_path.is_file()
    payload = json.loads(selection_path.read_text())
    assert payload["source_tab"] == "sources"
    assert payload["targets"][0]["relative_path"] == "venture-augur/deck-v1.pdf"
    assert payload["targets"][0]["archive_mode"] == "docs-archive"
    assert selection_path.parent == runtime / "routine-vault" / "selections"


def test_create_selection_accepts_private_vault_source_card_target(tmp_path, monkeypatch):
    _project, _docs, vault, _runtime = _roots(tmp_path, monkeypatch)
    source = vault / "sources" / "web" / "article.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Article\n")

    result = mod.create_selection(
        source_tab="sources",
        filter_summary={},
        targets=[
            {
                "kind": "source-cards",
                "source_path": str(source),
                "source_id": "source:web/article",
                "archive_mode": "git-aware",
                "title": "Article",
                "metadata": {"journey_category": "sources"},
            }
        ],
    )

    assert result["target_count"] == 1
    payload = json.loads(Path(result["selection_path"]).read_text())
    target = payload["targets"][0]
    assert target["root_key"] == "vault"
    assert target["repository_root"] == str(vault)
    assert target["relative_path"] == "sources/web/article.md"


def test_create_selection_accepts_shared_vault_source_card_target(tmp_path, monkeypatch):
    project, _docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    source = project / "project-brain" / "sources" / "README.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Shared sources\n")

    result = mod.create_selection(
        source_tab="sources",
        filter_summary={},
        targets=[
            {
                "kind": "source-cards",
                "source_path": str(source),
                "source_id": "source:shared/readme",
                "archive_mode": "git-aware",
                "title": "Shared README",
                "metadata": {"journey_category": "sources"},
            }
        ],
    )

    assert result["target_count"] == 1
    payload = json.loads(Path(result["selection_path"]).read_text())
    target = payload["targets"][0]
    assert target["root_key"] == "project"
    assert target["repository_root"] == str(project)
    assert target["relative_path"] == "project-brain/sources/README.md"


def test_create_selection_refuses_source_cards_outside_source_card_roots(
    tmp_path,
    monkeypatch,
):
    _project, _docs, vault, _runtime = _roots(tmp_path, monkeypatch)
    source = vault / "notes" / "idea.md"
    source.parent.mkdir(parents=True)
    source.write_text("idea")

    result = mod.create_selection(
        source_tab="sources",
        filter_summary={},
        targets=[
            {
                "kind": "source-cards",
                "source_path": str(source),
                "source_id": "source:bad",
                "archive_mode": "git-aware",
                "title": "Bad",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "kind_path_mismatch"


def test_create_selection_refuses_outside_path(tmp_path, monkeypatch):
    _roots(tmp_path, monkeypatch)
    outside = tmp_path / "outside.txt"
    outside.write_text("x")

    result = mod.create_selection(
        source_tab="notes",
        filter_summary={},
        targets=[
            {
                "kind": "vault-notes",
                "source_path": str(outside),
                "source_id": "bad",
                "archive_mode": "git-aware",
                "title": "Bad",
                "metadata": {},
            }
        ],
    )

    assert result["success"] is True
    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "outside_allowed_roots"


def test_create_selection_refuses_directory_target_as_not_file(tmp_path, monkeypatch):
    _project, docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    source = docs / "folder"
    source.mkdir()

    result = mod.create_selection(
        source_tab="sources",
        filter_summary={},
        targets=[
            {
                "kind": "docs",
                "source_path": str(source),
                "source_id": "doc:folder",
                "archive_mode": "docs-archive",
                "title": "Folder",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "not_file"


def test_create_selection_refuses_relative_source_path(tmp_path, monkeypatch):
    _roots(tmp_path, monkeypatch)

    result = mod.create_selection(
        source_tab="sources",
        filter_summary={},
        targets=[
            {
                "kind": "docs",
                "source_path": "relative/deck.pdf",
                "source_id": "doc:relative",
                "archive_mode": "docs-archive",
                "title": "Relative",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "invalid_source_path"


def test_create_selection_refuses_empty_source_path(tmp_path, monkeypatch):
    _roots(tmp_path, monkeypatch)

    result = mod.create_selection(
        source_tab="sources",
        filter_summary={},
        targets=[
            {
                "kind": "docs",
                "source_path": "",
                "source_id": "doc:empty",
                "archive_mode": "docs-archive",
                "title": "Empty",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "invalid_source_path"


def test_create_selection_requires_matching_archive_mode(tmp_path, monkeypatch):
    _project, _docs, vault, _runtime = _roots(tmp_path, monkeypatch)
    note = vault / "notes" / "idea.md"
    note.parent.mkdir(parents=True)
    note.write_text("idea")

    result = mod.create_selection(
        source_tab="notes",
        filter_summary={},
        targets=[
            {
                "kind": "vault-notes",
                "source_path": str(note),
                "source_id": "note:idea",
                "archive_mode": "docs-archive",
                "title": "Idea",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "archive_mode_mismatch"


def test_create_selection_refuses_sources_tab_with_vault_notes_kind(tmp_path, monkeypatch):
    _project, _docs, vault, _runtime = _roots(tmp_path, monkeypatch)
    source = vault / "notes" / "idea.md"
    source.parent.mkdir(parents=True)
    source.write_text("idea")

    result = mod.create_selection(
        source_tab="sources",
        filter_summary={},
        targets=[
            {
                "kind": "vault-notes",
                "source_path": str(source),
                "source_id": "note:idea",
                "archive_mode": "git-aware",
                "title": "Idea",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "source_tab_kind_mismatch"


def test_create_selection_refuses_notes_tab_with_docs_kind(tmp_path, monkeypatch):
    _project, docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    source = docs / "deck.pdf"
    source.write_bytes(b"pdf")

    result = mod.create_selection(
        source_tab="notes",
        filter_summary={},
        targets=[
            {
                "kind": "docs",
                "source_path": str(source),
                "source_id": "doc:deck",
                "archive_mode": "docs-archive",
                "title": "Deck",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "source_tab_kind_mismatch"


@pytest.mark.parametrize("root_name", ["project", "vault"])
def test_create_selection_refuses_docs_target_outside_documents_root(
    tmp_path,
    monkeypatch,
    root_name,
):
    project, _docs, vault, _runtime = _roots(tmp_path, monkeypatch)
    root = {"project": project, "vault": vault}[root_name]
    source = root / "docs" / "deck.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"pdf")

    result = mod.create_selection(
        source_tab="sources",
        filter_summary={},
        targets=[
            {
                "kind": "docs",
                "source_path": str(source),
                "source_id": f"doc:{root_name}",
                "archive_mode": "docs-archive",
                "title": "Deck",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "root_kind_mismatch"


def test_create_selection_refuses_vault_notes_target_under_documents_root(tmp_path, monkeypatch):
    _project, docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    source = docs / "notes" / "idea.md"
    source.parent.mkdir(parents=True)
    source.write_text("idea")

    result = mod.create_selection(
        source_tab="notes",
        filter_summary={},
        targets=[
            {
                "kind": "vault-notes",
                "source_path": str(source),
                "source_id": "note:idea",
                "archive_mode": "git-aware",
                "title": "Idea",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "root_kind_mismatch"


def test_create_selection_refuses_vault_notes_outside_notes_subpath(tmp_path, monkeypatch):
    _project, _docs, vault, _runtime = _roots(tmp_path, monkeypatch)
    source = vault / "journal" / "idea.md"
    source.parent.mkdir(parents=True)
    source.write_text("idea")

    result = mod.create_selection(
        source_tab="notes",
        filter_summary={},
        targets=[
            {
                "kind": "vault-notes",
                "source_path": str(source),
                "source_id": "note:idea",
                "archive_mode": "git-aware",
                "title": "Idea",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "kind_path_mismatch"


def test_create_selection_accepts_vault_notes_under_notes_subpath(tmp_path, monkeypatch):
    _project, _docs, vault, _runtime = _roots(tmp_path, monkeypatch)
    source = vault / "notes" / "idea.md"
    source.parent.mkdir(parents=True)
    source.write_text("idea")

    result = mod.create_selection(
        source_tab="notes",
        filter_summary={},
        targets=[
            {
                "kind": "vault-notes",
                "source_path": str(source),
                "source_id": "note:idea",
                "archive_mode": "git-aware",
                "title": "Idea",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 1
    payload = json.loads(Path(result["selection_path"]).read_text())
    assert payload["targets"][0]["relative_path"] == "notes/idea.md"


def test_create_selection_accepts_pages_live_target_under_project_root(tmp_path, monkeypatch):
    project, _docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    source = project / "apps" / "dashboard" / "app" / "page.tsx"
    source.parent.mkdir(parents=True)
    source.write_text("export default function Page() { return null }")

    result = mod.create_selection(
        source_tab="pages",
        filter_summary={},
        targets=[
            {
                "kind": "pages-live",
                "source_path": str(source),
                "source_id": "page:home",
                "archive_mode": "git-aware",
                "title": "Home",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 1
    payload = json.loads(Path(result["selection_path"]).read_text())
    target = payload["targets"][0]
    assert target["root_key"] == "project"
    assert target["repository_root"] == str(project)
    assert target["relative_path"] == "apps/dashboard/app/page.tsx"


def test_create_selection_refuses_pages_live_arbitrary_project_file(tmp_path, monkeypatch):
    project, _docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    source = project / "docs" / "random.md"
    source.parent.mkdir(parents=True)
    source.write_text("random")

    result = mod.create_selection(
        source_tab="pages",
        filter_summary={},
        targets=[
            {
                "kind": "pages-live",
                "source_path": str(source),
                "source_id": "page:random",
                "archive_mode": "git-aware",
                "title": "Random",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "kind_path_mismatch"


def test_create_selection_accepts_pages_live_skill_markdown(tmp_path, monkeypatch):
    project, _docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    source = project / "project-brain" / "capabilities" / "skills" / "example" / "SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text("# Example")

    result = mod.create_selection(
        source_tab="pages",
        filter_summary={},
        targets=[
            {
                "kind": "pages-live",
                "source_path": str(source),
                "source_id": "page:skill",
                "archive_mode": "git-aware",
                "title": "Skill",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 1
    payload = json.loads(Path(result["selection_path"]).read_text())
    assert payload["targets"][0]["relative_path"] == "project-brain/capabilities/skills/example/SKILL.md"


def test_create_selection_accepts_pages_live_skill_yaml_page(tmp_path, monkeypatch):
    project, _docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    source = project / "project-brain" / "capabilities" / "skills" / "example" / "augur" / "pages" / "example.yaml"
    source.parent.mkdir(parents=True)
    source.write_text("title: Example\n")

    result = mod.create_selection(
        source_tab="pages",
        filter_summary={},
        targets=[
            {
                "kind": "pages-live",
                "source_path": str(source),
                "source_id": "page:yaml",
                "archive_mode": "git-aware",
                "title": "YAML",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 1
    payload = json.loads(Path(result["selection_path"]).read_text())
    assert (
        payload["targets"][0]["relative_path"]
        == "project-brain/capabilities/skills/example/augur/pages/example.yaml"
    )


@pytest.mark.parametrize(
    "relative_path",
    [
        "skills/books/SKILL.md",
        "skills/books/augur/pages/library.yaml",
        "skills/books/augur/pages/library.yml",
    ],
)
def test_create_selection_accepts_pages_live_private_vault_skill_sources(
    tmp_path,
    monkeypatch,
    relative_path,
):
    _project, _docs, vault, _runtime = _roots(tmp_path, monkeypatch)
    source = vault / relative_path
    source.parent.mkdir(parents=True)
    source.write_text("---\ntitle: Library\n---\n")

    result = mod.create_selection(
        source_tab="pages",
        filter_summary={},
        targets=[
            {
                "kind": "pages-live",
                "source_path": str(source),
                "source_id": "page:private-library",
                "archive_mode": "git-aware",
                "title": "Private Library",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 1
    payload = json.loads(Path(result["selection_path"]).read_text())
    target = payload["targets"][0]
    assert target["root_key"] == "vault"
    assert target["repository_root"] == str(vault)
    assert target["relative_path"] == relative_path


def test_create_selection_accepts_pages_live_dashboard_app_page(tmp_path, monkeypatch):
    project, _docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    source = project / "apps" / "dashboard" / "app" / "example" / "page.tsx"
    source.parent.mkdir(parents=True)
    source.write_text("export default function Page() { return null }")

    result = mod.create_selection(
        source_tab="pages",
        filter_summary={},
        targets=[
            {
                "kind": "pages-live",
                "source_path": str(source),
                "source_id": "page:app-example",
                "archive_mode": "git-aware",
                "title": "App Example",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 1
    payload = json.loads(Path(result["selection_path"]).read_text())
    assert payload["targets"][0]["relative_path"] == "apps/dashboard/app/example/page.tsx"


def test_create_selection_accepts_pages_artifacts_target_under_documents_root(tmp_path, monkeypatch):
    _project, docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    source = docs / "pages" / "artifact.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html></html>")
    source.with_suffix("").with_suffix(".meta.yaml").write_text("slug: artifact\n")

    result = mod.create_selection(
        source_tab="pages",
        filter_summary={},
        targets=[
            {
                "kind": "pages-artifacts",
                "source_path": str(source),
                "source_id": "page:artifact",
                "archive_mode": "docs-archive",
                "title": "Artifact",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 1
    payload = json.loads(Path(result["selection_path"]).read_text())
    target = payload["targets"][0]
    assert target["root_key"] == "documents"
    assert target["repository_root"] is None
    assert target["relative_path"] == "pages/artifact.html"


def test_create_selection_refuses_pages_artifacts_html_without_sidecar(tmp_path, monkeypatch):
    _project, docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    source = docs / "pages" / "artifact.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html></html>")

    result = mod.create_selection(
        source_tab="pages",
        filter_summary={},
        targets=[
            {
                "kind": "pages-artifacts",
                "source_path": str(source),
                "source_id": "page:artifact",
                "archive_mode": "docs-archive",
                "title": "Artifact",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "kind_path_mismatch"


def test_create_selection_accepts_pages_artifacts_html_with_sidecar(tmp_path, monkeypatch):
    _project, docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    source = docs / "pages" / "artifact.html"
    source.parent.mkdir(parents=True)
    source.write_text("<html></html>")
    source.with_suffix("").with_suffix(".meta.yaml").write_text("slug: artifact\n")

    result = mod.create_selection(
        source_tab="pages",
        filter_summary={},
        targets=[
            {
                "kind": "pages-artifacts",
                "source_path": str(source),
                "source_id": "page:artifact",
                "archive_mode": "docs-archive",
                "title": "Artifact",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 1
    payload = json.loads(Path(result["selection_path"]).read_text())
    assert payload["targets"][0]["relative_path"] == "pages/artifact.html"


def test_create_selection_refuses_pages_live_in_nested_documents_root(tmp_path, monkeypatch):
    project, _docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    nested_docs = project / "Au-docs"
    nested_docs.mkdir()
    monkeypatch.setattr(mod, "get_documents_dir", lambda: nested_docs)
    source = nested_docs / "apps" / "dashboard" / "app" / "example" / "page.tsx"
    source.parent.mkdir(parents=True)
    source.write_text("export default function Page() { return null }")

    result = mod.create_selection(
        source_tab="pages",
        filter_summary={},
        targets=[
            {
                "kind": "pages-live",
                "source_path": str(source),
                "source_id": "page:nested-docs",
                "archive_mode": "git-aware",
                "title": "Nested Docs",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "root_kind_mismatch"


def test_create_selection_refuses_symlink_target_before_resolving(tmp_path, monkeypatch):
    _project, docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    real_source = docs / "real.pdf"
    real_source.write_bytes(b"pdf")
    symlink = docs / "alias.pdf"
    symlink.symlink_to(real_source)

    result = mod.create_selection(
        source_tab="sources",
        filter_summary={},
        targets=[
            {
                "kind": "docs",
                "source_path": str(symlink),
                "source_id": "doc:alias",
                "archive_mode": "docs-archive",
                "title": "Alias",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "symlink"


def test_create_selection_refuses_path_through_symlinked_parent(tmp_path, monkeypatch):
    _project, docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    real_dir = docs / "real"
    real_dir.mkdir()
    real_source = real_dir / "deck.pdf"
    real_source.write_bytes(b"pdf")
    symlink_dir = docs / "alias"
    symlink_dir.symlink_to(real_dir, target_is_directory=True)

    result = mod.create_selection(
        source_tab="sources",
        filter_summary={},
        targets=[
            {
                "kind": "docs",
                "source_path": str(symlink_dir / "deck.pdf"),
                "source_id": "doc:alias-parent",
                "archive_mode": "docs-archive",
                "title": "Alias Parent",
                "metadata": {},
            }
        ],
    )

    assert result["target_count"] == 0
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "symlink"


def test_create_selection_rejects_invalid_source_tab_without_writing_file(tmp_path, monkeypatch):
    _project, docs, _vault, runtime = _roots(tmp_path, monkeypatch)
    source = docs / "deck.pdf"
    source.write_bytes(b"pdf")

    result = mod.create_selection(
        source_tab="bad-tab",
        filter_summary={},
        targets=[
            {
                "kind": "docs",
                "source_path": str(source),
                "source_id": "doc:deck",
                "archive_mode": "docs-archive",
                "title": "Deck",
                "metadata": {},
            }
        ],
    )

    assert result == {
        "success": False,
        "error": "unsupported source_tab: bad-tab",
        "target_count": 0,
        "refusal_count": 0,
        "refusals": [],
    }
    assert not (runtime / "routine-vault" / "selections").exists()


def test_read_selection_round_trips_valid_generated_id(tmp_path, monkeypatch):
    _project, docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    source = docs / "deck.pdf"
    source.write_bytes(b"pdf")
    result = mod.create_selection(
        source_tab="sources",
        filter_summary={"search": "deck"},
        targets=[
            {
                "kind": "docs",
                "source_path": str(source),
                "source_id": "doc:deck",
                "archive_mode": "docs-archive",
                "title": "Deck",
                "metadata": {"number": 1},
            }
        ],
    )

    payload = mod.read_selection(result["selection_id"])

    assert payload["selection_id"] == result["selection_id"]
    assert payload["filter_summary"] == {"search": "deck"}
    assert payload["targets"][0]["metadata"] == {"number": "1"}


def test_read_selection_rejects_path_traversal_selection_id(tmp_path, monkeypatch):
    _roots(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match=r"invalid selection id: \.\./escape"):
        mod.read_selection("../escape")


def test_create_selection_refuses_malformed_target_without_aborting_valid_targets(
    tmp_path,
    monkeypatch,
):
    _project, docs, _vault, _runtime = _roots(tmp_path, monkeypatch)
    source = docs / "deck.pdf"
    source.write_bytes(b"pdf")

    result = mod.create_selection(
        source_tab="sources",
        filter_summary={},
        targets=[
            "not-a-dict",
            {
                "kind": "docs",
                "source_path": str(source),
                "source_id": "doc:deck",
                "archive_mode": "docs-archive",
                "title": "Deck",
                "metadata": {},
            },
        ],
    )

    assert result["target_count"] == 1
    assert result["refusal_count"] == 1
    assert result["refusals"][0]["refusal_category"] == "malformed_target"
