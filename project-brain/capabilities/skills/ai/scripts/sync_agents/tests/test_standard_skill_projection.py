from __future__ import annotations

import sys
from pathlib import Path

scripts_dir = Path(__file__).resolve().parents[2]
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

import yaml

from sync_agents.standard_skill_projection import (
    discover_standard_skill_bundle,
    iter_standard_skill_sources,
)


def test_discover_standard_skill_bundle(tmp_path: Path) -> None:
    root = tmp_path / "apple"
    (root / "apple-notes").mkdir(parents=True)
    (root / "DESCRIPTION.md").write_text(
        "# Apple\n\nLocal Apple skills.\n",
        encoding="utf-8",
    )
    (root / "apple-notes" / "SKILL.md").write_text(
        "# Apple Notes\n\nUse local notes.\n",
        encoding="utf-8",
    )

    bundle = discover_standard_skill_bundle(root)

    assert bundle.name == "apple"
    assert bundle.description == "Local Apple skills."
    assert [skill.name for skill in bundle.subskills] == ["apple-notes"]
    assert bundle.subskills[0].title == "Apple Notes"


def test_managed_skill_sources_include_standard_bundle_subskills(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from sync_agents import skill_sync

    skills_root = tmp_path / "skills"
    apple = skills_root / "apple"
    (apple / "apple-notes").mkdir(parents=True)
    (apple / "DESCRIPTION.md").write_text(
        "# Apple\n\nLocal Apple skills.\n",
        encoding="utf-8",
    )
    (apple / "apple-notes" / "SKILL.md").write_text(
        "# Apple Notes\n\nUse local notes.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        skill_sync,
        "get_managed_skill_source_dirs",
        lambda _project_root: [skills_root],
    )

    sources = skill_sync._load_managed_skill_sources(tmp_path)

    assert [source[0] for source in sources] == ["apple-notes"]
    assert sources[0][2].startswith("---\nname: apple-notes\n")
    assert sources[0][2].endswith("# Apple Notes\n\nUse local notes.\n")
    assert sources[0][3] == "# Apple Notes\n\nUse local notes."
    assert sources[0][4] == "Use local notes."


def test_standard_skill_sources_render_codex_compatible_frontmatter(
    tmp_path: Path,
) -> None:
    skills_root = tmp_path / "skills"
    apple = skills_root / "apple"
    (apple / "apple-notes").mkdir(parents=True)
    (apple / "DESCRIPTION.md").write_text(
        "# Apple\n\nLocal Apple skills.\n",
        encoding="utf-8",
    )
    (apple / "apple-notes" / "SKILL.md").write_text(
        "# Apple Notes\n\nUse local notes.\n",
        encoding="utf-8",
    )

    source = iter_standard_skill_sources(skills_root)[0]
    raw = source[2]

    assert raw.startswith("---\n")
    metadata = yaml.safe_load(raw.split("---", 2)[1])
    assert metadata == {
        "name": "apple-notes",
        "description": "Use local notes.",
    }
    assert source[3] == "# Apple Notes\n\nUse local notes."


def test_managed_skill_sources_use_project_personal_global_precedence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from sync_agents import skill_sync

    global_root = tmp_path / "global" / "capabilities" / "skills"
    personal_root = tmp_path / "personal" / "capabilities" / "skills"
    project_root = tmp_path / "project" / "project-brain" / "capabilities" / "skills"

    for root, body in (
        (global_root, "global email"),
        (personal_root, "personal email"),
        (project_root, "project email"),
    ):
        (root / "email").mkdir(parents=True)
        (root / "email" / "SKILL.md").write_text(
            f"---\nname: email\ndescription: {body}\n---\n# Email\n\n{body}\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        skill_sync,
        "get_managed_skill_source_dirs",
        lambda _project_root: [global_root, personal_root, project_root],
    )

    sources = skill_sync._load_managed_skill_sources(tmp_path)

    assert [source[0] for source in sources] == ["email"]
    assert sources[0][1] == project_root / "email"
    assert "project email" in sources[0][2]


def test_managed_skill_sources_preserve_logical_precedence_for_coincident_roots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from sync_agents import skill_sync
    from src.lib.brain_effective_skills import LogicalSkillRootLayer

    shared_root = tmp_path / "augur" / "project-brain" / "capabilities" / "skills"
    personal_root = tmp_path / "personal" / "capabilities" / "skills"

    for root, body in (
        (shared_root, "shared project email"),
        (personal_root, "personal email"),
    ):
        (root / "email").mkdir(parents=True)
        (root / "email" / "SKILL.md").write_text(
            f"---\nname: email\ndescription: {body}\n---\n# Email\n\n{body}\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        skill_sync,
        "get_managed_skill_source_dirs",
        lambda _project_root: [shared_root, personal_root],
    )
    monkeypatch.setattr(
        skill_sync,
        "_managed_skill_root_layers",
        lambda _project_root: [
            LogicalSkillRootLayer("global", "augur-core", shared_root),
            LogicalSkillRootLayer("personal", "personal", personal_root),
            LogicalSkillRootLayer("project", "project-augur", shared_root),
        ],
    )

    sources = skill_sync._load_managed_skill_sources(tmp_path)

    assert [source[0] for source in sources] == ["email"]
    assert sources[0][1] == shared_root / "email"
    assert "shared project email" in sources[0][2]
