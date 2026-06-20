"""Tests for src.lib.vault_links (per-machine `files` symlink generation)."""

import logging
import os

import pytest

from src.lib.vault_links import generate_links


def _vault(tmp_path):
    v = tmp_path / "vault"
    for d in ("career", "finance", "inbox", "wiki", "sources", "profile", "_augur"):
        (v / d).mkdir(parents=True)
    (v / "BRAIN.yaml").write_text("layout: domains\n", encoding="utf-8")
    return v


def test_links_created_for_matching_domains_only(tmp_path):
    v = _vault(tmp_path)
    docs = tmp_path / "docs"
    for d in ("career", "inbox", "sources"):
        (docs / d).mkdir(parents=True)
    created = generate_links(v, docs)
    link = v / "career" / "files"
    assert link.is_symlink() and link.resolve() == (docs / "career").resolve()
    assert not os.path.isabs(os.readlink(link))  # relative when possible
    assert not (v / "inbox" / "files").exists()  # capture infra excluded
    assert not (v / "finance" / "files").exists()  # no docs counterpart
    assert str(link) in created


def test_existing_real_folder_never_clobbered(tmp_path):
    v = _vault(tmp_path)
    docs = tmp_path / "docs"
    (docs / "career").mkdir(parents=True)
    (v / "career" / "files").mkdir()  # real folder
    (v / "career" / "files" / "keep.md").write_text("x", encoding="utf-8")
    generate_links(v, docs)
    assert (v / "career" / "files" / "keep.md").exists()


def test_gitignore_entry_added(tmp_path):
    v = _vault(tmp_path)
    docs = tmp_path / "docs"
    (docs / "career").mkdir(parents=True)
    generate_links(v, docs)
    assert "*/files" in (v / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_idempotent_and_repairs_stale(tmp_path):
    v = _vault(tmp_path)
    docs = tmp_path / "docs"
    (docs / "career").mkdir(parents=True)
    os.symlink("/nonexistent", v / "career" / "files")
    link = v / "career" / "files"
    created = generate_links(v, docs)
    assert link.resolve() == (docs / "career").resolve()
    assert str(link) in created  # stale repair counted
    again = generate_links(v, docs)
    assert str(link) not in again  # healthy link skipped
    assert link.resolve() == (docs / "career").resolve()


def test_per_domain_error_isolation(tmp_path, monkeypatch, caplog):
    v = _vault(tmp_path)
    docs = tmp_path / "docs"
    for d in ("career", "finance"):
        (docs / d).mkdir(parents=True)
    real_symlink = os.symlink

    def flaky(src, dst, **kwargs):
        if "finance" in str(dst):
            raise OSError("disk says no")  # both attempts fail
        real_symlink(src, dst, **kwargs)

    monkeypatch.setattr(os, "symlink", flaky)
    with caplog.at_level(logging.WARNING, logger="lib.vault_links"):
        created = generate_links(v, docs)  # must not raise
    link = v / "career" / "files"
    assert link.is_symlink() and str(link) in created
    assert not (v / "finance" / "files").exists()
    assert str(v / "finance" / "files") not in created
    assert "could not link" in caplog.text


def test_no_links_when_docs_root_absent(tmp_path):
    v = _vault(tmp_path)
    created = generate_links(v, tmp_path / "missing-docs")
    assert created == []
    assert not (v / "career" / "files").exists()


def test_non_dir_vault_raises(tmp_path):
    not_a_dir = tmp_path / "not-a-dir"
    not_a_dir.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="vault root is not a directory"):
        generate_links(not_a_dir, tmp_path / "docs")
