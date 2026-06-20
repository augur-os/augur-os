"""Auto-generated importability test for tab_scoring."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_tab_scoring_importable():
    """Verify that tab_scoring can be imported without errors."""
    mod = importlib.import_module("skills.daemon.scripts.ops.tab_scoring")
    assert mod is not None


def test_find_tab_scorer_uses_shared_vault_skill_root(tmp_path):
    """Tab scoring should resolve system-cleanup from project-brain, not retired skills/."""
    mod = importlib.import_module("skills.daemon.scripts.ops.tab_scoring")
    scorer = tmp_path / "project-brain" / "capabilities" / "skills" / "system-cleanup" / "scripts" / "tab_scorer.py"
    scorer.parent.mkdir(parents=True, exist_ok=True)
    (scorer.parent.parent / "SKILL.md").write_text("---\nname: system-cleanup\n---\n", encoding="utf-8")
    scorer.write_text("print('ok')\n", encoding="utf-8")

    assert mod._find_tab_scorer(tmp_path) == scorer
