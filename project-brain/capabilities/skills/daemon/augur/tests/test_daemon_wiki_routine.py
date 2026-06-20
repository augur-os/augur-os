from __future__ import annotations

import yaml
from pathlib import Path


def test_wiki_batched_daily_task_registered() -> None:
    tasks_path = Path(__file__).resolve().parents[1] / "config" / "tasks.yaml"
    data = yaml.safe_load(tasks_path.read_text(encoding="utf-8"))

    task = data["tasks"]["wiki-batched-daily"]

    assert task["schedule"] == "daily"
    assert task["hour"] == 6
    assert task["minute"] == 23
    assert task["script"] == "project-brain/capabilities/skills/ingest/scripts/run_wiki_batched_daily.py"
    assert task["enabled"] is True
