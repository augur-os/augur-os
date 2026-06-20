"""Auto-generated importability test for sync_repos."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def test_sync_repos_importable():
    """Verify that sync_repos can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.platform-admin.scripts.sync_repos")
    assert mod is not None


def test_trigger_code_review_loads_shared_vault_skill(tmp_path, capsys, monkeypatch):
    """Large-change review should load auto-code-review from project-brain."""
    import importlib

    mod = importlib.import_module("skills.platform-admin.scripts.sync_repos")
    review_script = tmp_path / "project-brain" / "capabilities" / "skills" / "auto-code-review" / "scripts" / "code_review.py"
    review_script.parent.mkdir(parents=True)
    (review_script.parent.parent / "SKILL.md").write_text("---\nname: auto-code-review\n---\n", encoding="utf-8")
    review_script.write_text(
        "from types import SimpleNamespace\n"
        "def scan(ctx):\n"
        "    return SimpleNamespace(summary='ok from project-brain')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "PROJECT_ROOT", tmp_path)

    mod.trigger_code_review(tmp_path, "test")

    assert "Review complete: ok from project-brain" in capsys.readouterr().out
