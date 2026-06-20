from __future__ import annotations

from pathlib import Path

from src.lib.brain_context import ActiveBrainContext
from src.lib.brain_registry_models import (
    Brain,
    BrainType,
    GitArrangement,
    GitConfig,
)
from src.lib.brain_stack import BrainStack, resolve_global_brain


def _brain(
    brain_id: str,
    brain_type: BrainType,
    root: Path,
    project: Path | None = None,
) -> Brain:
    git = (
        GitConfig(arrangement=GitArrangement.BUNDLED, host_repo=project)
        if brain_type is BrainType.PROJECT and project is not None
        else GitConfig(arrangement=GitArrangement.UNTRACKED)
    )
    return Brain(
        id=brain_id,
        type=brain_type,
        data_root=root,
        git=git,
        auto_activate_cwd_under=(project,) if project is not None else (),
    )


def _skill(brain_root: Path, name: str, *, tools: tuple[str, ...] = ()) -> Path:
    skill_dir = brain_root / "capabilities" / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    tools_yaml = ""
    if tools:
        tools_yaml = "x-augur-mcp-tools:\n" + "".join(f"  - {tool}\n" for tool in tools)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\n{tools_yaml}---\n# {name}\n",
        encoding="utf-8",
    )
    return skill_dir


def _memory_entry(brain_root: Path, name: str) -> None:
    entry = brain_root / "knowledge" / "memory" / "entries" / f"{name}.md"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(f"---\nname: {name}\n---\n{name}\n", encoding="utf-8")


def _stack(tmp_path: Path) -> BrainStack:
    core = tmp_path / "core"
    _skill(core, "shared", tools=("shared-tool",))
    _skill(core, "core-only")
    _memory_entry(core, "global-memory")

    vault = tmp_path / "vault"
    _skill(vault, "user-only")

    project = tmp_path / "repo"
    pbrain = project / "project-brain"
    _skill(pbrain, "shared", tools=("shared-tool", "project-tool"))
    _skill(pbrain, "proj-only")
    _memory_entry(pbrain, "project-memory")

    return BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=_brain("personal", BrainType.PERSONAL, vault),
        project=ActiveBrainContext(
            active_brain=_brain("project-repo", BrainType.PROJECT, pbrain, project),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )


def test_manager_snapshot_reports_grouped_effective_and_shadowed_rows(tmp_path: Path) -> None:
    from src.lib.brain_manager_snapshot import harness_manager_snapshot

    snap = harness_manager_snapshot(_stack(tmp_path))

    assert [tier["key"] for tier in snap["tier_details"]] == [
        "global",
        "personal",
        "project",
    ]
    assert [tier["label"] for tier in snap["tier_details"]] == [
        "Global",
        "User",
        "Project",
    ]

    skill_rows = {row["name"]: row for row in snap["groups"]["skills"]["entries"]}
    assert skill_rows["shared"]["winner_tier"] == "project"
    assert skill_rows["shared"]["winner_brain_id"] == "project-repo"
    assert skill_rows["shared"]["shadowed"] == ["global"]
    assert skill_rows["shared"]["owner"] == "augur"
    assert skill_rows["shared"]["actions"]["demote"]["enabled"] is True
    assert skill_rows["core-only"]["winner_tier"] == "global"
    assert skill_rows["core-only"]["actions"]["demote"]["enabled"] is False
    assert snap["groups"]["skills"]["effective"] == 4
    assert snap["groups"]["skills"]["shadowed"] == ["shared"]

    tool_rows = {row["name"]: row for row in snap["groups"]["mcp"]["entries"]}
    assert tool_rows["shared-tool"]["winner_tier"] == "project"
    assert tool_rows["shared-tool"]["shadowed"] == ["global"]
    assert tool_rows["project-tool"]["winner_tier"] == "project"

    memory_rows = {row["name"]: row for row in snap["groups"]["memory"]["entries"]}
    assert memory_rows["global-memory"]["winner_tier"] == "global"
    assert memory_rows["project-memory"]["winner_tier"] == "project"

    assert snap["skills"] == snap["groups"]["skills"]


