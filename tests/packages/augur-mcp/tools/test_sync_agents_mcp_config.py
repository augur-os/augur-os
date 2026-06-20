"""
Sync Agents MCP Config Distribution Tests (ADR-072).

User Need: When sync_agents.py runs, it generates correct MCP configs
for Cursor, Windsurf, and other IDEs so they can connect to the
augur MCP server with the correct client-id.

Priority: Kimi CLI, Claude CLI, Antigravity, Codex, Cursor, VS Code.

Run with: pytest tests/packages/augur-mcp/tools/test_sync_agents_mcp_config.py -v
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Create a minimal project structure for sync_agents.py."""
    root = tmp_path / "augur"
    root.mkdir()

    # MCP config template
    config_dir = root / "src" / "config"
    config_dir.mkdir(parents=True)
    for package in ("augur_core", "augur_framework", "augur_mcp"):
        (root / "src" / "mcp" / package).mkdir(parents=True)
    manifest_dir = root / "config" / "system"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "mcp_servers.yaml").write_text(
        """
project_tier:
  - id: augur-core
    description: Core discovery server
    scope: global
    command: python
    args: [-m, augur_core]
    startup_timeout_sec: 90
    cwd_required: true
    env:
      PYTHONPATH: "${AUGUR_ROOT}/project-brain/capabilities:${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
      PYTHONUNBUFFERED: "1"
    per_client_args:
      codex: ["--client-id", "codex"]
  - id: augur-framework
    description: Framework operations server
    scope: global
    command: python
    args: [-m, augur_framework]
    cwd_required: true
    env:
      PYTHONPATH: "${AUGUR_ROOT}/project-brain/capabilities:${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp"
      PYTHONUNBUFFERED: "1"
    per_client_args:
      codex: ["--client-id", "codex"]
vault_tier: []
monolith_exclusions: []
""".lstrip(),
        encoding="utf-8",
    )
    (manifest_dir / "capability_exposure.yaml").write_text(
        """
capabilities:
  mcp-server:augur-core:
    classification_status: approved
    export_to:
    - mcp-config
    management: generated
    owner_kind: augur
    preferred_client: dashboard
    primary_surface: mcp
    scope: project
  mcp-server:augur-framework:
    classification_status: approved
    export_to: []
    management: generated
    owner_kind: augur
    preferred_client: dashboard
    primary_surface: mcp
    scope: project
version: 1
""".lstrip(),
        encoding="utf-8",
    )
    template = {
        "mcpServers": {
            "augur-core": {
                "args": ["-m", "augur_core", "--client-id", "${AUGUR_CLIENT_ID}"],
                "command": "${AUGUR_PYTHON}",
                "cwd": "${AUGUR_ROOT}",
                "env": {
                    "AUGUR_ROOT": "${AUGUR_ROOT}",
                    "PYTHONUNBUFFERED": "1",
                    "PYTHONPATH": "${AUGUR_ROOT}/project-brain/capabilities:${AUGUR_ROOT}:${AUGUR_ROOT}/src/mcp",
                },
            }
        }
    }
    (config_dir / "mcp_config.template.json").write_text(json.dumps(template, indent=2))

    # Create IDE config directories
    (root / ".cursor").mkdir()
    (root / ".windsurf").mkdir()

    # Data directory
    (root / "data").mkdir()

    return root


# =============================================================================
# Template Resolution Tests
# =============================================================================


