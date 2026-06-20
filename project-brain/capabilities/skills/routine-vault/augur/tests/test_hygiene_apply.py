"""Tests for hygiene_apply — the atomic destructive primitive."""
from __future__ import annotations

# TODO_CLEANUP: This file is 1258 lines — consider splitting into smaller modules
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "hygiene_apply.py"
_SPEC = importlib.util.spec_from_file_location("hygiene_apply_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
sys.modules["hygiene_apply_under_test"] = mod
_SPEC.loader.exec_module(mod)


def _setup_docs(tmp_path, monkeypatch):
    docs = tmp_path / "au-docs"
    docs.mkdir()
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs)
    return docs


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


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        shell=False,
        text=True,
        capture_output=True,
        check=False,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        shell=False,
        text=True,
        capture_output=True,
        check=False,
    ).returncode == 0
    assert _git(repo, "config", "user.email", "test@example.com").returncode == 0
    assert _git(repo, "config", "user.name", "Test User").returncode == 0
    return repo


def _commit_file(repo: Path, rel_path: str, content: str = "hello\n") -> Path:
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    assert _git(repo, "add", rel_path).returncode == 0
    assert _git(repo, "commit", "-m", f"add {rel_path}").returncode == 0
    return path


def _init_bare_remote(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    result = subprocess.run(
        ["git", "init", "--bare", str(remote)],
        shell=False,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return remote


def _configure_origin(repo: Path, remote: Path) -> None:
    assert _git(repo, "remote", "add", "origin", str(remote)).returncode == 0
    branch = _git(repo, "branch", "--show-current").stdout.strip()
    assert branch
    assert _git(repo, "push", "-u", "origin", branch).returncode == 0


def test_refuses_unsupported_root(tmp_path, monkeypatch):
    _setup_docs(tmp_path, monkeypatch)
    with pytest.raises(mod.HygieneApplyError, match="root"):
        mod.hygiene_apply(root="vault", moves=[], dry_run=True)


def test_empty_moves_dry_run_returns_empty_result(tmp_path, monkeypatch):
    _setup_docs(tmp_path, monkeypatch)
    result = mod.hygiene_apply(root="docs", moves=[], dry_run=True)
    assert result["dry_run"] is True
    assert result["moves"] == []
    assert result["total_bytes_archived"] == 0
    assert result["paths_written"] == []
    assert result["lifecycle_updates"] == []


def test_hygiene_apply_lifecycle_updates_writes_yaml_before_moves(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    folder = docs_root / "ws"
    folder.mkdir(parents=True)
    (folder / "x.zip").write_bytes(b"x")

    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs_root)

    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "ws/x.zip", "reason": "test"}],
        dry_run=False,
        lifecycle_updates=[
            {
                "folder": "ws",
                "known_group": {
                    "name": "g1",
                    "canonical_strategy": "highest_version",
                    "pattern": "x-*.zip",
                    "decided_at": "2026-05-12T14:30:00Z",
                    "decided_by": "gsannikov",
                },
            }
        ],
    )
    yaml_path = folder / ".augur-lifecycle.yaml"
    assert yaml_path.exists()
    data = yaml.safe_load(yaml_path.read_text())
    assert data["known_groups"][0]["name"] == "g1"
    assert result["moves"][0]["status"] == "succeeded"
    assert result["lifecycle_updates"][0]["status"] == "written"


def test_hygiene_apply_lifecycle_updates_dry_run_writes_nothing(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    folder = docs_root / "ws"
    folder.mkdir(parents=True)
    (folder / "x.zip").write_bytes(b"x")

    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs_root)
    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "ws/x.zip", "reason": "test"}],
        dry_run=True,
        lifecycle_updates=[
            {
                "folder": "ws",
                "known_group": {
                    "name": "g",
                    "canonical_strategy": "highest_version",
                    "pattern": "x-*",
                },
            }
        ],
    )
    assert not (folder / ".augur-lifecycle.yaml").exists()
    assert result["lifecycle_updates"][0]["status"] == "would_succeed"


