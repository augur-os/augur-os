"""Tests for shared plugin assembler pipeline."""
import json
import re
import subprocess
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


def _approve_project_mcp_servers(monkeypatch, *clients: str) -> None:
    monkeypatch.setattr(
        "src.cli_config.manifest.resolve_capability_records",
        lambda _discovered, *, policy=None: [
            SimpleNamespace(
                id="mcp-server:augur-core",
                classification_status="approved",
                export_to=clients,
                current_exposure=(),
            ),
            SimpleNamespace(
                id="mcp-server:augur-framework",
                classification_status="approved",
                export_to=clients,
                current_exposure=(),
            ),
        ],
    )


_RETIRED_COMMAND_CUE = re.compile(
    r"(?<![\w/.-])/(?:dev-merge|dev-build|dev-debug|dev-loops|adr|dev|sweep)(?![\w/-])"
)
_COMMAND_DOC_PATH = re.compile(r"(?:[A-Za-z0-9_.-]+/)*commands/[^)\s]+\.md")
_RECURSIVE_PROJECT_DISPATCH = re.compile(
    r"execute\s+/project\s+(?:ask|keep|skillify|routines|adr|dev|sweep)\b",
    re.IGNORECASE,
)
_PROJECT_COMMAND_REFERENCE = re.compile(r"(?<![\w/.-])/project\s+([A-Za-z0-9_-]+)")
_VALID_PROJECT_COMMAND_VERBS = {"status", "init", "ask", "keep", "skillify", "routines", "adr", "dev", "sweep"}
_MALFORMED_PROJECT_ROUTER_REFERENCE = re.compile(r"project router implementation for `")


def _packaged_command_text_leaks(paths: list[Path], *, project_router_paths: set[Path]) -> list[str]:
    leaks = []
    for path in paths:
        content = path.read_text(encoding="utf-8")
        if _COMMAND_DOC_PATH.search(content):
            leaks.append(str(path))
            continue
        if path in project_router_paths and _RECURSIVE_PROJECT_DISPATCH.search(content):
            leaks.append(str(path))
            continue
        if _MALFORMED_PROJECT_ROUTER_REFERENCE.search(content):
            leaks.append(str(path))
            continue
        invalid_project_refs = [
            match.group(1)
            for match in _PROJECT_COMMAND_REFERENCE.finditer(content)
            if match.group(1) not in _VALID_PROJECT_COMMAND_VERBS
        ]
        if invalid_project_refs:
            leaks.append(str(path))
            continue
        if path not in project_router_paths and _RETIRED_COMMAND_CUE.search(content):
            leaks.append(str(path))
    return leaks


def test_should_include_skill_cowork():
    from plugin_assembler import should_include_skill
    from profiles import COWORK_PROFILE

    # brain group is packaged; internal groups are not
    assert should_include_skill("knowledge", {"x-augur-group": "brain"}, COWORK_PROFILE) is True
    assert should_include_skill("daemon", {"x-augur-group": "augur_admin"}, COWORK_PROFILE) is False
    assert should_include_skill("evals", {"x-augur-group": "augur_autoloops"}, COWORK_PROFILE) is False
    # excluded prefixes still apply within an allowed group
    assert should_include_skill("auto-lint", {"x-augur-group": "brain"}, COWORK_PROFILE) is False
    assert should_include_skill("dev-build", {"x-augur-group": "brain"}, COWORK_PROFILE) is False


def test_should_include_skill_codex():
    from plugin_assembler import should_include_skill
    from profiles import CODEX_PROFILE

    # codex packages knowledge + core + dev-loop + admin groups
    assert should_include_skill("knowledge", {"x-augur-group": "brain"}, CODEX_PROFILE) is True
    assert should_include_skill("onboard", {"x-augur-group": "augur_core"}, CODEX_PROFILE) is True
    assert should_include_skill("evals", {"x-augur-group": "augur_autoloops"}, CODEX_PROFILE) is True
    assert should_include_skill("platform-admin", {"x-augur-group": "augur_admin"}, CODEX_PROFILE) is True
    # codex allows dev-; auto- and the internal _COMMON skills stay excluded on top of groups
    assert should_include_skill("dev-build", {"x-augur-group": "brain"}, CODEX_PROFILE) is True
    assert should_include_skill("auto-lint", {"x-augur-group": "augur_autoloops"}, CODEX_PROFILE) is False
    assert should_include_skill("daemon", {"x-augur-group": "augur_admin"}, CODEX_PROFILE) is False


