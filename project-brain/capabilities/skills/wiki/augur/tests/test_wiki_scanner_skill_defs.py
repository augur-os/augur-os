from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "wiki_scanner.py"
SPEC = importlib.util.spec_from_file_location("wiki_scanner_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
wiki_scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki_scanner)


def test_scan_skill_defs_uses_shared_vault_skill_root(tmp_path):
    """Wiki rebuild inventory should include project-brain skill definitions."""
    skill_md = tmp_path / "project-brain" / "capabilities" / "skills" / "demo" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("---\nname: demo\nx-augur-hub: dev\n---\n# Demo Skill\n", encoding="utf-8")

    scanner = wiki_scanner.WikiScanner(
        vault_dir=tmp_path / "vault",
        documents_dir=tmp_path / "documents",
        project_root=tmp_path,
    )

    assert scanner._scan_skill_defs() == [
        {
            "path": str(skill_md),
            "type": "skill",
            "title": "Demo Skill",
            "hub": "dev",
            "format": "md",
            "source_surface": "skills",
            "tier": "medium",
            "weight": 1.0,
        }
    ]
