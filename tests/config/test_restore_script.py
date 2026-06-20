"""Tests for one-shot system config restoration."""

from __future__ import annotations

from pathlib import Path

import yaml

import scripts.restore_system_config as restore


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _template() -> dict:
    return {
        "active_profile": "local",
        "profiles": {
            "local": {
                "provider": "openai_compatible",
                "base_url": "http://localhost:11434/v1",
                "model": "qwen3.5:latest",
                "timeout_s": 120,
            },
            "remote": {
                "provider": "openai_compatible",
                "base_url": "https://example.test/v1",
                "model": "remote-model",
                "api_key_env": "REMOTE_API_KEY",
            },
        },
        "tasks": {"document_ocr": "local"},
    }


def test_build_restored_llm_replaces_flat_shape() -> None:
    restored = restore.build_restored_llm_config(
        {"model": "claude-opus-4", "provider": "anthropic"},
        _template(),
    )

    assert restored["active_profile"] == "local"
    assert "profiles" in restored
    assert "local" in restored["profiles"]


def test_build_restored_llm_leaves_valid_current_config_unchanged() -> None:
    current = _template()
    current["profiles"]["vision-local"] = {
        "provider": "openai_compatible",
        "base_url": "http://localhost:11434/v1",
        "model": "llava",
    }

    restored = restore.build_restored_llm_config(current, _template())

    assert restored == current


def test_build_restored_llm_salvages_matching_profile_values() -> None:
    current = _template()
    current["profiles"]["remote"]["api_key_env"] = "USER_REMOTE_KEY"
    current["profiles"]["remote"]["model"] = "user-model"

    restored = restore.build_restored_llm_config(current, _template())

    assert restored["profiles"]["remote"]["api_key_env"] == "USER_REMOTE_KEY"
    assert restored["profiles"]["remote"]["model"] == "user-model"


def test_build_restored_llm_drops_dangling_task() -> None:
    current = _template()
    current["tasks"]["broken"] = "ghost"

    restored = restore.build_restored_llm_config(current, _template())

    assert "broken" not in restored["tasks"]


def test_build_restored_settings_preserves_known_values() -> None:
    restored = restore.build_restored_settings({"mode": "dev", "default_cli": "codex", "x": 1})

    assert restored == {"mode": "dev", "default_cli": "codex"}


def test_apply_restore_writes_backups_and_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"
    cache = tmp_path / "cache"
    _write_yaml(
        root / "project-brain" / "capabilities" / "skills" / "ai" / "augur" / "config" / "llm.yaml.template",
        _template(),
    )
    _write_yaml(root / "config" / "system" / "llm.yaml", {"model": "x", "provider": "anthropic"})
    _write_yaml(root / "config" / "system" / "settings.yaml", {"mode": "production"})

    monkeypatch.setattr(restore, "get_project_root", lambda: root)
    monkeypatch.setattr(restore, "get_config_dir", lambda: root / "config")
    monkeypatch.setattr(restore, "get_cache_dir", lambda: cache)

    result1 = restore.restore_system_config(apply=True)
    first = (root / "config" / "system" / "llm.yaml").read_text(encoding="utf-8")
    result2 = restore.restore_system_config(apply=True)
    second = (root / "config" / "system" / "llm.yaml").read_text(encoding="utf-8")

    assert result1["success"] is True
    assert result2["success"] is True
    assert first == second
    assert (cache / "system-config-restore" / "llm.yaml.bak").exists()
    assert (cache / "system-config-restore" / "settings.yaml.bak").exists()


def test_dry_run_does_not_write(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "repo"
    cache = tmp_path / "cache"
    _write_yaml(
        root / "project-brain" / "capabilities" / "skills" / "ai" / "augur" / "config" / "llm.yaml.template",
        _template(),
    )
    llm_path = root / "config" / "system" / "llm.yaml"
    _write_yaml(llm_path, {"model": "x", "provider": "anthropic"})
    _write_yaml(root / "config" / "system" / "settings.yaml", {"mode": "production"})
    before = llm_path.read_text(encoding="utf-8")

    monkeypatch.setattr(restore, "get_project_root", lambda: root)
    monkeypatch.setattr(restore, "get_config_dir", lambda: root / "config")
    monkeypatch.setattr(restore, "get_cache_dir", lambda: cache)

    result = restore.restore_system_config(apply=False)

    assert result["success"] is True
    assert llm_path.read_text(encoding="utf-8") == before
    assert not cache.exists()
