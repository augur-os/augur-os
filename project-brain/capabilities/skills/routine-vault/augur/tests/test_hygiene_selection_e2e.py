"""Selection scan/apply end-to-end coverage for Browse sweep targets."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


_SCAN_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "hygiene_scan.py"
_SCAN_SPEC = importlib.util.spec_from_file_location("hygiene_selection_scan_under_test", _SCAN_MODULE_PATH)
assert _SCAN_SPEC and _SCAN_SPEC.loader
scan_mod = importlib.util.module_from_spec(_SCAN_SPEC)
sys.modules["hygiene_selection_scan_under_test"] = scan_mod
_SCAN_SPEC.loader.exec_module(scan_mod)

_APPLY_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "hygiene_apply.py"
_APPLY_SPEC = importlib.util.spec_from_file_location("hygiene_selection_apply_under_test", _APPLY_MODULE_PATH)
assert _APPLY_SPEC and _APPLY_SPEC.loader
apply_mod = importlib.util.module_from_spec(_APPLY_SPEC)
sys.modules["hygiene_selection_apply_under_test"] = apply_mod
_APPLY_SPEC.loader.exec_module(apply_mod)


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


def _write_selection(runtime: Path, payload: dict) -> str:
    selection_id = payload["selection_id"]
    selection_dir = runtime / "routine-vault" / "selections"
    selection_dir.mkdir(parents=True)
    (selection_dir / f"{selection_id}.json").write_text(json.dumps(payload), encoding="utf-8")
    return selection_id


def _patch_selection_runtime(monkeypatch, runtime: Path) -> None:
    for module in (scan_mod, apply_mod):
        read_selection = getattr(module, "read_selection", None)
        if read_selection is not None:
            monkeypatch.setitem(read_selection.__globals__, "get_runtime_dir", lambda: runtime)


def _patch_selection_roots(
    monkeypatch,
    *,
    docs: Path,
    vault: Path,
    project: Path,
) -> None:
    for module in (scan_mod, apply_mod):
        monkeypatch.setattr(module, "get_documents_dir", lambda: docs, raising=False)
        monkeypatch.setattr(module, "get_vault_dir", lambda: vault, raising=False)
        monkeypatch.setattr(module, "get_project_root", lambda: project, raising=False)
        selection_mod = getattr(module, "_ss_mod", None)
        if selection_mod is not None:
            monkeypatch.setattr(selection_mod, "get_documents_dir", lambda: docs, raising=False)
            monkeypatch.setattr(selection_mod, "get_vault_dir", lambda: vault, raising=False)
            monkeypatch.setattr(selection_mod, "get_project_root", lambda: project, raising=False)


def test_selection_scan_dry_run_and_apply_with_task1_archive_modes(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    runtime = tmp_path / "runtime"
    docs_root.mkdir()
    runtime.mkdir()
    doc = docs_root / "sources" / "old.pdf"
    doc.parent.mkdir()
    doc.write_bytes(b"old")
    repo = _init_repo(tmp_path)
    remote = _init_bare_remote(tmp_path)
    note = _commit_file(repo, "notes/topic/page.md")
    _configure_origin(repo, remote)
    _patch_selection_roots(
        monkeypatch,
        docs=docs_root,
        vault=repo,
        project=tmp_path / "project",
    )
    _patch_selection_runtime(monkeypatch, runtime)

    selection_id = _write_selection(
        runtime,
        {
            "selection_id": "browse-sweep-20260513-120005-abcdef12",
            "source_tab": "sources",
            "filter_summary": {"search": "old"},
            "targets": [
                {
                    "kind": "docs",
                    "source_path": str(doc),
                    "source_id": "doc1",
                    "archive_mode": "docs-archive",
                    "source_tab": "sources",
                    "title": "Old PDF",
                    "relative_path": "sources/old.pdf",
                    "root_key": "documents",
                    "repository_root": None,
                    "metadata": {},
                },
                {
                    "kind": "vault-notes",
                    "source_path": str(note),
                    "source_id": "note1",
                    "archive_mode": "git-aware",
                    "source_tab": "notes",
                    "title": "Page",
                    "relative_path": "notes/topic/page.md",
                    "root_key": "vault",
                    "repository_root": str(repo),
                    "metadata": {},
                },
            ],
            "refusals": [],
        },
    )

    scan = scan_mod.hygiene_scan_selection(selection_id)
    assert [item["source_id"] for item in scan["files"]] == ["doc1", "note1"]

    dry_run = apply_mod.hygiene_apply_selection(
        selection_id,
        moves=[
            {"source_id": "doc1", "reason": "superseded"},
            {"source_id": "note1", "reason": "superseded"},
        ],
        dry_run=True,
    )
    assert [move["status"] for move in dry_run["moves"]] == ["would_succeed", "would_succeed"]
    assert doc.exists()
    assert note.exists()

    result = apply_mod.hygiene_apply_selection(
        selection_id,
        moves=[
            {"source_id": "doc1", "reason": "superseded"},
            {"source_id": "note1", "reason": "superseded"},
        ],
        dry_run=False,
        apply_run_id="run-e2e",
    )

    assert [move["status"] for move in result["moves"]] == ["succeeded", "succeeded"]
    assert not doc.exists()
    assert (docs_root / "sources" / ".archive" / "old.pdf").exists()
    assert not note.exists()
    assert _git(repo, "status", "--porcelain").stdout == ""
    assert len(result["archive_records"]) == 2
    assert {record["archive_mode"] for record in result["archive_records"]} == {
        "docs-archive",
        "git-history-purge",
    }


def test_path_based_scan_and_apply_still_work_after_selection_entrypoints(tmp_path, monkeypatch):
    docs_root = tmp_path / "docs"
    docs_root.mkdir()
    folder = docs_root / "websites"
    folder.mkdir()
    source = folder / "old.zip"
    source.write_bytes(b"old")
    monkeypatch.setattr(scan_mod, "get_documents_dir", lambda: docs_root)
    monkeypatch.setattr(apply_mod, "get_documents_dir", lambda: docs_root)

    scan = scan_mod.hygiene_scan(str(folder))
    assert scan["files"][0]["relative_path"] == "websites/old.zip"

    result = apply_mod.hygiene_apply(
        root="docs",
        moves=[{"from": "websites/old.zip", "reason": "legacy path flow"}],
        dry_run=False,
    )
    assert result["moves"][0]["status"] == "succeeded"
    assert not source.exists()
    assert (folder / ".archive" / "old.zip").exists()
