"""Tests for the staged system-config pre-commit validator."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.config import precommit_check


def _valid_llm() -> str:
    return yaml.safe_dump(
        {
            "active_profile": "local",
            "profiles": {
                "local": {
                    "provider": "openai_compatible",
                    "base_url": "http://localhost:11434/v1",
                    "model": "qwen3.5:latest",
                },
            },
            "tasks": {},
        },
        sort_keys=False,
    )


def test_relevant_paths_are_detected() -> None:
    assert precommit_check.is_protected_path("config/system/llm.yaml")
    assert precommit_check.is_protected_path(Path("config/system/settings.yaml"))
    assert not precommit_check.is_protected_path("config/system/preferences.yaml")


def test_valid_llm_blob_passes() -> None:
    result = precommit_check.validate_blob("config/system/llm.yaml", _valid_llm())

    assert result.success is True
    assert result.error is None


def test_invalid_llm_blob_fails() -> None:
    result = precommit_check.validate_blob("config/system/llm.yaml", "model: x\nprovider: anthropic\n")

    assert result.success is False
    assert "unknown top-level" in (result.error or "")


def test_valid_settings_blob_passes() -> None:
    result = precommit_check.validate_blob("config/system/settings.yaml", "mode: production\n")

    assert result.success is True


def test_invalid_settings_blob_fails() -> None:
    result = precommit_check.validate_blob("config/system/settings.yaml", "mode: staging\n")

    assert result.success is False
    assert "mode" in (result.error or "")


def test_main_ignores_irrelevant_paths(capsys) -> None:
    exit_code = precommit_check.main(["docs/readme.md"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "No protected system config" in captured.out
