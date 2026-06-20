"""Auto-generated importability test for run_system_audits."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_run_system_audits_importable():
    """Verify that run_system_audits can be imported without errors."""
    import importlib
    mod = importlib.import_module("skills.daemon.scripts.run_system_audits")
    assert mod is not None


def test_create_dashboard_review_writes_runtime_attention_queue(tmp_path, monkeypatch):
    """Generated audit reviews should not recreate a vault channels root."""
    import importlib
    import yaml

    mod = importlib.import_module("skills.daemon.scripts.run_system_audits")
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(mod, "get_runtime_dir", lambda: runtime_dir)

    run = mod.AuditRun(
        total_findings=1,
        total_errors=0,
        total_warnings=1,
        audits_run=[
            {
                "success": True,
                "skill": "advisor",
                "summary": {"findings_count": 1},
            }
        ],
    )

    review_id = mod.create_dashboard_review(run)

    reviews_file = runtime_dir / "attention" / "reviews" / "pending_reviews.yaml"
    assert review_id.startswith("audit-")
    assert reviews_file.is_file()
    data = yaml.safe_load(reviews_file.read_text(encoding="utf-8"))
    assert data["reviews"][0]["id"] == review_id