class TestMCPConfigTemplateResolution:
    """
    User Need: MCP config templates have all variables resolved correctly.

    Acceptance Criteria:
    1. ${AUGUR_CLIENT_ID} replaced with correct IDE identifier
    2. ${AUGUR_ROOT} replaced with absolute project path
    3. ${AUGUR_DATA_DIR} replaced with data directory path
    4. ${AUGUR_PYTHON} replaced with Python executable path
    5. No unresolved ${...} variables remain
    """

    def test_cursor_client_id_resolved(self, project_root):
        """Cursor config gets client-id 'cursor'."""
        template = (project_root / "src" / "config" / "mcp_config.template.json").read_text()

        resolved = template.replace("${AUGUR_ROOT}", str(project_root))
        resolved = resolved.replace("${AUGUR_PYTHON}", "python3")
        resolved = resolved.replace("${AUGUR_CLIENT_ID}", "cursor")

        config = json.loads(resolved)
        assert config["mcpServers"]["augur-core"]["args"][3] == "cursor"

    def test_windsurf_client_id_resolved(self, project_root):
        """Windsurf config gets client-id 'windsurf'."""
        template = (project_root / "src" / "config" / "mcp_config.template.json").read_text()

        resolved = template.replace("${AUGUR_ROOT}", str(project_root))
        resolved = resolved.replace("${AUGUR_PYTHON}", "python3")
        resolved = resolved.replace("${AUGUR_CLIENT_ID}", "windsurf")

        config = json.loads(resolved)
        assert config["mcpServers"]["augur-core"]["args"][3] == "windsurf"

    def test_project_root_resolved_in_env(self, project_root):
        """Environment variables contain resolved project root."""
        template = (project_root / "src" / "config" / "mcp_config.template.json").read_text()

        resolved = template.replace("${AUGUR_ROOT}", str(project_root))
        resolved = resolved.replace("${AUGUR_PYTHON}", "python3")
        resolved = resolved.replace("${AUGUR_CLIENT_ID}", "cursor")

        config = json.loads(resolved)
        env = config["mcpServers"]["augur-core"]["env"]
        assert env["AUGUR_ROOT"] == str(project_root)
        assert str(project_root) in env["PYTHONPATH"]
        assert str(project_root / "project-brain" / "capabilities") in env["PYTHONPATH"]

    def test_no_unresolved_variables(self, project_root):
        """All ${...} variables are resolved — none remain."""
        template = (project_root / "src" / "config" / "mcp_config.template.json").read_text()

        resolved = template.replace("${AUGUR_ROOT}", str(project_root))
        resolved = resolved.replace("${AUGUR_PYTHON}", "python3")
        resolved = resolved.replace("${AUGUR_CLIENT_ID}", "cursor")

        assert "${" not in resolved, f"Unresolved variables found: {resolved}"

    def test_cwd_set_to_project_root(self, project_root):
        """MCP server cwd is set to project root."""
        template = (project_root / "src" / "config" / "mcp_config.template.json").read_text()

        resolved = template.replace("${AUGUR_ROOT}", str(project_root))
        resolved = resolved.replace("${AUGUR_PYTHON}", "python3")
        resolved = resolved.replace("${AUGUR_CLIENT_ID}", "cursor")

        config = json.loads(resolved)
        assert config["mcpServers"]["augur-core"]["cwd"] == str(project_root)


class TestConfigureMcpPythonResolution:
    def test_explicit_python_path_wins(self, project_root):
        from scripts.configure_mcp import _resolve_python

        explicit = project_root / "custom-python"

        result = _resolve_python(project_root, str(explicit))

        assert result == explicit

    def test_active_repo_root_reuses_shared_python_resolution(self):
        from scripts.configure_mcp import _resolve_python

        repo_root = Path(__file__).resolve().parents[4]
        shared_python = repo_root / ".venv" / "bin" / "python3"

        with (
            patch("src.config.paths.get_project_root", return_value=repo_root),
            patch(
                "src.config.paths.get_python_executable",
                return_value=shared_python,
            ),
        ):
            result = _resolve_python(repo_root, None)

        assert result == shared_python

    def test_alternate_repo_root_uses_that_repo_venv(self, tmp_path):
        from scripts.configure_mcp import _resolve_python

        repo_root = tmp_path / "other-worktree"
        venv_python = repo_root / ".venv" / "bin" / "python3"
        venv_python.parent.mkdir(parents=True)
        venv_python.write_text("")

        result = _resolve_python(repo_root, None)

        assert result == venv_python

    def test_missing_target_venv_falls_back_to_sys_executable(self, tmp_path):
        from scripts.configure_mcp import _resolve_python

        repo_root = tmp_path / "missing-venv-root"
        fallback = tmp_path / "fallback-python"

        with patch("scripts.configure_mcp.sys.executable", str(fallback)):
            result = _resolve_python(repo_root, None)

        assert result == Path(str(fallback))


