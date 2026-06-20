"""Auto-generated importability test for llm_escalation."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

from src.lib.ops_protocol import OpsContext

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def test_llm_escalation_importable():
    """Verify that llm_escalation can be imported without errors."""
    mod = importlib.import_module("skills.auto-skill-quality.scripts.fixers.llm_escalation")
    assert mod is not None


def test_llm_fix_prompt_uses_shared_vault_skill_context(tmp_path):
    """Escalation prompts should point agents at project-brain skill sources."""
    mod = importlib.import_module("skills.auto-skill-quality.scripts.fixers.llm_escalation")
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Demo skill description\nx-augur-config:\n  hub: dev\n---\n# Demo\n",
        encoding="utf-8",
    )

    prompt = mod.llm_fix(
        OpsContext(project_root=tmp_path),
        [{"skill_name": "demo", "dimension": "instruction", "score": 40, "detail": "too short"}],
    )

    assert "Purpose: Demo skill description" in prompt
    assert "Path: project-brain/capabilities/skills/demo/" in prompt