def test_hygiene_apply_lifecycle_updates_collision_refused(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    folder = docs_root / "ws"
    folder.mkdir(parents=True)
    (folder / "x.zip").write_bytes(b"x")
    (folder / ".augur-lifecycle.yaml").write_text(
        "known_groups:\n"
        "  - name: dup\n"
        "    canonical_strategy: highest_version\n"
        "    pattern: 'x-*'\n"
    )

    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs_root)
    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "ws/x.zip", "reason": "test"}],
        dry_run=False,
        lifecycle_updates=[
            {
                "folder": "ws",
                "known_group": {
                    "name": "dup",
                    "canonical_strategy": "not_a_group",
                    "members": ["a"],
                },
            }
        ],
    )
    assert result["lifecycle_updates"][0]["status"] == "refused"
    assert result["lifecycle_updates"][0]["refusal_category"] == "lifecycle_collision"
    assert result["moves"][0]["status"] == "succeeded"


def test_hygiene_apply_lifecycle_updates_folder_missing(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    monkeypatch.setattr(mod, "get_documents_dir", lambda: docs_root)
    result = mod.hygiene_apply(
        root="docs",
        moves=[],
        dry_run=False,
        lifecycle_updates=[
            {
                "folder": "nonexistent",
                "known_group": {
                    "name": "g",
                    "canonical_strategy": "highest_version",
                    "pattern": "x",
                },
            }
        ],
    )
    assert result["lifecycle_updates"][0]["status"] == "refused"
    assert result["lifecycle_updates"][0]["refusal_category"] == "folder_missing"


def test_dry_run_validates_but_does_not_move(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    src = folder / "x.zip"
    src.write_bytes(b"hello")

    result = mod.hygiene_apply(
        root="docs",
        moves=[{
            "from": "websites/x.zip",
            "reason": "test",
            "artifact_group": "test-group",
        }],
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert len(result["moves"]) == 1
    move = result["moves"][0]
    assert move["status"] == "would_succeed"
    assert move["from"] == "websites/x.zip"
    assert move["to"] == "websites/.archive/x.zip"
    # File NOT moved
    assert src.exists()
    assert not (folder / ".archive" / "x.zip").exists()


def test_refuses_never_touch_source(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "package-lock.json").write_bytes(b"{}")

    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/package-lock.json", "reason": "x"}],
        dry_run=True,
    )
    move = result["moves"][0]
    assert move["status"] == "would_refuse"
    assert move["refusal_category"] == "never_touch"


def test_refuses_symlink_source(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    target = folder / "real.zip"
    target.write_bytes(b"x")
    link = folder / "link.zip"
    os.symlink(target, link)

    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/link.zip", "reason": "x"}],
        dry_run=True,
    )
    move = result["moves"][0]
    assert move["status"] == "would_refuse"
    assert move["refusal_category"] == "symlink"


def test_refuses_milestone_pinned_source(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "pinned.zip").write_bytes(b"x")
    pins = {
        "websites/pinned.zip": {
            "tag": "intel-submission",
            "tagged_at": "2026-04-25T10:00:00Z",
        }
    }
    (folder / ".milestones.json").write_text(json.dumps(pins))

    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/pinned.zip", "reason": "x"}],
        dry_run=True,
    )
    move = result["moves"][0]
    assert move["status"] == "would_refuse"
    assert move["refusal_category"] == "milestone_pinned"


def test_refuses_deploy_root_source(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")
    (folder / ".augur-lifecycle.yaml").write_text("deploy_root: true\n")

    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "x"}],
        dry_run=True,
    )
    move = result["moves"][0]
    assert move["status"] == "would_refuse"
    assert move["refusal_category"] == "deploy_root"


def test_refuses_source_outside_store_root(tmp_path, monkeypatch):
    _setup_docs(tmp_path, monkeypatch)
    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "../escape.zip", "reason": "x"}],
        dry_run=True,
    )
    move = result["moves"][0]
    assert move["status"] == "would_refuse"
    assert move["refusal_category"] == "outside_store"


def test_refusal_of_one_move_does_not_abort_others(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "good.zip").write_bytes(b"x")
    (folder / "package-lock.json").write_bytes(b"{}")

    result = mod.hygiene_apply(
        root="docs",
        moves=[
            {"from": "websites/package-lock.json", "reason": "x"},
            {"from": "websites/good.zip", "reason": "x"},
        ],
        dry_run=True,
    )
    assert result["moves"][0]["status"] == "would_refuse"
    assert result["moves"][1]["status"] == "would_succeed"


