from __future__ import annotations

from pathlib import Path
import subprocess

from src.lib.frontmatter_utils import write_frontmatter
from src.lib.relationship_index import RelationshipIndex, _git_head_cache_key


def test_relationship_index_reads_wikilink_frontmatter_targets(tmp_path: Path) -> None:
    vault_root = tmp_path / "vault"
    note_path = vault_root / "brain" / "mentored.md"
    write_frontmatter(
        note_path,
        {
            "title": "Mentored",
            "mentors": ["[[Ada Lovelace]]", "[[Grace Hopper|Grace]]"],
        },
        "Body.\n",
    )

    index = RelationshipIndex.build(vault_root)

    assert index.relationships_for(note_path) == {
        "mentors": ["Ada Lovelace", "Grace Hopper"],
    }


def test_relationship_index_records_wikilinks_from_any_frontmatter_field(tmp_path: Path) -> None:
    vault_root = tmp_path / "vault"
    note_path = vault_root / "brain" / "plain.md"
    write_frontmatter(
        note_path,
        {
            "title": "[[Not A Relationship]]",
            "tags": ["[[Not A Relationship]]"],
        },
        "Body.\n",
    )

    index = RelationshipIndex.build(vault_root)

    assert index.relationships_for(note_path) == {
        "title": ["Not A Relationship"],
        "tags": ["Not A Relationship"],
    }


def test_git_head_cache_key_returns_none_when_git_probe_times_out(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_run(*_args, **_kwargs):
        assert _kwargs["timeout"] == 5
        raise subprocess.TimeoutExpired(cmd=["git"], timeout=5)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert _git_head_cache_key(tmp_path) is None


def test_git_head_cache_key_skips_git_inside_windows_mcp(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_run(*_args, **_kwargs):
        raise AssertionError("git should not run from Windows MCP cache keys")

    monkeypatch.setattr("src.lib.relationship_index._is_windows", lambda: True)
    monkeypatch.setenv("AUGUR_MCP_CLIENT_ID", "dashboard-demo")
    monkeypatch.setattr(subprocess, "run", fake_run)

    assert _git_head_cache_key(tmp_path) is None
