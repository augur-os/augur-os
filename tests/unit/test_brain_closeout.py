from __future__ import annotations

from pathlib import Path

from src.lib.brain_context import ActiveBrainContext
from src.lib.brain_registry_models import Brain, BrainType, GitArrangement, GitConfig
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


def _skill(brain_root: Path, name: str) -> None:
    skill_dir = brain_root / "capabilities" / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")


def _client_skills(root: Path, *names: str) -> None:
    for name in names:
        (root / name).mkdir(parents=True, exist_ok=True)


def _write_memory_entry(memory_dir: Path, name: str, description: str) -> None:
    entries_dir = memory_dir / "entries"
    entries_dir.mkdir(parents=True, exist_ok=True)
    (entries_dir / f"{name}.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                f"description: {description}",
                "type: insight",
                "source_client: codex",
                "---",
                "",
                description,
            ]
        ),
        encoding="utf-8",
    )


def _stack(tmp_path: Path) -> BrainStack:
    core = tmp_path / "core"
    _skill(core, "core-only")
    user = tmp_path / "user"
    _skill(user, "user-only")
    project = tmp_path / "repo"
    project_brain = project / "project-brain"
    _skill(project_brain, "project-only")
    _write_memory_entry(project_brain / "knowledge" / "memory", "closeout-memory", "round trip")
    return BrainStack(
        global_brain=resolve_global_brain(core_root=core),
        user_brain=_brain("personal", BrainType.PERSONAL, user),
        project=ActiveBrainContext(
            active_brain=_brain("project-repo", BrainType.PROJECT, project_brain, project),
            attached_project=project,
            source="test",
        ),
    )


def test_closeout_green_when_all_family_gates_pass(tmp_path: Path) -> None:
    from src.lib.brain_closeout import verify_family_closeout

    stack = _stack(tmp_path)
    client_dir = tmp_path / "repo" / ".codex" / "skills"
    _client_skills(client_dir, "core-only", "user-only", "project-only")

    report = verify_family_closeout(
        stack,
        clients=("codex",),
        client_dirs={"codex-local": client_dir},
        single_brain_skills={"project-only"},
        orphan_refs=[],
        project_root=tmp_path / "repo",
    )

    assert report.all_ok is True
    assert report.sections["harness"]["all_ok"] is True
    assert report.sections["parity"]["ok"] is True
    assert report.sections["orphan_refs"]["ok"] is True
    assert report.sections["memory_round_trip"]["ok"] is True
    assert report.sections["memory_round_trip"]["entry_count"] == 1
    assert report.sections["tiers"]["items"] == [
        {"tier": "global", "brain_id": "augur-core", "root": str(tmp_path / "core")},
        {"tier": "personal", "brain_id": "personal", "root": str(tmp_path / "user")},
        {
            "tier": "project",
            "brain_id": "project-repo",
            "root": str(tmp_path / "repo" / "project-brain"),
        },
    ]


def test_closeout_fails_on_missing_client_skill(tmp_path: Path) -> None:
    from src.lib.brain_closeout import verify_family_closeout

    stack = _stack(tmp_path)
    client_dir = tmp_path / "repo" / ".codex" / "skills"
    _client_skills(client_dir, "core-only", "project-only")

    report = verify_family_closeout(
        stack,
        clients=("codex",),
        client_dirs={"codex-local": client_dir},
        single_brain_skills={"project-only"},
        orphan_refs=[],
        project_root=tmp_path / "repo",
    )

    assert report.all_ok is False
    assert report.sections["harness"]["codex"]["ok"] is False
    assert report.sections["harness"]["codex"]["missing"] == ["user-only"]


def test_closeout_fails_on_orphan_refs(tmp_path: Path) -> None:
    from src.lib.brain_closeout import verify_family_closeout

    stack = _stack(tmp_path)
    client_dir = tmp_path / "repo" / ".codex" / "skills"
    _client_skills(client_dir, "core-only", "user-only", "project-only")

    report = verify_family_closeout(
        stack,
        clients=("codex",),
        client_dirs={"codex-local": client_dir},
        single_brain_skills={"project-only"},
        orphan_refs=["docs/example.md:3: old vault/skills reference"],
        project_root=tmp_path / "repo",
    )

    assert report.all_ok is False
    assert report.sections["orphan_refs"] == {
        "ok": False,
        "count": 1,
        "refs": ["docs/example.md:3: old vault/skills reference"],
    }


def test_scan_orphan_references_finds_live_text_hits(tmp_path: Path) -> None:
    from src.lib.brain_closeout import scan_orphan_references

    good = tmp_path / "src" / "good.py"
    good.parent.mkdir()
    good.write_text("canonical = 'capabilities/skills/example'\n", encoding="utf-8")
    bad = tmp_path / "docs" / "bad.md"
    bad.parent.mkdir()
    bad.write_text("old path: vault/skills/example\n", encoding="utf-8")

    refs = scan_orphan_references([tmp_path], ["vault/skills"])

    assert refs == [f"{bad}:1: old path: vault/skills/example"]


def test_scan_orphan_references_falls_back_per_root(monkeypatch, tmp_path: Path) -> None:
    import src.lib.brain_closeout as closeout

    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "old.md").write_text("old path: vault/skills/one\n", encoding="utf-8")
    (second / "old.md").write_text("old path: vault/skills/two\n", encoding="utf-8")
    monkeypatch.setattr(closeout, "_scan_root_with_rg", lambda _root, _fragments: [])

    refs = closeout.scan_orphan_references([first, second], ["vault/skills"])

    assert refs == [
        f"{first / 'old.md'}:1: old path: vault/skills/one",
        f"{second / 'old.md'}:1: old path: vault/skills/two",
    ]


def test_enabled_clients_from_dirs_requires_nonempty_skill_dir(tmp_path: Path) -> None:
    from src.lib.brain_closeout import enabled_clients_from_dirs

    codex = tmp_path / ".codex" / "skills"
    (codex / "ai").mkdir(parents=True)
    gemini = tmp_path / ".gemini" / "skills"
    gemini.mkdir(parents=True)

    assert enabled_clients_from_dirs(
        {
            "codex-local": codex,
            "gemini-local": gemini,
            "claude-local": tmp_path / "missing" / ".claude" / "skills",
        }
    ) == ("codex",)
