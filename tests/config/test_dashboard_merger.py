"""Tests for system-config dashboard merge/write handlers."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.mcp.augur_framework.tools.infrastructure.settings import dashboard


def _valid_llm() -> dict:
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
            },
        },
        "tasks": {"document_ocr": "local"},
    }


def _read_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@pytest.fixture()
def config_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "config"
    system = root / "system"
    system.mkdir(parents=True)
    (system / "llm.yaml").write_text(yaml.safe_dump(_valid_llm(), sort_keys=False), encoding="utf-8")
    (system / "settings.yaml").write_text("mode: production\n", encoding="utf-8")
    monkeypatch.setattr(dashboard._helpers, "_get_config_dir", lambda: root)
    return root


def test_merge_llm_payload_refuses_flat_shape() -> None:
    with pytest.raises(dashboard.LlmSchemaError, match="unknown top-level"):
        dashboard._merge_llm_payload(_valid_llm(), {"model": "x", "provider": "anthropic"})


def test_merge_llm_payload_updates_existing_profile() -> None:
    merged = dashboard._merge_llm_payload(_valid_llm(), {"profile": "remote", "model": "new-model"})

    assert merged["profiles"]["remote"]["model"] == "new-model"
    assert merged["profiles"]["local"]["model"] == "qwen3.5:latest"


def test_merge_llm_payload_adds_task_route() -> None:
    merged = dashboard._merge_llm_payload(_valid_llm(), {"tasks": {"cloud_vision": "remote"}})

    assert merged["tasks"] == {"document_ocr": "local", "cloud_vision": "remote"}


def test_atomic_write_yaml_replaces_existing_file(config_root: Path) -> None:
    path = config_root / "system" / "settings.yaml"

    dashboard._atomic_write_yaml(path, {"mode": "dev", "default_cli": "codex"})

    assert _read_yaml(path) == {"mode": "dev", "default_cli": "codex"}


def test_handle_llm_config_refuses_flat_shape_with_refusal_category(config_root: Path) -> None:
    path = config_root / "system" / "llm.yaml"

    result = dashboard._handle_llm_config({"config": {"model": "x", "provider": "anthropic"}})

    assert result["success"] is False
    assert result["refusal_category"] == "schema_violation"
    assert _read_yaml(path)["profiles"]["local"]["model"] == "qwen3.5:latest"


def test_handle_llm_config_merges_profile_update(config_root: Path) -> None:
    result = dashboard._handle_llm_config({"config": {"profile": "local", "model": "llama3"}})

    assert result["success"] is True
    data = _read_yaml(config_root / "system" / "llm.yaml")
    assert data["profiles"]["local"]["model"] == "llama3"
    assert "remote" in data["profiles"]


def test_handle_llm_config_write_validates_before_write(config_root: Path) -> None:
    path = config_root / "system" / "llm.yaml"
    before = path.read_text(encoding="utf-8")

    result = dashboard._handle_llm_config_write({"yaml": "model: x\nprovider: anthropic\n"})

    assert result["success"] is False
    assert result["refusal_category"] == "schema_violation"
    assert path.read_text(encoding="utf-8") == before


def test_handle_default_cli_preserves_settings(config_root: Path) -> None:
    result = dashboard._handle_default_cli({"default_cli": "claude"})

    assert result["success"] is True
    assert _read_yaml(config_root / "system" / "settings.yaml") == {
        "mode": "production",
        "default_cli": "claude",
    }
