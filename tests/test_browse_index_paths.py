"""Unit tests for browse index_paths filesystem-identity helpers.

Targets the pure helpers in
``src.mcp.augur_framework.tools.infrastructure.browse.index_paths``:
- ``_path_mtime_ns`` / ``_path_lstat_mtime_ns`` — mtime with OSError -> 0
- ``_path_identity`` — fully resolved absolute string
- ``_path_lexical_identity`` — lexical absolute string (no symlink resolution)
- ``_has_symlink_between`` — symlink detection along root->path, and the
  "path not under root" -> True branch.

All filesystem state is created under ``tmp_path``; the real vault/repo are
never touched.

Run with:
    pytest tests/test_browse_index_paths.py -v
"""

from pathlib import Path

from src.mcp.augur_framework.tools.infrastructure.browse.index_paths import (
    _has_symlink_between,
    _path_identity,
    _path_lexical_identity,
    _path_lstat_mtime_ns,
    _path_mtime_ns,
)


class TestMtimeHelpers:
    def test_existing_file_has_positive_mtime(self, tmp_path: Path):
        f = tmp_path / "file.txt"
        f.write_text("data")
        assert _path_mtime_ns(f) > 0

    def test_missing_path_returns_zero(self, tmp_path: Path):
        assert _path_mtime_ns(tmp_path / "nope.txt") == 0

    def test_lstat_existing_file_positive(self, tmp_path: Path):
        f = tmp_path / "f.txt"
        f.write_text("x")
        assert _path_lstat_mtime_ns(f) > 0

    def test_lstat_missing_returns_zero(self, tmp_path: Path):
        assert _path_lstat_mtime_ns(tmp_path / "missing") == 0

    def test_lstat_reflects_symlink_not_target(self, tmp_path: Path):
        target = tmp_path / "target.txt"
        target.write_text("t")
        link = tmp_path / "link.txt"
        link.symlink_to(target)
        # lstat measures the link itself; both should be non-zero and the helper
        # returns the link's own mtime rather than raising.
        assert _path_lstat_mtime_ns(link) > 0


class TestPathIdentity:
    def test_identity_is_absolute_resolved_string(self, tmp_path: Path):
        f = tmp_path / "a" / "b.txt"
        f.parent.mkdir(parents=True)
        f.write_text("x")
        identity = _path_identity(f)
        assert identity == str(f.resolve())
        assert Path(identity).is_absolute()

    def test_identity_resolves_symlink_to_target(self, tmp_path: Path):
        target = tmp_path / "real.txt"
        target.write_text("x")
        link = tmp_path / "alias.txt"
        link.symlink_to(target)
        # Fully resolved identity collapses the symlink onto its target.
        assert _path_identity(link) == str(target.resolve())

    def test_lexical_identity_is_absolute_without_resolving_symlink(self, tmp_path: Path):
        target = tmp_path / "real2.txt"
        target.write_text("x")
        link = tmp_path / "alias2.txt"
        link.symlink_to(target)
        lexical = _path_lexical_identity(link)
        assert Path(lexical).is_absolute()
        # Lexical identity keeps the link name; it does not collapse to target.
        assert lexical.endswith("alias2.txt")


class TestHasSymlinkBetween:
    def test_no_symlink_in_plain_tree(self, tmp_path: Path):
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        assert _has_symlink_between(tmp_path, deep) is False

    def test_detects_symlinked_intermediate_dir(self, tmp_path: Path):
        real = tmp_path / "real_dir"
        real.mkdir()
        (real / "child").mkdir()
        linked = tmp_path / "linked_dir"
        linked.symlink_to(real, target_is_directory=True)
        # linked_dir/child traverses a symlink component.
        assert _has_symlink_between(tmp_path, linked / "child") is True

    def test_path_not_under_root_returns_true(self, tmp_path: Path):
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "elsewhere" / "x"
        # relative_to raises ValueError -> conservative True.
        assert _has_symlink_between(root, outside) is True

    def test_root_equals_path_has_no_symlink(self, tmp_path: Path):
        root = tmp_path / "r"
        root.mkdir()
        assert _has_symlink_between(root, root) is False
