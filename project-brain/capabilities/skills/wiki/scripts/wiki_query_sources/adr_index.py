from __future__ import annotations

from datetime import date, timedelta

from src.lib.adr_utils import get_adr_dir, load_adrs_index

from .base import SourceResult


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _record_text(record: dict) -> str:
    return (
        f"{record.get('adr_number', '?')} | {record.get('status', '?')} | "
        f"{record.get('date', '?')} | {record.get('title', '')}\n"
        f"  Decision: {record.get('decision_summary', '') or '(none)'}\n"
    )


class AdrIndexAdapter:
    kind = "adr_index"

    def resolve(self, spec: dict, budget_tokens: int) -> SourceResult:
        records = load_adrs_index(get_adr_dir())
        status_filter = spec.get("status")
        if status_filter:
            allowed = {str(status) for status in status_filter}
            records = [record for record in records if record.get("status") in allowed]

        recent_days = spec.get("recent_days")
        if recent_days is not None:
            cutoff = date.today() - timedelta(days=int(recent_days))
            records = [record for record in records if _record_date(record) is not None and _record_date(record) >= cutoff]

        parts: list[str] = []
        citations: list[str] = []
        running_tokens = 0
        truncated = False
        for record in records:
            block = _record_text(record)
            tokens = _approx_tokens(block)
            if running_tokens + tokens > budget_tokens:
                truncated = True
                break
            parts.append(block)
            citations.append(f"adrs-index.json:{record.get('adr_number', '?')}")
            running_tokens += tokens

        return SourceResult(text="".join(parts), citations=citations, truncated=truncated)


def _record_date(record: dict) -> date | None:
    try:
        return date.fromisoformat(str(record.get("date") or ""))
    except ValueError:
        return None
