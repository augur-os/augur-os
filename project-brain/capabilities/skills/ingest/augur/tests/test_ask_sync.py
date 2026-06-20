"""Auto-generated importability test for ask_sync."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_ask_sync_importable():
    """Verify that ask_sync can be imported without errors."""
    import importlib
    mod = importlib.import_module("ask_sync")
    assert mod is not None


def test_load_recent_ask_outcomes_includes_project_brain_syntheses(monkeypatch, tmp_path):
    from src.lib.ingest import ask_sync

    project_brain = tmp_path / "project-brain"
    synthesis = project_brain / "knowledge" / "syntheses" / "2026-06-01-demo.md"
    synthesis.parent.mkdir(parents=True)
    created = datetime.now(tz=timezone.utc).isoformat()
    synthesis.write_text(
        "\n".join(
            [
                "---",
                "title: Demo retained outcome",
                "type: synthesis",
                "query: Demo retained outcome",
                f"created: '{created}'",
                "tags:",
                "- ask",
                "- demo",
                "---",
                "",
                "Project-brain ask retention should feed compounding.",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(ask_sync, "get_runtime_dir", lambda: tmp_path / "runtime")
    monkeypatch.setattr(ask_sync, "get_skill_data_dir", lambda skill: tmp_path / "vault" / skill)
    monkeypatch.setattr(ask_sync, "get_project_brain_dir", lambda: project_brain)

    outcomes = ask_sync.load_recent_ask_outcomes(days_back=1, limit=10)

    assert [item["question"] for item in outcomes] == ["Demo retained outcome"]
    assert outcomes[0]["path"] == str(synthesis)
