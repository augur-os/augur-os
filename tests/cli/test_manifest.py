"""Tests for src/cli_config/manifest.py."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.cli_config.manifest import Manifest, load_manifest


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "mcp_servers.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_loads_minimal_manifest(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "project_tier": [
                {"id": "augur", "command": "python", "args": ["-m", "augur_mcp"]},
            ],
            "vault_tier": [],
            "monolith_exclusions": [],
        },
    )
    m = load_manifest(p)
    assert isinstance(m, Manifest)
    assert m.project_tier[0].id == "augur"
    assert m.vault_tier == []
    assert m.monolith_exclusions == []


def test_validates_unique_ids(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "project_tier": [
                {"id": "augur", "command": "python", "args": []},
                {"id": "augur", "command": "python", "args": []},
            ],
        },
    )
    with pytest.raises(ValueError, match="Duplicate server id"):
        load_manifest(p)


def test_vault_entry_must_have_bundle(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "project_tier": [],
            "vault_tier": [{"id": "augur-apple", "command": "python", "args": []}],
        },
    )
    with pytest.raises(ValueError, match="missing 'bundle'"):
        load_manifest(p)


def test_vault_entry_id_must_have_augur_prefix(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "vault_tier": [
                {
                    "id": "apple",
                    "command": "python",
                    "args": [],
                    "bundle": "apple",
                    "bundle_path": "/tmp/apple",
                },
            ],
        },
    )
    with pytest.raises(ValueError, match="must start with 'augur-'"):
        load_manifest(p)


def test_exclusion_must_have_corresponding_vault_entry(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "vault_tier": [],
            "monolith_exclusions": ["apple"],
        },
    )
    with pytest.raises(ValueError, match="without vault_tier entry"):
        load_manifest(p)


def test_empty_manifest_loads(tmp_path: Path) -> None:
    p = _write(tmp_path, {})
    m = load_manifest(p)
    assert m.project_tier == m.vault_tier == []
    assert m.monolith_exclusions == []


def test_canonical_manifest_loads() -> None:
    """The committed config/system/mcp_servers.yaml must load cleanly.

    Track 3a PR 6 atomically replaced the legacy `augur` monolith with
    `augur-core` + `augur-framework`; this test now asserts on the new
    project-tier shape.
    """
    m = load_manifest()
    project_ids = {e.id for e in m.project_tier}
    assert "augur-core" in project_ids
    assert "augur-framework" in project_ids
    assert "augur" not in project_ids
    assert next(e for e in m.project_tier if e.id == "augur-core").startup_timeout_sec == 90


def test_per_client_args_loads(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "project_tier": [
                {
                    "id": "augur",
                    "command": "python",
                    "args": ["-m", "augur_mcp"],
                    "per_client_args": {
                        "claude": ["--client-id", "claude"],
                        "codex": ["--client-id", "codex"],
                        "gemini": ["--client-id", "gemini"],
                    },
                }
            ],
        },
    )
    m = load_manifest(p)
    entry = m.project_tier[0]
    assert entry.per_client_args["claude"] == ["--client-id", "claude"]
    assert entry.per_client_args["codex"] == ["--client-id", "codex"]
    assert entry.per_client_args["gemini"] == ["--client-id", "gemini"]


def test_per_client_args_optional(tmp_path: Path) -> None:
    """Entries without per_client_args have empty dict."""
    p = _write(
        tmp_path,
        {
            "project_tier": [{"id": "augur", "command": "python", "args": []}],
        },
    )
    m = load_manifest(p)
    assert m.project_tier[0].per_client_args == {}


def test_startup_timeout_loads(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "project_tier": [
                {
                    "id": "augur-core",
                    "command": "python",
                    "args": ["-m", "augur_core"],
                    "startup_timeout_sec": 90,
                },
            ],
        },
    )
    m = load_manifest(p)
    assert m.project_tier[0].startup_timeout_sec == 90


def test_startup_timeout_rejects_invalid_value(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "project_tier": [
                {
                    "id": "augur-core",
                    "command": "python",
                    "args": ["-m", "augur_core"],
                    "startup_timeout_sec": 0,
                },
            ],
        },
    )
    with pytest.raises(ValueError, match="startup_timeout_sec"):
        load_manifest(p)


def test_per_client_args_rejects_unknown_client(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "project_tier": [
                {
                    "id": "augur",
                    "command": "python",
                    "args": [],
                    "per_client_args": {"nonexistent": ["--foo"]},
                }
            ],
        },
    )
    with pytest.raises(ValueError, match="unknown client"):
        load_manifest(p)


def test_per_client_args_rejects_non_list_value(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "project_tier": [
                {
                    "id": "augur",
                    "command": "python",
                    "args": [],
                    "per_client_args": {"claude": "not-a-list"},
                }
            ],
        },
    )
    with pytest.raises(ValueError, match="must be a list"):
        load_manifest(p)


def test_platform_allowlist_filters_augur_servers(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "project_tier": [
                {"id": "augur-core", "command": "python", "args": ["-m", "augur_core"]},
            ],
            "vault_tier": [
                {
                    "id": "augur-apple",
                    "command": "python",
                    "args": ["-m", "augur_shared.bundle_server", "apple"],
                    "bundle": "apple",
                    "bundle_path": "/tmp/apple",
                    "platforms": ["darwin"],
                },
                {
                    "id": "augur-ingest",
                    "command": "python",
                    "args": ["-m", "augur_shared.bundle_server", "ingest"],
                    "bundle": "ingest",
                    "bundle_path": "/tmp/ingest",
                },
            ],
            "monolith_exclusions": ["apple", "ingest"],
        },
    )
    m = load_manifest(p)

    assert m.vault_tier[0].platforms == ["darwin"]
    assert {e.id for e in m.all_augur_servers(platform_name="Windows")} == {
        "augur-core",
        "augur-ingest",
    }
    assert {e.id for e in m.all_augur_servers(platform_name="Darwin")} == {
        "augur-core",
        "augur-apple",
        "augur-ingest",
    }


def test_platforms_rejects_unknown_value(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        {
            "project_tier": [
                {
                    "id": "augur-core",
                    "command": "python",
                    "args": ["-m", "augur_core"],
                    "platforms": ["temple-os"],
                },
            ],
        },
    )
    with pytest.raises(ValueError, match="unknown value"):
        load_manifest(p)
