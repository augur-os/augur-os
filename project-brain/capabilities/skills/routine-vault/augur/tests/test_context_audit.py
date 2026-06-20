"""Auto-generated importability test for context_audit."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

MODULE_PATH = SCRIPTS_DIR / "context_audit.py"


def _load_context_audit():
    spec = importlib.util.spec_from_file_location("loop_memory_context_audit_under_test", MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_context_audit_importable():
    """Verify that context_audit can be imported without errors."""
    mod = _load_context_audit()
    assert mod is not None


def test_get_skill_md_files_uses_shared_vault_root(tmp_path):
    """Context budget checks should scan project-brain skill Markdown."""
    mod = _load_context_audit()
    skill_md = tmp_path / "project-brain" / "capabilities" / "skills" / "demo" / "SKILL.md"
    skill_md.parent.mkdir(parents=True)
    skill_md.write_text("---\nname: demo\n---\n# Demo\n", encoding="utf-8")

    assert mod._get_skill_md_files(tmp_path) == [skill_md]
