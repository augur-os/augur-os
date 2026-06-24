# tests/test_artifacts_serve_core.py
from pathlib import Path

import src.mcp.augur_core.tools.core.artifacts_serve as asv
from src.lib.artifacts_sidecar import write_sidecar, Sidecar, sidecar_path_for_html


def _make(docs: Path, slug: str, body="<html><title>T</title>x</html>", hub="dev"):
    d = docs / hub / "artifacts"; d.mkdir(parents=True, exist_ok=True)
    html = d / f"{slug}.html"; html.write_text(body, encoding="utf-8")
    write_sidecar(sidecar_path_for_html(html), Sidecar(slug=slug, title="T", kind="generated", hub=hub))
    return html


def test_resolve_returns_metadata(tmp_path):
    _make(tmp_path, "demo")
    r = asv.artifact_resolve_impl("demo", docs_dir=tmp_path)
    assert r["found"] and r["slug"] == "demo" and r["kind"] == "generated"
    assert r["url"] == "/artifact/demo"
    assert r["path"].endswith("demo.html")


def test_resolve_unknown_slug(tmp_path):
    assert asv.artifact_resolve_impl("nope", docs_dir=tmp_path) == {"found": False}


def test_html_returns_file_content(tmp_path):
    _make(tmp_path, "demo", body="<html>HELLO-BODY</html>")
    r = asv.artifact_html_impl("demo", docs_dir=tmp_path, allowed_roots=[tmp_path])
    assert r["found"] and "HELLO-BODY" in r["content"]


def test_html_refuses_outside_roots(tmp_path):
    _make(tmp_path, "demo")
    other = tmp_path / "other"; other.mkdir()
    r = asv.artifact_html_impl("demo", docs_dir=tmp_path, allowed_roots=[other])
    assert r == {"found": False}


def test_resolve_skips_corrupt_sidecar(tmp_path):
    """A corrupt/incomplete sidecar must not 500 the resolve — it is skipped."""
    # Corrupt artifact sorted BEFORE the target so it is scanned first.
    bad_dir = tmp_path / "dev" / "artifacts"
    bad_dir.mkdir(parents=True, exist_ok=True)
    (bad_dir / "aaa-corrupt.html").write_text("<html>x</html>", encoding="utf-8")
    # Sidecar missing required fields (slug/title/kind/hub) -> read_sidecar raises.
    (bad_dir / "aaa-corrupt.meta.yaml").write_text("note: incomplete\n", encoding="utf-8")
    _make(tmp_path, "good-one")

    r = asv.artifact_resolve_impl("good-one", docs_dir=tmp_path)
    assert r["found"] and r["slug"] == "good-one"
