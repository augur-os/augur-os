from __future__ import annotations

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


def test_plugin_dir_uses_github_layout(tmp_path):
    from formatters.copilot import CopilotFormatter

    assert CopilotFormatter().plugin_dir(tmp_path / "build") == tmp_path / "build" / ".github"


def test_write_manifest_creates_copilot_instruction_files(tmp_path):
    from formatters.copilot import CopilotFormatter

    plugin_dir = tmp_path / ".github"
    plugin_dir.mkdir()
    CopilotFormatter().write_manifest(plugin_dir, "1.2.3")

    instructions = (plugin_dir / "copilot-instructions.md").read_text(encoding="utf-8")
    agent = (plugin_dir / "agents" / "augur.agent.md").read_text(encoding="utf-8")

    assert "AUGUR-GENERATED" in instructions
    assert "review-first" in instructions
    assert agent.startswith("---\n")
    assert "name: augur" in agent


def test_write_skills_creates_github_agent_skills(tmp_path):
    from formatters.copilot import CopilotFormatter

    plugin_dir = tmp_path / ".github"
    plugin_dir.mkdir()
    CopilotFormatter().write_skills(plugin_dir, {"ask": "---\nname: ask\n---\nAsk body\n"})

    assert (plugin_dir / "skills" / "ask" / "SKILL.md").exists()
    assert "Ask body" in (plugin_dir / "skills" / "ask" / "SKILL.md").read_text(encoding="utf-8")


def test_write_commands_creates_prompt_files(tmp_path):
    from formatters.copilot import CopilotFormatter

    plugin_dir = tmp_path / ".github"
    plugin_dir.mkdir()
    CopilotFormatter().write_commands(
        plugin_dir,
        {"ask": {"description": "Ask Augur", "body": "Use Augur ask."}},
    )

    prompt = plugin_dir / "prompts" / "augur-ask.prompt.md"
    content = prompt.read_text(encoding="utf-8")

    assert content.startswith("---\n")
    assert "description: Ask Augur" in content
    assert "Use Augur ask." in content


def test_write_commands_serializes_tricky_description_as_single_value(tmp_path):
    from formatters.copilot import CopilotFormatter

    plugin_dir = tmp_path / ".github"
    plugin_dir.mkdir()
    CopilotFormatter().write_commands(
        plugin_dir,
        {"review": {"description": "Scope: cloud\nmode: review", "body": "Review scope."}},
    )

    content = (plugin_dir / "prompts" / "augur-review.prompt.md").read_text(encoding="utf-8")
    frontmatter = content.split("---", 2)[1]
    data = yaml.safe_load(frontmatter)

    assert data == {"description": "Scope: cloud\nmode: review"}
    assert "mode" not in data


def test_install_copies_only_github_assets(tmp_path):
    from formatters.copilot import CopilotFormatter

    output = tmp_path / "build"
    source = output / ".github"
    source.mkdir(parents=True)
    (source / "copilot-instructions.md").write_text("generated\n", encoding="utf-8")
    (source / "prompts").mkdir()
    (source / "prompts" / "augur-ask.prompt.md").write_text("ask\n", encoding="utf-8")

    repo = tmp_path / "repo"
    (repo / ".github").mkdir(parents=True)
    (repo / ".github" / "user-owned.md").write_text("keep\n", encoding="utf-8")
    (repo / ".github" / "prompts").mkdir()
    (repo / ".github" / "prompts" / "user.prompt.md").write_text("keep prompt\n", encoding="utf-8")

    ok = CopilotFormatter().install(output, "1.0.0", install_root=repo)

    assert ok is True
    assert (repo / ".github" / "copilot-instructions.md").read_text(encoding="utf-8") == "generated\n"
    assert (repo / ".github" / "prompts" / "augur-ask.prompt.md").read_text(encoding="utf-8") == "ask\n"
    assert (repo / ".github" / "user-owned.md").read_text(encoding="utf-8") == "keep\n"
    assert (repo / ".github" / "prompts" / "user.prompt.md").read_text(encoding="utf-8") == "keep prompt\n"


def test_install_preserves_user_owned_same_path_prompt_and_copies_missing_generated_file(tmp_path):
    from formatters.copilot import CopilotFormatter

    output = tmp_path / "build"
    source = output / ".github"
    (source / "prompts").mkdir(parents=True)
    (source / "prompts" / "augur-ask.prompt.md").write_text(
        "<!-- AUGUR-GENERATED -->\nnew ask\n",
        encoding="utf-8",
    )
    (source / "prompts" / "augur-save.prompt.md").write_text(
        "<!-- AUGUR-GENERATED -->\nsave\n",
        encoding="utf-8",
    )

    repo = tmp_path / "repo"
    (repo / ".github" / "prompts").mkdir(parents=True)
    (repo / ".github" / "prompts" / "augur-ask.prompt.md").write_text(
        "user ask\n",
        encoding="utf-8",
    )

    ok = CopilotFormatter().install(output, "1.0.0", install_root=repo)

    assert ok is True
    assert (repo / ".github" / "prompts" / "augur-ask.prompt.md").read_text(encoding="utf-8") == "user ask\n"
    assert (
        repo / ".github" / "prompts" / "augur-save.prompt.md"
    ).read_text(encoding="utf-8") == "<!-- AUGUR-GENERATED -->\nsave\n"


