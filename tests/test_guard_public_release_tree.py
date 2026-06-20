from __future__ import annotations

from pathlib import Path

import scripts.guard_public_release_tree as g

REPO = Path(__file__).resolve().parents[1]


def test_guard_source_has_no_committed_personal_markers():
    text = (REPO / "scripts/guard_public_release_tree.py").read_text(encoding="utf-8")
    # "janedoe" stands in for any real owner username; the guard source must
    # carry no personal username or private-brand marker.
    for forbidden in ("janedoe", "IntelSubmit", "angel-deck", "Au-vault", "Au-docs"):
        assert forbidden not in text, f"personal marker {forbidden!r} committed in guard source"


def test_generic_secret_markers_still_present():
    assert "PRIVATE KEY" in g.FORBIDDEN_CONTENT_MARKERS
    assert any("API_KEY" in m for m in g.FORBIDDEN_CONTENT_MARKERS)


def test_env_marker_regex_flags_content(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_PRIVATE_MARKER_REGEX", "janedoe")
    f = tmp_path / "README.md"
    f.write_text("contact janedoe@example.com\n", encoding="utf-8")
    violations = g.collect_public_tree_violations(tmp_path, allowed_paths=None)
    assert any(v.reason == "forbidden content marker" and "janedoe" in (v.detail or "") for v in violations)


def test_no_env_marker_no_marker_violation(tmp_path, monkeypatch):
    monkeypatch.delenv("AUGUR_PRIVATE_MARKER_REGEX", raising=False)
    f = tmp_path / "README.md"
    f.write_text("contact janedoe@example.com\n", encoding="utf-8")
    violations = g.collect_public_tree_violations(tmp_path, allowed_paths=None)
    assert not any(v.reason == "forbidden content marker" for v in violations)


import textwrap


def _scope_file(tmp_path: Path, scope: str) -> Path:
    cfg_dir = tmp_path / "config/system"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "release_scope.yaml").write_text(f"scope: {scope}\n", encoding="utf-8")
    # minimal partition policy so scan_partition has something to read
    (cfg_dir / "partition_policy.yaml").write_text(
        textwrap.dedent("""
            private_paths: ["secret/**"]
            forbidden_suffixes: [".key"]
            forbidden_names: [".env"]
            secret_patterns: []
            exclude_dirs: [".git"]
            exclude_globs: []
            """),
        encoding="utf-8",
    )
    return cfg_dir / "release_scope.yaml"


def test_full_scope_flags_partition_finding(tmp_path, monkeypatch):
    # source_root carries scope=full + policy; the pushed tree has a .key file
    src = tmp_path / "src_root"
    src.mkdir()
    _scope_file(src, "full")
    tree = tmp_path / "tree"
    (tree / "app").mkdir(parents=True)
    (tree / "app/server.key").write_text("x", encoding="utf-8")
    monkeypatch.delenv("AUGUR_PRIVATE_MARKER_REGEX", raising=False)
    try:
        g.guard_public_tree(tree, source_root=src)
        assert False, "expected PublicReleaseGuardError"
    except g.PublicReleaseGuardError as exc:
        assert any("server.key" in v.path for v in exc.violations)


def test_full_scope_clean_tree_passes(tmp_path, monkeypatch):
    src = tmp_path / "src_root"
    src.mkdir()
    _scope_file(src, "full")
    tree = tmp_path / "tree"
    (tree / "app").mkdir(parents=True)
    (tree / "app/ok.py").write_text("print('hi')\n", encoding="utf-8")
    monkeypatch.delenv("AUGUR_PRIVATE_MARKER_REGEX", raising=False)
    assert g.guard_public_tree(tree, source_root=src) == []