def test_manager_snapshot_reports_root_standard_profile_files(tmp_path: Path) -> None:
    from src.lib.brain_manager_snapshot import harness_manager_snapshot

    stack = _stack(tmp_path)
    project_brain = tmp_path / "repo" / "project-brain"
    (project_brain / "IDENTITY.md").write_text(
        "---\ntitle: Identity\n---\n\n# Identity\n",
        encoding="utf-8",
    )
    (project_brain / "SOUL.md").write_text(
        "---\ntitle: Soul\n---\n\n# Soul\n",
        encoding="utf-8",
    )
    (project_brain / "USER.md").write_text(
        "---\ntitle: User\n---\n\n# User\n",
        encoding="utf-8",
    )
    for filename in ("AGENTS.md", "MEMORY.md", "TOOLS.md", "HEARTBEAT.md"):
        (project_brain / filename).write_text(
            f"---\ntitle: {filename}\n---\n\n# {filename}\n",
            encoding="utf-8",
        )

    rows = {
        row["name"]: row
        for row in harness_manager_snapshot(stack, project_root=tmp_path / "repo")["groups"]["profile"]["entries"]
    }

    assert rows["identity"]["winner_tier"] == "project"
    assert rows["identity"]["winner_brain_id"] == "project-repo"
    assert rows["soul"]["winner_tier"] == "project"
    assert rows["user"]["winner_tier"] == "project"
    assert "agents" not in rows
    assert "memory" not in rows
    assert "tools" not in rows
    assert "heartbeat" not in rows


def test_manager_snapshot_dedupes_coincident_root_standard_profile_files(
    tmp_path: Path,
) -> None:
    from src.lib.brain_manager_snapshot import harness_manager_snapshot

    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    _skill(project_brain, "shared")
    (project_brain / "IDENTITY.md").write_text(
        "---\ntitle: Identity\n---\n\n# Identity\n",
        encoding="utf-8",
    )

    stack = BrainStack(
        global_brain=resolve_global_brain(core_root=project_brain),
        user_brain=None,
        project=ActiveBrainContext(
            active_brain=_brain("project-repo", BrainType.PROJECT, project_brain, project),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )

    rows = {
        row["name"]: row
        for row in harness_manager_snapshot(stack, project_root=project)["groups"]["profile"]["entries"]
    }

    assert rows["identity"]["winner_tier"] == "global"
    assert rows["identity"]["tiers"] == [
        {
            "tier": "global",
            "tier_label": "Global",
            "brain_id": "augur-core",
            "path": "project-brain/IDENTITY.md",
            "status": "effective",
            "owner": "augur",
        }
    ]


def test_skill_promote_and_demote_round_trip_updates_effective_snapshot(tmp_path: Path) -> None:
    from src.lib.brain_manager_snapshot import (
        harness_demote_capability,
        harness_manager_snapshot,
        harness_promote_capability,
    )

    stack = _stack(tmp_path)
    client_skill = tmp_path / "client" / "codex" / "skills" / "client-only"
    client_skill.mkdir(parents=True)
    (client_skill / "SKILL.md").write_text(
        "---\nname: client-only\n---\n# client-only\n",
        encoding="utf-8",
    )

    promoted = harness_promote_capability(
        stack,
        capability_type="skills",
        name="client-only",
        source_path=client_skill,
        target_tier="project",
        project_root=tmp_path / "repo",
        remove_source=True,
    )

    assert promoted["success"] is True
    promoted_path = Path(promoted["target_path"])
    assert promoted_path.is_dir()
    assert not client_skill.exists()
    promoted_rows = {
        row["name"]: row
        for row in harness_manager_snapshot(stack, project_root=tmp_path / "repo")["groups"]["skills"]["entries"]
    }
    assert promoted_rows["client-only"]["winner_tier"] == "project"

    demoted = harness_demote_capability(
        stack,
        capability_type="skills",
        name="client-only",
        target_client="codex",
        target_scope="local",
        client_skill_dirs={"codex-local": tmp_path / "client" / "codex" / "skills"},
        project_root=tmp_path / "repo",
        remove_source=True,
    )

    assert demoted["success"] is True
    assert Path(demoted["target_path"], "SKILL.md").is_file()
    assert not promoted_path.exists()
    demoted_rows = {
        row["name"]: row
        for row in harness_manager_snapshot(stack, project_root=tmp_path / "repo")["groups"]["skills"]["entries"]
    }
    assert "client-only" not in demoted_rows
