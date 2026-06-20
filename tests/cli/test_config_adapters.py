"""Tests for the per-client config adapters."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import tomllib

from src.cli_config.adapters import ClaudeAdapter, CodexAdapter, CopilotAdapter, GeminiAdapter
from src.cli_config.adapters._paths import render_entry_dict
from src.cli_config.manifest import Manifest, ServerEntry


def _make_manifest(*entries: ServerEntry) -> Manifest:
    project = [e for e in entries if not e.id.startswith("augur-")]
    vault = [e for e in entries if e.id.startswith("augur-")]
    return Manifest(project_tier=project, vault_tier=vault, monolith_exclusions=[])


def _assert_codex_entry_launches(entry: dict, server_args: list[str]) -> None:
    if entry["command"] == "powershell.exe":
        assert entry["args"][:4] == ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
        assert entry["args"][4].replace("\\", "/").endswith("/scripts/augur-codex-mcp.ps1")
        assert entry["args"][5:] == server_args
        return

    assert entry["command"].replace("\\", "/").endswith("/scripts/augur-codex-mcp")
    assert entry["args"] == server_args


def _policy_record(
    capability_id: str,
    *,
    status: str = "approved",
    export_to: tuple[str, ...] = (),
    current_exposure: tuple[str, ...] = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        id=capability_id,
        classification_status=status,
        export_to=export_to,
        current_exposure=current_exposure,
    )


def _set_mcp_policy_records(monkeypatch: pytest.MonkeyPatch, *records: SimpleNamespace) -> None:
    monkeypatch.setattr(
        "src.cli_config.manifest.resolve_capability_records",
        lambda _discovered, *, policy=None: list(records),
    )


def test_render_entry_dict_matches_mcp_runtime_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    if os.name == "nt":
        python_path = project_root / ".venv" / "Scripts" / "python.exe"
    else:
        python_path = project_root / ".venv" / "bin" / "python3"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    monkeypatch.setattr(
        "src.cli_config.adapters._paths.get_project_root",
        lambda: project_root,
    )

    rendered = render_entry_dict(
        ServerEntry(
            id="augur-core",
            description="core",
            command="python",
            args=["-m", "augur_core"],
            cwd_required=True,
            env={
                "PYTHONPATH": "${AUGUR_ROOT}/project-brain/capabilities:${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp",
                "PYTHONUNBUFFERED": "1",
            },
            per_client_args={"gemini": ["--client-id", "gemini"]},
        ),
        client="gemini",
    )

    assert rendered == {
        "command": str(python_path),
        "args": ["-m", "augur_core", "--client-id", "gemini"],
        "cwd": str(project_root),
        "env": {
            "AUGUR_ROOT": str(project_root),
            "PYTHONPATH": f"{project_root}/project-brain/capabilities:{project_root}:{project_root}/src/mcp",
            "PYTHONUNBUFFERED": "1",
        },
    }


@pytest.fixture
def manifest_with_apple() -> Manifest:
    return _make_manifest(
        ServerEntry(
            id="augur",
            description="monolith",
            command="python",
            args=["-m", "augur_framework"],
            cwd_required=True,
            env={"PYTHONUNBUFFERED": "1"},
        ),
        ServerEntry(
            id="augur-apple",
            description="apple per-bundle server",
            command="python",
            args=["-m", "augur_shared.bundle_server", "apple"],
            bundle="apple",
            bundle_path="~/Projects/Au-vault/skills/apple",
        ),
    )


def test_manifest_filters_mcp_servers_by_capability_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.cli_config.manifest import _build_manifest

    manifest = _build_manifest(
        {
            "project_tier": [
                {
                    "id": "augur-core",
                    "command": "python",
                    "args": ["-m", "src.mcp.augur_core"],
                    "platforms": ["darwin"],
                    "scope": "global",
                },
                {
                    "id": "augur-framework",
                    "command": "python",
                    "args": ["-m", "src.mcp.augur_framework"],
                    "scope": "global",
                },
                {
                    "id": "augur-legacy",
                    "command": "python",
                    "args": ["-m", "src.mcp.augur_legacy"],
                    "scope": "global",
                },
                {
                    "id": "augur-linux",
                    "command": "python",
                    "args": ["-m", "src.mcp.augur_linux"],
                    "platforms": ["linux"],
                    "scope": "global",
                },
            ]
        }
    )
    _set_mcp_policy_records(
        monkeypatch,
        _policy_record("mcp-server:augur-core", export_to=("gemini",)),
        _policy_record(
            "mcp-server:augur-framework",
            status="blocked",
            current_exposure=("gemini",),
        ),
        _policy_record("mcp-server:augur-linux", export_to=("gemini",)),
    )

    assert [entry.id for entry in manifest.all_augur_servers_for_client("gemini", platform_name="darwin")] == [
        "augur-core",
        "augur-legacy",
    ]


def test_manifest_filter_uses_policy_next_to_loaded_manifest(tmp_path: Path) -> None:
    from src.cli_config.manifest import load_manifest

    manifest_path = tmp_path / "config" / "system" / "mcp_servers.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        """
