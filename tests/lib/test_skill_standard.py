from __future__ import annotations

from pathlib import Path
from types import MappingProxyType

import pytest

from src.lib.skill_standard import (
    NormalizedSkill,
    STANDARD_PRIMARY_SURFACES,
    STANDARD_TOOL_SURFACES,
    normalize_skill_frontmatter,
    normalize_skill_file,
)


def test_normalize_new_x_augur_block_prefers_standard_shape(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "name: knowledge\n"
        "description: Search memory and documents.\n"
        "x-augur:\n"
        "  type: domain\n"
        "  release: mvp\n"
        "  commands:\n"
        "    - id: search\n"
        "      visibility: core\n"
        "  tools:\n"
        "    - name: memory-search\n"
        "      surface: mcp\n"
        "    - name: knowledge-project-index-rebuild\n"
        "      surface: cli\n"
        "  dashboard:\n"
        "    pages:\n"
        "      - /workspace/memory\n"
        "---\n"
        "# Knowledge\n",
        encoding="utf-8",
    )

    meta = normalize_skill_file(skill_md, shared_root=tmp_path.parent, private_root=None)

    assert meta.name == "knowledge"
    assert meta.description == "Search memory and documents."
    # Hubs were retired in ADR-802; the field is retained but never populated.
    assert meta.hub == ""
    assert meta.skill_type == "domain"
    assert meta.release == "mvp"
    assert [command.id for command in meta.commands] == ["search"]
    assert [(tool.name, tool.surface) for tool in meta.tools] == [
        ("memory-search", "mcp"),
        ("knowledge-project-index-rebuild", "cli"),
    ]
    assert meta.dashboard_pages == ("/workspace/memory",)
    assert meta.ownership == "augur"
    assert meta.warnings == ()


def test_normalize_legacy_fields_remain_readable() -> None:
    meta = normalize_skill_frontmatter(
        {
            "name": "dream",
            "description": "Cross-client overnight synthesis routine.",
            "x-augur-type": "skill",
            "x-augur-release": "mvp",
            "x-augur-commands": [{"id": "dream", "visibility": "user", "type": "routine"}],
            "x-augur-cli-integrations": [{"name": "dream-cli"}],
            "x-augur-mcp-tools": ["dream-status", {"name": "dream-config"}],
            "x-augur-dashboard-pages": ["/command/dream"],
        },
        source_path="project-brain/capabilities/skills/dream/SKILL.md",
        ownership="augur",
    )

    assert meta.name == "dream"
    # Hubs were retired in ADR-802; the field is retained but never populated.
    assert meta.hub == ""
    assert meta.skill_type == "skill"
    assert meta.release == "mvp"
    assert [command.id for command in meta.commands] == ["dream"]
    assert [(tool.name, tool.surface) for tool in meta.tools] == [
        ("dream-status", "mcp"),
        ("dream-config", "mcp"),
    ]
    assert meta.metadata["cli_integrations"] == "dream-cli"
    assert meta.dashboard_pages == ("/command/dream",)
    assert "legacy x-augur-* fields used" in meta.warnings


def test_new_x_augur_block_wins_over_legacy_for_same_concept() -> None:
    meta = normalize_skill_frontmatter(
        {
            "name": "example",
            "description": "Example skill.",
            "x-augur-mcp-tools": ["legacy-tool"],
            "x-augur": {
                "tools": [{"name": "new-tool", "surface": "cli"}],
            },
        },
        source_path="project-brain/capabilities/skills/example/SKILL.md",
        ownership="augur",
    )

    assert [(tool.name, tool.surface) for tool in meta.tools] == [("new-tool", "cli")]
    assert "legacy fields shadowed by x-augur block" in meta.warnings


def test_new_x_augur_empty_values_do_not_fall_back_to_legacy() -> None:
    meta = normalize_skill_frontmatter(
        {
            "name": "example",
            "description": "Example skill.",
            "x-augur-type": "legacy-type",
            "x-augur-release": "legacy-release",
            "x-augur-tags": ["legacy-tag"],
            "x-augur": {
                "type": "",
                "release": "",
                "tags": [],
            },
        },
        source_path="project-brain/capabilities/skills/example/SKILL.md",
        ownership="augur",
    )

    assert meta.skill_type == ""
    assert meta.release == ""
    assert meta.tags == ()
    assert "legacy fields shadowed by x-augur block" in meta.warnings


def test_legacy_dependencies_are_reported_as_legacy_fields() -> None:
    meta = normalize_skill_frontmatter(
        {
            "name": "example",
            "description": "Example skill.",
            "x-augur-dependencies": ["knowledge", "rag"],
        },
        source_path="project-brain/capabilities/skills/example/SKILL.md",
        ownership="augur",
    )

    assert meta.dependencies == ("knowledge", "rag")
    assert "legacy x-augur-* fields used" in meta.warnings


