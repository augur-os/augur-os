import pytest

from src.config.paths import invalidate_project_cache
from skills.wiki.scripts.wiki_query_sources import MemoryMdAdapter, SourceResult


@pytest.fixture(autouse=True)
def _clear_path_cache():
    invalidate_project_cache()
    yield
    invalidate_project_cache()


def test_adapter_kind_matches_registry():
    assert MemoryMdAdapter().kind == "memory_md"


def test_resolve_full_memory_md(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    content = "## Decisions\n- 2026-05-01 decided X\n\n## Preferences\n- prefer Y\n"
    (memory_dir / "MEMORY.md").write_text(content, encoding="utf-8")

    result = MemoryMdAdapter().resolve({"kind": "memory_md"}, budget_tokens=10_000)

    assert isinstance(result, SourceResult)
    assert "## Decisions" in result.text
    assert "## Preferences" in result.text
    assert result.truncated is False
    assert any("MEMORY.md" in c for c in result.citations)


def test_resolve_section_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    content = "## Decisions\n- decided X\n\n## Preferences\n- prefer Y\n"
    (memory_dir / "MEMORY.md").write_text(content, encoding="utf-8")

    result = MemoryMdAdapter().resolve(
        {"kind": "memory_md", "section": "Decisions"},
        budget_tokens=10_000,
    )

    assert "decided X" in result.text
    assert "prefer Y" not in result.text


def test_resolve_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    result = MemoryMdAdapter().resolve({"kind": "memory_md"}, budget_tokens=10_000)
    assert result.text == ""
    assert result.citations == []