def test_should_include_skill_gemini():
    from plugin_assembler import should_include_skill
    from profiles import GEMINI_PROFILE

    # gemini inherits codex's full toolset
    assert should_include_skill("knowledge", {"x-augur-group": "brain"}, GEMINI_PROFILE) is True
    assert should_include_skill("evals", {"x-augur-group": "augur_autoloops"}, GEMINI_PROFILE) is True
    assert should_include_skill("auto-lint", {"x-augur-group": "augur_autoloops"}, GEMINI_PROFILE) is False
    assert should_include_skill("ai", {"x-augur-group": "augur_core"}, GEMINI_PROFILE) is False


def test_discover_skills_reads_shared_vault_without_legacy_root(monkeypatch, tmp_path):
    import plugin_assembler
    from profiles import CODEX_PROFILE

    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "career"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: career\nx-augur-group: brain\n---\n# Career\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(plugin_assembler, "_get_project_root", lambda: tmp_path)

    discovered = plugin_assembler.discover_skills(CODEX_PROFILE)

    assert discovered == {
        "career": "---\nname: career\nx-augur-group: brain\n---\n# Career\n",
    }


def test_transform_skill_md():
    from plugin_assembler import transform_skill_md

    input_md = "---\nname: career\ndescription: Job search\nx-augur-group: career\n---\n# Career\nRun `/career` to start.\n"
    result = transform_skill_md(input_md, "career", "claude-code")

    assert "name: career" in result
    assert "description: Job search" in result
    assert "x-augur-group" not in result
    assert "AUGUR-ADAPTED-COPY" in result
    assert "`/career`" not in result


def test_assemble_cowork(tmp_path):
    from plugin_assembler import assemble

    output, version = assemble("cowork", tmp_path / "cowork-out")
    assert isinstance(version, str)
    assert (output / "plugins" / "augur" / ".claude-plugin" / "plugin.json").exists()
    assert (output / "plugins" / "augur" / ".mcp.json").exists()
    # Desktop ships ask + keep (keep.md carries the shell-free Session
    # Reconcile flow for bare /keep — spec 2026-06-11).
    commands_dir = output / "plugins" / "augur" / "commands"
    assert sorted(p.name for p in commands_dir.glob("*.md")) == ["ask.md", "keep.md"]
    assert "Session Reconcile" in (commands_dir / "keep.md").read_text(encoding="utf-8")
    assert (output / "plugins" / "augur" / "skills").exists()


def test_assemble_cowork_removes_stale_command_output(tmp_path):
    from plugin_assembler import assemble

    output_dir = tmp_path / "cowork-out"
    stale_commands_dir = output_dir / "plugins" / "augur" / "commands"
    stale_commands_dir.mkdir(parents=True)
    (stale_commands_dir / "save.md").write_text("stale retired command", encoding="utf-8")

    output, version = assemble("cowork", output_dir)

    assert isinstance(version, str)
    assert output == output_dir
    # Retired commands are swept; only the current cowork set remains.
    assert sorted(p.name for p in stale_commands_dir.glob("*.md")) == ["ask.md", "keep.md"]


def test_assemble_removes_stale_skill_output(tmp_path):
    from plugin_assembler import assemble

    output_dir = tmp_path / "codex-out"
    stale_skill_dir = output_dir / "plugins" / "augur" / "skills" / "obsidian"
    stale_skill_dir.mkdir(parents=True)
    (stale_skill_dir / "SKILL.md").write_text("stale skill", encoding="utf-8")

    output, version = assemble("codex", output_dir)

    assert isinstance(version, str)
    assert output == output_dir
    assert not stale_skill_dir.exists()


