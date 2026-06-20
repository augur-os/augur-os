"""Claude native scheduled task loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CLAUDE_WARNING = "Claude schedule interpretation is provisional until timezone semantics are verified."


def _load_prompt_body(prompt_path_str: str) -> tuple[Path | None, str]:
    """Return the expanded prompt path and body when readable."""

    if not prompt_path_str.strip():
        return None, ""

    prompt_path = Path(prompt_path_str).expanduser()
    if not prompt_path.is_file():
        return prompt_path, ""

    try:
        return prompt_path, prompt_path.read_text(encoding="utf-8")
    except OSError:
        return prompt_path, ""


def load_claude_schedules() -> list[dict[str, Any]]:
    """Load Claude local scheduled tasks from the user support tree."""
    home = Path.home()
    sessions_root = home / "Library" / "Application Support" / "Claude" / "local-agent-mode-sessions"
    if not sessions_root.exists():
        return []

    rows: list[dict[str, Any]] = []
    for scheduled_json in sorted(sessions_root.glob("**/scheduled-tasks.json")):
        try:
            payload = json.loads(scheduled_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for task in payload.get("scheduledTasks") or payload.get("tasks") or []:
            if not isinstance(task, dict):
                continue
            prompt_path, prompt_body = _load_prompt_body(str(task.get("filePath", "")))
            task_id = str(task.get("id", "unknown"))
            prompt_summary = ""
            if prompt_body:
                prompt_summary = next(
                    (line.strip() for line in reversed(prompt_body.splitlines()) if line.strip()),
                    "",
                )
            rows.append(
                {
                    "id": f"claude:{task_id}",
                    "native_id": task_id,
                    "title": task_id.replace("-", " ").title(),
                    "source": "claude",
                    "kind": "native-schedule",
                    "workspace": str((task.get("userSelectedFolders") or [""])[0]),
                    "schedule_human": str(task.get("cronExpression", "")),
                    "prompt_summary": prompt_summary,
                    "prompt_body": prompt_body,
                    "source_path": str(prompt_path) if prompt_path else "",
                    "model": str(task.get("model", "")),
                    "status": "active" if task.get("enabled", True) else "disabled",
                    "last_run_at": None,
                    "next_run_at": None,
                    "raw_schedule": {
                        "type": "cron",
                        "value": task.get("cronExpression", ""),
                    },
                    "warnings": [_CLAUDE_WARNING],
                }
            )
    return rows
