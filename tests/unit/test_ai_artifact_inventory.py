from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from src.lib.ai_artifact_inventory import (
    AiArtifactRecord,
    INVENTORY_RELATIVE_PATH,
    load_ai_artifact_inventory,
    scan_ai_artifacts,
    write_ai_artifact_inventory,
)
import src.lib.ai_artifact_inventory as ai_inventory


def _record(
    *,
    id: str,
    artifact_type: str = "agent-profile",
    client: str = "codex",
    title: str = "dev",
    relative_path: str = ".codex/agents/dev.md",
    classification: str = "source",
    confidence: object = 0.95,
    warnings: list[str] | None = None,
) -> AiArtifactRecord:
    return AiArtifactRecord(
        id=id,
        project_brain_id="project-demo",
        project_root="/tmp/demo",
        artifact_type=artifact_type,
        client=client,
        vendor=client,
        source_path=f"/tmp/demo/{relative_path}",
        relative_path=relative_path,
        title=title,
        classification=classification,
        confidence=confidence,
        warnings=warnings or [],
        discovered_at="2026-06-04T00:00:00Z",
        freshness="sha256:test",
        provenance={"scanner": "test"},
    )


def test_problem_metadata_flags_scanner_warnings_and_low_confidence() -> None:
    assert hasattr(ai_inventory, "derive_ai_artifact_problem_metadata")
    record = _record(
        id="codex-agent",
        classification="unknown",
        confidence=0.4,
        warnings=["unknown_source", "permission_denied"],
    )

    metadata = ai_inventory.derive_ai_artifact_problem_metadata(record, [record])

    assert metadata["problem_tags"] == "permission_denied,unknown_source,low_confidence,missing_mcp_config"
    assert metadata["problem_count"] == "4"
    assert metadata["problem_summary"] == "Permission denied"
    assert "permission_denied" in metadata["problem_evidence"]


def test_problem_metadata_flags_duplicate_instruction_surfaces() -> None:
    assert hasattr(ai_inventory, "derive_ai_artifact_problem_metadata")
    first = _record(
        id="claude-agents",
        artifact_type="instruction",
        client="claude",
        title="AGENTS.md",
        relative_path="AGENTS.md",
    )
    second = _record(
        id="claude-agents-copy",
        artifact_type="instruction",
        client="claude",
        title="AGENTS.md",
        relative_path="docs/AGENTS.md",
    )

    metadata = ai_inventory.derive_ai_artifact_problem_metadata(first, [first, second])

    assert "duplicate" in metadata["problem_tags"].split(",")
    assert "conflicting_instruction" in metadata["problem_tags"].split(",")
    assert "docs/AGENTS.md" in metadata["problem_evidence"]


def test_problem_metadata_does_not_flag_different_instruction_surfaces_as_conflicts() -> None:
    root_agents = _record(
        id="project-agents",
        artifact_type="instruction",
        client="project",
        title="Agents",
        relative_path="AGENTS.md",
    )
    root_claude = _record(
        id="project-claude",
        artifact_type="instruction",
        client="project",
        title="Claude",
        relative_path="CLAUDE.md",
    )

    metadata = ai_inventory.derive_ai_artifact_problem_metadata(
        root_agents,
        [root_agents, root_claude],
    )

    assert "conflicting_instruction" not in metadata.get("problem_tags", "").split(",")


def test_problem_metadata_handles_non_numeric_confidence_without_low_confidence() -> None:
    record = _record(
        id="legacy-agent",
        confidence="manual",
        warnings=["unknown_source"],
    )

    metadata = ai_inventory.derive_ai_artifact_problem_metadata(record, [record])
    browse_entry = ai_inventory._record_to_browse_entry(record, "agent-profiles", [record])

    assert "low_confidence" not in metadata["problem_tags"].split(",")
    assert browse_entry["metadata"]["confidence"] == "manual"