def test_normalize_skill_file_merges_sidecar_config_contributions(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "name: sidecar-skill\n"
        "description: Sidecar backed skill.\n"
        "x-augur-config-file: config.yaml\n"
        "---\n"
        "# Sidecar Skill\n",
        encoding="utf-8",
    )
    (tmp_path / "config.yaml").write_text(
        "contributions:\n"
        "  commands:\n"
        "    - id: sidecar-command\n"
        "      visibility: user\n"
        "  pages:\n"
        "    - /workspace/sidecar\n",
        encoding="utf-8",
    )

    meta = normalize_skill_file(skill_md, shared_root=tmp_path.parent, private_root=None)

    assert [command.id for command in meta.commands] == ["sidecar-command"]
    assert meta.dashboard_pages == ("/workspace/sidecar",)
    assert "legacy x-augur-* fields used" in meta.warnings


def test_sidecar_dict_page_contributions_use_route_before_id(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        "---\n"
        "name: ai\n"
        "description: AI client management.\n"
        "x-augur-config-file: config.yaml\n"
        "---\n"
        "# AI\n",
        encoding="utf-8",
    )
    (tmp_path / "config.yaml").write_text(
        "contributions:\n"
        "  pages:\n"
        "    - id: agents\n"
        "      title: Agents\n"
        "      icon: Bot\n"
        "    - id: setup\n"
        "      route: /command/setup\n",
        encoding="utf-8",
    )

    meta = normalize_skill_file(skill_md, shared_root=tmp_path.parent, private_root=None)

    assert meta.dashboard_pages == ("agents", "/command/setup")


def test_legacy_commands_dedupe_by_command_id_preserving_first() -> None:
    meta = normalize_skill_frontmatter(
        {
            "name": "routine-codebase",
            "description": "Codebase routines.",
            "x-augur-commands": [
                {"id": "/auto-test-pytest", "visibility": "direct"},
            ],
            "x-augur-config": {
                "contributions": {
                    "commands": [
                        {"id": "auto-test-pytest", "visibility": "sidecar"},
                        {"id": "auto-test-build", "visibility": "sidecar"},
                    ]
                }
            },
        },
        source_path="project-brain/capabilities/skills/routine-codebase/SKILL.md",
        ownership="augur",
    )

    assert [command.id for command in meta.commands] == [
        "/auto-test-pytest",
        "auto-test-build",
    ]
    assert meta.commands[0].visibility == "direct"


def test_normalized_skill_metadata_is_read_only() -> None:
    meta = NormalizedSkill(
        name="example",
        description="Example skill.",
        source_path="project-brain/capabilities/skills/example/SKILL.md",
        ownership="augur",
        metadata={"owner": "platform"},
    )

    assert isinstance(meta.metadata, MappingProxyType)
    assert meta.metadata["owner"] == "platform"
    with pytest.raises(TypeError):
        meta.metadata["owner"] = "user"


def test_new_x_augur_null_scalars_normalize_to_empty_strings() -> None:
    meta = normalize_skill_frontmatter(
        {
            "name": "example",
            "description": "Example skill.",
            "x-augur": {
                "hub": None,
                "type": None,
                "release": None,
            },
        },
        source_path="project-brain/capabilities/skills/example/SKILL.md",
        ownership="augur",
    )

    assert meta.hub == ""
    assert meta.skill_type == ""
    assert meta.release == ""


def test_invalid_tool_surface_is_preserved_for_scanner() -> None:
    meta = normalize_skill_frontmatter(
        {
            "name": "audio-ingest",
            "description": "Audio ingest.",
            "x-augur": {
                "tools": [{"name": "audio-classify", "surface": "mcp-tool"}],
            },
        },
        source_path="project-brain/capabilities/skills/audio-ingest/SKILL.md",
        ownership="augur",
    )

    assert "mcp-tool" not in STANDARD_PRIMARY_SURFACES
    assert meta.tools[0].surface == "mcp-tool"
    assert "invalid tool surface: audio-classify -> mcp-tool" in meta.warnings


def test_skill_is_primary_surface_but_not_tool_surface() -> None:
    meta = normalize_skill_frontmatter(
        {
            "name": "audio-ingest",
            "description": "Audio ingest.",
            "x-augur": {
                "tools": [{"name": "audio-classify", "surface": "skill"}],
            },
        },
        source_path="project-brain/capabilities/skills/audio-ingest/SKILL.md",
        ownership="augur",
    )

    assert "skill" in STANDARD_PRIMARY_SURFACES
    assert "skill" not in STANDARD_TOOL_SURFACES
    assert meta.tools[0].surface == "skill"
    assert "invalid tool surface: audio-classify -> skill" in meta.warnings