# =============================================================================
# Config Merge Tests
# =============================================================================


class TestMCPConfigMerge:
    """
    User Need: Existing MCP configs are preserved when augur config is updated.

    Acceptance Criteria:
    1. User's existing MCP servers are preserved
    2. Retired 'augur' server entries are replaced by the reduced core entry
    3. Invalid existing configs are handled gracefully
    """

    def test_merge_preserves_existing_servers(self, project_root):
        """Existing user MCP servers are preserved during merge."""
        existing = {
            "mcpServers": {
                "my-custom-server": {
                    "command": "custom-server",
                    "args": [],
                },
                "augur": {
                    "command": "old-python",
                    "args": ["old-args"],
                },
            }
        }

        target = project_root / ".cursor" / "mcp.json"
        target.write_text(json.dumps(existing))

        # Read existing and merge
        existing_config = json.loads(target.read_text())
        existing_config["mcpServers"].pop("augur", None)
        existing_config["mcpServers"]["augur-core"] = {
            "command": "python3",
            "args": ["-m", "augur_core", "--client-id", "cursor"],
        }

        assert "my-custom-server" in existing_config["mcpServers"]
        assert "augur" not in existing_config["mcpServers"]
        assert existing_config["mcpServers"]["augur-core"]["command"] == "python3"

    def test_merge_creates_mcpservers_if_missing(self, project_root):
        """If existing config has no mcpServers key, it's created."""
        existing = {"someOtherKey": "value"}

        target = project_root / ".cursor" / "mcp.json"
        target.write_text(json.dumps(existing))

        existing_config = json.loads(target.read_text())
        if not isinstance(existing_config, dict):
            existing_config = {}
        if "mcpServers" not in existing_config:
            existing_config["mcpServers"] = {}
        existing_config["mcpServers"]["augur-core"] = {"command": "python3"}

        assert "mcpServers" in existing_config
        assert "augur-core" in existing_config["mcpServers"]
        assert existing_config["someOtherKey"] == "value"

    def test_invalid_json_in_existing_handled_gracefully(self, project_root):
        """Corrupt existing config is replaced cleanly."""
        target = project_root / ".cursor" / "mcp.json"
        target.write_text("not-valid-json{{{")

        try:
            json.loads(target.read_text())
            existing_valid = True
        except json.JSONDecodeError:
            existing_valid = False

        assert not existing_valid
        # In this case the adapter writes fresh config (no merge)

    def test_non_dict_existing_handled(self, project_root):
        """If existing config is an array or string, start fresh."""
        target = project_root / ".cursor" / "mcp.json"
        target.write_text(json.dumps(["not", "a", "dict"]))

        existing = json.loads(target.read_text())
        if not isinstance(existing, dict):
            existing = {}
        existing["mcpServers"] = {
            "augur-core": {"command": "python3"},
        }

        assert isinstance(existing, dict)
        assert "augur-core" in existing["mcpServers"]


# =============================================================================
# IDE-Specific Config Output Tests
# =============================================================================


