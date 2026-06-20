from __future__ import annotations

import json
from pathlib import Path

from scripts import skill_standard_audit
from src.lib.skill_standard_scan import SkillStandardReport


def test_audit_json_reports_counts(tmp_path: Path, capsys) -> None:
    shared = tmp_path / "project-brain" / "capabilities" / "skills"
    private = tmp_path / "vault" / "skills"
    skill_dir = shared / "knowledge"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: knowledge\n"
        "description: Knowledge.\n"
        "x-augur:\n"
        "  tools:\n"
        "    - name: memory-search\n"
        "      surface: cli\n"
        "---\n",
        encoding="utf-8",
    )

    code = skill_standard_audit.main(
        [
            "--shared-root",
            str(shared),
            "--private-root",
            str(private),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["fail_count"] == 0
    assert payload["warn_count"] == 0
    assert payload["skills_scanned"] == 1


def test_audit_default_roots_bind_to_script_checkout(monkeypatch, capsys) -> None:
    calls: list[tuple[str, Path]] = []
    shared = Path("/tmp/shared-skills")
    private = Path("/tmp/private-skills")

    def fake_shared_root(project_root: Path) -> Path:
        calls.append(("shared", project_root))
        return shared

    def fake_private_root(project_root: Path) -> Path:
        calls.append(("private", project_root))
        return private

    def fake_scan(shared_root: Path, private_root: Path | None) -> SkillStandardReport:
        assert shared_root == shared
        assert private_root == private
        return SkillStandardReport(
            skills_scanned=0,
            fail_count=0,
            warn_count=0,
            issues=(),
        )

    monkeypatch.setattr(
        skill_standard_audit,
        "get_project_brain_skills_dir",
        fake_shared_root,
    )
    monkeypatch.setattr(
        skill_standard_audit,
        "get_configured_vault_skills_dir",
        fake_private_root,
    )
    monkeypatch.setattr(skill_standard_audit, "scan_skill_roots", fake_scan)

    code = skill_standard_audit.main(["--json"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["skills_scanned"] == 0
    assert calls == [
        ("shared", skill_standard_audit.PROJECT_ROOT),
        ("private", skill_standard_audit.PROJECT_ROOT),
    ]


def test_audit_warning_exit_code_respects_fail_on_warn(tmp_path: Path) -> None:
    shared = tmp_path / "project-brain" / "capabilities" / "skills"
    private = tmp_path / "vault" / "skills"
    skill_dir = private / "file-manager"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: file-manager\n"
        "description: Private files.\n"
        "x-augur:\n"
        "  tools:\n"
        "    - name: get-pending\n"
        "      surface: mcp-tool\n"
        "---\n",
        encoding="utf-8",
    )

    args = [
        "--shared-root",
        str(shared),
        "--private-root",
        str(private),
        "--json",
    ]

    assert skill_standard_audit.main(args) == 0
    assert skill_standard_audit.main([*args, "--fail-on-warn"]) == 1