# TODO_CLEANUP: This file is 864 lines — consider splitting into smaller modules
project_tier:
  - id: augur-core
    command: python
    args: ["-m", "src.mcp.augur_core"]
    scope: global
  - id: augur-framework
    command: python
    args: ["-m", "src.mcp.augur_framework"]
    scope: global
vault_tier: []
monolith_exclusions: []
""".lstrip(),
        encoding="utf-8",
    )
    (manifest_path.parent / "capability_exposure.yaml").write_text(
        """
version: 1
capabilities:
  mcp-server:augur-core:
    classification_status: approved
    export_to: [gemini]
  mcp-server:augur-framework:
    classification_status: blocked
    export_to: []
""".lstrip(),
        encoding="utf-8",
    )

    manifest = load_manifest(manifest_path)

    assert [entry.id for entry in manifest.all_augur_servers_for_client("gemini")] == ["augur-core"]


def test_active_project_scope_is_excluded_from_home_ai_client_configs() -> None:
    from src.cli_config.manifest import load_manifest

    manifest = load_manifest()
    existing_ids = {
        "augur-core",
        "augur-framework",
        "augur-ingest",
        "augur-vault",
    }

    for client in ("claude", "codex", "gemini"):
        assert [
            entry.id
            for entry in manifest.all_augur_servers_for_client(
                client,
                existing_server_ids=existing_ids,
            )
        ] == []


def test_manifest_preserves_existing_unclassified_mcp_server_without_exporting_new_ones(
    tmp_path: Path,
) -> None:
    from src.cli_config.manifest import load_manifest

    manifest_path = tmp_path / "config" / "system" / "mcp_servers.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        """
project_tier:
  - id: augur-existing
    command: python
    args: ["-m", "src.mcp.augur_existing"]
    scope: global
  - id: augur-new
    command: python
    args: ["-m", "src.mcp.augur_new"]
    scope: global
vault_tier: []
monolith_exclusions: []
""".lstrip(),
        encoding="utf-8",
    )
    (manifest_path.parent / "capability_exposure.yaml").write_text(
        "version: 1\ncapabilities: {}\n",
        encoding="utf-8",
    )

    manifest = load_manifest(manifest_path)

    assert (
        manifest.all_augur_servers_for_client(
            "codex",
            existing_server_ids=set(),
        )
        == []
    )
    assert [
        entry.id
        for entry in manifest.all_augur_servers_for_client(
            "codex",
            existing_server_ids={"augur-existing"},
        )
    ] == ["augur-existing"]


def test_manifest_policy_resolution_failure_preserves_only_existing_mcp_servers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.cli_config.manifest import load_manifest

    manifest_path = tmp_path / "config" / "system" / "mcp_servers.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        """
project_tier:
  - id: augur-existing
    command: python
    args: ["-m", "src.mcp.augur_existing"]
    scope: global
  - id: augur-new
    command: python
    args: ["-m", "src.mcp.augur_new"]
    scope: global
