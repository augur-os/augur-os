"""Behavior tests for setup persisted state (preferences.yaml)."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SETUP_DIR = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "onboard" / "scripts" / "setup"

PKG = "onboard_setup_pkg"


def _ensure_package() -> None:
    if PKG in sys.modules:
        return
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    spec = importlib.util.spec_from_file_location(
        PKG,
        SETUP_DIR / "__init__.py",
        submodule_search_locations=[str(SETUP_DIR)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[PKG] = module
    spec.loader.exec_module(module)


_ensure_package()
state = importlib.import_module(f"{PKG}.state")


def test_load_persisted_state_empty_when_file_missing(tmp_path: Path) -> None:
    path = tmp_path / "preferences.yaml"

    result = state.load_persisted_state(path)

    assert result.skipped == []
    assert result.ever_completed is False


def test_save_skipped_persists_and_dedupes(tmp_path: Path) -> None:
    path = tmp_path / "preferences.yaml"

    saved = state.save_skipped(["wiki-pages-5", "integration", "wiki-pages-5"], path)

    assert saved == ["integration", "wiki-pages-5"]
    loaded = state.load_persisted_state(path)
    assert loaded.skipped == ["integration", "wiki-pages-5"]


def test_load_persisted_state_strips_whitespace_entries(tmp_path: Path) -> None:
    path = tmp_path / "preferences.yaml"
    state.save_skipped(["wiki-pages-5", "", "   "], path)

    loaded = state.load_persisted_state(path)

    assert loaded.skipped == ["wiki-pages-5"]


def test_save_ever_completed_writes_true(tmp_path: Path) -> None:
    path = tmp_path / "preferences.yaml"

    state.save_ever_completed(True, path)

    assert state.load_persisted_state(path).ever_completed is True
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["setup"]["ever_completed"] is True


def test_save_skipped_preserves_existing_ever_completed(tmp_path: Path) -> None:
    path = tmp_path / "preferences.yaml"
    state.save_ever_completed(True, path)

    state.save_skipped(["integration"], path)

    loaded = state.load_persisted_state(path)
    assert loaded.skipped == ["integration"]
    assert loaded.ever_completed is True


def test_load_persisted_state_handles_corrupt_yaml(tmp_path: Path) -> None:
    path = tmp_path / "preferences.yaml"
    path.write_text("not: yaml: at all: :::\n", encoding="utf-8")

    try:
        result = state.load_persisted_state(path)
    except yaml.YAMLError:
        return

    assert result.skipped == []
    assert result.ever_completed is False


def test_load_persisted_state_ignores_non_dict_setup_block(tmp_path: Path) -> None:
    path = tmp_path / "preferences.yaml"
    path.write_text("setup: [not, a, dict]\n", encoding="utf-8")

    result = state.load_persisted_state(path)

    assert result.skipped == []
    assert result.ever_completed is False
