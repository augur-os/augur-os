from pathlib import Path

from src.lib.brain_classify.lint import scan_contamination


def test_lint_flags_project_page_in_personal_brain(tmp_path):
    vault_wiki = tmp_path / "Au-vault" / "wiki" / "concepts"
    pb_wiki = tmp_path / "project-brain" / "knowledge" / "wiki" / "concepts"
    vault_wiki.mkdir(parents=True)
    pb_wiki.mkdir(parents=True)
    (vault_wiki / "leak.md").write_text("about `src/mcp/augur_core/` and ADR-781", encoding="utf-8")
    (vault_wiki / "ok.md").write_text("family `health/` recipes", encoding="utf-8")
    (pb_wiki / "fine.md").write_text("dashboard in `apps/dashboard/`", encoding="utf-8")

    findings = scan_contamination(personal_roots=[vault_wiki], project_roots=[pb_wiki])
    flagged = {Path(f.path).name: f for f in findings}
    assert "leak.md" in flagged and flagged["leak.md"].host == "personal" and flagged["leak.md"].subject == "project"
    assert "ok.md" not in flagged
    assert "fine.md" not in flagged
