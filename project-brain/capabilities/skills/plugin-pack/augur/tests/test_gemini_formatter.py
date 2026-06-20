"""Tests for Gemini formatter (Gemini CLI extension output)."""
import json
import logging
import sys
import tomllib
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


def test_plugin_dir_uses_gemini_extensions_layout(tmp_path):
    from formatters.gemini import GeminiFormatter

    assert GeminiFormatter().plugin_dir(tmp_path / "build") == (
        tmp_path / "build" / "extensions" / "augur"
    )


def test_write_manifest_creates_gemini_manifest_and_context(tmp_path):
    from formatters.gemini import GeminiFormatter

    fmt = GeminiFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()

    fmt.write_manifest(plugin_dir, "1.0.0")

    manifest_path = plugin_dir / "gemini-extension.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    assert data["name"] == "augur"
    assert data["version"] == "1.0.0"
    assert data["contextFileName"] == "GEMINI.md"
    assert "mcpServers" not in data

    context = (plugin_dir / "GEMINI.md").read_text()
    assert "/augur:ask" in context
    assert "/augur:project" in context
    assert "/augur:dev" not in context
    assert "/augur:skillify" in context
    assert "/augur:save" not in context
    assert "/augur:search" not in context
    assert "augur MCP server" in context


def test_write_mcp_config_merges_gemini_client_id_into_manifest(monkeypatch, tmp_path):
    from formatters.gemini import GeminiFormatter

    monkeypatch.setattr(
        "src.cli_config.manifest.resolve_capability_records",
        lambda _discovered, *, policy=None: [
            SimpleNamespace(
                id="mcp-server:augur-core",
                classification_status="approved",
                export_to=("gemini",),
                current_exposure=(),
            ),
            SimpleNamespace(
                id="mcp-server:augur-framework",
                classification_status="approved",
                export_to=("gemini",),
                current_exposure=(),
            ),
        ],
    )

    fmt = GeminiFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()

    fmt.write_manifest(plugin_dir, "1.0.0")
    fmt.write_mcp_config(plugin_dir, Path("/fake/root"), "/fake/python")

    data = json.loads((plugin_dir / "gemini-extension.json").read_text())
    servers = data["mcpServers"]
    assert "augur" not in servers
    assert servers["augur-core"]["command"] == "/fake/python"
    assert servers["augur-core"]["args"] == ["-m", "augur_core", "--client-id", "gemini"]
    assert servers["augur-framework"]["args"] == [
        "-m",
        "augur_framework",
        "--client-id",
        "gemini",
    ]
    assert servers["augur-core"]["cwd"] == "/fake/root"
    assert servers["augur-core"]["env"]["AUGUR_ROOT"] == "/fake/root"
    assert servers["augur-core"]["env"]["PYTHONPATH"] == "/fake/root/project-brain/capabilities:/fake/root:/fake/root/src/mcp"
    assert "augur_mcp" not in json.dumps(data)
    for bundle in ("augur-apple", "augur-lifestyle", "augur-file-manager", "augur-obsidian", "augur-ingest"):
        assert bundle not in servers


def test_write_skills_creates_skill_dirs(tmp_path):
    from formatters.gemini import GeminiFormatter

    fmt = GeminiFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()

    fmt.write_skills(
        plugin_dir,
        {
            "career": "---\nname: career\n---\n# Career\n",
            "knowledge": "---\nname: knowledge\n---\n# Knowledge\n",
        },
    )

    assert (plugin_dir / "skills" / "career" / "SKILL.md").exists()
    assert (plugin_dir / "skills" / "knowledge" / "SKILL.md").exists()


