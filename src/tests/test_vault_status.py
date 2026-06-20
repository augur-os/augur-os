from __future__ import annotations

from src.mcp.augur_framework.tools.internal import vault_status


def test_compute_health_score_uses_project_brain_skills_for_orphan_check(tmp_path, monkeypatch):
    """Vault health should not mark project-brain skills as orphaned."""
    project_root = tmp_path / "project"
    skill_dir = project_root / "project-brain" / "capabilities" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\n", encoding="utf-8")

    vault = tmp_path / "vault"
    note = vault / "brain" / "demo" / "note.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Demo\n", encoding="utf-8")

    monkeypatch.setattr("src.mcp.augur_shared.compat.get_project_root", lambda: project_root)

    _score, issues = vault_status._compute_health_score(vault)

    assert "orphan_dirs" not in issues
