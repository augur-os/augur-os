"""Tests for Codex formatter (Codex plugin output)."""
import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SHARED_VAULT_ROOT = REPO_ROOT / "project-brain"
PLUGIN_PACK_ROOT = SHARED_VAULT_ROOT / "capabilities" / "skills" / "plugin-pack"
for _path in (REPO_ROOT, SHARED_VAULT_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

SCRIPTS_DIR = PLUGIN_PACK_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_write_manifest_creates_codex_plugin_dir(tmp_path):
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    fmt.write_manifest(plugin_dir, "1.0.0")

    manifest_path = plugin_dir / ".codex-plugin" / "plugin.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text())
    assert data["name"] == "augur"
    assert data["version"] == "1.0.0"
    assert data["skills"] == "./skills/"
    assert data["mcpServers"] == "./.mcp.json"
    assert data["interface"]["displayName"] == "Augur"
    assert data["interface"]["category"] == "Productivity"


def test_write_mcp_config_uses_codex_client_id(tmp_path):
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    project_root = Path("/fake/root")
    fmt.write_mcp_config(plugin_dir, project_root, "/fake/python")

    mcp_path = plugin_dir / ".mcp.json"
    assert mcp_path.exists()
    data = json.loads(mcp_path.read_text())
    servers = data["mcpServers"]
    # augur-framework joined the export set when artifact-locate/keep/cleanup
    # landed on it (capability_exposure mcp-server:augur-framework, 2026-06-11).
    assert set(servers) == {"augur-core", "augur-framework"}
    assert servers["augur-core"]["args"] == ["-m", "augur_core", "--client-id", "codex"]
    assert servers["augur-framework"]["args"] == ["-m", "augur_framework", "--client-id", "codex"]
    assert servers["augur-core"]["cwd"] == str(project_root)
    assert "augur_mcp" not in mcp_path.read_text()


def test_write_skills_creates_skill_dirs(tmp_path):
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    fmt.write_skills(plugin_dir, {
        "career": "---\nname: career\n---\n# Career\n",
        "dev-test": "---\nname: dev-test\n---\n# Dev Test\n",
    })
    assert (plugin_dir / "skills" / "career" / "SKILL.md").exists()
    assert (plugin_dir / "skills" / "dev-test" / "SKILL.md").exists()


def test_write_skills_does_not_copy_source_command_docs(tmp_path):
    from formatters.codex import CodexFormatter

    fmt = CodexFormatter()
    project_root = tmp_path / "repo"
    source_skill_dir = project_root / "project-brain" / "capabilities" / "skills" / "augur-core"
    source_commands_dir = source_skill_dir / "commands"
    source_commands_dir.mkdir(parents=True)
    (source_skill_dir / "SKILL.md").write_text("---\nname: augur-core\n---\n", encoding="utf-8")
    (source_commands_dir / "adr.md").write_text("# ADR command\n", encoding="utf-8")

    plugin_dir = tmp_path / "build" / "plugins" / "augur"
    plugin_dir.mkdir(parents=True)
    fmt.write_mcp_config(plugin_dir, project_root, "/fake/python")

    fmt.write_skills(
        plugin_dir,
        {"augur-core": "---\nname: augur-core\n---\n[commands/adr.md](commands/adr.md)\n"},
    )

    assert not (plugin_dir / "skills" / "augur-core" / "commands").exists()


def test_write_skills_sanitizes_command_doc_links_and_retired_command_cues(tmp_path):
    from formatters.codex import CodexFormatter

    fmt = CodexFormatter()
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
                    "- [commands/ask.md](commands/ask.md)",
                    "- [commands/airplane.md](commands/airplane.md)",
                    "- [commands/dev-merge.md](commands/dev-merge.md)",
                    "Use `/adr`, `/dev`, `/sweep`, `/dev-merge`, `/dev-build`, `/dev-debug`, or `/dev-loops`.",
                    "Keep non-command paths like project-brain/decisions/adrs/ADR-001.md and /dev/null intact.",
                    "",
                ]
            ),
        },
    )

    content = (plugin_dir / "skills" / "augur-core" / "SKILL.md").read_text(encoding="utf-8")
    retired_command_cue = re.compile(
        r"(?<![\w/.-])/(?:dev-merge|dev-build|dev-debug|dev-loops|adr|dev|sweep)(?![\w/-])"
    )

    assert "commands/adr.md" not in content
    assert "commands/dev-merge.md" not in content
    assert retired_command_cue.search(content) is None
    assert "/project adr" in content
    assert "/project dev merge" in content
    assert "the packaged /ask command" in content
    assert "the packaged Augur workflow 'airplane'" in content
    assert "/project ask" not in content
    assert "/project airplane" not in content
    assert "project-brain/decisions/adrs/ADR-001.md" in content
    assert "/dev/null" in content


