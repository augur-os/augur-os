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


def _make_client_skill(dirpath: Path, *names: str) -> None:
    for name in names:
        (dirpath / name).mkdir(parents=True, exist_ok=True)


def _brain(brain_id: str, brain_type: BrainType, root: Path, project: Path | None = None) -> Brain:
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


def _src_skill(brain_root: Path, name: str) -> None:
    skill_dir = brain_root / "capabilities" / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")


def _stack(tmp_path: Path) -> BrainStack:
    core = tmp_path / "core"
    _src_skill(core, "ai")
    vault = tmp_path / "vault"
    _src_skill(vault, "books")
    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    _src_skill(project_brain, "proj-skill")
    return BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=_brain("personal", BrainType.PERSONAL, vault),
        project=ActiveBrainContext(
            active_brain=_brain("project-repo", BrainType.PROJECT, project_brain, project),
            attached_project=project,
            source="nearest-project-brain",
        ),
    )


def test_client_received_skills_unions_local_and_global_subdirs(tmp_path: Path) -> None:
    from src.lib.brain_verify_harness import client_received_skills

    client_dirs = {
        "claude-local": tmp_path / "repo" / ".claude" / "skills",
        "claude-global": tmp_path / "home" / ".claude" / "skills",
        "claude-global-superpowers": tmp_path / "home" / ".codex" / "superpowers" / "skills",
        "codex-local": tmp_path / "repo" / ".codex" / "skills",
    }
    _make_client_skill(client_dirs["claude-local"], "ai", "proj-skill")
    _make_client_skill(client_dirs["claude-global"], "ai", "books")
    _make_client_skill(client_dirs["claude-global-superpowers"], "vendor-only")
    _make_client_skill(client_dirs["codex-local"], "ai")

    received = client_received_skills("claude", client_dirs=client_dirs)

    assert received == {"ai", "proj-skill", "books"}


def test_client_received_skills_empty_when_no_dirs(tmp_path: Path) -> None:
    from src.lib.brain_verify_harness import client_received_skills

    received = client_received_skills(
        "gemini",
        client_dirs={"gemini-local": tmp_path / "nope" / ".gemini" / "skills"},
    )
    assert received == set()


def test_verify_harness_skills_flags_missing_per_client(tmp_path: Path) -> None:
    from src.lib.brain_verify_harness import verify_harness_skills

    claude_local = tmp_path / "repo" / ".claude" / "skills"
    _make_client_skill(claude_local, "ai", "proj-skill")
    codex_local = tmp_path / "repo" / ".codex" / "skills"
    _make_client_skill(codex_local, "ai", "books", "proj-skill")
    client_dirs = {"claude-local": claude_local, "codex-local": codex_local}

    reports = verify_harness_skills(_stack(tmp_path), clients=("claude", "codex"), client_dirs=client_dirs)
    by_client = {report.client: report for report in reports}

    assert set(by_client["claude"].expected) == {"ai", "books", "proj-skill"}
    assert by_client["claude"].missing == ("books",)
    assert by_client["claude"].ok() is False
    assert by_client["codex"].missing == ()
    assert by_client["codex"].ok() is True


def test_verify_harness_summary_reports_ok_and_missing(tmp_path: Path) -> None:
    from src.lib.brain_verify_harness import verify_harness_summary

    claude_local = tmp_path / "repo" / ".claude" / "skills"
    _make_client_skill(claude_local, "ai", "proj-skill")
    client_dirs = {"claude-local": claude_local}

    summary = verify_harness_summary(_stack(tmp_path), clients=("claude",), client_dirs=client_dirs)

    assert summary["claude"]["ok"] is False
    assert summary["claude"]["missing"] == ["books"]
    assert summary["all_ok"] is False