vault_tier: []
monolith_exclusions: []
""".lstrip(),
        encoding="utf-8",
    )
    (manifest_path.parent / "capability_exposure.yaml").write_text(
        "version: 1\ncapabilities: {}\n",
        encoding="utf-8",
    )

    def fail_resolution(*_args: object, **_kwargs: object) -> list[SimpleNamespace]:
        raise RuntimeError("policy resolver unavailable")

    monkeypatch.setattr(
        "src.cli_config.manifest.resolve_capability_records",
        fail_resolution,
    )

    manifest = load_manifest(manifest_path)

    assert [
        entry.id
        for entry in manifest.all_augur_servers_for_client(
            "codex",
            existing_server_ids={"augur-existing"},
        )
    ] == ["augur-existing"]
    assert (
        manifest.all_augur_servers_for_client(
            "codex",
            existing_server_ids=set(),
        )
        == []
    )


def test_codex_adapter_writes_toml(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    cfg = tmp_path / "config.toml"
    adapter = CodexAdapter()
    adapter.apply(manifest_with_apple, config_path=cfg)
    data = tomllib.loads(cfg.read_text())
    assert "augur" in data["mcp_servers"]
    assert "augur-apple" in data["mcp_servers"]
    _assert_codex_entry_launches(
        data["mcp_servers"]["augur-apple"],
        ["-m", "augur_shared.bundle_server", "apple"],
    )


def test_codex_adapter_preserves_non_augur_servers(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text('[mcp_servers.context7]\ncommand = "npx"\nargs = ["-y", "@upstash/context7-mcp"]\n')
    adapter = CodexAdapter()
    adapter.apply(manifest_with_apple, config_path=cfg)
    data = tomllib.loads(cfg.read_text())
    assert "context7" in data["mcp_servers"]
    assert data["mcp_servers"]["context7"]["command"] == "npx"
    assert "augur" in data["mcp_servers"]


def test_codex_adapter_applies_client_filtered_entries_and_preserves_other_servers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[mcp_servers.context7]\ncommand = "npx"\nargs = []\n'
        '[mcp_servers.augur-framework]\ncommand = "old"\nargs = []\n'
    )
    manifest = Manifest(
        project_tier=[
            ServerEntry(
                id="augur-core",
                description="core",
                command="python",
                args=["-m", "src.mcp.augur_core"],
            ),
            ServerEntry(
                id="augur-framework",
                description="framework",
                command="python",
                args=["-m", "src.mcp.augur_framework"],
            ),
        ],
        vault_tier=[],
        monolith_exclusions=[],
    )
    _set_mcp_policy_records(
        monkeypatch,
        _policy_record("mcp-server:augur-core", export_to=("codex",)),
        _policy_record(
            "mcp-server:augur-framework",
            status="blocked",
            current_exposure=("codex",),
        ),
    )

    CodexAdapter().apply(manifest, config_path=cfg)

    data = tomllib.loads(cfg.read_text())
    assert "context7" in data["mcp_servers"]
    assert "augur-core" in data["mcp_servers"]
    assert "augur-framework" not in data["mcp_servers"]


def test_codex_adapter_accepts_generic_mcp_config_policy_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cfg = tmp_path / "config.toml"
    manifest = Manifest(
        project_tier=[
            ServerEntry(
                id="augur-framework",
                description="framework",
                command="python",
                args=["-m", "src.mcp.augur_framework"],
            ),
        ],
        vault_tier=[],
        monolith_exclusions=[],
    )
    _set_mcp_policy_records(
        monkeypatch,
        _policy_record("mcp-server:augur-framework", export_to=("mcp-config",)),
    )

    CodexAdapter().apply(manifest, config_path=cfg)

    data = tomllib.loads(cfg.read_text())
    assert "augur-framework" in data["mcp_servers"]


def test_codex_adapter_idempotent(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    cfg = tmp_path / "config.toml"
    adapter = CodexAdapter()
    adapter.apply(manifest_with_apple, config_path=cfg)
    first = cfg.read_text()
    adapter.apply(manifest_with_apple, config_path=cfg)
    second = cfg.read_text()
    assert first == second


def test_codex_adapter_diff_signals_changes(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    cfg = tmp_path / "config.toml"
    adapter = CodexAdapter()
    diff = adapter.diff(manifest_with_apple, config_path=cfg)
    assert {e.id for e in diff.added} == {"augur", "augur-apple"}
    adapter.apply(manifest_with_apple, config_path=cfg)
    diff2 = adapter.diff(manifest_with_apple, config_path=cfg)
    assert not diff2.has_changes


def test_codex_adapter_creates_backup(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text("[other]\nkey = 'value'\n")
    adapter = CodexAdapter()
    backup = adapter.apply(manifest_with_apple, config_path=cfg)
    assert backup.exists()
    assert backup.name.startswith("config.toml.bak.")


def test_codex_adapter_removes_stale_augur_entries(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[mcp_servers.augur-apple]\ncommand = "old"\nargs = []\n' '[mcp_servers.context7]\ncommand = "npx"\nargs = []\n'
    )
    empty = Manifest(project_tier=[], vault_tier=[], monolith_exclusions=[])
    CodexAdapter().apply(empty, config_path=cfg)
    data = tomllib.loads(cfg.read_text())
    assert "augur-apple" not in data["mcp_servers"]
    assert "context7" in data["mcp_servers"]


def test_codex_adapter_removes_unsupported_platform_augur_entries(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("src.cli_config.manifest.platform.system", lambda: "Windows")
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        '[mcp_servers.augur-apple]\ncommand = "old"\nargs = []\n' '[mcp_servers.context7]\ncommand = "npx"\nargs = []\n'
    )
    manifest = Manifest(
        project_tier=[
            ServerEntry(
                id="augur-core",
                description="core",
                command="python",
                args=["-m", "augur_core"],
            ),
        ],
        vault_tier=[
            ServerEntry(
                id="augur-apple",
                description="apple per-bundle server",
                command="python",
                args=["-m", "augur_shared.bundle_server", "apple"],
                bundle="apple",
                bundle_path="/tmp/apple",
                platforms=["darwin"],
            ),
        ],
        monolith_exclusions=["apple"],
    )

    CodexAdapter().apply(manifest, config_path=cfg)

    data = tomllib.loads(cfg.read_text())
    assert "augur-core" in data["mcp_servers"]
    assert "augur-apple" not in data["mcp_servers"]
    assert "context7" in data["mcp_servers"]


def test_claude_adapter_writes_json(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text("{}")
    adapter = ClaudeAdapter()
    adapter.apply(manifest_with_apple, config_path=cfg)
    data = json.loads(cfg.read_text())
    assert "augur" in data["mcpServers"]
    assert "augur-apple" in data["mcpServers"]


def test_claude_adapter_preserves_other_keys(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text(json.dumps({"theme": "dark", "mcpServers": {"context7": {"command": "npx", "args": []}}}))
    adapter = ClaudeAdapter()
    adapter.apply(manifest_with_apple, config_path=cfg)
    data = json.loads(cfg.read_text())
    assert data["theme"] == "dark"
    assert "context7" in data["mcpServers"]


def test_claude_adapter_applies_client_filtered_entries_and_preserves_other_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text(
        json.dumps(
            {
                "theme": "dark",
                "mcpServers": {
                    "context7": {"command": "npx", "args": []},
                    "augur-framework": {"command": "old", "args": []},
                },
            }
        )
    )
    manifest = Manifest(
        project_tier=[
            ServerEntry(
                id="augur-core",
                description="core",
                command="python",
                args=["-m", "src.mcp.augur_core"],
            ),
            ServerEntry(
                id="augur-framework",
                description="framework",
                command="python",
                args=["-m", "src.mcp.augur_framework"],
            ),
        ],
        vault_tier=[],
        monolith_exclusions=[],
    )
    _set_mcp_policy_records(
        monkeypatch,
        _policy_record("mcp-server:augur-core", export_to=("claude",)),
        _policy_record(
            "mcp-server:augur-framework",
            status="blocked",
            current_exposure=("claude",),
        ),
    )

    ClaudeAdapter().apply(manifest, config_path=cfg)

    data = json.loads(cfg.read_text())
    assert data["theme"] == "dark"
    assert "context7" in data["mcpServers"]
    assert "augur-core" in data["mcpServers"]
    assert "augur-framework" not in data["mcpServers"]


def test_gemini_adapter_uses_gemini_path() -> None:
    adapter = GeminiAdapter()
    assert adapter.default_config_path() == Path.home() / ".gemini" / "settings.json"


def test_gemini_adapter_skips_bundle_servers_to_stay_under_function_cap(
    tmp_path: Path,
    manifest_with_apple: Manifest,
) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "context7": {"command": "npx", "args": []},
                    "augur-apple": {"command": "old", "args": []},
                }
            }
        )
    )

    GeminiAdapter().apply(manifest_with_apple, config_path=cfg)

    data = json.loads(cfg.read_text())
    assert "context7" in data["mcpServers"]
    assert "augur" in data["mcpServers"]
    assert "augur-apple" not in data["mcpServers"]


def test_gemini_adapter_filters_policy_and_still_skips_bundle_servers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "context7": {"command": "npx", "args": []},
                    "augur-framework": {"command": "old", "args": []},
                    "augur-apple": {"command": "old", "args": []},
                }
            }
        )
    )
    manifest = Manifest(
        project_tier=[
            ServerEntry(
                id="augur-core",
                description="core",
                command="python",
                args=["-m", "src.mcp.augur_core"],
            ),
            ServerEntry(
                id="augur-framework",
                description="framework",
                command="python",
                args=["-m", "src.mcp.augur_framework"],
            ),
        ],
        vault_tier=[
            ServerEntry(
                id="augur-apple",
                description="apple per-bundle server",
                command="python",
                args=["-m", "src.mcp.bundle_server", "apple"],
                bundle="apple",
                bundle_path="/tmp/apple",
            ),
        ],
        monolith_exclusions=[],
    )
    _set_mcp_policy_records(
        monkeypatch,
        _policy_record("mcp-server:augur-core", export_to=("gemini",)),
        _policy_record(
            "mcp-server:augur-framework",
            status="blocked",
            current_exposure=("gemini",),
        ),
        _policy_record("mcp-server:augur-apple", export_to=("gemini",)),
    )

    GeminiAdapter().apply(manifest, config_path=cfg)

    data = json.loads(cfg.read_text())
    assert "context7" in data["mcpServers"]
    assert "augur-core" in data["mcpServers"]
    assert "augur-framework" not in data["mcpServers"]
    assert "augur-apple" not in data["mcpServers"]


def test_codex_runtime_mcp_servers_are_client_filtered(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from src.cli_config.codex_runtime import _build_codex_mcp_servers

    manifest_path = tmp_path / "config" / "system" / "mcp_servers.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("""
