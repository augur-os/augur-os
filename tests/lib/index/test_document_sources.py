from __future__ import annotations

from pathlib import Path

from src.lib.index.document_sources import (
    DocumentSource,
    default_document_sources,
    media_kind_for_path,
    should_index_source_file,
)


def test_default_document_sources_include_docs_desktop_downloads(tmp_path, monkeypatch):
    docs = tmp_path / "Au-docs"
    home = tmp_path / "home"
    desktop = home / "Desktop"
    downloads = home / "Downloads"
    for path in (docs, desktop, downloads):
        path.mkdir(parents=True)

    unresolved_docs = docs / ".." / "Au-docs"
    unresolved_home = home / ".." / "home"
    monkeypatch.setattr(Path, "home", lambda: unresolved_home)

    sources = default_document_sources(documents_dir=unresolved_docs)

    assert [(s.id, s.name, s.path) for s in sources] == [
        ("documents", "Documents", docs.resolve()),
        ("desktop", "Desktop", desktop.resolve()),
        ("downloads", "Downloads", downloads.resolve()),
    ]
    assert sources[0].preserve_legacy_output is True
    assert sources[1].preserve_legacy_output is False
    assert sources[2].preserve_legacy_output is False
    assert sources[0].attached_brain_ids == ("personal",)
    assert sources[0].source_type == "local"
    assert sources[0].provider == "filesystem"
    assert sources[1].attached_brain_ids == ("personal",)
    assert sources[2].attached_brain_ids == ("personal",)


def test_default_document_sources_skip_missing_desktop_downloads(tmp_path, monkeypatch):
    docs = tmp_path / "Au-docs"
    home = tmp_path / "home"
    docs.mkdir()
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)

    sources = default_document_sources(documents_dir=docs)

    assert [source.id for source in sources] == ["documents"]


def test_should_index_source_file_excludes_noise(tmp_path):
    root = tmp_path / "Downloads"
    root.mkdir()
    source = DocumentSource(id="downloads", name="Downloads", path=root)

    cases = {
        root / "report.pdf": True,
        root / "meeting.m4a": True,
        root / "clip.mp4": True,
        root / "scan.png": True,
        root / ".DS_Store": False,
        root / "Chrome.part": False,
        root / "archive.crdownload": False,
        root / "Installer.dmg": False,
        root / "App.app" / "Contents" / "Info.plist": False,
        root / "Example.app" / "Contents" / "manual.pdf": False,
        root / "node_modules" / "pkg" / "guide.pdf": False,
        root / "vendor" / "pkg" / "guide.pdf": False,
        root / "venv" / "pkg" / "guide.pdf": False,
        root / "env" / "pkg" / "guide.pdf": False,
        root / "site-packages" / "pkg" / "guide.pdf": False,
        root / ".pnpm" / "pkg" / "guide.pdf": False,
        root / ".Trash" / "old.pdf": False,
    }

    for path, expected in cases.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
        assert should_index_source_file(path, source) is expected


def test_should_index_source_file_rejects_absolute_paths_outside_source(tmp_path):
    root = tmp_path / "Downloads"
    outside = tmp_path / "Elsewhere" / "report.pdf"
    root.mkdir()
    outside.parent.mkdir()
    outside.write_text("x", encoding="utf-8")
    source = DocumentSource(id="downloads", name="Downloads", path=root)

    try:
        result = should_index_source_file(outside, source)
    except ValueError as exc:
        raise AssertionError("outside absolute paths should return False") from exc

    assert result is False


def test_should_index_source_file_rejects_symlink_targets_outside_source(tmp_path):
    root = tmp_path / "Downloads"
    outside = tmp_path / "Elsewhere" / "secret.pdf"
    linked = root / "linked.pdf"
    root.mkdir()
    outside.parent.mkdir()
    outside.write_text("x", encoding="utf-8")
    linked.symlink_to(Path("..") / "Elsewhere" / "secret.pdf")
    source = DocumentSource(id="downloads", name="Downloads", path=root)

    assert should_index_source_file(linked, source) is False


def test_should_index_source_file_rejects_relative_symlink_escape(tmp_path, monkeypatch):
    root = tmp_path / "Downloads"
    outside = tmp_path / "Elsewhere" / "secret.pdf"
    linked = root / "linked.pdf"
    root.mkdir()
    outside.parent.mkdir()
    outside.write_text("x", encoding="utf-8")
    linked.symlink_to(Path("..") / "Elsewhere" / "secret.pdf")
    source = DocumentSource(id="downloads", name="Downloads", path=root)
    monkeypatch.chdir(root)

    assert should_index_source_file(Path("linked.pdf"), source) is False


def test_should_index_source_file_rejects_relative_parent_escape(tmp_path, monkeypatch):
    root = tmp_path / "Downloads"
    outside = tmp_path / "Elsewhere" / "report.pdf"
    root.mkdir()
    outside.parent.mkdir()
    outside.write_text("x", encoding="utf-8")
    source = DocumentSource(id="downloads", name="Downloads", path=root)
    monkeypatch.chdir(root)

    assert should_index_source_file(Path("..") / "Elsewhere" / "report.pdf", source) is False


def test_should_index_source_file_rejects_symlink_lexical_exclusions(tmp_path):
    root = tmp_path / "Downloads"
    report = root / "report.pdf"
    hidden_link = root / ".hidden" / "linked.pdf"
    app_link = root / "Example.app" / "Contents" / "linked.pdf"
    root.mkdir()
    report.write_text("x", encoding="utf-8")
    hidden_link.parent.mkdir()
    app_link.parent.mkdir(parents=True)
    hidden_link.symlink_to(Path("..") / "report.pdf")
    app_link.symlink_to(Path("..") / ".." / "report.pdf")
    source = DocumentSource(id="downloads", name="Downloads", path=root)

    assert should_index_source_file(hidden_link, source) is False
    assert should_index_source_file(app_link, source) is False


def test_should_index_source_file_rejects_directory_symlink_lexical_exclusions(tmp_path):
    root = tmp_path / "Downloads"
    docs = root / "docs"
    guide = docs / "guide.pdf"
    root.mkdir()
    docs.mkdir()
    guide.write_text("x", encoding="utf-8")
    (root / "node_modules").symlink_to("docs", target_is_directory=True)
    (root / ".hidden").symlink_to("docs", target_is_directory=True)
    (root / "Example.app").symlink_to("docs", target_is_directory=True)
    source = DocumentSource(id="downloads", name="Downloads", path=root)

    assert should_index_source_file(root / "node_modules" / "guide.pdf", source) is False
    assert should_index_source_file(root / ".hidden" / "guide.pdf", source) is False
    assert should_index_source_file(root / "Example.app" / "guide.pdf", source) is False


def test_media_kind_for_path():
    assert media_kind_for_path(Path("scan.png")) == "image"
    assert media_kind_for_path(Path("voice.m4a")) == "audio"
    assert media_kind_for_path(Path("meeting.mp4")) == "video"
    assert media_kind_for_path(Path("clip.webm")) == "video"
    assert media_kind_for_path(Path("deck.pdf")) == ""
