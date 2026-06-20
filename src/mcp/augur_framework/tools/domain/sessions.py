"""
Per-session focus state management (ADR-254).

Manages ephemeral session files that track which hub/skill an agent session
is focused on and which tools it has used recently. Files live in a
sessions directory under state/ and are pruned automatically.
"""

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


def create_session(
    sessions_dir: Path,
    session_id: str,
    source: str,
    hub: str | None = None,
    skill: str | None = None,
) -> dict:
    """Create a new session file with atomic write.

    Returns the session data dict that was written.
    """
    now = datetime.now(timezone.utc).isoformat()
    data = {
        "session_id": session_id,
        "source": source,
        "hub": hub,
        "skill": skill,
        "recent_tools": [],
        "started_at": now,
        "last_activity": now,
    }
    _write_session(sessions_dir, session_id, data)
    return data


def read_session(sessions_dir: Path, session_id: str) -> dict | None:
    """Read a session file. Returns None if missing."""
    session_path = sessions_dir / f"{session_id}.json"
    try:
        return json.loads(session_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def update_session_tool(sessions_dir: Path, session_id: str, tool_name: str) -> None:
    """Append a tool to recent_tools (keep last 20), update last_activity."""
    data = read_session(sessions_dir, session_id)
    if data is None:
        return
    tools = data.get("recent_tools", [])
    tools.append(tool_name)
    data["recent_tools"] = tools[-20:]
    data["last_activity"] = datetime.now(timezone.utc).isoformat()
    _write_session(sessions_dir, session_id, data)


def delete_session(sessions_dir: Path, session_id: str) -> None:
    """Delete a session file. No error if missing."""
    path = sessions_dir / f"{session_id}.json"
    path.unlink(missing_ok=True)


def prune_stale_sessions(sessions_dir: Path, max_age_seconds: int = 3600) -> int:
    """Prune session files older than max_age_seconds. Returns count pruned."""
    if not sessions_dir.exists():
        return 0
    now = time.time()
    count = 0
    for path in sessions_dir.glob("*.json"):
        if now - path.stat().st_mtime > max_age_seconds:
            path.unlink(missing_ok=True)
            count += 1
    return count


def _write_session(sessions_dir: Path, session_id: str, data: dict) -> None:
    """Atomic write via tmp file rename."""
    sessions_dir.mkdir(parents=True, exist_ok=True)
    target = sessions_dir / f"{session_id}.json"
    fd, tmp_path = tempfile.mkstemp(dir=sessions_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, target)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise
