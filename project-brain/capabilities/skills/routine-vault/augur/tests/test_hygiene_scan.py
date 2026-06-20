"""Tests for hygiene_scan — the read-only scanner."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "hygiene_scan.py"
_SPEC = importlib.util.spec_from_file_location("hygiene_scan_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
sys.modules["hygiene_scan_under_test"] = mod
_SPEC.loader.exec_module(mod)


def test_refuses_path_outside_au_docs(tmp_path, monkeypatch):
    docs = tmp_path / "au-docs"
    docs.mkdir()
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    # Au-vault path is outside Au-docs
    vault = tmp_path / "au-vault"
    vault.mkdir()
    (vault / "notes").mkdir()

    with pytest.raises(mod.HygieneScanError, match="outside Au-docs"):
        mod.hygiene_scan(str(vault / "notes"))


def test_refuses_nonexistent_path(tmp_path, monkeypatch):
    docs = tmp_path / "au-docs"
    docs.mkdir()
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    with pytest.raises(mod.HygieneScanError, match="does not exist"):
        mod.hygiene_scan(str(docs / "missing"))


def test_refuses_path_pointing_to_file_not_dir(tmp_path, monkeypatch):
    docs = tmp_path / "au-docs"
    docs.mkdir()
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    (docs / "x.zip").write_bytes(b"x")
    with pytest.raises(mod.HygieneScanError, match="not a directory"):
        mod.hygiene_scan(str(docs / "x.zip"))


def test_scan_empty_dir(tmp_path, monkeypatch):
    docs = tmp_path / "au-docs"
    docs.mkdir()
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    (docs / "empty").mkdir()
    result = mod.hygiene_scan(str(docs / "empty"))
    assert result["root"] == str(docs)
    assert result["scanned_path"] == "empty"
    assert result["files"] == []
    assert result["lifecycle_config"] is None
    assert result["milestone_pins"] == []
    assert result["never_touch_skipped"] == []
    assert result["warnings"] == []


def test_accepts_relative_path_under_au_docs(tmp_path, monkeypatch):
    docs = tmp_path / "au-docs"
    docs.mkdir()
    (docs / "venture-augur" / "websites").mkdir(parents=True)
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    monkeypatch.chdir(docs)
    result = mod.hygiene_scan("venture-augur/websites")
    assert result["scanned_path"] == "venture-augur/websites"


def _setup_docs(tmp_path, monkeypatch):
    docs = tmp_path / "au-docs"
    docs.mkdir()
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    return docs


def test_lists_regular_files_in_scanned_folder(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "guriqo-com-V10031.zip").write_bytes(b"x" * 100)
    (folder / "guriqo-com-V10032.zip").write_bytes(b"y" * 200)

    result = mod.hygiene_scan(str(folder))
    names = sorted(f["name"] for f in result["files"])
    assert names == ["guriqo-com-V10031.zip", "guriqo-com-V10032.zip"]
    by_name = {f["name"]: f for f in result["files"]}
    assert by_name["guriqo-com-V10031.zip"]["size_bytes"] == 100
    assert by_name["guriqo-com-V10032.zip"]["size_bytes"] == 200


def test_includes_relative_path_and_mtime_and_hash(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "venture-augur" / "websites"
    folder.mkdir(parents=True)
    (folder / "x.zip").write_bytes(b"hello")

    result = mod.hygiene_scan(str(folder))
    f = result["files"][0]
    assert f["relative_path"] == "venture-augur/websites/x.zip"
    assert "mtime_iso" in f and f["mtime_iso"].endswith("Z")
    # sha256 of b"hello"
    assert f["content_hash_sha256"] == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert f["is_symlink"] is False


def test_skips_never_touch_files(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")
    (folder / "package-lock.json").write_bytes(b"{}")
    (folder / ".augur-ignore").write_text("*\n")

    result = mod.hygiene_scan(str(folder))
    names = [f["name"] for f in result["files"]]
    assert names == ["x.zip"]
    assert "package-lock.json" in result["never_touch_skipped"]
    assert ".augur-ignore" in result["never_touch_skipped"]


def test_does_not_recurse_into_never_touch_dirs(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")
    archive = folder / ".archive"
    archive.mkdir()
    (archive / "old.zip").write_bytes(b"old")
    git = folder / ".git"
    git.mkdir()
    (git / "config").write_text("")

    result = mod.hygiene_scan(str(folder))
    names = [f["name"] for f in result["files"]]
    assert names == ["x.zip"]
    assert ".archive" in result["never_touch_skipped"]
    assert ".git" in result["never_touch_skipped"]


def test_refuses_symlink_files(tmp_path, monkeypatch):
    import os
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    target = folder / "real.zip"
    target.write_bytes(b"x")
    link = folder / "link.zip"
    os.symlink(target, link)

    result = mod.hygiene_scan(str(folder))
    names = [f["name"] for f in result["files"]]
    assert names == ["real.zip"]
    warnings = [w for w in result["warnings"] if "symlink" in w.lower()]
    assert any("link.zip" in w for w in warnings)


def test_recurses_into_subfolders_and_reports_folder_configs(tmp_path, monkeypatch):
    """A sweep target covers all descendant folders, not only direct children."""
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")
    sub = folder / "subfolder"
    sub.mkdir()
    (sub / "y.zip").write_bytes(b"y")
    (sub / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: nested-build\n"
        "    canonical_strategy: highest_version\n"
        "    pattern: 'nested-*.zip'\n"
    )

    result = mod.hygiene_scan(str(folder))
    paths = [f["relative_path"] for f in result["files"]]
    assert paths == ["websites/subfolder/y.zip", "websites/x.zip"]

    nested = next(f for f in result["files"] if f["name"] == "y.zip")
    assert nested["relative_to_scanned"] == "subfolder/y.zip"
    assert nested["folder_relative_path"] == "websites/subfolder"

    configs = result["folder_lifecycle_configs"]
    assert configs["websites/subfolder"]["known_groups"][0]["name"] == "nested-build"


def test_scan_returns_lifecycle_config(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / ".augur-lifecycle.yaml").write_text(
        "enabled: true\n"
        "pattern_hints:\n  - 'guriqo-com-V*.zip'\n"
        "keep_latest: 1\n"
        "deploy_root: false\n"
    )
    (folder / "x.zip").write_bytes(b"x")

    result = mod.hygiene_scan(str(folder))
    assert result["lifecycle_config"] is not None
    assert result["lifecycle_config"]["enabled"] is True
    assert result["lifecycle_config"]["pattern_hints"] == ["guriqo-com-V*.zip"]
    assert result["lifecycle_config"]["keep_latest"] == 1
    assert result["lifecycle_config"]["deploy_root"] is False


def test_hygiene_scan_returns_known_groups_in_lifecycle_config(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    folder = docs_root / "venture-augur" / "websites"
    folder.mkdir(parents=True)
    (folder / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: guriqo-com-build\n"
        "    canonical_strategy: highest_version\n"
        "    pattern: 'guriqo-com-*.zip'\n"
        "    decided_at: '2026-05-12T14:30:00Z'\n"
        "    decided_by: gsannikov\n"
    )
    (folder / "guriqo-com-V10001.zip").write_bytes(b"x")

    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs_root)

    result = mod.hygiene_scan(str(folder))
    groups = result["lifecycle_config"]["known_groups"]
    assert isinstance(groups, list)
    assert groups[0]["name"] == "guriqo-com-build"
    assert groups[0]["canonical_strategy"] == "highest_version"
    assert groups[0]["pattern"] == "guriqo-com-*.zip"


def test_hygiene_scan_malformed_known_groups_surfaces_warning(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    folder = docs_root / "x"
    folder.mkdir(parents=True)
    (folder / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: bad\n"
        "    canonical_strategy: bogus\n"
    )
    (folder / "f.txt").write_bytes(b"x")

    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs_root)

    result = mod.hygiene_scan(str(folder))
    assert result["lifecycle_config"] is None
    assert any("canonical_strategy" in w for w in result["warnings"])


def test_scan_returns_milestone_pins(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    pins_payload = {
        "websites/guriqo-com-V10025.zip": {
            "tag": "intel-submission",
            "tagged_at": "2026-04-25T10:00:00Z",
            "note": "sent",
        }
    }
    (folder / ".milestones.json").write_text(json.dumps(pins_payload))
    (folder / "x.zip").write_bytes(b"x")

    result = mod.hygiene_scan(str(folder))
    assert len(result["milestone_pins"]) == 1
    pin = result["milestone_pins"][0]
    assert pin["relative_path"] == "websites/guriqo-com-V10025.zip"
    assert pin["tag"] == "intel-submission"


def test_scan_refuses_when_lifecycle_enabled_false(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / ".augur-lifecycle.yaml").write_text("enabled: false\n")

    with pytest.raises(mod.HygieneScanError, match="enabled: false"):
        mod.hygiene_scan(str(folder))


def test_scan_surfaces_malformed_lifecycle_as_warning(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / ".augur-lifecycle.yaml").write_text("enabled: : invalid\n")
    (folder / "x.zip").write_bytes(b"x")

    result = mod.hygiene_scan(str(folder))
    assert result["lifecycle_config"] is None
    assert any("lifecycle" in w.lower() for w in result["warnings"])


def _write_selection(runtime: Path, payload: dict) -> str:
    selection_id = payload["selection_id"]
    selection_dir = runtime / "routine-vault" / "selections"
    selection_dir.mkdir(parents=True)
    (selection_dir / f"{selection_id}.json").write_text(json.dumps(payload), encoding="utf-8")
    return selection_id


def _patch_selection_runtime(monkeypatch, runtime: Path) -> None:
    read_selection = getattr(mod, "read_selection", None)
    if read_selection is not None:
        monkeypatch.setitem(read_selection.__globals__, "get_runtime_dir", lambda: runtime)


def _patch_selection_roots(
    monkeypatch,
    *,
    docs: Path,
    vault: Path | None = None,
    project: Path | None = None,
) -> None:
    vault_root = vault or docs.parent / "vault"
    project_root = project or docs.parent / "project"
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs, raising=False)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault_root, raising=False)
    monkeypatch.setattr(mod, "get_project_root", lambda: project_root, raising=False)
    selection_mod = getattr(mod, "_ss_mod", None)
    if selection_mod is not None:
        monkeypatch.setattr(selection_mod, "get_documents_dir", lambda: docs, raising=False)
        monkeypatch.setattr(selection_mod, "get_vault_dir", lambda: vault_root, raising=False)
        monkeypatch.setattr(selection_mod, "get_project_root", lambda: project_root, raising=False)


def test_hygiene_scan_selection_reads_selection_id_and_returns_docs_and_git_targets(
    tmp_path,
    monkeypatch,
):
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    runtime = tmp_path / "runtime"
    for path in (docs, vault, runtime):
        path.mkdir()
    doc = docs / "venture" / "deck-v1.pdf"
    note = vault / "notes" / "old.md"
    doc.parent.mkdir()
    note.parent.mkdir(parents=True)
    doc.write_bytes(b"pdf")
    note.write_text("old", encoding="utf-8")
    _patch_selection_roots(monkeypatch, docs=docs, vault=vault, project=tmp_path / "project")
    _patch_selection_runtime(monkeypatch, runtime)

    selection_id = _write_selection(
        runtime,
        {
            "selection_id": "browse-sweep-20260513-120000-abcdef12",
            "source_tab": "sources",
            "filter_summary": {"search": "old"},
            "targets": [
                {
                    "kind": "docs",
                    "source_path": str(doc),
                    "source_id": "doc1",
                    "archive_mode": "docs-folder-archive",
                    "source_tab": "sources",
                    "title": "Deck",
                    "relative_path": "venture/deck-v1.pdf",
                    "root_key": "documents",
                    "repository_root": None,
                    "artifact_group": "deck",
                    "metadata": {"format": "pdf"},
                },
                {
                    "kind": "vault-notes",
                    "source_path": str(note),
                    "source_id": "note1",
                    "archive_mode": "git-aware-archive",
                    "source_tab": "notes",
                    "title": "Old",
                    "relative_path": "notes/old.md",
                    "root_key": "vault",
                    "repository_root": str(vault),
                    "metadata": {"artifact_group": "notes-old"},
                },
            ],
            "refusals": [],
        },
    )

    result = mod.hygiene_scan_selection(selection_id)

    assert result["selection_id"] == selection_id
    assert result["target_count"] == 2
    by_id = {item["source_id"]: item for item in result["files"]}
    assert by_id["doc1"]["absolute_path"] == str(doc.resolve())
    assert by_id["doc1"]["relative_path"] == "venture/deck-v1.pdf"
    assert by_id["doc1"]["archive_mode"] == "docs-folder-archive"
    assert by_id["doc1"]["artifact_group"] == "deck"
    assert by_id["doc1"]["content_hash_sha256"] == (
        "c35b21d6ca39aa7cc3b79a705d989f1a6e88b99ab43988d74048799e3db926a3"
    )
    assert by_id["doc1"]["size_bytes"] == 3
    assert by_id["doc1"]["mtime_iso"].endswith("Z")
    assert by_id["note1"]["absolute_path"] == str(note.resolve())
    assert by_id["note1"]["relative_path"] == "notes/old.md"
    assert by_id["note1"]["repository_root"] == str(vault)
    assert by_id["note1"]["archive_mode"] == "git-aware-archive"
    assert by_id["note1"]["artifact_group"] == "notes-old"
    assert result["candidates"] == result["files"]


def test_hygiene_scan_selection_refuses_stale_target_replaced_by_symlink_without_hashing(
    tmp_path,
    monkeypatch,
):
    docs = tmp_path / "docs"
    runtime = tmp_path / "runtime"
    outside = tmp_path / "outside-secret.txt"
    for path in (docs, runtime):
        path.mkdir()
    source = docs / "venture" / "deck-v1.pdf"
    source.parent.mkdir()
    source.write_bytes(b"old")
    outside.write_text("do-not-hash", encoding="utf-8")
    _patch_selection_roots(monkeypatch, docs=docs)
    _patch_selection_runtime(monkeypatch, runtime)

    selection_id = _write_selection(
        runtime,
        {
            "selection_id": "browse-sweep-20260513-120010-abcdef12",
            "source_tab": "sources",
            "filter_summary": {},
            "targets": [
                {
                    "kind": "docs",
                    "source_path": str(source),
                    "source_id": "doc-symlink",
                    "archive_mode": "docs-folder-archive",
                    "source_tab": "sources",
                    "title": "Deck",
                    "relative_path": "venture/deck-v1.pdf",
                    "root_key": "documents",
                    "repository_root": None,
                    "metadata": {},
                }
            ],
            "refusals": [],
        },
    )
    source.unlink()
    source.symlink_to(outside)

    result = mod.hygiene_scan_selection(selection_id)

    assert result["files"] == []
    assert result["candidate_count"] == 0
    assert result["refusals"][0]["source_id"] == "doc-symlink"
    assert result["refusals"][0]["status"] == "refused"
    assert result["refusals"][0]["refusal_category"] == "symlink"
    assert any("doc-symlink" in warning for warning in result["warnings"])


def test_hygiene_scan_selection_refuses_raw_target_outside_allowed_roots(
    tmp_path,
    monkeypatch,
):
    docs = tmp_path / "docs"
    vault = tmp_path / "vault"
    runtime = tmp_path / "runtime"
    outside = tmp_path / "outside" / "note.md"
    for path in (docs, vault, runtime):
        path.mkdir()
    outside.parent.mkdir()
    outside.write_text("outside", encoding="utf-8")
    _patch_selection_roots(monkeypatch, docs=docs, vault=vault, project=tmp_path / "project")
    _patch_selection_runtime(monkeypatch, runtime)

    selection_id = _write_selection(
        runtime,
        {
            "selection_id": "browse-sweep-20260513-120011-abcdef12",
            "source_tab": "notes",
            "targets": [
                {
                    "kind": "vault-notes",
                    "source_path": str(outside),
                    "source_id": "outside-note",
                    "archive_mode": "git-aware-archive",
                    "source_tab": "notes",
                    "title": "Outside",
                    "relative_path": "notes/outside.md",
                    "root_key": "vault",
                    "repository_root": str(vault),
                    "metadata": {},
                }
            ],
            "refusals": [],
        },
    )

    result = mod.hygiene_scan_selection(selection_id)

    assert result["files"] == []
    assert result["refusals"][0]["source_id"] == "outside-note"
    assert result["refusals"][0]["refusal_category"] == "outside_allowed_roots"
