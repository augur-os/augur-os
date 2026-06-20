"""Tests for dashboard registry workflow discovery."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from apps.dashboard.scripts import generate_registry


def test_scan_workflows_reads_fallbacks_from_vault_config_ai(monkeypatch, tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    config_workflows = vault / "config" / "ai" / "agent-workflows"
    legacy_workflows = vault / "ai" / "agent-workflows"
    config_workflows.mkdir(parents=True)
    legacy_workflows.mkdir(parents=True)
    (config_workflows / "config-only.md").write_text(
        "---\ndescription: Config workflow\nmode: dev\n---\n",
        encoding="utf-8",
    )
    (legacy_workflows / "legacy-only.md").write_text(
        "---\ndescription: Legacy workflow\nmode: dev\n---\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(generate_registry, "_iter_skill_dirs", lambda: [])
    monkeypatch.setattr(generate_registry, "PROJECT_ROOT", tmp_path / "project")
    monkeypatch.setattr(generate_registry, "VAULT_ROOT", vault)
    monkeypatch.setattr(
        generate_registry,
        "get_vault_config_dir",
        lambda: vault / "config",
        raising=False,
    )

    workflows = generate_registry.scan_workflows()

    assert workflows == {
        "config-only": {
            "mode": "dev",
            "description": "Config workflow",
            "file": "config/ai/agent-workflows/config-only.md",
            "command": "/config-only",
        }
    }


def test_scan_skills_excludes_repo_root_transitional_records(monkeypatch, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    shared_skill = project_root / "project-brain" / "capabilities" / "skills" / "knowledge"
    repo_root_skill = project_root.joinpath("skills", "legacy")
    private_skill = tmp_path / "private-vault" / "skills" / "apple"
    for skill_dir in (shared_skill, repo_root_skill, private_skill):
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {skill_dir.name}\ndescription: {skill_dir.name}\nx-augur-hub: workspace\n---\n",
            encoding="utf-8",
        )

    records = [
        SimpleNamespace(
            name="knowledge",
            path=shared_skill,
            hub="brain",
            description="shared",
            origin="project-brain",
            source="project-brain",
            source_root="project-brain",
        ),
        SimpleNamespace(
            name="legacy",
            path=repo_root_skill,
            hub="brain",
            description="legacy",
            origin="repo-root-transitional",
            source="repo-root-transitional",
            source_root="project-brain",
        ),
        SimpleNamespace(
            name="apple",
            path=private_skill,
            hub="life",
            description="private",
            origin="private-vault",
            source="private-vault",
            source_root="private-vault",
        ),
    ]

    monkeypatch.setattr(generate_registry, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(generate_registry, "VAULT_ROOT", tmp_path / "private-vault")
    monkeypatch.setattr(generate_registry, "_get_discovered_skills", lambda: records)

    skills = generate_registry.scan_skills()

    assert sorted(skills) == ["apple", "knowledge"]
    assert skills["knowledge"]["path"] == "project-brain/capabilities/skills/knowledge"
    assert skills["apple"]["path"] == str(private_skill)
    assert all(not meta["path"].startswith("skills/") for meta in skills.values())