def test_install_forwards_formatter_kwargs(monkeypatch, tmp_path):
    import plugin_assembler

    calls = []

    class DummyFormatter:
        def install(self, output_dir, version, **kwargs):
            calls.append((output_dir, version, kwargs))
            return True

    monkeypatch.setitem(plugin_assembler._FORMATTERS, "codex", DummyFormatter)

    assert plugin_assembler.install(
        "codex",
        tmp_path / "codex-out",
        "skills-latest",
        cache_dir=tmp_path / "cache",
        global_marketplace_dir=tmp_path / "marketplace",
    ) is True
    assert calls == [
        (
            tmp_path / "codex-out",
            "skills-latest",
            {
                "cache_dir": tmp_path / "cache",
                "global_marketplace_dir": tmp_path / "marketplace",
            },
        )
    ]


def test_assemble_uses_windows_venv_python_when_available(monkeypatch, tmp_path):
    import plugin_assembler

    project_root = tmp_path / "project"
    python_exe = project_root / ".venv" / "Scripts" / "python.exe"
    python_exe.parent.mkdir(parents=True)
    python_exe.write_text("", encoding="utf-8")

    seen = {}

    class DummyFormatter:
        def plugin_dir(self, output_dir):
            return output_dir / "plugins" / "augur"

        def write_manifest(self, plugin_dir, version):
            pass

        def write_mcp_config(self, plugin_dir, project_root_arg, python_path):
            seen["project_root"] = project_root_arg
            seen["python_path"] = python_path

        def write_skills(self, plugin_dir, transformed):
            pass

        def write_commands(self, plugin_dir, commands):
            pass

        def write_marketplace(self, output_dir, version):
            pass

    monkeypatch.setattr(plugin_assembler, "_get_project_root", lambda: project_root)
    monkeypatch.setattr(plugin_assembler, "discover_skills", lambda _profile: {})
    monkeypatch.setitem(plugin_assembler._FORMATTERS, "codex", DummyFormatter)

    plugin_assembler.assemble("codex", tmp_path / "out")

    assert seen == {
        "project_root": project_root,
        "python_path": str(python_exe),
    }


def test_assemble_codex(tmp_path):
    from plugin_assembler import assemble

    output, version = assemble("codex", tmp_path / "codex-out")
    assert version == "skills-latest"
    assert (output / "plugins" / "augur" / ".codex-plugin" / "plugin.json").exists()
    assert (output / "plugins" / "augur" / ".mcp.json").exists()
    assert (output / "plugins" / "augur" / "skills" / "ask" / "SKILL.md").exists()
    project_command = output / "plugins" / "augur" / "skills" / "project" / "SKILL.md"
    assert project_command.exists()
    project_text = project_command.read_text(encoding="utf-8")
    assert "Current-folder project router" in project_text
    assert not (output / "plugins" / "augur" / "skills" / "dev" / "SKILL.md").exists()
    assert not (output / "plugins" / "augur" / "skills" / "adr" / "SKILL.md").exists()
    assert not (output / "plugins" / "augur" / "skills" / "sweep" / "SKILL.md").exists()
    assert not (output / "plugins" / "augur" / "skills" / "dev-build" / "SKILL.md").exists()
    assert (output / "plugins" / "augur" / "skills" / "skillify" / "SKILL.md").exists()
    assert not any((output / "plugins" / "augur" / "skills").glob("*/commands/*.md"))

    manifest = json.loads(
        (output / "plugins" / "augur" / ".codex-plugin" / "plugin.json").read_text()
    )
    assert manifest["interface"]["displayName"] == "Augur"
    assert manifest["version"] == "skills-latest"


def test_assemble_codex_sanitizes_non_command_skill_text(tmp_path):
    from plugin_assembler import assemble

    output, _version = assemble("codex", tmp_path / "codex-out")
    skills_dir = output / "plugins" / "augur" / "skills"
    skill_files = sorted(skills_dir.glob("*/SKILL.md"))
    project_router_paths = {skills_dir / "project" / "SKILL.md"}

    assert _packaged_command_text_leaks(skill_files, project_router_paths=project_router_paths) == []


