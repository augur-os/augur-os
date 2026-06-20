"""wiki_tools entry sites must resolve the durable wiki dir via resolve_wiki_dir."""
from pathlib import Path

WIKI_TOOLS = Path(__file__).resolve().parents[2] / "scripts" / "mcp" / "wiki_tools.py"
WIKI_RESET = Path(__file__).resolve().parents[2] / "scripts" / "wiki_reset.py"


def test_wiki_tools_uses_resolver_not_hardwired_personal():
    src = WIKI_TOOLS.read_text(encoding="utf-8")
    assert "wiki_dir = get_wiki_dir()" not in src
    assert "wiki_dir=get_wiki_dir()" not in src
    assert "resolve_wiki_dir" in src


def test_wiki_reset_uses_resolver():
    src = WIKI_RESET.read_text(encoding="utf-8")
    assert "wiki_dir = get_wiki_dir()" not in src
    assert "resolve_wiki_dir" in src


def test_wiki_status_defaults_to_active_resolved_wiki(monkeypatch, tmp_path):
    from skills.wiki.scripts import wiki_status

    active_wiki_dir = tmp_path / "project-brain" / "knowledge" / "wiki"
    compiled_wiki_dir = active_wiki_dir
    seen: dict[str, Path | None] = {}

    monkeypatch.setattr(wiki_status, "resolve_wiki_dir", lambda: active_wiki_dir)

    def fake_compiled_wiki_dir(wiki_dir=None):
        seen["wiki_dir"] = wiki_dir
        return compiled_wiki_dir

    monkeypatch.setattr(
        wiki_status,
        "get_compiled_wiki_dir",
        fake_compiled_wiki_dir,
    )
    monkeypatch.setattr(wiki_status, "get_rag_dir", lambda: tmp_path / "rag")
    monkeypatch.setattr(wiki_status, "get_runtime_dir", lambda: tmp_path / "runtime")
    monkeypatch.setattr(
        wiki_status,
        "get_rag_category_dir",
        lambda _category: tmp_path / "rag" / "wiki",
    )
    monkeypatch.setattr(
        wiki_status,
        "lint_wiki",
        lambda wiki_dir: {"ok": True, "pages": 0, "hubs": 0},
    )
    monkeypatch.setattr(
        wiki_status,
        "build_source_inventory",
        lambda *, rag_dir, wiki_dir: [],
    )
    monkeypatch.setattr(wiki_status, "load_compounding_queries", lambda: [])

    def missing_state(_runtime_wiki_dir):
        raise OSError("missing state")

    monkeypatch.setattr(wiki_status, "load_compiler_state", missing_state)

    payload = wiki_status.build_wiki_status()

    assert seen["wiki_dir"] == active_wiki_dir
    assert payload["wiki_dir"] == str(compiled_wiki_dir)
