"""Tests for Cowork formatter (Claude Desktop plugin output)."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SHARED_VAULT_ROOT = REPO_ROOT / "project-brain"
PLUGIN_PACK_ROOT = SHARED_VAULT_ROOT / "capabilities" / "skills" / "plugin-pack"
for _path in (REPO_ROOT, SHARED_VAULT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

SCRIPTS_DIR = PLUGIN_PACK_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_write_manifest_creates_claude_plugin_dir(tmp_path):
    from formatters.cowork import CoworkFormatter
    fmt = CoworkFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    fmt.write_manifest(plugin_dir, "1.0.0")

    manifest_path = plugin_dir / ".claude-plugin" / "plugin.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    assert data["name"] == "augur"
    assert data["version"] == "1.0.0"
    assert data["author"]["name"] == "Gur Sannikov"


def test_write_mcp_config(monkeypatch, tmp_path):
    from formatters.cowork import CoworkFormatter

    monkeypatch.setattr(
        "src.cli_config.manifest.resolve_capability_records",
        lambda _discovered, *, policy=None: [
            SimpleNamespace(
                id="mcp-server:augur-core",
                classification_status="approved",
                export_to=("cowork",),
                current_exposure=(),
            ),
            SimpleNamespace(
                id="mcp-server:augur-framework",
                classification_status="approved",
                export_to=("cowork",),
                current_exposure=(),
            ),
        ],
    )

    fmt = CoworkFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    fmt.write_mcp_config(plugin_dir, Path("/fake/root"), "/fake/python")

    mcp_path = plugin_dir / ".mcp.json"
    assert mcp_path.exists()
    data = json.loads(mcp_path.read_text())
    assert "augur" not in data["mcpServers"]
    assert data["mcpServers"]["augur-core"]["args"] == [
        "-m",
        "augur_core",
        "--client-id",
        "cowork",
    ]
    assert data["mcpServers"]["augur-framework"]["args"] == [
        "-m",
        "augur_framework",
        "--client-id",
        "cowork",
    ]
    assert "augur_mcp" not in mcp_path.read_text()


def test_write_skills(tmp_path):
    from formatters.cowork import CoworkFormatter
    fmt = CoworkFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    fmt.write_skills(plugin_dir, {
        "career": "---\nname: career\n---\n# Career\n",
        "finance": "---\nname: finance\n---\n# Finance\n",
    })
    assert (plugin_dir / "skills" / "career" / "SKILL.md").exists()
    assert (plugin_dir / "skills" / "finance" / "SKILL.md").exists()


def test_write_commands(tmp_path):
    from formatters.cowork import CoworkFormatter
    fmt = CoworkFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    fmt.write_commands(plugin_dir, {
        "ask": {"description": "Ask a question", "body": "Ask body."},
    })
    cmd_path = plugin_dir / "commands" / "ask.md"
    assert cmd_path.exists()
    content = cmd_path.read_text()
    assert "name: ask" in content
    assert "Ask body." in content


def test_write_commands_with_empty_command_set_does_not_create_commands_dir(tmp_path):
    from formatters.cowork import CoworkFormatter

    fmt = CoworkFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()

    fmt.write_commands(plugin_dir, {})

    assert not (plugin_dir / "commands").exists()


def test_write_commands_with_empty_command_set_removes_stale_commands_dir(tmp_path):
    from formatters.cowork import CoworkFormatter

    fmt = CoworkFormatter()
    plugin_dir = tmp_path / "augur"
    stale_commands_dir = plugin_dir / "commands"
    stale_commands_dir.mkdir(parents=True)
    (stale_commands_dir / "ask.md").write_text("stale command", encoding="utf-8")

    fmt.write_commands(plugin_dir, {})

    assert not stale_commands_dir.exists()


def test_write_marketplace(tmp_path):
    from formatters.cowork import CoworkFormatter
    fmt = CoworkFormatter()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    fmt.write_marketplace(output_dir, "1.0.0")

    mp_path = output_dir / ".claude-plugin" / "marketplace.json"
    assert mp_path.exists()
    data = json.loads(mp_path.read_text())
    assert data["name"] == "augur-cowork"
    assert len(data["plugins"]) == 1


def test_register_mcp_connector_preserves_existing_augur_server_when_policy_resolution_fails(
    monkeypatch,
    tmp_path,
):
    from formatters import cowork
    from src.cli_config.manifest import Manifest, ServerEntry

    home = tmp_path / "home"
    config_path = (
        home
        / "Library"
        / "Application Support"
        / "Claude"
        / "claude_desktop_config.json"
    )
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "context7": {"command": "npx", "args": []},
                    "augur-existing": {"command": "old", "args": []},
                }
            }
        ),
        encoding="utf-8",
    )

    project_root = tmp_path / "project"
    project_root.mkdir()
    policy_path = tmp_path / "capability_exposure.yaml"
    policy_path.write_text("version: 1\ncapabilities: {}\n", encoding="utf-8")
    manifest = Manifest(
        project_tier=[
            ServerEntry(
                id="augur-existing",
                description="existing",
                command="python",
                args=["-m", "augur_existing"],
            ),
            ServerEntry(
                id="augur-new",
                description="new",
                command="python",
                args=["-m", "augur_new"],
            ),
        ],
        vault_tier=[],
        monolith_exclusions=[],
        policy_path=policy_path,
    )

    def fail_resolution(*_args, **_kwargs):
        raise RuntimeError("policy resolver unavailable")

    monkeypatch.setattr(cowork.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr("src.config.paths.get_project_root", lambda: project_root)
    monkeypatch.setitem(cowork.build_augur_mcp_servers.__globals__, "load_manifest", lambda _path: manifest)
    monkeypatch.setattr(
        "src.cli_config.manifest.resolve_capability_records",
        fail_resolution,
    )

    cowork._register_mcp_connector(tmp_path / "output")

    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert "context7" in data["mcpServers"]
    assert "augur-existing" in data["mcpServers"]
    assert "augur-new" not in data["mcpServers"]


def test_register_mcp_connector_from_worktree_uses_main_root(
    monkeypatch,
    tmp_path,
):
    from formatters import cowork
    from src.cli_config.manifest import Manifest, ServerEntry

    home = tmp_path / "home"
    config_path = (
        home
        / "Library"
        / "Application Support"
        / "Claude"
        / "claude_desktop_config.json"
    )
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")

    main_root = tmp_path / "main"
    worktree_root = tmp_path / "worktree"
    (main_root / ".git" / "worktrees" / "worktree").mkdir(parents=True)
    (main_root / ".venv" / "bin").mkdir(parents=True)
    (main_root / ".venv" / "bin" / "python3").write_text("", encoding="utf-8")
    (main_root / "project.yaml").write_text("name: augur\n", encoding="utf-8")
    worktree_root.mkdir()
    (worktree_root / ".git").write_text(
        f"gitdir: {main_root / '.git' / 'worktrees' / 'worktree'}\n",
        encoding="utf-8",
    )
    policy_path = tmp_path / "capability_exposure.yaml"
    policy_path.write_text("version: 1\ncapabilities: {}\n", encoding="utf-8")
    manifest = Manifest(
        project_tier=[
            ServerEntry(
                id="augur-core",
                description="core",
                command="python",
                args=["-m", "augur_core"],
            ),
        ],
        vault_tier=[],
        monolith_exclusions=[],
        policy_path=policy_path,
    )

    monkeypatch.setattr(cowork.Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr("src.config.paths.get_project_root", lambda: worktree_root)
    monkeypatch.setitem(cowork.build_augur_mcp_servers.__globals__, "load_manifest", lambda _path: manifest)
    monkeypatch.setattr(
        "src.cli_config.manifest.resolve_capability_records",
        lambda _discovered, *, policy=None: [
            SimpleNamespace(
                id="mcp-server:augur-core",
                classification_status="approved",
                export_to=("cowork",),
                current_exposure=(),
            )
        ],
    )

    cowork._register_mcp_connector(tmp_path / "output")

    data = json.loads(config_path.read_text(encoding="utf-8"))
    rendered = json.dumps(data["mcpServers"]["augur-core"])
    assert str(main_root) in rendered
    assert str(worktree_root) not in rendered
