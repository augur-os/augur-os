"""Tests for the shared never-touch path classifier."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "never_touch.py"
_SPEC = importlib.util.spec_from_file_location("never_touch_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def test_git_dir_is_never_touch():
    assert mod.is_never_touch(Path("venture-augur/.git/config"))


def test_obsidian_dir_is_never_touch():
    assert mod.is_never_touch(Path(".obsidian/app.json"))


def test_pytest_cache_is_never_touch():
    assert mod.is_never_touch(Path("foo/.pytest_cache/v/cache.bin"))


def test_tmp_driveupload_is_never_touch():
    assert mod.is_never_touch(Path(".tmp.driveupload/x"))


def test_node_modules_is_never_touch():
    assert mod.is_never_touch(Path("foo/node_modules/x/index.js"))


def test_venv_is_never_touch():
    assert mod.is_never_touch(Path(".venv/bin/python"))


def test_pycache_is_never_touch():
    assert mod.is_never_touch(Path("foo/__pycache__/x.pyc"))


def test_archive_dir_is_never_touch():
    assert mod.is_never_touch(Path("foo/.archive/bar.zip"))


def test_archive_dir_nested_is_never_touch():
    assert mod.is_never_touch(Path("foo/.archive/2026-05/bar.zip"))


def test_package_lock_is_never_touch():
    assert mod.is_never_touch(Path("foo/package-lock.json"))


def test_pnpm_lock_is_never_touch():
    assert mod.is_never_touch(Path("foo/pnpm-lock.yaml"))


def test_uv_lock_is_never_touch():
    assert mod.is_never_touch(Path("uv.lock"))


def test_augur_docs_marker_is_never_touch():
    assert mod.is_never_touch(Path(".augur-docs"))


def test_augur_vault_marker_is_never_touch():
    assert mod.is_never_touch(Path(".augur-vault"))


def test_augur_ignore_marker_is_never_touch():
    assert mod.is_never_touch(Path("foo/.augur-ignore"))


def test_augur_reserved_marker_is_never_touch():
    assert mod.is_never_touch(Path(".augur-reserved"))


def test_normal_file_is_not_never_touch():
    assert not mod.is_never_touch(Path("venture-augur/websites/guriqo-com-V10032.zip"))


def test_ds_store_is_not_never_touch():
    # DS_Store is a separate concern (cosmetic clutter); never-touch only
    # protects working-state files. Caller may add own ignore handling.
    assert not mod.is_never_touch(Path("foo/.DS_Store"))


def test_constants_are_frozensets():
    assert isinstance(mod.NEVER_TOUCH_DIR_NAMES, frozenset)
    assert isinstance(mod.NEVER_TOUCH_FILE_GLOBS, frozenset)
    assert isinstance(mod.NEVER_TOUCH_PREFIXES, frozenset)