def test_problem_metadata_ignores_non_finite_confidence() -> None:
    for confidence in (math.nan, math.inf, -math.inf):
        record = _record(
            id=f"legacy-agent-{confidence}",
            confidence=confidence,
            warnings=["unknown_source"],
        )

        metadata = ai_inventory.derive_ai_artifact_problem_metadata(record, [record])
        browse_entry = ai_inventory._record_to_browse_entry(record, "agent-profiles", [record])

        assert "low_confidence" not in metadata["problem_tags"].split(",")
        assert browse_entry["metadata"]["confidence"] == ""


def test_problem_metadata_does_not_flag_project_docs_missing_mcp_config() -> None:
    readme = _record(
        id="project-readme",
        artifact_type="project-doc",
        client="project",
        title="Readme",
        relative_path="README.md",
        classification="source",
    )
    agent = _record(
        id="codex-agent",
        artifact_type="agent-profile",
        client="codex",
        title="dev",
        relative_path=".codex/agents/dev.md",
    )

    metadata = ai_inventory.derive_ai_artifact_problem_metadata(readme, [readme, agent])

    assert "missing_mcp_config" not in metadata.get("problem_tags", "").split(",")


def test_scan_empty_project_returns_empty_inventory(tmp_path: Path) -> None:
    project = tmp_path / "empty"
    project.mkdir()

    inventory = scan_ai_artifacts(
        project,
        "project-empty",
        "2026-06-04T00:00:00+00:00",
    )

    assert inventory.project_brain_id == "project-empty"
    assert inventory.project_root == str(project.resolve())
    assert inventory.artifacts == []
    assert inventory.warnings == []


def test_scan_existing_ai_project_classifies_known_artifacts_read_only(tmp_path: Path) -> None:
    project = tmp_path / "firmware"
    project.mkdir()
    agents = project / ".codex" / "agents"
    agents.mkdir(parents=True)
    skills = project / ".claude" / "skills" / "debugger"
    skills.mkdir(parents=True)
    cursor_rules = project / ".cursor" / "rules"
    cursor_rules.mkdir(parents=True)

    instruction = project / "AGENTS.md"
    generated_agent = agents / "generated.md"
    skill = skills / "SKILL.md"
    cursor_rule = cursor_rules / "project.mdc"
    mcp_config = project / ".mcp.json"

    instruction.write_text("# Human project instructions\n", encoding="utf-8")
    generated_agent.write_text(
        "---\nname: generated\n---\n<!-- AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY -->\n",
        encoding="utf-8",
    )
    skill.write_text("---\nname: debugger\ndescription: Debug firmware\n---\n", encoding="utf-8")
    cursor_rule.write_text("Apply this rule to firmware work.\n", encoding="utf-8")
    mcp_config.write_text('{"mcpServers": {}}\n', encoding="utf-8")

    before = {
        path: path.read_text(encoding="utf-8")
        for path in (instruction, generated_agent, skill, cursor_rule, mcp_config)
    }

    inventory = scan_ai_artifacts(
        project_root=project,
        project_brain_id="project-firmware",
        discovered_at="2026-06-04T00:00:00+00:00",
    )

    by_path = {Path(record.relative_path): record for record in inventory.artifacts}
    assert Path("AGENTS.md") in by_path
    assert Path(".codex/agents/generated.md") in by_path
    assert Path(".claude/skills/debugger/SKILL.md") in by_path
    assert Path(".cursor/rules/project.mdc") in by_path
    assert Path(".mcp.json") in by_path

    assert by_path[Path("AGENTS.md")].artifact_type == "instruction"
    assert by_path[Path(".codex/agents/generated.md")].artifact_type == "agent-profile"
    assert by_path[Path(".claude/skills/debugger/SKILL.md")].artifact_type == "skill"
    assert by_path[Path(".cursor/rules/project.mdc")].client == "cursor"
    assert by_path[Path(".codex/agents/generated.md")].classification == "generated"
    # AGENTS.md is a repo-authored root instruction file → source (was mis-flagged unknown).
    assert by_path[Path("AGENTS.md")].classification == "source"
    assert "unknown_source" not in by_path[Path("AGENTS.md")].warnings

    after = {
        path: path.read_text(encoding="utf-8")
        for path in (instruction, generated_agent, skill, cursor_rule, mcp_config)
    }
    assert after == before


