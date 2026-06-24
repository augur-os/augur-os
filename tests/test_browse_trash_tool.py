# tests/test_browse_trash_tool.py
from pathlib import Path

import src.mcp.augur_framework.tools.infrastructure.browse_trash as bt


def test_trash_moves_file_and_sidecar(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    (docs / "pages").mkdir(parents=True)
    html = docs / "pages" / "p.html"
    side = docs / "pages" / "p.meta.yaml"
    html.write_text("<html></html>", encoding="utf-8")
    side.write_text("slug: p", encoding="utf-8")

    trashed: list[str] = []
    monkeypatch.setattr(bt, "_send_to_trash", lambda p: trashed.append(str(p)))

    result = bt.browse_trash_impl([str(html)], allowed_roots=[docs])
    assert str(html) in result["trashed"]
    # sidecar trashed alongside the html
    assert any(t.endswith("p.meta.yaml") for t in trashed)
    assert result["refused"] == []


def test_trash_refuses_path_outside_allowed_roots(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("x", encoding="utf-8")
    monkeypatch.setattr(bt, "_send_to_trash", lambda p: None)
    result = bt.browse_trash_impl([str(outside)], allowed_roots=[docs])
    assert result["trashed"] == []
    assert result["refused"][0]["reason"] == "outside allowed roots"
