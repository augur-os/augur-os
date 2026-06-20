"""apply_renames: map-driven rename with vault-wide wikilink rewrite."""

import subprocess
from pathlib import Path

import pytest

from scripts.migrations.apply_renames import apply_map, parse_map


def _git_vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    v.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=v, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=v, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=v, check=True)
    return v


def _commit_all(v: Path) -> None:
    subprocess.run(["git", "add", "-A"], cwd=v, check=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=v, check=True)


def test_rename_rewrites_wikilinks_and_embeds(tmp_path):
    v = _git_vault(tmp_path)
    (v / "career").mkdir()
    (v / "career" / "2026-04-21-very-long-capture-name.md").write_text("# x", encoding="utf-8")
    (v / "career" / "other.md").write_text(
        "see [[2026-04-21-very-long-capture-name]] and "
        "[[2026-04-21-very-long-capture-name|alias]] and "
        "![[2026-04-21-very-long-capture-name]]",
        encoding="utf-8",
    )
    _commit_all(v)
    apply_map(v, [("career/2026-04-21-very-long-capture-name.md", "career/capture-name.md")], use_git=True)
    body = (v / "career" / "other.md").read_text(encoding="utf-8")
    assert "[[capture-name]]" in body and "[[capture-name|alias]]" in body and "![[capture-name]]" in body
    assert "very-long" not in body
    assert (v / "career" / "capture-name.md").exists()


def test_collision_refused(tmp_path):
    v = _git_vault(tmp_path)
    (v / "a.md").write_text("x", encoding="utf-8")
    (v / "b.md").write_text("y", encoding="utf-8")
    _commit_all(v)
    try:
        apply_map(v, [("a.md", "b.md")], use_git=True)
        raise AssertionError("expected SystemExit")
    except SystemExit:
        pass
    assert (v / "a.md").read_text(encoding="utf-8") == "x"


def test_move_across_dirs_files_inbox_note(tmp_path):
    v = _git_vault(tmp_path)
    (v / "inbox").mkdir()
    (v / "career").mkdir()
    (v / "inbox" / "x.md").write_text("x", encoding="utf-8")
    _commit_all(v)
    apply_map(v, [("inbox/x.md", "career/x.md")], use_git=True)
    assert (v / "career" / "x.md").exists() and not (v / "inbox" / "x.md").exists()


def test_parse_map_ignores_comments(tmp_path):
    m = tmp_path / "map.tsv"
    m.write_text("# comment\ninbox/a.md\tcareer/a.md\t reason here\n", encoding="utf-8")
    assert parse_map(m) == [("inbox/a.md", "career/a.md")]


def test_plain_rename_without_git(tmp_path):
    v = tmp_path / "docs"
    (v / "career").mkdir(parents=True)
    (v / "career" / "image-4.png").write_bytes(b"png")
    apply_map(v, [("career/image-4.png", "career/star-method.png")], use_git=False)
    assert (v / "career" / "star-method.png").exists()


def test_prefix_stem_not_rewritten(tmp_path):
    """Renaming stem 'star' must not touch [[star-method]] or [[star-wars|alias]].

    The regex anchors on ]|# after the stem so prefix matches are excluded.
    """
    v = _git_vault(tmp_path)
    (v / "career").mkdir()
    (v / "career" / "star.md").write_text("# star", encoding="utf-8")
    (v / "career" / "ref.md").write_text(
        "[[star]] and [[star|alias]] and ![[star]] " "but not [[star-method]] or [[star-wars|the force]]",
        encoding="utf-8",
    )
    _commit_all(v)
    apply_map(v, [("career/star.md", "career/north-star.md")], use_git=True)
    body = (v / "career" / "ref.md").read_text(encoding="utf-8")
    # exact-stem references rewritten
    assert "[[north-star]]" in body
    assert "[[north-star|alias]]" in body
    assert "![[north-star]]" in body
    # prefix stems untouched
    assert "[[star-method]]" in body
    assert "[[star-wars|the force]]" in body