project_tier:
  - id: augur-core
    command: python
    args: ["-m", "src.mcp.augur_core"]
    scope: global
  - id: augur-framework
    command: python
    args: ["-m", "src.mcp.augur_framework"]
    scope: global
""")
    _set_mcp_policy_records(
        monkeypatch,
        _policy_record("mcp-server:augur-core", export_to=("codex",)),
        _policy_record(
            "mcp-server:augur-framework",
            status="blocked",
            current_exposure=("codex",),
        ),
    )

    servers = _build_codex_mcp_servers(tmp_path)

    assert set(servers) == {"augur-core"}


def test_codex_adapter_uses_compact_launcher_without_env(tmp_path: Path) -> None:
    """Codex uses the cwd-independent launcher instead of embedding env/cwd."""
    cfg = tmp_path / "config.toml"
    cfg.write_text("")
    manifest = _make_manifest(
        ServerEntry(
            id="augur",
            description="monolith",
            command="python",
            args=["-m", "augur_framework"],
            cwd_required=True,
            env={"PYTHONPATH": "${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"},
        ),
    )
    CodexAdapter().apply(manifest, config_path=cfg)
    data = tomllib.loads(cfg.read_text())
    entry = data["mcp_servers"]["augur"]
    _assert_codex_entry_launches(entry, ["-m", "augur_framework"])
    assert "cwd" not in entry
    assert "env" not in entry


def test_codex_adapter_renders_startup_timeout(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text("")
    manifest = Manifest(
        project_tier=[
            ServerEntry(
                id="augur-core",
                description="core",
                command="python",
                args=["-m", "augur_core"],
                startup_timeout_sec=90,
            )
        ],
        vault_tier=[],
        monolith_exclusions=[],
    )

    CodexAdapter().apply(manifest, config_path=cfg)

    data = tomllib.loads(cfg.read_text())
    entry = data["mcp_servers"]["augur-core"]
    _assert_codex_entry_launches(entry, ["-m", "augur_core"])
    assert entry["startup_timeout_sec"] == 90


def test_codex_adapter_omits_cwd_when_required(tmp_path: Path) -> None:
    """The launcher resolves cwd at runtime, so Codex entries omit `cwd`."""
    cfg = tmp_path / "config.toml"
    cfg.write_text("")
    manifest = _make_manifest(
        ServerEntry(
            id="augur",
            description="",
            command="python",
            args=["-m", "augur_framework"],
            cwd_required=True,
        ),
    )
    CodexAdapter().apply(manifest, config_path=cfg)
    data = tomllib.loads(cfg.read_text())
    assert "cwd" not in data["mcp_servers"]["augur"]


def test_codex_adapter_omits_cwd_when_not_required(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text("")
    manifest = _make_manifest(
        ServerEntry(
            id="augur-test",
            description="",
            command="python",
            args=[],
            cwd_required=False,
            bundle="x",
            bundle_path="/tmp/x",
        ),
    )
    CodexAdapter().apply(manifest, config_path=cfg)
    data = tomllib.loads(cfg.read_text())
    assert "cwd" not in data["mcp_servers"]["augur-test"]


def test_canonical_manifest_renders_cleanly_for_all_adapters(tmp_path: Path) -> None:
    """The committed config/system/mcp_servers.yaml renders without literal ${VAR} strings."""
    from src.cli_config.manifest import load_manifest

    manifest = load_manifest()  # canonical file

    for AdapterCls, fname in [
        (ClaudeAdapter, "claude.json"),
        (CodexAdapter, "codex.toml"),
        (GeminiAdapter, "gemini.json"),
        (CopilotAdapter, "copilot.json"),
    ]:
        cfg = tmp_path / fname
        cfg.write_text("{}" if fname.endswith(".json") else "")
        AdapterCls().apply(manifest, config_path=cfg)

        rendered = cfg.read_text()
        assert "${" not in rendered, f"{fname}: literal ${{...}} remains in rendered output"


def test_adapter_apply_returns_none_when_no_prior_config(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    """apply() returns None instead of a sentinel when there was no file to back up."""
    cfg = tmp_path / "config.toml"
    # File does not exist yet.
    backup = CodexAdapter().apply(manifest_with_apple, config_path=cfg)
    assert backup is None


def test_claude_adapter_apply_returns_none_when_no_prior_config(tmp_path: Path, manifest_with_apple: Manifest) -> None:
    cfg = tmp_path / "settings.json"
    backup = ClaudeAdapter().apply(manifest_with_apple, config_path=cfg)
    assert backup is None


def test_codex_adapter_appends_codex_per_client_args(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text("")
    manifest = _make_manifest(
        ServerEntry(
            id="augur",
            description="",
            command="python",
            args=["-m", "augur_framework"],
            per_client_args={
                "claude": ["--client-id", "claude"],
                "codex": ["--client-id", "codex"],
                "gemini": ["--client-id", "gemini"],
            },
        ),
    )
    CodexAdapter().apply(manifest, config_path=cfg)
    data = tomllib.loads(cfg.read_text())
    _assert_codex_entry_launches(
        data["mcp_servers"]["augur"],
        ["-m", "augur_framework", "--client-id", "codex"],
    )


def test_claude_adapter_appends_claude_per_client_args(tmp_path: Path) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text("{}")
    manifest = _make_manifest(
        ServerEntry(
            id="augur",
            description="",
            command="python",
            args=["-m", "augur_framework"],
            per_client_args={
                "claude": ["--client-id", "claude"],
                "gemini": ["--client-id", "gemini"],
            },
        ),
    )
    ClaudeAdapter().apply(manifest, config_path=cfg)
    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["augur"]["args"] == ["-m", "augur_framework", "--client-id", "claude"]


def test_gemini_adapter_appends_gemini_per_client_args(tmp_path: Path) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text("{}")
    manifest = _make_manifest(
        ServerEntry(
            id="augur",
            description="",
            command="python",
            args=["-m", "augur_framework"],
            per_client_args={
                "claude": ["--client-id", "claude"],
                "gemini": ["--client-id", "gemini"],
            },
        ),
    )
    GeminiAdapter().apply(manifest, config_path=cfg)
    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["augur"]["args"] == ["-m", "augur_framework", "--client-id", "gemini"]


def test_copilot_adapter_appends_copilot_per_client_args(tmp_path: Path) -> None:
    cfg = tmp_path / "mcp-config.json"
    cfg.write_text("{}")
    manifest = _make_manifest(
        ServerEntry(
            id="augur",
            description="",
            command="python",
            args=["-m", "augur_framework"],
            per_client_args={
                "claude": ["--client-id", "claude"],
                "copilot": ["--client-id", "copilot"],
            },
        ),
    )
    CopilotAdapter().apply(manifest, config_path=cfg)
    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["augur"]["args"] == ["-m", "augur_framework", "--client-id", "copilot"]


def test_no_per_client_args_does_not_change_args(tmp_path: Path) -> None:
    """Without per_client_args, args are unchanged across adapters."""
    cfg = tmp_path / "config.toml"
    cfg.write_text("")
    manifest = _make_manifest(
        ServerEntry(
            id="augur-test",
            description="",
            command="python",
            args=["-m", "augur_shared.bundle_server", "x"],
            bundle="x",
            bundle_path="/tmp/x",
        ),
    )
    CodexAdapter().apply(manifest, config_path=cfg)
    data = tomllib.loads(cfg.read_text())
    _assert_codex_entry_launches(
        data["mcp_servers"]["augur-test"],
        ["-m", "augur_shared.bundle_server", "x"],
    )