def test_write_skills_sanitizes_command_references(tmp_path):
    from formatters.gemini import GeminiFormatter

    fmt = GeminiFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()

    fmt.write_skills(
        plugin_dir,
        {
            "augur-core": "\n".join(
                [
                    "---",
                    "name: augur-core",
                    "---",
                    "- [commands/adr.md](commands/adr.md)",
                    "- [commands/airplane.md](commands/airplane.md)",
                    "Use `/dev-merge` and inspect `project-brain/capabilities/skills/augur-core/commands/ask.md`.",
                    "Keep /dev/null intact.",
                    "",
                ]
            ),
        },
    )

    content = (plugin_dir / "skills" / "augur-core" / "SKILL.md").read_text(encoding="utf-8")
    assert "commands/adr.md" not in content
    assert "project-brain/capabilities/skills/augur-core/commands/ask.md" not in content
    assert "/dev-merge" not in content
    assert "/project adr" in content
    assert "the packaged /ask command" in content
    assert "the packaged Augur workflow 'airplane'" in content
    assert "/project ask" not in content
    assert "/project airplane" not in content
    assert "/project dev merge" in content
    assert "/dev/null" in content


def test_write_commands_creates_namespaced_toml(tmp_path):
    from formatters.gemini import GeminiFormatter

    fmt = GeminiFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()

    fmt.write_commands(
        plugin_dir,
        {
            "ask": {"description": "Ask a question", "body": "Ask body."},
            "save": {"description": "Save content", "body": "Save body."},
        },
    )

    ask_path = plugin_dir / "commands" / "augur" / "ask.toml"
    assert ask_path.exists()
    parsed = tomllib.loads(ask_path.read_text())
    assert parsed["description"] == "Ask a question"
    assert "Ask body." in parsed["prompt"]
    assert "{{args}}" in parsed["prompt"]

    assert (plugin_dir / "commands" / "augur" / "save.toml").exists()


def test_write_commands_sanitizes_prompts_except_project_router(tmp_path):
    from formatters.gemini import GeminiFormatter

    fmt = GeminiFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()

    fmt.write_commands(
        plugin_dir,
        {
            "routines": {
                "description": "Run routines",
                "body": "Review via `/dev-merge` and `commands/dev.md`.",
            },
            "project": {
                "description": "Current-folder project router",
                "body": "Top-level `/adr`, `/dev`, and `/sweep` are retired. See commands/adr.md.",
            },
        },
    )

    routines = tomllib.loads((plugin_dir / "commands" / "augur" / "routines.toml").read_text())
    project = tomllib.loads((plugin_dir / "commands" / "augur" / "project.toml").read_text())

    assert "/dev-merge" not in routines["prompt"]
    assert "commands/dev.md" not in routines["prompt"]
    assert "/project dev merge" in routines["prompt"]
    assert "/project dev" in routines["prompt"]
    assert "Top-level `/adr`, `/dev`, and `/sweep` are retired" in project["prompt"]
    assert "commands/adr.md" not in project["prompt"]
    assert "the packaged project router implementation for adr" in project["prompt"]
    assert "project router implementation for `adr`" not in project["prompt"]
    assert "execute /project adr" not in project["prompt"]


def test_write_marketplace_noops(tmp_path):
    from formatters.gemini import GeminiFormatter

    fmt = GeminiFormatter()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    fmt.write_marketplace(output_dir, "1.0.0")

    assert not (output_dir / ".agents").exists()
    assert not (output_dir / ".claude-plugin").exists()


def test_install_replaces_augur_extension_and_logs_restart_note(tmp_path, caplog):
    from formatters.gemini import GeminiFormatter

    caplog.set_level(logging.INFO)
    fmt = GeminiFormatter()
    output_dir = tmp_path / "build"
    plugin_dir = output_dir / "extensions" / "augur"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "gemini-extension.json").write_text('{"name": "augur"}\n')

    extensions_dir = tmp_path / "home" / ".gemini" / "extensions"
    existing = extensions_dir / "augur"
    existing.mkdir(parents=True)
    (existing / "old.txt").write_text("old")

    result = fmt.install(output_dir, "1.0.0", extensions_dir=extensions_dir)

    assert result is True
    assert "Restart Gemini CLI" in caplog.text
    assert not (existing / "old.txt").exists()
    assert (existing / "gemini-extension.json").exists()