def test_path_qualified_links_rewritten_on_cross_dir_move(tmp_path):
    """Both [[inbox/x]] (path-qualified) and [[x]] (stem) rewrite on inbox/x.md -> career/y.md."""
    v = _git_vault(tmp_path)
    (v / "inbox").mkdir()
    (v / "career").mkdir()
    (v / "inbox" / "x.md").write_text("# x", encoding="utf-8")
    (v / "career" / "ref.md").write_text(
        "path [[inbox/x]] and [[inbox/x|alias]] and stem [[x]] and ![[x]]",
        encoding="utf-8",
    )
    _commit_all(v)
    apply_map(v, [("inbox/x.md", "career/y.md")], use_git=True)
    body = (v / "career" / "ref.md").read_text(encoding="utf-8")
    assert "[[career/y]]" in body and "[[career/y|alias]]" in body
    assert "[[y]]" in body and "![[y]]" in body
    assert "inbox/x" not in body and "[[x]]" not in body


def test_parse_map_rejects_forbidden_characters(tmp_path):
    """Backslash/bracket/pipe/hash/control chars in old or new entries are fatal."""
    m = tmp_path / "map.tsv"
    bad_lines = [
        "a\\g<0>.md\tb.md",  # backslash (regex template injection)
        "a.md\tb[1].md",  # bracket
        "a[x].md\tb.md",  # bracket in old
        "a|b.md\tc.md",  # pipe
        "a.md\tb#c.md",  # hash
        "a\x01.md\tb.md",  # control character
    ]
    for bad in bad_lines:
        m.write_text(bad + "\n", encoding="utf-8")
        with pytest.raises(SystemExit):
            parse_map(m)


def test_directory_src_refused(tmp_path):
    """A directory in the map is fatal — and no unrelated links get touched."""
    v = _git_vault(tmp_path)
    (v / "inbox").mkdir()
    (v / "inbox" / "x.md").write_text("x", encoding="utf-8")
    (v / "ref.md").write_text("an unrelated [[notes]] link", encoding="utf-8")
    _commit_all(v)
    with pytest.raises(SystemExit):
        apply_map(v, [("inbox", "archive")], use_git=True)
    assert (v / "inbox" / "x.md").exists()
    assert (v / "ref.md").read_text(encoding="utf-8") == "an unrelated [[notes]] link"


def test_unreferenced_duplicate_stem_proceeds(tmp_path, capsys):
    """Duplicate stems with ZERO inbound links proceed with a NOTE (real case:
    35/58 cheat-sheet images share stems like image-4 across topic dirs)."""
    v = tmp_path / "docs"
    (v / "topic-a").mkdir(parents=True)
    (v / "topic-b").mkdir(parents=True)
    (v / "topic-a" / "image-4.png").write_bytes(b"a")
    (v / "topic-b" / "image-4.png").write_bytes(b"b")
    apply_map(v, [("topic-a/image-4.png", "topic-a/star-method.png")], use_git=False)
    assert (v / "topic-a" / "star-method.png").exists()
    assert (v / "topic-b" / "image-4.png").exists()  # other duplicate untouched
    out = capsys.readouterr().out
    assert "NOTE: duplicate stem" in out and "proceeding" in out


def test_parse_map_rejects_path_escapes(tmp_path):
    """Absolute paths and .. components are fatal (plain mode could escape the root)."""
    m = tmp_path / "map.tsv"
    bad_lines = [
        "../a.md\tb.md",  # parent escape in old
        "a.md\t../b.md",  # parent escape in new
        "a/../b.md\tc.md",  # embedded parent component
        "/abs/a.md\tb.md",  # absolute old
        "a.md\t/abs/b.md",  # absolute new
    ]
    for bad in bad_lines:
        m.write_text(bad + "\n", encoding="utf-8")
        with pytest.raises(SystemExit):
            parse_map(m)


def test_ambiguous_old_stem_refused(tmp_path):
    """Two files share stem 'x' AND a [[x]] link exists; renaming one would
    retarget that link at the other file — refusal."""
    v = _git_vault(tmp_path)
    (v / "inbox").mkdir()
    (v / "career").mkdir()
    (v / "inbox" / "x.md").write_text("inbox copy", encoding="utf-8")
    (v / "career" / "x.md").write_text("career copy", encoding="utf-8")
    (v / "ref.md").write_text("[[x]] points at one of them", encoding="utf-8")
    _commit_all(v)
    with pytest.raises(SystemExit):
        apply_map(v, [("inbox/x.md", "inbox/y.md")], use_git=True)
    # nothing changed
    assert (v / "inbox" / "x.md").read_text(encoding="utf-8") == "inbox copy"
    assert (v / "career" / "x.md").read_text(encoding="utf-8") == "career copy"
    assert "[[x]]" in (v / "ref.md").read_text(encoding="utf-8")
