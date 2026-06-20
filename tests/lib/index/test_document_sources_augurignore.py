from src.lib.index.document_sources import DocumentSource, should_index_source_file


def _docs(tmp_path):
    root = tmp_path / "Au-docs"
    (root / "private" / "keepSafe").mkdir(parents=True)
    (root / "finance").mkdir(parents=True)
    secret = root / "private" / "keepSafe" / "stripe_backup_code.txt"
    secret.write_text("code", encoding="utf-8")
    ok = root / "finance" / "budget.md"
    ok.write_text("# Budget", encoding="utf-8")
    return root, secret, ok


def test_augurignore_excludes_private(tmp_path):
    root, secret, ok = _docs(tmp_path)
    (root / ".augurignore").write_text("private/\n", encoding="utf-8")
    src = DocumentSource("documents", "Au-docs", root, preserve_legacy_output=True)
    assert should_index_source_file(secret, src) is False
    assert should_index_source_file(ok, src) is True


def test_no_augurignore_indexes_markdown(tmp_path):
    root, secret, ok = _docs(tmp_path)
    src = DocumentSource("documents", "Au-docs", root, preserve_legacy_output=True)
    assert should_index_source_file(ok, src) is True