def test_real_apply_moves_file_to_archive(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    src = folder / "x.zip"
    src.write_bytes(b"payload")

    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale", "artifact_group": "g"}],
        dry_run=False,
    )

    assert result["dry_run"] is False
    move = result["moves"][0]
    assert move["status"] == "succeeded"
    assert not src.exists()
    dest = folder / ".archive" / "x.zip"
    assert dest.exists()
    assert dest.read_bytes() == b"payload"
    assert result["total_bytes_archived"] == len(b"payload")


def test_apply_creates_archive_directory(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")

    assert not (folder / ".archive").exists()
    mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale"}],
        dry_run=False,
    )
    assert (folder / ".archive").is_dir()


def test_destination_collision_appends_dup_suffix(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    archive = folder / ".archive"
    archive.mkdir()
    # Pre-existing archive entry with the same basename
    (archive / "x.zip").write_bytes(b"older")
    src = folder / "x.zip"
    src.write_bytes(b"newer-but-second-archived")

    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale"}],
        dry_run=False,
    )
    move = result["moves"][0]
    assert move["status"] == "succeeded"
    # Destination should end with .dup-<shorthash>
    assert ".dup-" in move["to"]
    # Original archive entry untouched
    assert (archive / "x.zip").read_bytes() == b"older"
    # Newly-archived entry exists under the dup name
    dup_dest = docs / move["to"]
    assert dup_dest.read_bytes() == b"newer-but-second-archived"


def test_real_apply_refuses_archive_directory_symlink_without_moving_outside_docs(
    tmp_path,
    monkeypatch,
):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    outside_archive = tmp_path / "outside-archive"
    outside_archive.mkdir()
    archive = folder / ".archive"
    archive.symlink_to(outside_archive, target_is_directory=True)
    src = folder / "x.zip"
    src.write_bytes(b"payload")

    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale"}],
        dry_run=False,
    )

    move = result["moves"][0]
    assert move["status"] == "refused"
    assert move["refusal_category"] == "archive_parent_symlink"
    assert src.exists()
    assert src.read_bytes() == b"payload"
    assert archive.is_symlink()
    assert not (outside_archive / "x.zip").exists()
    assert result["total_bytes_archived"] == 0
    assert result["paths_written"] == []


def test_real_apply_refuses_archive_directory_file_collision_without_crashing(
    tmp_path,
    monkeypatch,
):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    archive = folder / ".archive"
    archive.write_text("not a directory\n", encoding="utf-8")
    src = folder / "x.zip"
    src.write_bytes(b"payload")

    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale"}],
        dry_run=False,
    )

    move = result["moves"][0]
    assert move["status"] == "refused"
    assert move["refusal_category"] == "archive_parent_not_directory"
    assert src.exists()
    assert archive.read_text(encoding="utf-8") == "not a directory\n"
    assert result["total_bytes_archived"] == 0
    assert result["paths_written"] == []


def test_manifest_jsonl_entry_written_after_move(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")

    mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale", "artifact_group": "g"}],
        dry_run=False,
    )

    manifest = folder / ".archive" / "_manifest.jsonl"
    assert manifest.exists()
    lines = manifest.read_text().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["from"] == "websites/x.zip"
    assert entry["to"] == "websites/.archive/x.zip"
    assert entry["reason"] == "stale"
    assert entry["artifact_group"] == "g"
    assert "archived_at" in entry
    assert "apply_run_id" in entry


def test_manifest_is_append_only_across_calls(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "a.zip").write_bytes(b"a")
    (folder / "b.zip").write_bytes(b"b")

    mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/a.zip", "reason": "stale"}],
        dry_run=False,
    )
    mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/b.zip", "reason": "stale"}],
        dry_run=False,
    )

    manifest = folder / ".archive" / "_manifest.jsonl"
    lines = manifest.read_text().splitlines()
    assert len(lines) == 2
    entries = [json.loads(line) for line in lines]
    assert entries[0]["from"] == "websites/a.zip"
    assert entries[1]["from"] == "websites/b.zip"


