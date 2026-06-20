from pathlib import Path

from src.lib.index._scanners_knowledge import index_prompts


def _domains_vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    v.mkdir()
    (v / "BRAIN.yaml").write_text("layout: domains\n", encoding="utf-8")
    return v


def _prompt_card(path: Path, pid: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nid: {pid}\nlabel: {pid}\ndescription: A {pid} card\n"
        f"x-augur-note-type: prompt\nx-augur-prompt-triggerable: true\nsource: vault\n"
        f"---\nBody {{{{x}}}}\n",
        encoding="utf-8",
    )


def _clear_vault_cache() -> None:
    from src.config import paths as _paths

    _paths._dir_cache.pop("vault", None)


def test_index_prompts_finds_cards_in_domain_folders(tmp_path, monkeypatch):
    vault = _domains_vault(tmp_path)
    monkeypatch.setenv("AUGUR_VAULT", str(vault))
    _clear_vault_cache()

    # one still in inbox, one filed into a domain folder, one in a machine dir
    _prompt_card(vault / "inbox" / "in-inbox.md", "in-inbox")
    _prompt_card(vault / "profile" / "filed-card.md", "filed-card")
    _prompt_card(vault / "_augur" / "archive" / "old.md", "old-card")  # machine → excluded

    # a non-prompt note in a domain must NOT be indexed as a prompt
    (vault / "venture").mkdir(parents=True, exist_ok=True)
    (vault / "venture" / "thought.md").write_text(
        "---\nx-augur-note-type: thought\n---\njust a thought\n", encoding="utf-8"
    )

    root = tmp_path / "proj"
    root.mkdir()  # no skills → only vault cards are scanned
    rag = tmp_path / "rag"
    rag.mkdir()

    index_prompts(root, rag)

    out = rag / "prompts" / "brain" / "vault"
    ids = {p.stem for p in out.glob("*.md")} if out.is_dir() else set()

    assert "in-inbox" in ids
    assert "filed-card" in ids  # THE FIX: prompt card filed into a domain still indexed
    assert "old-card" not in ids  # machine path excluded
    assert "thought" not in ids  # non-prompt note excluded

    _clear_vault_cache()
