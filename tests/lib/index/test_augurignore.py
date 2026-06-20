from src.lib.index.augurignore import load_augurignore, path_is_ignored


def test_dir_pattern_ignores_nested(tmp_path):
    (tmp_path / ".augurignore").write_text("private/\n", encoding="utf-8")
    pats = load_augurignore(tmp_path)
    assert path_is_ignored("private/keepSafe/stripe_backup_code.txt", pats)
    assert path_is_ignored("private/family/id.pdf", pats)
    assert not path_is_ignored("finance/budget.xlsx", pats)


def test_glob_matches_anywhere(tmp_path):
    (tmp_path / ".augurignore").write_text("**/*recovery*\n**/*backup*code*\n", encoding="utf-8")
    pats = load_augurignore(tmp_path)
    assert path_is_ignored("finance/Keep/BTC Wallet Recovery Backup Sheet/_1.md", pats)
    assert path_is_ignored("a/b/github-recovery-codes.txt", pats)
    assert not path_is_ignored("finance/budget.xlsx", pats)


def test_bare_name_matches_segment(tmp_path):
    (tmp_path / ".augurignore").write_text("keepSafe\n", encoding="utf-8")
    pats = load_augurignore(tmp_path)
    assert path_is_ignored("keepSafe/x.txt", pats)
    assert path_is_ignored("a/keepSafe/x.txt", pats)


def test_comments_and_blanks_ignored(tmp_path):
    (tmp_path / ".augurignore").write_text("# secrets\n\nprivate/\n", encoding="utf-8")
    pats = load_augurignore(tmp_path)
    assert pats == ["private/"]


def test_absent_file_is_empty_noop(tmp_path):
    pats = load_augurignore(tmp_path)
    assert pats == []
    assert not path_is_ignored("anything/at/all.md", pats)
