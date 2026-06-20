"""Behavior tests for setup foundation probes."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

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
foundation = importlib.import_module(f"{PKG}.probes.foundation")


def test_index_machine_done_when_manifest_present(setup_env) -> None:
    manifest = PROJECT_ROOT / "docs" / "generated" / "skill-manifest.json"
    assert manifest.exists(), "Repo manifest expected for this test"

    result = foundation.index_machine()

    assert result.status == "done"
    assert "skill inventory" in (result.details or "")


def test_index_machine_pending_when_no_inventory(setup_env, monkeypatch, tmp_path) -> None:
    fake_root = tmp_path / "no-manifest-root"
    fake_root.mkdir()
    monkeypatch.setattr(foundation, "get_project_root", lambda: fake_root)
    monkeypatch.setattr(foundation, "get_runtime_dir", lambda: tmp_path / "empty-runtime")

    result = foundation.index_machine()

    assert result.status == "pending"


def test_vault_done_when_writable(setup_env) -> None:
    result = foundation.vault()

    assert result.status == "done"
    assert str(setup_env.vault_dir) in (result.details or "")


def test_vault_pending_when_missing(setup_env, monkeypatch, tmp_path) -> None:
    missing = tmp_path / "no-such-vault"
    monkeypatch.setattr(foundation, "get_vault_dir", lambda: missing)

    result = foundation.vault()

    assert result.status == "pending"
    assert "missing" in (result.details or "")


def test_human_profile_done_with_memory_profile(setup_env) -> None:
    setup_env.add_profile()

    result = foundation.human_profile()

    assert result.status == "done"


def test_human_profile_pending_when_too_short(setup_env) -> None:
    vault_dir = setup_env.vault_dir / "memory"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "profile.md").write_text("tiny", encoding="utf-8")

    result = foundation.human_profile()

    assert result.status == "pending"


def test_human_profile_pending_when_absent(setup_env) -> None:
    result = foundation.human_profile()

    assert result.status == "pending"


def test_voice_profile_done_when_english_present(setup_env) -> None:
    setup_env.add_voice_profile("en")

    result = foundation.voice_profile()

    assert result.status == "done"


def test_voice_profile_done_when_hebrew_present(setup_env) -> None:
    setup_env.add_voice_profile("he")

    result = foundation.voice_profile()

    assert result.status == "done"


def test_voice_profile_pending_when_only_too_short(setup_env) -> None:
    profile_dir = setup_env.vault_dir / "profile" / "en"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "about-me.md").write_text("tiny", encoding="utf-8")

    result = foundation.voice_profile()

    assert result.status == "pending"
