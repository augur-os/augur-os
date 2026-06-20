from __future__ import annotations

import importlib
import sys
from pathlib import Path


PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_main_resolves_evals_dir_under_shared_vault(tmp_path, monkeypatch):
    """Feedback prompts should read eval state from project-brain skill sources."""
    mod = importlib.import_module("skills.auto-skill-quality.scripts.feedback_hook")
    captured: dict[str, Path] = {}

    monkeypatch.setattr(mod, "get_project_root", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["feedback_hook", "--skill", "demo"])
    monkeypatch.setattr(
        mod,
        "should_prompt_feedback",
        lambda _skill_name, evals_dir: captured.setdefault("evals_dir", evals_dir) and False,
    )

    mod.main()

    assert captured["evals_dir"] == tmp_path / "project-brain" / "capabilities" / "skills" / "demo" / "evals"
