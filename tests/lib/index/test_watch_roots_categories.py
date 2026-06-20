from pathlib import Path

from src.lib.index.watch_roots import WatchRoot, categories_for_path


def _roots(vault: Path) -> list[WatchRoot]:
    roots = [WatchRoot(path=vault, category="vault")]
    wiki = vault / "wiki"
    if wiki.is_dir():
        roots.append(WatchRoot(path=wiki, category="wiki"))
    return roots


def _write(path: Path, note_type: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = f"---\nx-augur-note-type: {note_type}\n---\nbody\n" if note_type else "no fm\n"
    path.write_text(fm, encoding="utf-8")


def test_plain_vault_note_maps_to_vault_only(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "profile" / "thought.md"
    _write(note, "thought")
    assert categories_for_path(note, _roots(vault)) == {"vault"}


def test_vault_prompt_card_maps_to_vault_and_prompts(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    card = vault / "profile" / "a-prompt.md"
    _write(card, "prompt")
    assert categories_for_path(card, _roots(vault)) == {"vault", "prompts"}


def test_wiki_page_maps_to_wiki(tmp_path):
    vault = tmp_path / "vault"
    (vault / "wiki").mkdir(parents=True)
    page = vault / "wiki" / "topic.md"
    _write(page, None)
    assert categories_for_path(page, _roots(vault)) == {"wiki"}


def test_machine_path_maps_to_empty(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    machine = vault / "_augur" / "prompts" / "x.md"
    _write(machine, "prompt")
    assert categories_for_path(machine, _roots(vault)) == set()


def test_non_indexable_extension_maps_to_empty(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    binary = vault / "profile" / "image.png"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"\x89PNG")
    assert categories_for_path(binary, _roots(vault)) == set()


def test_watch_categories_includes_prompts():
    from src.lib.index.incremental import WATCH_CATEGORIES

    assert "prompts" in WATCH_CATEGORIES
    for required in ("vault", "wiki", "documents"):
        assert required in WATCH_CATEGORIES
