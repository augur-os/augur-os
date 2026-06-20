from __future__ import annotations

from pathlib import Path


def test_build_wiki_status_includes_compounding_queries(tmp_path: Path, monkeypatch) -> None:
    from skills.wiki.scripts import wiki_status

    vault_dir = tmp_path / "vault"
    wiki_dir = vault_dir / "wiki"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "queries.yaml").write_text(
        "queries:\n  - setup completeness\n  - user prompts\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(wiki_status, "get_vault_dir", lambda: vault_dir)
    monkeypatch.setattr(wiki_status, "resolve_wiki_dir", lambda: wiki_dir)
    monkeypatch.setattr(wiki_status, "get_compiled_wiki_dir", lambda wiki_dir_arg=None: wiki_dir)
    monkeypatch.setattr(wiki_status, "get_rag_category_dir", lambda _category: tmp_path / "rag")
    monkeypatch.setattr(wiki_status, "get_rag_dir", lambda: tmp_path / "rag")
    monkeypatch.setattr(wiki_status, "get_runtime_dir", lambda: tmp_path / "runtime")

    payload = wiki_status.build_wiki_status()

    assert payload["compounding"]["queries"] == ["setup completeness", "user prompts"]


def test_load_compounding_queries_supports_adr731_registry_mapping(tmp_path: Path) -> None:
    from skills.wiki.scripts.wiki_status import load_compounding_queries

    vault_dir = tmp_path / "vault"
    wiki_dir = vault_dir / "wiki"
    wiki_dir.mkdir(parents=True)
    (wiki_dir / "queries.yaml").write_text(
        "version: 1\nqueries:\n  active-projects:\n    title: Active Projects\n  knowledge-gaps:\n    title: Knowledge Gaps\n",
        encoding="utf-8",
    )

    assert load_compounding_queries(vault_dir) == ["active-projects", "knowledge-gaps"]