def test_write_commands_writes_project_router_not_retired_project_commands(tmp_path):
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    fmt.write_commands(plugin_dir, {
        "project": {
            "description": "Current-folder project router",
            "body": "# /project\n\nDispatch project-scoped workflows.",
        },
    })
    # Codex uses skills/ for commands too (they are just skills)
    cmd_path = plugin_dir / "skills" / "project" / "SKILL.md"
    assert cmd_path.exists()
    assert "# /project" in cmd_path.read_text(encoding="utf-8")
    assert not (plugin_dir / "skills" / "dev" / "SKILL.md").exists()
    assert not (plugin_dir / "skills" / "adr" / "SKILL.md").exists()
    assert not (plugin_dir / "skills" / "sweep" / "SKILL.md").exists()


def test_write_commands_sanitizes_retired_cues_except_project_router(tmp_path):
    from formatters.codex import CodexFormatter

    fmt = CodexFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()

    fmt.write_commands(
        plugin_dir,
        {
            "routines": {
                "description": "Unified command surface for personal/global Augur routines",
                "body": "Review via `/dev-merge` and inspect `/dev-loops`.",
            },
            "project": {
                "description": "Current-folder project router",
                "body": (
                    "Top-level `/adr`, `/dev`, and `/sweep` are retired. Use `/project`.\n"
                    "Dispatch via commands/adr.md, commands/dev.md, and commands/sweep.md."
                ),
            },
        },
    )

    routines_content = (plugin_dir / "skills" / "routines" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    project_content = (plugin_dir / "skills" / "project" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "/dev-merge" not in routines_content
    assert "/dev-loops" not in routines_content
    assert "/project dev merge" in routines_content
    assert "/project dev loops" in routines_content
    assert "Top-level `/adr`, `/dev`, and `/sweep` are retired" in project_content
    assert "commands/adr.md" not in project_content
    assert "commands/dev.md" not in project_content
    assert "commands/sweep.md" not in project_content
    assert "the packaged project router implementation for adr" in project_content
    assert "the packaged project router implementation for dev" in project_content
    assert "the packaged project router implementation for sweep" in project_content
    assert "project router implementation for `adr`" not in project_content
    assert "execute /project adr" not in project_content
    assert "execute /project dev" not in project_content
    assert "execute /project sweep" not in project_content


def test_write_commands_serializes_usage_description_as_valid_yaml(tmp_path):
    from formatters.codex import CodexFormatter

    fmt = CodexFormatter()
    plugin_dir = tmp_path / "augur"
    plugin_dir.mkdir()
    description = "Current-folder project router. Usage: /project <verb> [args]"

    fmt.write_commands(
        plugin_dir,
        {
            "project": {
                "description": description,
                "body": "# /project\n\nDispatch project-scoped workflows.",
            },
        },
    )

    cmd_path = plugin_dir / "skills" / "project" / "SKILL.md"
    metadata = yaml.safe_load(cmd_path.read_text(encoding="utf-8").split("---", 2)[1])
    assert metadata == {"name": "project", "description": description}


def test_write_marketplace_creates_agents_dir(tmp_path):
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    fmt.write_marketplace(output_dir, "1.0.0")

    mp_path = output_dir / ".agents" / "plugins" / "marketplace.json"
    assert mp_path.exists()
    data = json.loads(mp_path.read_text())
    assert data["name"] == "augur-local"
    assert data["plugins"][0]["name"] == "augur"
    assert data["plugins"][0]["source"]["source"] == "local"
    assert data["plugins"][0]["source"]["path"] == "./plugins/augur"
    assert data["plugins"][0]["policy"]["installation"] == "INSTALLED_BY_DEFAULT"


def test_install_to_cache(tmp_path):
    """Install should copy plugin to ~/.codex/plugins/cache/ structure."""
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()

    output_dir = tmp_path / "build"
    plugin_dir = output_dir / "plugins" / "augur"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "test.txt").write_text("test")

    fake_home = tmp_path / "home"
    codex_cache = fake_home / ".codex" / "plugins" / "cache"
    codex_cache.mkdir(parents=True)
    agents_dir = fake_home / ".agents" / "plugins"
    agents_dir.mkdir(parents=True)

    result = fmt.install(
        output_dir,
        "1.0.0",
        cache_dir=codex_cache,
        global_marketplace_dir=agents_dir,
    )
    assert result is True

    cached = codex_cache / "augur-local" / "augur" / "1.0.0" / "test.txt"
    assert cached.exists()

    local_plugin = fake_home / "plugins" / "augur" / "test.txt"
    assert local_plugin.exists()

    mp = agents_dir / "marketplace.json"
    assert mp.exists()
    data = json.loads(mp.read_text())
    augur_entry = [p for p in data["plugins"] if p["name"] == "augur"]
    assert len(augur_entry) == 1
    assert augur_entry[0]["source"]["path"] == "./plugins/augur"


def test_install_removes_stale_augur_cache_versions(tmp_path):
    """Install should remove stale sync-managed Augur plugin cache versions."""
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()

    output_dir = tmp_path / "build"
    plugin_dir = output_dir / "plugins" / "augur"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "test.txt").write_text("fresh", encoding="utf-8")

    fake_home = tmp_path / "home"
    codex_cache = fake_home / ".codex" / "plugins" / "cache"
    stale_dir = codex_cache / "augur-local" / "augur" / "0.20260503.0"
    stale_dir.mkdir(parents=True)
    (stale_dir / ".mcp.json").write_text('{"mcpServers":{"augur-obsidian":{}}}', encoding="utf-8")
    agents_dir = fake_home / ".agents" / "plugins"
    agents_dir.mkdir(parents=True)

    result = fmt.install(
        output_dir,
        "skills-latest",
        cache_dir=codex_cache,
        global_marketplace_dir=agents_dir,
    )

    assert result is True
    assert not stale_dir.exists()
    assert (codex_cache / "augur-local" / "augur" / "skills-latest" / "test.txt").exists()


