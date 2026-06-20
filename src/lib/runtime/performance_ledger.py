"""Performance ledger for agent task tracking (ADR-460)."""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.config.paths import get_state_dir


def _ledger_path() -> Path:
    return get_state_dir() / "agents" / "performance.json"


@dataclass
class TaskRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent: str = ""
    tier: str = "standard"
    model: str = "sonnet"
    tokens_in: int = 0
    tokens_out: int = 0
    duration_seconds: float = 0.0
    files_edited: int = 0
    files_created: int = 0
    outcome: str = "unknown"  # success | failure | escalated | timeout
    task_signals: list[str] = field(default_factory=list)
    escalated_from: str | None = None


def record_task(record: TaskRecord) -> None:
    """Append a task record and update aggregates."""
    path = _ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = _load(path)
    data["records"].append(asdict(record))
    _update_aggregates(data, record)
    _save(path, data)


def get_aggregates() -> dict[str, Any]:
    """Return per-agent per-tier aggregates."""
    data = _load(_ledger_path())
    return data.get("aggregates", {})


def compact(max_age_days: int = 30, max_size_mb: float = 10.0) -> int:
    """Roll old records into aggregates, enforce size cap. Returns records removed."""
    path = _ledger_path()
    if not path.exists():
        return 0

    data = _load(path)
    cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
    before = len(data["records"])

    # Keep only recent records
    data["records"] = [r for r in data["records"] if r.get("timestamp", "") >= cutoff]

    # Size cap: evict oldest if over limit
    serialized = json.dumps(data)
    while len(serialized) > max_size_mb * 1_000_000 and data["records"]:
        data["records"].pop(0)
        serialized = json.dumps(data)

    removed = before - len(data["records"])
    if removed > 0:
        _save(path, data)
    return removed


def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"records": [], "aggregates": {}}


def _save(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str))
    # Path.replace uses os.replace — atomic overwrite on POSIX *and* Windows.
    # Path.rename (the previous call) raised FileExistsError on Windows when
    # path already existed, crashing the MCP server on every telemetry write.
    tmp.replace(path)


def _update_aggregates(data: dict, record: TaskRecord) -> None:
    key = f"{record.agent}:{record.tier}"
    aggs = data.setdefault("aggregates", {})
    agg = aggs.get(key, {"total_tasks": 0, "successes": 0, "total_tokens": 0, "total_duration": 0.0})

    agg["total_tasks"] += 1
    if record.outcome == "success":
        agg["successes"] += 1
    agg["total_tokens"] += record.tokens_in + record.tokens_out
    agg["total_duration"] += record.duration_seconds
    agg["success_rate"] = round(agg["successes"] / agg["total_tasks"], 3) if agg["total_tasks"] else 0
    agg["avg_tokens"] = agg["total_tokens"] // agg["total_tasks"] if agg["total_tasks"] else 0
    agg["avg_duration"] = round(agg["total_duration"] / agg["total_tasks"], 2) if agg["total_tasks"] else 0
    agg["last_updated"] = datetime.now().isoformat()
    aggs[key] = agg