def test_scan_skips_outside_root_symlink_and_records_warning(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    agents = project / ".codex" / "agents"
    agents.mkdir(parents=True)
    outside = tmp_path / "outside.md"
    outside.write_text("---\nname: leaked\n---\n", encoding="utf-8")
    (agents / "leak.md").symlink_to(outside)

    inventory = scan_ai_artifacts(
        project,
        "project-repo",
        "2026-06-04T00:00:00+00:00",
    )

    assert inventory.artifacts == []
    assert inventory.warnings == [".codex/agents/leak.md: resolved target outside project_root"]


def test_globbed_artifacts_are_not_skipped_by_parent_directory_name(tmp_path: Path) -> None:
    project = tmp_path / "build" / "repo"
    agents = project / ".codex" / "agents"
    agents.mkdir(parents=True)
    agent = agents / "generated.md"
    agent.write_text(
        "---\nname: generated\n---\n<!-- AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY -->\n",
        encoding="utf-8",
    )

    inventory = scan_ai_artifacts(
        project,
        "project-repo",
        "2026-06-04T00:00:00+00:00",
    )

    by_path = {Path(record.relative_path): record for record in inventory.artifacts}
    assert Path(".codex/agents/generated.md") in by_path
    assert by_path[Path(".codex/agents/generated.md")].artifact_type == "agent-profile"


def test_scan_gemini_copilot_and_prompt_artifact_fixtures(tmp_path: Path) -> None:
    project = tmp_path / "multi-client"
    gemini_skill = project / ".gemini" / "skills" / "writer"
    gemini_prompt_dir = project / ".gemini" / "prompts"
    github_agents = project / ".github" / "agents"
    shared_prompts = project / "prompts"
    gemini_skill.mkdir(parents=True)
    gemini_prompt_dir.mkdir(parents=True)
    github_agents.mkdir(parents=True)
    shared_prompts.mkdir(parents=True)

    (gemini_skill / "SKILL.md").write_text(
        "---\nname: gemini-writer\ndescription: Draft release copy\n---\n",
        encoding="utf-8",
    )
    (gemini_prompt_dir / "daily.md").write_text(
        "---\ntitle: Daily Review\n---\nReview today's project notes.\n",
        encoding="utf-8",
    )
    (project / ".github" / "copilot-instructions.md").write_text(
        "# Copilot Instructions\nUse project-local evidence.\n",
        encoding="utf-8",
    )
    (github_agents / "reviewer.md").write_text(
        "---\nname: copilot-reviewer\n---\nReview pull requests.\n",
        encoding="utf-8",
    )
    (shared_prompts / "launch.md").write_text(
        "---\ntitle: Launch Prompt\n---\nSummarize launch blockers.\n",
        encoding="utf-8",
    )

    inventory = scan_ai_artifacts(
        project,
        "project-multi-client",
        "2026-06-04T00:00:00+00:00",
    )

    by_path = {Path(record.relative_path): record for record in inventory.artifacts}

    gemini_skill_record = by_path[Path(".gemini/skills/writer/SKILL.md")]
    assert gemini_skill_record.artifact_type == "skill"
    assert gemini_skill_record.client == "gemini"
    assert gemini_skill_record.vendor == "gemini"
    assert gemini_skill_record.title == "gemini-writer"

    gemini_prompt_record = by_path[Path(".gemini/prompts/daily.md")]
    assert gemini_prompt_record.artifact_type == "prompt"
    assert gemini_prompt_record.client == "gemini"
    assert gemini_prompt_record.vendor == "gemini"
    assert gemini_prompt_record.title == "Daily Review"

    copilot_instruction = by_path[Path(".github/copilot-instructions.md")]
    assert copilot_instruction.artifact_type == "instruction"
    assert copilot_instruction.client == "copilot"
    assert copilot_instruction.vendor == "github"

    copilot_agent = by_path[Path(".github/agents/reviewer.md")]
    assert copilot_agent.artifact_type == "agent-profile"
    assert copilot_agent.client == "copilot"
    assert copilot_agent.vendor == "github"

    project_prompt = by_path[Path("prompts/launch.md")]
    assert project_prompt.artifact_type == "prompt"
    assert project_prompt.client == "project"
    assert project_prompt.vendor == "project"
    assert project_prompt.title == "Launch Prompt"


def test_scan_copilot_prompt_folder_without_broad_markdown_scan(tmp_path: Path) -> None:
    project = tmp_path / "copilot-prompts"
    copilot_prompts = project / ".github" / "prompts"
    docs = project / "docs"
    copilot_prompts.mkdir(parents=True)
    docs.mkdir(parents=True)

    (copilot_prompts / "review.prompt.md").write_text(
        "---\ntitle: Copilot Review Prompt\n---\nReview this pull request.\n",
        encoding="utf-8",
    )
    (copilot_prompts / "notes.md").write_text(
        "# Notes\nThis is ordinary markdown in a prompt folder.\n",
        encoding="utf-8",
    )
    (copilot_prompts / "readme.md").write_text(
        "---\ncategory: docs\n---\nThis frontmatter is not prompt metadata.\n",
        encoding="utf-8",
    )
    (docs / "prompt-like.md").write_text(
        "---\ntitle: Do Not Treat As Prompt\n---\nThis is normal documentation.\n",
        encoding="utf-8",
    )

    inventory = scan_ai_artifacts(
        project,
        "project-copilot-prompts",
        "2026-06-04T00:00:00+00:00",
    )

    by_path = {Path(record.relative_path): record for record in inventory.artifacts}
    copilot_prompt = by_path[Path(".github/prompts/review.prompt.md")]
    assert copilot_prompt.artifact_type == "prompt"
    assert copilot_prompt.client == "copilot"
    assert copilot_prompt.vendor == "github"
    assert copilot_prompt.title == "Copilot Review Prompt"
    assert Path(".github/prompts/notes.md") not in by_path
    assert Path(".github/prompts/readme.md") not in by_path
    assert Path("docs/prompt-like.md") not in by_path


def test_scan_prompt_folder_indexes_valid_metadata_without_prompt_filename(tmp_path: Path) -> None:
    project = tmp_path / "metadata-prompts"
    prompts = project / ".claude" / "prompts"
    prompts.mkdir(parents=True)
    (prompts / "triage.md").write_text(
        "---\nlabel: Triage Prompt\ndescription: Sort incoming issues\n---\nTriage issues.\n",
        encoding="utf-8",
    )

    inventory = scan_ai_artifacts(
        project,
        "project-metadata-prompts",
        "2026-06-04T00:00:00+00:00",
    )

    by_path = {Path(record.relative_path): record for record in inventory.artifacts}
    prompt = by_path[Path(".claude/prompts/triage.md")]
    assert prompt.artifact_type == "prompt"
    assert prompt.client == "claude"
    assert prompt.title == "Triage Prompt"


def test_scan_vscode_mcp_config_as_vscode_client(tmp_path: Path) -> None:
    project = tmp_path / "vscode-mcp"
    vscode_dir = project / ".vscode"
    vscode_dir.mkdir(parents=True)
    (vscode_dir / "mcp.json").write_text('{"servers": {}}\n', encoding="utf-8")

    inventory = scan_ai_artifacts(
        project,
        "project-vscode-mcp",
        "2026-06-04T00:00:00+00:00",
    )

    by_path = {Path(record.relative_path): record for record in inventory.artifacts}
    mcp_config = by_path[Path(".vscode/mcp.json")]
    assert mcp_config.artifact_type == "mcp-config"
    assert mcp_config.client == "vscode"
    assert mcp_config.vendor == "vscode"


def test_scan_records_known_glob_failures_as_inventory_warnings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = tmp_path / "glob-warning"
    project.mkdir()
    original_glob = Path.glob

    def fake_glob(self: Path, pattern: str):
        if self == project.resolve() and pattern == ".codex/prompts/*.md":
            raise PermissionError("Permission denied")
        return original_glob(self, pattern)

    monkeypatch.setattr(Path, "glob", fake_glob)

    inventory = scan_ai_artifacts(
        project,
        "project-glob-warning",
        "2026-06-04T00:00:00+00:00",
    )

    assert inventory.artifacts == []
    assert ".codex/prompts/*.md: Permission denied" in inventory.warnings


def test_scan_records_invalid_frontmatter_metadata_warning(tmp_path: Path) -> None:
    project = tmp_path / "bad-frontmatter"
    prompts = project / ".codex" / "prompts"
    prompts.mkdir(parents=True)
    (prompts / "bad.md").write_text(
        "---\ntitle: [\n---\nUse this prompt anyway.\n",
        encoding="utf-8",
    )

    inventory = scan_ai_artifacts(
        project,
        "project-bad-frontmatter",
        "2026-06-04T00:00:00+00:00",
    )

    by_path = {Path(record.relative_path): record for record in inventory.artifacts}
    prompt = by_path[Path(".codex/prompts/bad.md")]
    assert prompt.artifact_type == "prompt"
    # .codex/prompts/* is a client-export projection → generated; the test's real
    # purpose (invalid frontmatter → invalid_metadata warning) is asserted below.
    assert prompt.classification == "generated"
    assert "unknown_source" not in prompt.warnings
    assert "invalid_metadata" in prompt.warnings


def test_write_and_load_inventory_uses_project_brain_config_dir(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    brain_root = project / "project-brain"
    project.mkdir()
    (project / "CLAUDE.md").write_text("Claude instructions\n", encoding="utf-8")

    inventory = scan_ai_artifacts(
        project_root=project,
        project_brain_id="project-repo",
        discovered_at="2026-06-04T00:00:00+00:00",
    )
    written = write_ai_artifact_inventory(inventory, brain_root)

    assert written == brain_root / INVENTORY_RELATIVE_PATH
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["project_brain_id"] == "project-repo"
    assert payload["generated_at"] == "2026-06-04T00:00:00+00:00"
    assert payload["artifacts"][0]["relative_path"] == "CLAUDE.md"

    loaded = load_ai_artifact_inventory(brain_root)
    assert loaded is not None
    assert loaded.project_brain_id == "project-repo"
    assert loaded.project_root == inventory.project_root
    assert loaded.generated_at == inventory.generated_at
    assert loaded.warnings == inventory.warnings

    record = inventory.artifacts[0]
    loaded_record = loaded.artifacts[0]
    assert loaded_record.id == record.id
    assert loaded_record.project_brain_id == record.project_brain_id
    assert loaded_record.project_root == record.project_root
    assert loaded_record.artifact_type == record.artifact_type
    assert loaded_record.client == record.client
    assert loaded_record.vendor == record.vendor
    assert loaded_record.source_path == record.source_path
    assert loaded_record.relative_path == record.relative_path
    assert loaded_record.title == record.title
    assert loaded_record.classification == record.classification
    assert loaded_record.confidence == record.confidence
    assert loaded_record.warnings == record.warnings
    assert loaded_record.discovered_at == record.discovered_at
    assert loaded_record.freshness == record.freshness
    assert loaded_record.provenance == record.provenance


def test_classify_client_dir_copies_are_generated() -> None:
    cls, conf, _ = ai_inventory._classify(
        Path("/x/.claude/skills/foo/SKILL.md"), ".claude/skills/foo/SKILL.md", "no marker"
    )
    assert cls == "generated"
    assert conf == 0.9
    cls2, _, _ = ai_inventory._classify(Path("/x/.codex/agents/dev.md"), ".codex/agents/dev.md", "")
    assert cls2 == "generated"


def test_classify_repo_authored_files_are_source() -> None:
    for rel in (
        "CLAUDE.md",
        "AGENTS.md",
        "README.md",
        "project-brain/IDENTITY.md",
        "plugins/agents/foo.md",
        "docs/agent-topics/CODING.md",
        "skills/foo/SKILL.md",
    ):
        cls, conf, warnings = ai_inventory._classify(Path("/x/" + rel), rel, "")
        assert cls == "source", rel
        assert conf == 0.85, rel
        assert "unknown_source" not in warnings, rel


def test_classify_generated_marker_takes_precedence() -> None:
    cls, conf, _ = ai_inventory._classify(
        Path("/x/project-brain/thing.md"), "project-brain/thing.md", "Generated by Augur"
    )
    assert cls == "generated"
    assert conf == 0.95  # marker wins over the source-prefix path


def test_classify_unrecognized_path_is_unknown() -> None:
    cls, conf, warnings = ai_inventory._classify(Path("/x/random/thing.md"), "random/thing.md", "")
    assert cls == "unknown"
    assert conf < 0.5
    assert "unknown_source" in warnings


def test_browse_skills_entries_skip_generated_client_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Generated client artifacts (e.g. .codex/skills/* autosync exports) are
    # projections of canonical Augur surfaces and must not surface as
    # standalone skill cards. System-metadata-style views still show them.
    generated_skill = _record(
        id="codex-skill-ask",
        artifact_type="skill",
        client="codex",
        title="ask",
        relative_path=".codex/skills/ask/SKILL.md",
        classification="generated",
    )
    source_skill = _record(
        id="project-skill-knowledge",
        artifact_type="skill",
        client="project",
        title="knowledge",
        relative_path="skills/knowledge/SKILL.md",
        classification="source",
    )
    generated_prompt = _record(
        id="codex-prompt-daily",
        artifact_type="prompt",
        client="codex",
        title="Daily Review",
        relative_path=".codex/prompts/daily.md",
        classification="generated",
    )
    inventory = ai_inventory.AiArtifactInventory(
        schema_version=1,
        project_brain_id="project-demo",
        project_root="/tmp/demo",
        generated_at="2026-06-11T00:00:00Z",
        artifacts=[generated_skill, source_skill, generated_prompt],
        warnings=[],
    )
    monkeypatch.setattr(
        ai_inventory,
        "load_registered_project_inventories",
        lambda: [inventory],
    )

    skill_entries = ai_inventory.inventory_browse_entries_for_category("skills")
    skill_titles = [entry["title"] for entry in skill_entries]
    assert skill_titles == ["knowledge"]
    assert "ask" not in skill_titles

    metadata_entries = ai_inventory.inventory_browse_entries_for_category("system-metadata")
    metadata_titles = [entry["title"] for entry in metadata_entries]
    assert "Daily Review" in metadata_titles


def test_agent_directory_readme_is_not_an_agent_profile(tmp_path: Path) -> None:
    # plugins/agents/README.md documents the profile format (its example
    # frontmatter contains "name: <agent-name>") and must not be indexed as
    # an agent profile itself.
    agents_dir = tmp_path / "plugins" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "README.md").write_text("---\nname: <agent-name>\n---\n# Agent profile format\n", encoding="utf-8")
    (agents_dir / "advisor.md").write_text("---\nname: advisor\n---\n# Advisor\n", encoding="utf-8")

    inventory = scan_ai_artifacts(tmp_path, "project-demo")

    profiles = [r for r in inventory.artifacts if r.artifact_type == "agent-profile"]
    names = {Path(r.relative_path).name for r in profiles}
    assert "advisor.md" in names
    assert "README.md" not in names
