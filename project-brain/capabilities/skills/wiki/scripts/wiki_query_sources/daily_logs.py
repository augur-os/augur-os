from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from src.config.paths import get_vault_dir

from .base import SourceResult


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _date_from_name(path: Path) -> date | None:
    try:
        return date.fromisoformat(path.stem)
    except ValueError:
        return None


class DailyLogsAdapter:
    kind = "daily_logs"

    def resolve(self, spec: dict, budget_tokens: int) -> SourceResult:
        daily_dir = get_vault_dir() / "memory" / "daily"
        if not daily_dir.exists():
            return SourceResult(text="", citations=[], truncated=False)

        recent_days = int(spec.get("recent_days", 30))
        cutoff = date.today() - timedelta(days=recent_days)
        files = [
            path
            for path in sorted(daily_dir.glob("*.md"), reverse=True)
            if (_date_from_name(path) is not None and _date_from_name(path) >= cutoff)
        ]

        parts: list[str] = []
        citations: list[str] = []
        running_tokens = 0
        truncated = False
        for path in files:
            text = path.read_text(encoding="utf-8")
            block = f"=== {path.name} ===\n{text}\n"
            tokens = _approx_tokens(block)
            if running_tokens + tokens > budget_tokens:
                truncated = True
                break
            parts.append(block)
            citations.append(f"{path}:{len(text.splitlines())} lines")
            running_tokens += tokens

        return SourceResult(text="\n".join(parts), citations=citations, truncated=truncated)