def test_install_merges_existing_marketplace(tmp_path):
    """Install should merge into existing marketplace.json, not overwrite."""
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()

    output_dir = tmp_path / "build"
    plugin_dir = output_dir / "plugins" / "augur"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "test.txt").write_text("test")

    fake_home = tmp_path / "home"
    codex_cache = fake_home / ".codex" / "plugins" / "cache"
    codex_cache.mkdir(parents=True)
    agents_dir = fake_home / ".agents" / "plugins"
    agents_dir.mkdir(parents=True)

    existing = {
        "name": "my-marketplace",
        "interface": {"displayName": "My Marketplace"},
        "plugins": [
            {"name": "other-plugin", "source": {"source": "local", "path": "./other"}}
        ],
    }
    (agents_dir / "marketplace.json").write_text(json.dumps(existing))

    fmt.install(output_dir, "1.0.0", cache_dir=codex_cache, global_marketplace_dir=agents_dir)

    data = json.loads((agents_dir / "marketplace.json").read_text())
    names = [p["name"] for p in data["plugins"]]
    assert "other-plugin" in names
    assert "augur" in names
    assert data["name"] == "my-marketplace"
    augur_entry = [p for p in data["plugins"] if p["name"] == "augur"][0]
    assert augur_entry["source"]["path"] == "./plugins/augur"


def test_install_defaults_to_repo_local_paths(tmp_path):
    from formatters.codex import CodexFormatter
    fmt = CodexFormatter()

    project_root = tmp_path / "repo"
    output_dir = project_root / "build" / "codex"
    plugin_dir = output_dir / "plugins" / "augur"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "test.txt").write_text("test")
    fmt.write_mcp_config(plugin_dir, project_root, "/fake/python")

    result = fmt.install(output_dir, "1.0.0")
    assert result is True

    assert (project_root / ".agents" / "plugins" / "marketplace.json").exists()
    assert (project_root / "plugins" / "augur" / "test.txt").exists()
    assert (
        project_root / ".codex" / "plugins" / "cache" / "augur-local" / "augur" / "1.0.0" / "test.txt"
    ).exists()
