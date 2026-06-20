from __future__ import annotations

from pathlib import Path

from src.lib.brain_effective_skills import (
    LogicalSkillRootLayer,
    build_effective_skill_report,
    choose_effective_named_sources,
)


def _source(root: Path, name: str) -> tuple[str, Path, str]:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    return (name, skill_dir, f"{name} from {root.name}")


def test_project_overrides_personal_and_global(tmp_path: Path) -> None:
    global_root = tmp_path / "global"
    personal_root = tmp_path / "personal"
    project_root = tmp_path / "project"

    def loader(root: Path) -> list[tuple[str, Path, str]]:
        if root == global_root:
            return [_source(root, "email"), _source(root, "ask")]
        if root == personal_root:
            return [_source(root, "email"), _source(root, "obsidian")]
        if root == project_root:
            return [_source(root, "email")]
        return []

    choices = choose_effective_named_sources(
        [global_root, personal_root, project_root],
        loader,
        name_getter=lambda item: item[0],
        path_getter=lambda item: item[1],
    )

    by_name = {choice.name: choice for choice in choices}
    assert by_name["email"].root == project_root
    assert by_name["email"].shadowed_roots == (global_root, personal_root)
    assert by_name["obsidian"].root == personal_root
    assert by_name["ask"].root == global_root


def test_shadow_report_is_stable_and_sorted(tmp_path: Path) -> None:
    global_root = tmp_path / "global"
    personal_root = tmp_path / "personal"

    def loader(root: Path) -> list[tuple[str, Path, str]]:
        return [_source(root, "zeta"), _source(root, "alpha")]

    choices = choose_effective_named_sources(
        [global_root, personal_root],
        loader,
        name_getter=lambda item: item[0],
        path_getter=lambda item: item[1],
    )

    assert [choice.name for choice in choices] == ["alpha", "zeta"]
    assert all(choice.root == personal_root for choice in choices)
    assert all(choice.shadowed_roots == (global_root,) for choice in choices)


def test_report_preserves_logical_layers_when_physical_roots_are_deduped(
    tmp_path: Path,
) -> None:
    shared_project_root = tmp_path / "augur" / "project-brain" / "capabilities" / "skills"
    personal_root = tmp_path / "personal" / "capabilities" / "skills"

    def loader(root: Path) -> list[tuple[str, Path, str]]:
        if root == shared_project_root:
            return [_source(root, "ingest")]
        if root == personal_root:
            return [_source(root, "apple-notes")]
        return []

    report = build_effective_skill_report(
        (
            LogicalSkillRootLayer(
                tier="global",
                brain_id="augur-core",
                root=shared_project_root,
            ),
            LogicalSkillRootLayer(
                tier="personal",
                brain_id="personal",
                root=personal_root,
            ),
            LogicalSkillRootLayer(
                tier="project",
                brain_id="project-augur",
                root=shared_project_root,
            ),
        ),
        loader,
        name_getter=lambda item: item[0],
        path_getter=lambda item: item[1],
    )

    assert [(layer.tier, layer.brain_id, layer.root) for layer in report.logical_layers] == [
        ("global", "augur-core", shared_project_root),
        ("personal", "personal", personal_root),
        ("project", "project-augur", shared_project_root),
    ]
    assert report.physical_roots == (shared_project_root, personal_root)
    assert [choice.name for choice in report.choices] == ["apple-notes", "ingest"]
    assert report.shadowed_count == 1
    assert [choice.name for choice in report.shadowed_choices] == ["ingest"]


def test_report_uses_logical_layers_for_effective_selection(
    tmp_path: Path,
) -> None:
    shared_project_root = tmp_path / "augur" / "project-brain" / "capabilities" / "skills"
    personal_root = tmp_path / "personal" / "capabilities" / "skills"

    def loader(root: Path) -> list[tuple[str, Path, str]]:
        if root == shared_project_root:
            return [_source(root, "email")]
        if root == personal_root:
            return [_source(root, "email")]
        return []

    report = build_effective_skill_report(
        (
            LogicalSkillRootLayer(
                tier="global",
                brain_id="augur-core",
                root=shared_project_root,
            ),
            LogicalSkillRootLayer(
                tier="personal",
                brain_id="personal",
                root=personal_root,
            ),
            LogicalSkillRootLayer(
                tier="project",
                brain_id="project-augur",
                root=shared_project_root,
            ),
        ),
        loader,
        physical_roots=(shared_project_root, personal_root),
        name_getter=lambda item: item[0],
        path_getter=lambda item: item[1],
    )

    by_name = {choice.name: choice for choice in report.choices}
    assert report.physical_roots == (shared_project_root, personal_root)
    assert by_name["email"].root == shared_project_root
    assert by_name["email"].path == shared_project_root / "email"
    assert by_name["email"].shadowed_paths == (
        shared_project_root / "email",
        personal_root / "email",
    )
    assert report.shadowed_count == 2


def test_report_counts_total_shadowed_sources(tmp_path: Path) -> None:
    global_root = tmp_path / "global"
    personal_root = tmp_path / "personal"
    project_root = tmp_path / "project"

    def loader(root: Path) -> list[tuple[str, Path, str]]:
        if root == global_root:
            return [_source(root, "email")]
        if root == personal_root:
            return [_source(root, "email")]
        if root == project_root:
            return [_source(root, "email")]
        return []

    report = build_effective_skill_report(
        (
            LogicalSkillRootLayer(
                tier="global",
                brain_id="augur-core",
                root=global_root,
            ),
            LogicalSkillRootLayer(
                tier="personal",
                brain_id="personal",
                root=personal_root,
            ),
            LogicalSkillRootLayer(
                tier="project",
                brain_id="project-augur",
                root=project_root,
            ),
        ),
        loader,
        name_getter=lambda item: item[0],
        path_getter=lambda item: item[1],
    )

    assert report.shadowed_count == 2
    assert [choice.name for choice in report.shadowed_choices] == ["email"]
    assert report.shadowed_choices[0].shadowed_paths == (
        global_root / "email",
        personal_root / "email",
    )