def test_assemble_gemini(monkeypatch, tmp_path):
    from plugin_assembler import assemble

    _approve_project_mcp_servers(monkeypatch, "gemini")

    output, version = assemble("gemini", tmp_path / "gemini-out")
    assert isinstance(version, str)

    manifest_path = output / "extensions" / "augur" / "gemini-extension.json"
    context_path = output / "extensions" / "augur" / "GEMINI.md"
    ask_command_path = output / "extensions" / "augur" / "commands" / "augur" / "ask.toml"
    project_command_path = output / "extensions" / "augur" / "commands" / "augur" / "project.toml"

    assert manifest_path.exists()
    assert context_path.exists()
    assert ask_command_path.exists()
    assert project_command_path.exists()
    assert not (output / "extensions" / "augur" / "commands" / "augur" / "dev.toml").exists()
    assert not (output / "extensions" / "augur" / "commands" / "augur" / "adr.toml").exists()
    assert not (output / "extensions" / "augur" / "commands" / "augur" / "sweep.toml").exists()
    context_text = context_path.read_text(encoding="utf-8")
    assert "/augur:project" in context_text
    assert "/augur:dev" not in context_text

    manifest = json.loads(manifest_path.read_text())
    assert "augur" not in manifest["mcpServers"]
    assert manifest["mcpServers"]["augur-core"]["args"] == [
        "-m",
        "augur_core",
        "--client-id",
        "gemini",
    ]
    assert manifest["mcpServers"]["augur-framework"]["args"] == [
        "-m",
        "augur_framework",
        "--client-id",
        "gemini",
    ]
    assert "augur_mcp" not in manifest_path.read_text()

    text_files = [
        *sorted((output / "extensions" / "augur" / "skills").glob("*/SKILL.md")),
        *sorted((output / "extensions" / "augur" / "commands" / "augur").glob("*.toml")),
        context_path,
    ]
    assert _packaged_command_text_leaks(text_files, project_router_paths={project_command_path}) == []


def test_assemble_copilot(monkeypatch, tmp_path):
    from plugin_assembler import assemble

    _approve_project_mcp_servers(monkeypatch, "copilot")

    output, version = assemble("copilot", tmp_path / "copilot-out")
    assert isinstance(version, str)

    github_dir = output / ".github"
    assert (github_dir / "copilot-instructions.md").exists()
    assert (github_dir / "agents" / "augur.agent.md").exists()
    assert (github_dir / "copilot-mcp.md").exists()
    assert (github_dir / "prompts" / "augur-ask.prompt.md").exists()
    assert (github_dir / "prompts" / "augur-wiki.prompt.md").exists()
    assert (github_dir / "skills" / "knowledge" / "SKILL.md").exists()

    mcp_doc = (github_dir / "copilot-mcp.md").read_text(encoding="utf-8")
    assert "--client-id" in mcp_doc
    assert "copilot" in mcp_doc
    assert "augur-core" in mcp_doc
    assert "augur-framework" in mcp_doc
    assert "augur_mcp" not in mcp_doc


def test_cli_assemble_gemini_from_script_path(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "plugin_assembler.py"),
            "--target",
            "gemini",
            "--output",
            str(tmp_path / "gemini-cli-out"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "gemini-cli-out" / "extensions" / "augur" / "gemini-extension.json").exists()


def test_cli_assemble_copilot_from_script_path(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "plugin_assembler.py"),
            "--target",
            "copilot",
            "--output",
            str(tmp_path / "copilot-cli-out"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "copilot-cli-out" / ".github" / "copilot-instructions.md").exists()


def test_assemble_unknown_target_raises(tmp_path):
    from plugin_assembler import assemble
    import pytest
    with pytest.raises(ValueError, match="Unknown target"):
        assemble("unknown", tmp_path / "out")
