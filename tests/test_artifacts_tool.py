"""Tests for artifacts MCP tool: sidecar I/O, slug derivation, list/reindex."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.mcp.augur_framework.tools.infrastructure.artifacts import (
    Sidecar,
    artifacts_list_impl,
    artifacts_reindex_impl,
    derive_slug,
    derive_title,
    read_sidecar,
    save_artifact_impl,
    write_sidecar,
)


def test_write_and_read_sidecar_roundtrip(tmp_path: Path) -> None:
    sidecar_path = tmp_path / "foo.meta.yaml"
    sc = Sidecar(
        slug="foo",
        title="Foo Title",
        kind="generated",
        hub="career",
        source={
            "type": "brainstorm",
            "session": "brainstorm/abc",
            "origin_path": ".superpowers/brainstorm/abc/foo.html",
        },
        tags=["onboarding"],
        created_at="2026-05-10T00:00:00Z",
        promoted_at="2026-05-10T00:01:00Z",
        notes="",
    )

    write_sidecar(sidecar_path, sc)

    loaded = read_sidecar(sidecar_path)
    assert loaded == sc


def test_derive_title_from_html_title_tag() -> None:
    html = "<html><head><title>My Title</title></head><body></body></html>"
    assert derive_title(html, fallback="x.html") == "My Title"


def test_derive_title_falls_back_to_h1() -> None:
    html = "<html><body><h1>From H1</h1></body></html>"
    assert derive_title(html, fallback="x.html") == "From H1"


def test_derive_title_falls_back_to_filename() -> None:
    assert derive_title("<html></html>", fallback="my-file.html") == "my-file"


def test_derive_slug_from_title() -> None:
    assert derive_slug(title="Onboarding \u2014 6 Directions") == "onboarding-6-directions"


def test_derive_slug_from_filename_when_title_empty() -> None:
    assert derive_slug(title="", filename="resume-coleman.html") == "resume-coleman"


def test_artifacts_list_empty_when_no_files(tmp_path: Path) -> None:
    result = artifacts_list_impl(docs_dir=tmp_path)
    assert result == {"artifacts": []}


def test_artifacts_list_returns_html_with_sidecar(tmp_path: Path) -> None:
    hub_dir = tmp_path / "career" / "artifacts"
    hub_dir.mkdir(parents=True)
    html = hub_dir / "spec-x.html"
    html.write_text("<html><title>Spec X</title></html>", encoding="utf-8")
    sc = Sidecar(slug="spec-x", title="Spec X", kind="saved", hub="career")
    write_sidecar(hub_dir / "spec-x.meta.yaml", sc)

    result = artifacts_list_impl(docs_dir=tmp_path)

    assert len(result["artifacts"]) == 1
    entry = result["artifacts"][0]
    assert entry["slug"] == "spec-x"
    assert entry["title"] == "Spec X"
    assert entry["kind"] == "saved"
    assert entry["hub"] == "career"
    assert entry["url"] == "/artifact/spec-x"
    assert entry["path"].endswith("career/artifacts/spec-x.html")


def test_artifacts_list_skips_html_without_sidecar(tmp_path: Path) -> None:
    (tmp_path / "orphan.html").write_text("<html></html>", encoding="utf-8")
    result = artifacts_list_impl(docs_dir=tmp_path)
    assert result["artifacts"] == []


def test_reindex_creates_sidecar_for_html_without_one(tmp_path: Path) -> None:
    career = tmp_path / "career" / "resumes"
    career.mkdir(parents=True)
    html = career / "resume.html"
    html.write_text("<html><title>My Resume</title></html>", encoding="utf-8")

    result = artifacts_reindex_impl(docs_dir=tmp_path, dry_run=False)

    sidecar = career / "resume.meta.yaml"
    assert sidecar.exists()
    sc = read_sidecar(sidecar)
    assert sc.slug == "my-resume"
    assert sc.title == "My Resume"
    assert sc.kind == "saved"
    assert sc.hub == "career"
    assert result["created"] == 1


def test_reindex_dry_run_does_not_write(tmp_path: Path) -> None:
    html = tmp_path / "venture-augur" / "logos" / "concepts.html"
    html.parent.mkdir(parents=True)
    html.write_text("<html><title>Concepts</title></html>", encoding="utf-8")

    result = artifacts_reindex_impl(docs_dir=tmp_path, dry_run=True)

    assert not html.with_suffix("").with_suffix(".meta.yaml").exists()
    assert result["created"] == 0
    assert result["proposed"] == 1
    assert result["proposals"][0]["hub"] == "venture-augur"


def test_reindex_skips_html_with_existing_sidecar(tmp_path: Path) -> None:
    html = tmp_path / "career" / "artifacts" / "x.html"
    html.parent.mkdir(parents=True)
    html.write_text("<html></html>", encoding="utf-8")
    sc = Sidecar(slug="x", title="X", kind="saved", hub="career")
    write_sidecar(html.with_suffix("").with_suffix(".meta.yaml"), sc)

    result = artifacts_reindex_impl(docs_dir=tmp_path, dry_run=False)

    assert result["created"] == 0


def test_reindex_appends_suffix_for_duplicate_global_slugs(tmp_path: Path) -> None:
    first = tmp_path / "career" / "one.html"
    second = tmp_path / "brain" / "two.html"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text("<html><title>Same Title</title></html>", encoding="utf-8")
    second.write_text("<html><title>Same Title</title></html>", encoding="utf-8")

    artifacts_reindex_impl(docs_dir=tmp_path, dry_run=False)

    slugs = {
        read_sidecar(first.with_suffix("").with_suffix(".meta.yaml")).slug,
        read_sidecar(second.with_suffix("").with_suffix(".meta.yaml")).slug,
    }
    assert slugs == {"same-title", "same-title-2"}


def test_import_copies_brainstorm_html_into_docs_dir(tmp_path: Path) -> None:
    brain_root = tmp_path / "brainstorm" / "27346-1777974008" / "content"
    brain_root.mkdir(parents=True)
    src = brain_root / "spec-written.html"
    src.write_text("<html><title>Spec Written</title></html>", encoding="utf-8")

    docs = tmp_path / "docs"
    docs.mkdir()

    result = artifacts_reindex_impl(
        docs_dir=docs,
        dry_run=False,
        import_glob=str(brain_root / "*.html"),
        import_hub="career",
    )

    assert result["imported"] == 1
    target = docs / "career" / "artifacts" / "spec-written.html"
    assert target.exists()
    sidecar = target.with_suffix("").with_suffix(".meta.yaml")
    assert sidecar.exists()
    sc = read_sidecar(sidecar)
    assert sc.kind == "generated"
    assert sc.hub == "career"
    assert sc.source.get("type") == "brainstorm"
    assert sc.source.get("origin_path", "").endswith("spec-written.html")


def test_import_uses_unique_slug_filenames_for_duplicate_source_names(tmp_path: Path) -> None:
    first_root = tmp_path / "brainstorm" / "one" / "content"
    second_root = tmp_path / "brainstorm" / "two" / "content"
    first_root.mkdir(parents=True)
    second_root.mkdir(parents=True)
    (first_root / "waiting.html").write_text(
        "<html><title>Waiting</title></html>",
        encoding="utf-8",
    )
    (second_root / "waiting.html").write_text(
        "<html><title>Waiting</title></html>",
        encoding="utf-8",
    )
    docs = tmp_path / "docs"

    result = artifacts_reindex_impl(
        docs_dir=docs,
        dry_run=False,
        import_glob=str(tmp_path / "brainstorm" / "*" / "content" / "*.html"),
        import_hub="dev",
    )

    assert result["imported"] == 2
    assert (docs / "dev" / "artifacts" / "waiting.html").exists()
    assert (docs / "dev" / "artifacts" / "waiting-2.html").exists()
    assert read_sidecar(docs / "dev" / "artifacts" / "waiting.meta.yaml").slug == "waiting"
    assert read_sidecar(docs / "dev" / "artifacts" / "waiting-2.meta.yaml").slug == "waiting-2"


def test_save_artifact_writes_file_and_sidecar(tmp_path: Path) -> None:
    src = tmp_path / "src" / "draft.html"
    src.parent.mkdir()
    src.write_text("<html><title>Draft</title></html>", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()

    result = save_artifact_impl(
        docs_dir=docs,
        source_path=src,
        hub="career",
        slug=None,
        title=None,
        tags=["draft"],
    )

    assert result["slug"] == "draft"
    assert result["target"].endswith("career/artifacts/draft.html")
    target = Path(result["target"])
    assert target.exists()
    sidecar = target.with_suffix("").with_suffix(".meta.yaml")
    assert sidecar.exists()
    sc = read_sidecar(sidecar)
    assert sc.tags == ["draft"]
    assert sc.kind == "saved"


def test_save_artifact_appends_suffix_on_slug_collision(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    target_dir = docs / "career" / "artifacts"
    target_dir.mkdir(parents=True)
    (target_dir / "x.html").write_text("<html></html>", encoding="utf-8")
    write_sidecar(
        target_dir / "x.meta.yaml",
        Sidecar(slug="x", title="X", kind="saved", hub="career"),
    )

    src = tmp_path / "x.html"
    src.write_text("<html><title>X</title></html>", encoding="utf-8")
    result = save_artifact_impl(
        docs_dir=docs,
        source_path=src,
        hub="career",
        slug="x",
        title="X",
        tags=[],
    )

    assert result["slug"] == "x-2"


def test_refresh_pages_index_invokes_reindex(monkeypatch):
    """_refresh_pages_index reindexes the pages category with resolved paths, and never raises."""
    import src.mcp.augur_framework.tools.infrastructure.artifacts as artifacts_mod

    calls: list[tuple] = []

    def fake_reindex(category, root, rag_dir, **kwargs):
        calls.append((category, root, rag_dir, kwargs))
        return 1

    monkeypatch.setattr("src.lib.index.unified_indexer.reindex_category", fake_reindex)
    artifacts_mod._refresh_pages_index()

    assert len(calls) == 1
    assert calls[0][0] == "pages"
    assert "documents_dir" in calls[0][3]


def test_refresh_pages_index_swallows_errors(monkeypatch):
    """A failing reindex must not break the artifact save (best-effort refresh)."""
    import src.mcp.augur_framework.tools.infrastructure.artifacts as artifacts_mod

    def boom(*args, **kwargs):
        raise RuntimeError("index exploded")

    monkeypatch.setattr("src.lib.index.unified_indexer.reindex_category", boom)
    artifacts_mod._refresh_pages_index()  # must not raise


def test_save_artifact_appends_suffix_on_cross_hub_slug_collision(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    existing_dir = docs / "brain" / "artifacts"
    existing_dir.mkdir(parents=True)
    (existing_dir / "x.html").write_text("<html></html>", encoding="utf-8")
    write_sidecar(
        existing_dir / "x.meta.yaml",
        Sidecar(slug="x", title="X", kind="saved", hub="brain"),
    )

    src = tmp_path / "source.html"
    src.write_text("<html><title>X</title></html>", encoding="utf-8")
    result = save_artifact_impl(
        docs_dir=docs,
        source_path=src,
        hub="career",
        slug="x",
        title="X",
        tags=[],
    )

    assert result["slug"] == "x-2"