def test_install_prunes_stale_augur_managed_files(tmp_path):
    from formatters.copilot import CopilotFormatter

    output = tmp_path / "build"
    source = output / ".github"
    (source / "skills" / "ask").mkdir(parents=True)
    (source / "skills" / "ask" / "SKILL.md").write_text(
        "<!-- AUGUR-GENERATED -->\nask\n",
        encoding="utf-8",
    )

    repo = tmp_path / "repo"
    stale_skill = repo / ".github" / "skills" / "removed-skill" / "SKILL.md"
    stale_skill.parent.mkdir(parents=True)
    stale_skill.write_text("<!-- AUGUR-GENERATED -->\nretired\n", encoding="utf-8")
    stale_prompt = repo / ".github" / "prompts" / "augur-retired.prompt.md"
    stale_prompt.parent.mkdir(parents=True)
    stale_prompt.write_text("<!-- AUGUR-GENERATED -->\nretired prompt\n", encoding="utf-8")
    stale_agent = repo / ".github" / "agents" / "augur-retired.agent.md"
    stale_agent.parent.mkdir(parents=True)
    stale_agent.write_text("<!-- AUGUR-GENERATED -->\nretired agent\n", encoding="utf-8")
    user_skill = repo / ".github" / "skills" / "my-own" / "notes.md"
    user_skill.parent.mkdir(parents=True)
    user_skill.write_text("user notes\n", encoding="utf-8")
    user_root_file = repo / ".github" / "workflows.md"
    user_root_file.write_text("<!-- AUGUR-GENERATED -->\noutside prune roots\n", encoding="utf-8")

    ok = CopilotFormatter().install(output, "1.0.0", install_root=repo)

    assert ok is True
    assert not stale_skill.exists()
    assert not stale_skill.parent.exists()  # emptied dir pruned
    assert not stale_prompt.exists()
    assert not stale_agent.exists()
    assert user_skill.read_text(encoding="utf-8") == "user notes\n"
    assert user_root_file.exists()  # prune limited to agents/skills/prompts
    assert (
        repo / ".github" / "skills" / "ask" / "SKILL.md"
    ).read_text(encoding="utf-8") == "<!-- AUGUR-GENERATED -->\nask\n"


def test_install_prune_skips_symlinked_dirs(tmp_path):
    from formatters.copilot import CopilotFormatter

    output = tmp_path / "build"
    source = output / ".github"
    (source / "skills" / "ask").mkdir(parents=True)
    (source / "skills" / "ask" / "SKILL.md").write_text(
        "<!-- AUGUR-GENERATED -->\nask\n",
        encoding="utf-8",
    )

    external_empty = tmp_path / "external-empty"
    external_empty.mkdir()
    repo = tmp_path / "repo"
    (repo / ".github" / "skills").mkdir(parents=True)
    linked_dir = repo / ".github" / "skills" / "linked"
    linked_dir.symlink_to(external_empty, target_is_directory=True)

    ok = CopilotFormatter().install(output, "1.0.0", install_root=repo)

    assert ok is True
    assert linked_dir.is_symlink()
    assert external_empty.exists()


def test_install_keeps_marked_files_still_present_in_fresh_output(tmp_path):
    from formatters.copilot import CopilotFormatter

    output = tmp_path / "build"
    source = output / ".github"
    (source / "prompts").mkdir(parents=True)
    (source / "prompts" / "augur-ask.prompt.md").write_text(
        "<!-- AUGUR-GENERATED -->\nask\n",
        encoding="utf-8",
    )

    repo = tmp_path / "repo"
    installed = repo / ".github" / "prompts" / "augur-ask.prompt.md"
    installed.parent.mkdir(parents=True)
    installed.write_text("<!-- AUGUR-GENERATED -->\nold ask\n", encoding="utf-8")

    ok = CopilotFormatter().install(output, "1.0.0", install_root=repo)

    assert ok is True
    assert installed.read_text(encoding="utf-8") == "<!-- AUGUR-GENERATED -->\nask\n"


def test_install_overwrites_same_path_generated_prompt(tmp_path):
    from formatters.copilot import CopilotFormatter

    output = tmp_path / "build"
    source = output / ".github"
    (source / "prompts").mkdir(parents=True)
    (source / "prompts" / "augur-ask.prompt.md").write_text(
        "<!-- AUGUR-GENERATED -->\nnew ask\n",
        encoding="utf-8",
    )

    repo = tmp_path / "repo"
    (repo / ".github" / "prompts").mkdir(parents=True)
    (repo / ".github" / "prompts" / "augur-ask.prompt.md").write_text(
        "<!-- AUGUR-GENERATED -->\nold ask\n",
        encoding="utf-8",
    )

    ok = CopilotFormatter().install(output, "1.0.0", install_root=repo)

    assert ok is True
    assert (
        repo / ".github" / "prompts" / "augur-ask.prompt.md"
    ).read_text(encoding="utf-8") == "<!-- AUGUR-GENERATED -->\nnew ask\n"
