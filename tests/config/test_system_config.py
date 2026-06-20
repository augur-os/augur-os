"""Tests for validated system config readers."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.config.schemas.llm_schema import LlmSchemaError
from src.config.schemas.settings_schema import SettingsSchemaError
from src.config import system_config


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


@pytest.fixture()
def config_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "config"
    system = root / "system"
    system.mkdir(parents=True)
    monkeypatch.setattr(system_config, "get_config_dir", lambda: root)
    system_config.invalidate_caches()
    yield root
    system_config.invalidate_caches()


def _valid_llm() -> dict:
    return {
        "active_profile": "local",
        "profiles": {
            "local": {
                "provider": "openai_compatible",
                "base_url": "http://localhost:11434/v1",
                "model": "qwen3.5:latest",
            },
        },
        "tasks": {},
    }


def test_load_llm_config_validates_and_caches(config_root: Path) -> None:
    path = config_root / "system" / "llm.yaml"
    _write_yaml(path, _valid_llm())

    first = system_config.load_llm_config()
    path.write_text("model: broken\nprovider: anthropic\n", encoding="utf-8")
    second = system_config.load_llm_config()

    assert first is second
    assert second.active_profile == "local"


def test_invalidate_caches_forces_reload(config_root: Path) -> None:
    path = config_root / "system" / "llm.yaml"
    _write_yaml(path, _valid_llm())
    assert system_config.load_llm_config().profiles["local"].model == "qwen3.5:latest"

    data = _valid_llm()
    data["profiles"]["local"]["model"] = "new-model"
    _write_yaml(path, data)
    system_config.invalidate_caches()

    assert system_config.load_llm_config().profiles["local"].model == "new-model"


def test_load_llm_config_rejects_broken_shape(config_root: Path) -> None:
    (config_root / "system" / "llm.yaml").write_text(
        "model: claude-opus-4\nprovider: anthropic\n",
        encoding="utf-8",
    )

    with pytest.raises(LlmSchemaError, match="llm.yaml"):
        system_config.load_llm_config()


def test_load_llm_config_requires_file(config_root: Path) -> None:
    with pytest.raises(FileNotFoundError, match="llm.yaml"):
        system_config.load_llm_config()


def test_raw_llm_reader_returns_unvalidated_mapping(config_root: Path) -> None:
    (config_root / "system" / "llm.yaml").write_text(
        "model: claude-opus-4\nprovider: anthropic\n",
        encoding="utf-8",
    )

    assert system_config.llm_config_raw() == {
        "model": "claude-opus-4",
        "provider": "anthropic",
    }


def test_settings_defaults_when_missing(config_root: Path) -> None:
    cfg = system_config.load_settings_config()

    assert cfg.mode == "production"
    assert cfg.default_cli is None


def test_load_settings_config_rejects_invalid_mode(config_root: Path) -> None:
    _write_yaml(config_root / "system" / "settings.yaml", {"mode": "staging"})

    with pytest.raises(SettingsSchemaError, match="settings.yaml"):
        system_config.load_settings_config()


def test_raw_settings_reader_returns_empty_when_missing(config_root: Path) -> None:
    assert system_config.settings_config_raw() == {}