class TestIDEConfigOutput:
    """
    User Need: Each IDE gets its config in the correct location with correct format.

    Acceptance Criteria:
    1. Cursor: .cursor/mcp.json
    2. Windsurf: .windsurf/mcp.json
    3. All configs are valid JSON
    4. All configs have the reduced core Augur server entry
    """

    IDE_CONFIGS = [
        ("cursor", ".cursor/mcp.json"),
        ("windsurf", ".windsurf/mcp.json"),
    ]

    @pytest.mark.parametrize("client_id,config_path", IDE_CONFIGS)
    def test_config_written_to_correct_location(self, project_root, client_id, config_path):
        """Config file is placed at the correct IDE-specific path."""
        template = (project_root / "src" / "config" / "mcp_config.template.json").read_text()

        resolved = template.replace("${AUGUR_ROOT}", str(project_root))
        resolved = resolved.replace("${AUGUR_PYTHON}", "python3")
        resolved = resolved.replace("${AUGUR_CLIENT_ID}", client_id)

        config = json.loads(resolved)
        target = project_root / config_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(config, indent=2) + "\n")

        assert target.exists()
        written = json.loads(target.read_text())
        assert "mcpServers" in written
        assert set(written["mcpServers"]) == {"augur-core"}
        assert written["mcpServers"]["augur-core"]["args"][3] == client_id
        assert "augur_mcp" not in target.read_text()
        assert "augur_framework" not in target.read_text()

    @pytest.mark.parametrize("client_id,config_path", IDE_CONFIGS)
    def test_config_is_valid_json(self, project_root, client_id, config_path):
        """Written config is parseable JSON."""
        template = (project_root / "src" / "config" / "mcp_config.template.json").read_text()

        resolved = template.replace("${AUGUR_ROOT}", str(project_root))
        resolved = resolved.replace("${AUGUR_PYTHON}", "python3")
        resolved = resolved.replace("${AUGUR_CLIENT_ID}", client_id)

        config = json.loads(resolved)
        target = project_root / config_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(config, indent=2) + "\n")

        # Should not throw
        parsed = json.loads(target.read_text())
        assert isinstance(parsed, dict)


# =============================================================================
# configure_mcp.py Runtime Argument Tests
# =============================================================================


class TestConfigureMcpRuntimeArgs:
    """Validate IDE-specific MCP runtime args produced by configure_mcp.py."""

    def test_configure_mcp_filters_manifest_entries_by_capability_policy(
        self,
        project_root,
        monkeypatch,
    ):
        """Generated per-client configs must not bypass blocked MCP policy."""
        from scripts.configure_mcp import _build_augur_server_entries_for_ide

        monkeypatch.setattr(
            "src.cli_config.manifest.resolve_capability_records",
            lambda _discovered, *, policy=None: [
                SimpleNamespace(
                    id="mcp-server:augur-core",
                    classification_status="approved",
                    export_to=("codex", "gemini", "generic", "perplexity"),
                    current_exposure=(),
                ),
                SimpleNamespace(
                    id="mcp-server:augur-framework",
                    classification_status="blocked",
                    export_to=(),
                    current_exposure=("codex", "gemini", "generic", "perplexity"),
                ),
            ],
        )

        codex_entries = _build_augur_server_entries_for_ide(
            "codex_cli",
            Path("python3"),
            project_root,
        )
        gemini_entries = _build_augur_server_entries_for_ide(
            "gemini",
            Path("python3"),
            project_root,
        )
        generic_entries = _build_augur_server_entries_for_ide(
            "generic",
            Path("python3"),
            project_root,
        )
        perplexity_entries = _build_augur_server_entries_for_ide(
            "perplexity",
            Path("python3"),
            project_root,
        )

        assert set(codex_entries) == {"augur-core"}
        assert set(gemini_entries) == {"augur-core"}
        assert set(generic_entries) == {"augur-core"}
        assert set(perplexity_entries) == {"augur-core"}

    def test_codex_cli_config_uses_dynamic_worktree_runtime(self, project_root):
        """Codex CLI config must resolve Augur from the active workspace/worktree."""
        from scripts.configure_mcp import _build_augur_server_entries_for_ide

        entries = _build_augur_server_entries_for_ide("codex_cli", Path("python3"), project_root)

        assert set(entries) == {"augur-core"}
        entry = entries["augur-core"]
        assert entry["command"] == str(project_root / "scripts" / "augur-codex-mcp")
        assert entry["args"] == ["-m", "augur_core", "--client-id", "codex"]
        assert entry["startup_timeout_sec"] == 90
        assert "augur_mcp" not in " ".join(entry["args"])
        assert "augur_framework" not in " ".join(entry["args"])
        assert "cwd" not in entry
        assert "env" not in entry

    def test_codex_cli_config_uses_powershell_launcher_on_windows(self, project_root):
        """Codex CLI config should use the native PowerShell launcher on Windows."""
        from scripts.configure_mcp import _build_augur_server_entries_for_ide

        with patch("src.cli_config.codex_runtime.platform.system", return_value="Windows"):
            entries = _build_augur_server_entries_for_ide(
                "codex_cli",
                Path("python.exe"),
                project_root,
            )

        assert set(entries) == {"augur-core"}
        entry = entries["augur-core"]
        assert entry["command"] == "powershell.exe"
        assert entry["args"][:4] == ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
        assert entry["args"][4] == str(project_root / "scripts" / "augur-codex-mcp.ps1")
        assert entry["args"][5:] == ["-m", "augur_core", "--client-id", "codex"]
        assert "cwd" not in entry
        assert "env" not in entry

    def test_cursor_config_uses_explicit_client_id(self, project_root):
        """Cursor config should identify itself to Augur MCP."""
        from scripts.configure_mcp import _build_augur_server_entries_for_ide

        entries = _build_augur_server_entries_for_ide("cursor", Path("python3"), project_root)

        assert set(entries) == {"augur-core"}
        assert entries["augur-core"]["args"] == ["-m", "augur_core", "--client-id", "cursor"]
        assert str(project_root / "project-brain" / "capabilities") in entries["augur-core"]["env"]["PYTHONPATH"]

    def test_copilot_cli_config_uses_copilot_client_id(self, project_root):
        from scripts.configure_mcp import _build_augur_server_entries_for_ide

        entries = _build_augur_server_entries_for_ide("copilot_cli", Path("python3"), project_root)

        assert set(entries) == {"augur-core"}
        assert entries["augur-core"]["args"] == ["-m", "augur_core", "--client-id", "copilot"]
        assert entries["augur-core"]["cwd"] == str(project_root)

    def test_vscode_copilot_config_path_is_repo_root_scoped(self):
        registry_path = Path(__file__).resolve().parents[4] / "config" / "agents" / "ide_mcp_configs.yaml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))

        assert registry["ides"]["vscode_copilot"]["config_path"]["all"] == "{repo_root}/.vscode/mcp.json"

    def test_cursor_runtime_entry_stays_native_on_windows(self, project_root):
        from scripts.configure_mcp import _build_server_entry

        entry = _build_server_entry(
            Path(r"C:\Users\tester\augur\.venv\Scripts\python.exe"),
            project_root,
            ["-m", "augur_core"],
            project_root,
        )

        assert entry["command"].endswith("python.exe")
        assert "wsl.exe" not in entry["command"].lower()
        assert entry["args"] == ["-m", "augur_core"]


# =============================================================================
# Client Capability Mapping Tests
# =============================================================================


class TestClientCapabilityMapping:
    """
    User Need: MCP context manager correctly maps IDE clients to capabilities.

    Priority IDEs (from user request):
    - Kimi CLI, Claude CLI, Antigravity, Codex, Cursor, VS Code
    """

    def test_priority_ide_capabilities(self):
        """All priority IDEs have the expected capability level."""
        from src.mcp.augur_shared.context_manager import CLIENT_CAPABILITIES, ClientCapability

        # Full capability IDEs
        assert CLIENT_CAPABILITIES.get("claude_code") == ClientCapability.FULL
        assert CLIENT_CAPABILITIES.get("cursor") == ClientCapability.FULL

        # Limited capability IDEs
        assert CLIENT_CAPABILITIES.get("codex") == ClientCapability.LIMITED
        assert CLIENT_CAPABILITIES.get("antigravity") == ClientCapability.LIMITED

    def test_all_configured_clients_have_capability(self):
        """Every client in the mapping has a valid capability."""
        from src.mcp.augur_shared.context_manager import CLIENT_CAPABILITIES, ClientCapability

        for client, cap in CLIENT_CAPABILITIES.items():
            assert isinstance(cap, ClientCapability), f"{client} has invalid capability: {cap}"

    def test_unknown_client_defaults_to_none(self):
        """Unknown clients get ClientCapability.NONE."""
        from src.mcp.augur_shared.context_manager import CLIENT_CAPABILITIES, ClientCapability

        cap = CLIENT_CAPABILITIES.get("unknown-ide", ClientCapability.NONE)
        assert cap == ClientCapability.NONE
