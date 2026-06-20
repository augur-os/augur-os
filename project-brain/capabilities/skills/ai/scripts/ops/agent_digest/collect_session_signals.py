"""Session log signal collector for agent-digest.

Scans session logs for user correction signals (phrases indicating
the user corrected the agent's behavior).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

CORRECTION_PATTERNS = [
    re.compile(r"\bno[,.]?\s+(don'?t|do not|never|stop)\b", re.IGNORECASE),
    re.compile(r"\b(don'?t|do not)\s+\w+", re.IGNORECASE),
    re.compile(r"\bstop\s+\w+", re.IGNORECASE),
    re.compile(r"\b(that'?s\s+)?wrong\b", re.IGNORECASE),
    re.compile(r"\bI\s+said\b", re.IGNORECASE),
]

FALSE_POSITIVE_PATTERNS = [
    re.compile(r"\bno\s+(issues?|problems?|worries|thanks)\b", re.IGNORECASE),
    re.compile(r"\bno\s+need\b", re.IGNORECASE),
]


def extract_corrections(lines: list[str]) -> list[str]:
    """Extract lines that contain user correction signals."""
    corrections = []
    for line in lines:
        if any(fp.search(line) for fp in FALSE_POSITIVE_PATTERNS):
            continue
        if any(cp.search(line) for cp in CORRECTION_PATTERNS):
            corrections.append(line)
    return corrections


def infer_directive(
    text: str,
    directive_map: dict[str, dict],
) -> str | None:
    """Try to match correction text to a known directive by keyword overlap."""
    text_lower = text.lower()
    best_match = None
    best_score = 0
    for directive_id, info in directive_map.items():
        label = info.get("label", "").lower()
        description = info.get("description", "").lower()
        keywords = set(re.findall(r"\w+", label + " " + description))
        text_words = set(re.findall(r"\w+", text_lower))
        overlap = len(keywords & text_words)
        if overlap > best_score:
            best_score = overlap
            best_match = directive_id
    if best_score >= 1:
        return best_match
    return None


def load_directive_map(map_path: Path) -> dict[str, dict]:
    """Load directive map from YAML."""
    with map_path.open() as f:
        data = yaml.safe_load(f)
    return data.get("directives", {})


def _extract_user_messages(jsonl_line: str) -> str | None:
    """Extract user message text from a Claude Code session JSONL line."""
    try:
        record = json.loads(jsonl_line)
    except (json.JSONDecodeError, ValueError):
        return None
    # Claude Code session format: {"type": "human", "message": {"content": "..."}}
    if record.get("type") == "human":
        msg = record.get("message", {})
        if isinstance(msg, dict):
            content = msg.get("content", "")
            if isinstance(content, str):
                return content
            # content can be a list of blocks
            if isinstance(content, list):
                return " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict)
                )
    return None


def _find_claude_session_dirs() -> list[Path]:
    """Find Claude Code project session directories."""
    claude_dir = Path.home() / ".claude" / "projects"
    if not claude_dir.exists():
        return []
    return [d for d in claude_dir.iterdir() if d.is_dir()]


def collect(
    logs_dir: Path,
    directive_map_path: Path,
    since_hours: int = 24,
) -> list[dict]:
    """Collect correction signals from session logs.

    Scans two sources:
    1. Augur logs dir (get_logs_dir()) for .jsonl files
    2. Claude Code session dirs (~/.claude/projects/*/**.jsonl) for user messages
    """
    directive_map = load_directive_map(directive_map_path)
    now = datetime.now(timezone.utc).isoformat()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    events = []

    # Source 1: Augur logs dir
    if logs_dir.exists():
        for log_file in sorted(logs_dir.glob("*.jsonl")):
            try:
                lines = log_file.read_text().strip().split("\n")
            except (OSError, UnicodeDecodeError):
                continue

            corrections = extract_corrections(lines)
            for correction in corrections:
                directive = infer_directive(correction, directive_map)
                rule = directive if directive else f"inferred:{correction[:50]}"
                events.append({
                    "ts": now,
                    "source": "session_log",
                    "type": "user_correction",
                    "signal": correction[:200],
                    "rule": rule,
                    "session": log_file.stem,
                })

    # Source 2: Claude Code session logs
    for project_dir in _find_claude_session_dirs():
        for session_file in sorted(project_dir.glob("*.jsonl")):
            try:
                mtime = datetime.fromtimestamp(
                    session_file.stat().st_mtime, tz=timezone.utc,
                )
                if mtime < cutoff:
                    continue
                raw_lines = session_file.read_text().strip().split("\n")
            except (OSError, UnicodeDecodeError):
                continue

            # Extract only user (human) messages
            user_messages = []
            for line in raw_lines:
                msg = _extract_user_messages(line)
                if msg:
                    user_messages.append(msg)

            corrections = extract_corrections(user_messages)
            for correction in corrections:
                directive = infer_directive(correction, directive_map)
                rule = directive if directive else f"inferred:{correction[:50]}"
                events.append({
                    "ts": now,
                    "source": "session_log",
                    "type": "user_correction",
                    "signal": correction[:200],
                    "rule": rule,
                    "session": session_file.stem,
                })

    return events
