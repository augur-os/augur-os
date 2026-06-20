from __future__ import annotations

from pathlib import Path


def test_refresh_notes_browse_index_calls_vault_reindex(monkeypatch, tmp_path: Path) -> None:
    from src.lib.ingest import note_index_refresh as mod

    root = tmp_path / "repo"
    rag = tmp_path / "rag"
    vault = tmp_path / "vault"
    calls: list[tuple[str, Path, Path, Path]] = []

    monkeypatch.setattr(mod, "get_project_root", lambda: root)
    monkeypatch.setattr(mod, "get_rag_dir", lambda: rag)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)

    def fake_reindex_category(category: str, project_root: Path, rag_dir: Path, *, vault_dir: Path) -> int:
        calls.append((category, project_root, rag_dir, vault_dir))
        return 7

    monkeypatch.setattr(mod, "reindex_category", fake_reindex_category)

    result = mod.refresh_notes_browse_index()

    assert result.success is True
    assert result.count == 7
    assert result.error == ""
    assert result.to_dict() == {"success": True, "count": 7}
    assert calls == [("vault", root, rag, vault)]


def test_refresh_notes_browse_index_accepts_explicit_paths(monkeypatch, tmp_path: Path) -> None:
    from src.lib.ingest import note_index_refresh as mod

    root = tmp_path / "explicit-repo"
    rag = tmp_path / "explicit-rag"
    vault = tmp_path / "explicit-vault"
    calls: list[tuple[str, Path, Path, Path]] = []

    monkeypatch.setattr(
        mod,
        "get_project_root",
        lambda: (_ for _ in ()).throw(AssertionError("get_project_root should not be called")),
    )
    monkeypatch.setattr(
        mod,
        "get_rag_dir",
        lambda: (_ for _ in ()).throw(AssertionError("get_rag_dir should not be called")),
    )
    monkeypatch.setattr(
        mod,
        "get_vault_dir",
        lambda: (_ for _ in ()).throw(AssertionError("get_vault_dir should not be called")),
    )

    def fake_reindex_category(category: str, project_root: Path, rag_dir: Path, *, vault_dir: Path) -> int:
        calls.append((category, project_root, rag_dir, vault_dir))
        return 3

    monkeypatch.setattr(mod, "reindex_category", fake_reindex_category)

    result = mod.refresh_notes_browse_index(project_root=root, rag_dir=rag, vault_dir=vault)

    assert result.success is True
    assert result.count == 3
    assert calls == [("vault", root, rag, vault)]


def test_refresh_prompts_browse_index_calls_prompts_reindex(monkeypatch, tmp_path: Path) -> None:
    from src.lib.ingest import note_index_refresh as mod

    root = tmp_path / "repo"
    rag = tmp_path / "rag"
    vault = tmp_path / "vault"
    calls: list[tuple[str, Path, Path, Path]] = []

    monkeypatch.setattr(mod, "get_project_root", lambda: root)
    monkeypatch.setattr(mod, "get_rag_dir", lambda: rag)
    monkeypatch.setattr(mod, "get_vault_dir", lambda: vault)

    def fake_reindex_category(category: str, project_root: Path, rag_dir: Path, *, vault_dir: Path) -> int:
        calls.append((category, project_root, rag_dir, vault_dir))
        return 4

    monkeypatch.setattr(mod, "reindex_category", fake_reindex_category)

    result = mod.refresh_prompts_browse_index()

    assert result.success is True
    assert result.count == 4
    assert calls == [("prompts", root, rag, vault)]


def test_refresh_prompts_browse_index_returns_failure_without_raising(monkeypatch, tmp_path: Path) -> None:
    from src.lib.ingest import note_index_refresh as mod

    monkeypatch.setattr(mod, "get_project_root", lambda: tmp_path / "repo")
    monkeypatch.setattr(mod, "get_rag_dir", lambda: tmp_path / "rag")
    monkeypatch.setattr(mod, "get_vault_dir", lambda: tmp_path / "vault")

    def fail_reindex_category(category: str, project_root: Path, rag_dir: Path, *, vault_dir: Path) -> int:
        raise RuntimeError("prompts boom")

    monkeypatch.setattr(mod, "reindex_category", fail_reindex_category)

    result = mod.refresh_prompts_browse_index()

    assert result.success is False
    assert result.error == "prompts boom"


def test_refresh_browse_after_write_maps_paths_to_categories(monkeypatch, tmp_path):
    from src.lib.ingest import note_index_refresh as mod
    from src.lib.index.watch_roots import WatchRoot

    vault = tmp_path / "vault"
    (vault / "profile").mkdir(parents=True)
    card = vault / "profile" / "p.md"
    card.write_text("---\nx-augur-note-type: prompt\n---\nbody\n", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_sync_categories(categories, *, project_root, rag_dir=None, vault_dir=None,
                             documents_dir=None, **kw):
        captured["categories"] = set(categories)
        return {c: 1 for c in categories}

    monkeypatch.setattr(mod, "sync_categories", fake_sync_categories)
    monkeypatch.setattr(mod, "resolve_watch_roots",
                        lambda: [WatchRoot(path=vault, category="vault")])
    monkeypatch.setattr(mod, "get_project_root", lambda: tmp_path / "repo")

    result = mod.refresh_browse_after_write(paths=[card], vault_dir=vault)

    assert captured["categories"] == {"vault", "prompts"}
    assert result["vault"].success is True
    assert result["prompts"].success is True


def test_refresh_browse_after_write_accepts_explicit_categories(monkeypatch, tmp_path):
    from src.lib.ingest import note_index_refresh as mod

    captured: dict[str, object] = {}

    def fake_sync_categories(categories, *, project_root, **kw):
        captured["categories"] = set(categories)
        return {c: 0 for c in categories}

    monkeypatch.setattr(mod, "sync_categories", fake_sync_categories)
    monkeypatch.setattr(mod, "get_project_root", lambda: tmp_path / "repo")

    result = mod.refresh_browse_after_write(categories={"prompts"})
    assert captured["categories"] == {"prompts"}
    assert result["prompts"].success is True


def test_refresh_browse_after_write_empty_is_noop(monkeypatch, tmp_path):
    from src.lib.ingest import note_index_refresh as mod

    def boom(*a, **k):
        raise AssertionError("sync_categories should not be called")

    monkeypatch.setattr(mod, "sync_categories", boom)
    assert mod.refresh_browse_after_write(paths=[], categories=set()) == {}


def test_refresh_browse_after_write_never_raises(monkeypatch, tmp_path):
    from src.lib.ingest import note_index_refresh as mod

    def fail_sync(categories, *, project_root, **kw):
        raise RuntimeError("index boom")

    monkeypatch.setattr(mod, "sync_categories", fail_sync)
    monkeypatch.setattr(mod, "get_project_root", lambda: tmp_path / "repo")

    result = mod.refresh_browse_after_write(categories={"vault", "prompts"})
    assert result["vault"].success is False
    assert result["prompts"].success is False
    assert "index boom" in result["vault"].error


def test_refresh_notes_browse_index_returns_failure_without_raising(monkeypatch, tmp_path: Path) -> None:
    from src.lib.ingest import note_index_refresh as mod

    monkeypatch.setattr(mod, "get_project_root", lambda: tmp_path / "repo")
    monkeypatch.setattr(mod, "get_rag_dir", lambda: tmp_path / "rag")
    monkeypatch.setattr(mod, "get_vault_dir", lambda: tmp_path / "vault")

    def fail_reindex_category(category: str, project_root: Path, rag_dir: Path, *, vault_dir: Path) -> int:
        raise RuntimeError("index boom")

    monkeypatch.setattr(mod, "reindex_category", fail_reindex_category)

    result = mod.refresh_notes_browse_index()

    assert result.success is False
    assert result.count == 0
    assert result.error == "index boom"
    assert result.to_dict() == {"success": False, "count": 0, "error": "index boom"}
