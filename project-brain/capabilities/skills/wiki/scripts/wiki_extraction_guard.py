"""Skip wiki concept extraction when no selected source has changed."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def _read_last_ts(path: Path) -> float | None:
    try:
        return float(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _path_value(source: Any) -> str:
    if isinstance(source, dict):
        return str(source.get("source_path") or source.get("path") or "")
    return str(getattr(source, "source_path", "") or "")


def _modified_value(source: Any) -> str:
    if isinstance(source, dict):
        return str(source.get("modified_at") or source.get("modified") or "")
    return str(getattr(source, "modified_at", "") or "")


def _parse_modified_ts(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        pass
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return None


def _source_mtime(source: Any) -> float | None:
    raw_path = _path_value(source)
    if not raw_path:
        return _parse_modified_ts(_modified_value(source))
    if "://" in raw_path or raw_path.startswith("git:"):
        return float("inf")
    try:
        return Path(raw_path).expanduser().stat().st_mtime
    except OSError:
        return _parse_modified_ts(_modified_value(source))


def should_skip(sources: list[Any], last_ts_path: Path) -> bool:
    """True when all selected sources are older than last_ts_path."""
    last_ts = _read_last_ts(last_ts_path)
    if last_ts is None:
        return False
    if not sources:
        return True
    saw_known_source = False
    for source in sources:
        mtime = _source_mtime(source)
        if mtime is None:
            continue
        saw_known_source = True
        if mtime > last_ts:
            return False
    return saw_known_source


def write_last_ts(path: Path, ts: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{ts:.6f}\n", encoding="utf-8")