def test_manifest_failure_rolls_back_rename(tmp_path, monkeypatch):
    """If manifest write fails, the move is reverted (the file is moved back)."""
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    src = folder / "x.zip"
    src.write_bytes(b"payload")

    # Patch _append_manifest to raise mid-flight
    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(mod, "_append_manifest", boom)

    result = mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale"}],
        dry_run=False,
    )

    move = result["moves"][0]
    assert move["status"] == "refused"
    assert move["refusal_category"] == "manifest_write_failed"
    # The source has been restored
    assert src.exists()
    assert src.read_bytes() == b"payload"
    # The destination does not exist
    assert not (folder / ".archive" / "x.zip").exists()


def test_augur_ignore_written_at_archive_root(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")

    mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale"}],
        dry_run=False,
    )

    augur_ignore = folder / ".archive" / ".augur-ignore"
    assert augur_ignore.exists()
    assert augur_ignore.read_text() == "*\n"


def test_augur_ignore_not_overwritten_if_user_modified(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    archive = folder / ".archive"
    archive.mkdir()
    (archive / ".augur-ignore").write_text("# custom user content\n*\n")
    (folder / "x.zip").write_bytes(b"x")

    mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale"}],
        dry_run=False,
    )

    assert (archive / ".augur-ignore").read_text() == "# custom user content\n*\n"


def test_gitignore_gets_archive_entry_appended(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")
    (docs / ".gitignore").write_text("node_modules/\n")

    mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/x.zip", "reason": "stale"}],
        dry_run=False,
    )

    content = (docs / ".gitignore").read_text()
    assert "node_modules/" in content
    assert ".archive/" in content


def test_gitignore_archive_entry_idempotent(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "a.zip").write_bytes(b"a")
    (folder / "b.zip").write_bytes(b"b")
    (docs / ".gitignore").write_text(".archive/\n")

    mod.hygiene_apply(root="docs", moves=[{"from": "websites/a.zip", "reason": "x"}], dry_run=False)
    mod.hygiene_apply(root="docs", moves=[{"from": "websites/b.zip", "reason": "x"}], dry_run=False)

    lines = [ln for ln in (docs / ".gitignore").read_text().splitlines() if ln.strip()]
    assert lines.count(".archive/") == 1


def test_gitignore_created_if_absent(tmp_path, monkeypatch):
    docs = _setup_docs(tmp_path, monkeypatch)
    folder = docs / "websites"
    folder.mkdir()
    (folder / "x.zip").write_bytes(b"x")

    mod.hygiene_apply(root="docs", moves=[{"from": "websites/x.zip", "reason": "x"}], dry_run=False)

    gi = docs / ".gitignore"
    assert gi.exists()
    assert ".archive/" in gi.read_text()


def test_hygiene_apply_selection_docs_archive_reuses_existing_manifest_flow(
    tmp_path,
    monkeypatch,
):
    docs_root = tmp_path / "docs"
    runtime = tmp_path / "runtime"
    docs_root.mkdir()
    runtime.mkdir()
    source = docs_root / "venture" / "old.pdf"
    source.parent.mkdir()
    source.write_bytes(b"old")
    _patch_selection_roots(monkeypatch, docs=docs_root)
    _patch_selection_runtime(monkeypatch, runtime)

    selection_id = _write_selection(
        runtime,
        {
            "selection_id": "browse-sweep-20260513-120001-abcdef12",
            "source_tab": "sources",
            "targets": [
                {
                    "kind": "docs",
                    "source_path": str(source),
                    "source_id": "doc1",
                    "archive_mode": "docs-folder-archive",
                    "source_tab": "sources",
                    "title": "Old",
                    "relative_path": "venture/old.pdf",
                    "root_key": "documents",
                    "repository_root": None,
                    "metadata": {},
                }
            ],
        },
    )

    result = mod.hygiene_apply_selection(
        selection_id,
        moves=[{"source_id": "doc1", "reason": "superseded", "artifact_group": "deck"}],
        dry_run=False,
        apply_run_id="run-docs",
    )

    assert result["selection_id"] == selection_id
    assert result["moves"][0]["status"] == "succeeded"
    assert result["moves"][0]["source_id"] == "doc1"
    assert result["moves"][0]["archive_mode"] == "docs-folder-archive"
    assert not source.exists()
    assert (docs_root / "venture" / ".archive" / "old.pdf").exists()
    manifest = docs_root / "venture" / ".archive" / "_manifest.jsonl"
    assert manifest.exists()
    manifest_entry = json.loads(manifest.read_text().splitlines()[0])
    assert manifest_entry["from"] == "venture/old.pdf"
    assert manifest_entry["apply_run_id"] == "run-docs"
    assert result["archive_records"] == [
        {
            "archive_source": "sweep",
            "selection_id": selection_id,
            "source_id": "doc1",
            "source_tab": "sources",
            "kind": "docs",
            "archive_mode": "docs-folder-archive",
            "original_path": str(source.resolve()),
            "relative_path": "venture/old.pdf",
            "archived_path": "venture/.archive/old.pdf",
            "repository_root": None,
            "git_action": None,
            "reason": "superseded",
            "artifact_group": "deck",
            "apply_run_id": "run-docs",
            "recovery_hint": None,
        }
    ]


def test_hygiene_apply_selection_git_aware_uses_git_history_purge(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    remote = _init_bare_remote(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")
    _configure_origin(repo, remote)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    _patch_selection_roots(monkeypatch, docs=tmp_path / "docs", vault=repo, project=tmp_path / "project")
    _patch_selection_runtime(monkeypatch, runtime)

    selection_id = _write_selection(
        runtime,
        {
            "selection_id": "browse-sweep-20260513-120002-abcdef12",
            "source_tab": "notes",
            "targets": [
                {
                    "kind": "vault-notes",
                    "source_path": str(source),
                    "source_id": "note1",
                    "archive_mode": "git-aware-archive",
                    "source_tab": "notes",
                    "title": "Page",
                    "relative_path": "notes/topic/page.md",
                    "root_key": "vault",
                    "repository_root": str(repo),
                    "metadata": {},
                }
            ],
        },
    )

    result = mod.hygiene_apply_selection(
        selection_id,
        moves=[{"source_id": "note1", "reason": "superseded", "artifact_group": "topic"}],
        dry_run=False,
        apply_run_id="run-git",
    )

    assert result["moves"][0]["status"] == "succeeded"
    assert result["moves"][0]["archive_mode"] == "git-history-purge"
    assert result["moves"][0]["git_action"] == "mv+purge"
    assert result["moves"][0]["archive_commit"]
    assert result["moves"][0]["purge_commit"]
    assert not source.exists()
    assert not (repo / result["moves"][0]["archived_path"]).exists()
    assert (repo / "archive" / "_ledger" / "sweep.jsonl").is_file()
    assert _git(repo, "status", "--porcelain").stdout == ""
    assert result["archive_records"][0]["archive_mode"] == "git-history-purge"
    assert result["archive_records"][0]["archived_path"] == result["moves"][0]["archived_path"]
    assert result["archive_records"][0]["apply_run_id"] == "run-git"
    assert result["archive_records"][0]["archive_commit"] == result["moves"][0]["archive_commit"]
    assert result["archive_records"][0]["purge_commit"] == result["moves"][0]["purge_commit"]


def test_hygiene_apply_selection_git_partial_result_needs_attention(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    source = _commit_file(repo, "notes/topic/page.md")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    _patch_selection_roots(monkeypatch, docs=tmp_path / "docs", vault=repo, project=tmp_path / "project")
    _patch_selection_runtime(monkeypatch, runtime)

    selection_id = _write_selection(
        runtime,
        {
            "selection_id": "browse-sweep-20260513-120102-abcdef12",
            "source_tab": "notes",
            "targets": [
                {
                    "kind": "vault-notes",
                    "source_path": str(source),
                    "source_id": "note-partial",
                    "archive_mode": "git-aware-archive",
                    "source_tab": "notes",
                    "title": "Page",
                    "relative_path": "notes/topic/page.md",
                    "root_key": "vault",
                    "repository_root": str(repo),
                    "metadata": {},
                }
            ],
        },
    )

    def fake_apply_git_history_purge_archive(**kwargs):
        return {
            "status": "partial",
            "failure_phase": "archive_push",
            "archive_mode": "git-history-purge",
            "git_action": "mv+purge",
            "original_path": str(source),
            "archived_path": "archive/sweep/notes/2026-05-14/notes/topic/page.md",
            "repo_root": str(repo),
            "archive_commit": "abc123",
            "archive_pushed": False,
            "purged": False,
            "purge_commit": None,
            "purge_pushed": False,
            "reason": kwargs["reason"],
            "artifact_group": kwargs["artifact_group"],
            "apply_run_id": kwargs["apply_run_id"],
            "recovery_hint": "do not delete before push",
        }

    monkeypatch.setattr(
        mod,
        "_load_apply_git_history_purge_archive",
        lambda: fake_apply_git_history_purge_archive,
    )

    result = mod.hygiene_apply_selection(
        selection_id,
        moves=[{"source_id": "note-partial", "reason": "superseded"}],
        dry_run=False,
        apply_run_id="run-partial",
    )

    assert result["moves"][0]["status"] == "needs_attention"
    assert result["moves"][0]["failure_phase"] == "archive_push"
    assert result["archive_records"] == []


def test_hygiene_apply_selection_refuses_unknown_target_without_moving(
    tmp_path,
    monkeypatch,
):
    docs_root = tmp_path / "docs"
    runtime = tmp_path / "runtime"
    docs_root.mkdir()
    runtime.mkdir()
    source = docs_root / "venture" / "old.pdf"
    source.parent.mkdir()
    source.write_bytes(b"old")
    _patch_selection_roots(monkeypatch, docs=docs_root)
    _patch_selection_runtime(monkeypatch, runtime)

    selection_id = _write_selection(
        runtime,
        {
            "selection_id": "browse-sweep-20260513-120003-abcdef12",
            "source_tab": "sources",
            "targets": [
                {
                    "kind": "docs",
                    "source_path": str(source),
                    "source_id": "doc1",
                    "archive_mode": "docs-folder-archive",
                    "source_tab": "sources",
                    "title": "Old",
                    "relative_path": "venture/old.pdf",
                    "root_key": "documents",
                    "repository_root": None,
                    "metadata": {},
                }
            ],
        },
    )

    result = mod.hygiene_apply_selection(
        selection_id,
        moves=[{"source_id": "missing", "reason": "superseded"}],
        dry_run=False,
    )

    assert result["moves"] == [
        {
            "source_id": "missing",
            "reason": "superseded",
            "status": "refused",
            "refusal_category": "unknown_target",
        }
    ]
    assert result["archive_records"] == []
    assert source.exists()
    assert not (docs_root / "venture" / ".archive").exists()


def test_hygiene_apply_selection_dry_run_does_not_move_docs_or_git_targets(
    tmp_path,
    monkeypatch,
):
    docs_root = tmp_path / "docs"
    runtime = tmp_path / "runtime"
    docs_root.mkdir()
    runtime.mkdir()
    doc = docs_root / "venture" / "old.pdf"
    doc.parent.mkdir()
    doc.write_bytes(b"old")
    repo = _init_repo(tmp_path)
    note = _commit_file(repo, "notes/topic/page.md")
    _patch_selection_roots(monkeypatch, docs=docs_root, vault=repo, project=tmp_path / "project")
    _patch_selection_runtime(monkeypatch, runtime)

    selection_id = _write_selection(
        runtime,
        {
            "selection_id": "browse-sweep-20260513-120004-abcdef12",
            "source_tab": "sources",
            "targets": [
                {
                    "kind": "docs",
                    "source_path": str(doc),
                    "source_id": "doc1",
                    "archive_mode": "docs-folder-archive",
                    "source_tab": "sources",
                    "title": "Old",
                    "relative_path": "venture/old.pdf",
                    "root_key": "documents",
                    "repository_root": None,
                    "metadata": {},
                },
                {
                    "kind": "vault-notes",
                    "source_path": str(note),
                    "source_id": "note1",
                    "archive_mode": "git-aware-archive",
                    "source_tab": "notes",
                    "title": "Page",
                    "relative_path": "notes/topic/page.md",
                    "root_key": "vault",
                    "repository_root": str(repo),
                    "metadata": {},
                },
            ],
        },
    )

    result = mod.hygiene_apply_selection(
        selection_id,
        moves=[
            {"source_id": "doc1", "reason": "superseded"},
            {"source_id": "note1", "reason": "superseded"},
        ],
        dry_run=True,
        apply_run_id="run-dry",
    )

    by_source = {move["source_id"]: move for move in result["moves"]}
    assert by_source["doc1"]["status"] == "would_succeed"
    assert by_source["doc1"]["archive_mode"] == "docs-folder-archive"
    assert by_source["note1"]["status"] == "would_succeed"
    assert by_source["note1"]["archive_mode"] == "git-history-purge"
    assert by_source["note1"]["git_action"] == "mv+purge"
    assert result["archive_records"] == []
    assert doc.exists()
    assert not (docs_root / "venture" / ".archive").exists()
    assert note.exists()
    assert not (repo / "archive").exists()
    assert _git(repo, "status", "--porcelain").stdout == ""


def test_hygiene_apply_selection_git_dry_run_refuses_existing_archive_destination(
    tmp_path,
    monkeypatch,
):
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    repo = _init_repo(tmp_path)
    note = _commit_file(repo, "notes/topic/page.md")
    today = datetime.now(timezone.utc).date().isoformat()
    archived_rel = f"archive/sweep/notes/{today}/notes/topic/page.md"
    archived = repo / archived_rel
    archived.parent.mkdir(parents=True)
    archived.write_text("already archived\n", encoding="utf-8")
    _patch_selection_roots(monkeypatch, docs=docs_root, vault=repo, project=tmp_path / "project")

    selection = {
        "selection_id": "browse-sweep-20260513-120024-abcdef12",
        "source_tab": "notes",
        "targets": [
            {
                "kind": "vault-notes",
                "source_path": str(note),
                "source_id": "note-collision",
                "archive_mode": "git-aware-archive",
                "source_tab": "notes",
                "title": "Page",
                "relative_path": "notes/topic/page.md",
                "root_key": "vault",
                "repository_root": str(repo),
                "metadata": {},
            }
        ],
        "refusals": [],
    }

    dry_run = mod.hygiene_apply_selection(
        selection,
        moves=[{"source_id": "note-collision", "reason": "superseded"}],
        dry_run=True,
        apply_run_id="run-dry-collision",
    )
    real = mod.hygiene_apply_selection(
        selection,
        moves=[{"source_id": "note-collision", "reason": "superseded"}],
        dry_run=False,
        apply_run_id="run-real-collision",
    )

    assert dry_run["moves"][0]["status"] == "would_refuse"
    assert dry_run["moves"][0]["refusal_category"] == "archive_destination_exists"
    assert dry_run["moves"][0]["archive_mode"] == "git-history-purge"
    assert real["moves"][0]["status"] == "refused"
    assert real["moves"][0]["refusal_category"] == "archive_destination_exists"
    assert note.exists()
    assert archived.read_text(encoding="utf-8") == "already archived\n"
    assert _git(repo, "status", "--porcelain", "--", "notes/topic/page.md").stdout == ""


def test_hygiene_apply_selection_accepts_task4_selection_keyword_wrapper(
    tmp_path,
    monkeypatch,
):
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    source = docs_root / "venture" / "old.pdf"
    source.parent.mkdir()
    source.write_bytes(b"old")
    _patch_selection_roots(monkeypatch, docs=docs_root)

    selection = {
        "selection_id": "browse-sweep-20260513-120020-abcdef12",
        "source_tab": "sources",
        "targets": [
            {
                "kind": "docs",
                "source_path": str(source),
                "source_id": "doc-wrapper",
                "archive_mode": "docs-folder-archive",
                "source_tab": "sources",
                "title": "Old",
                "relative_path": "venture/old.pdf",
                "root_key": "documents",
                "repository_root": None,
                "metadata": {},
            }
        ],
        "refusals": [],
    }

    result = mod.hygiene_apply_selection(
        selection=selection,
        moves=[{"source_id": "doc-wrapper", "reason": "superseded"}],
        dry_run=True,
    )

    assert result["selection_id"] == selection["selection_id"]
    assert result["moves"][0]["status"] == "would_succeed"
    assert result["moves"][0]["source_id"] == "doc-wrapper"
    assert source.exists()


def test_hygiene_apply_selection_refuses_invalid_git_target_during_dry_run(
    tmp_path,
    monkeypatch,
):
    docs_root = tmp_path / "docs"
    vault = tmp_path / "vault"
    outside = tmp_path / "outside" / "note.md"
    docs_root.mkdir()
    vault.mkdir()
    outside.parent.mkdir()
    outside.write_text("outside", encoding="utf-8")
    _patch_selection_roots(monkeypatch, docs=docs_root, vault=vault)
    selection = {
        "selection_id": "browse-sweep-20260513-120021-abcdef12",
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
    }

    result = mod.hygiene_apply_selection(
        selection,
        moves=[{"source_id": "outside-note", "reason": "bad root"}],
        dry_run=True,
    )

    assert result["moves"] == [
        {
            "source_id": "outside-note",
            "source_path": str(outside),
            "reason": "bad root",
            "status": "would_refuse",
            "refusal_category": "outside_allowed_roots",
            "archive_mode": "git-aware-archive",
            "kind": "vault-notes",
        }
    ]
    assert outside.exists()


def test_hygiene_apply_selection_refuses_symlink_replacement_in_dry_run_and_real_apply(
    tmp_path,
    monkeypatch,
):
    docs_root = tmp_path / "docs"
    outside = tmp_path / "outside.txt"
    docs_root.mkdir()
    source = docs_root / "venture" / "old.pdf"
    source.parent.mkdir()
    source.write_bytes(b"old")
    outside.write_text("outside", encoding="utf-8")
    _patch_selection_roots(monkeypatch, docs=docs_root)
    selection = {
        "selection_id": "browse-sweep-20260513-120022-abcdef12",
        "source_tab": "sources",
        "targets": [
            {
                "kind": "docs",
                "source_path": str(source),
                "source_id": "doc-symlink",
                "archive_mode": "docs-folder-archive",
                "source_tab": "sources",
                "title": "Old",
                "relative_path": "venture/old.pdf",
                "root_key": "documents",
                "repository_root": None,
                "metadata": {},
            }
        ],
        "refusals": [],
    }
    source.unlink()
    source.symlink_to(outside)

    dry_run = mod.hygiene_apply_selection(
        selection,
        moves=[{"source_id": "doc-symlink", "reason": "superseded"}],
        dry_run=True,
    )
    real = mod.hygiene_apply_selection(
        selection,
        moves=[{"source_id": "doc-symlink", "reason": "superseded"}],
        dry_run=False,
    )

    assert dry_run["moves"][0]["status"] == "would_refuse"
    assert real["moves"][0]["status"] == "refused"
    assert dry_run["moves"][0]["refusal_category"] == "symlink"
    assert real["moves"][0]["refusal_category"] == "symlink"
    assert source.is_symlink()
    assert outside.read_text(encoding="utf-8") == "outside"


def test_hygiene_apply_selection_unknown_target_uses_would_refuse_in_dry_run(
    tmp_path,
    monkeypatch,
):
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    _patch_selection_roots(monkeypatch, docs=docs_root)
    selection = {
        "selection_id": "browse-sweep-20260513-120023-abcdef12",
        "source_tab": "sources",
        "targets": [],
        "refusals": [],
    }

    result = mod.hygiene_apply_selection(
        selection,
        moves=[{"source_id": "missing", "reason": "not selected"}],
        dry_run=True,
    )

    assert result["moves"] == [
        {
            "source_id": "missing",
            "reason": "not selected",
            "status": "would_refuse",
            "refusal_category": "unknown_target",
        }
    ]


def test_hygiene_apply_docs_only_import_does_not_load_git_archive(tmp_path, monkeypatch):
    real_spec_from_file_location = importlib.util.spec_from_file_location

    def refusing_git_archive_spec(name, location, *args, **kwargs):
        if str(location).endswith("git_archive.py"):
            raise AssertionError("git_archive loaded during docs-only import")
        return real_spec_from_file_location(name, location, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "spec_from_file_location", refusing_git_archive_spec)
    spec = importlib.util.spec_from_file_location("hygiene_apply_docs_only_under_test", _MODULE_PATH)
    assert spec and spec.loader
    docs_only_mod = importlib.util.module_from_spec(spec)
    sys.modules["hygiene_apply_docs_only_under_test"] = docs_only_mod
    spec.loader.exec_module(docs_only_mod)

    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    source = docs_root / "venture" / "old.pdf"
    source.parent.mkdir()
    source.write_bytes(b"old")
    monkeypatch.setattr(docs_only_mod, "get_documents_dir", lambda: docs_root)

    result = docs_only_mod.hygiene_apply(
        root="docs",
        moves=[{"from": "venture/old.pdf", "reason": "docs only"}],
        dry_run=True,
    )

    assert result["moves"][0]["status"] == "would_succeed"
