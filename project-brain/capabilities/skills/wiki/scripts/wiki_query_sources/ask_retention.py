from __future__ import annotations

from typing import Any

from src.lib.ingest.ask_sync import load_recent_ask_outcomes

from .base import SourceResult


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class AskRetentionAdapter:
    kind = "ask_retention"

    def resolve(self, spec: dict, budget_tokens: int) -> SourceResult:
        outcomes = load_recent_ask_outcomes(
            days_back=int(spec.get("recent_days", 7)),
            limit=int(spec.get("limit", 20)),
        )
        if not outcomes:
            return SourceResult(text="", citations=[], truncated=False)

        parts: list[str] = []
        citations: list[str] = []
        running_tokens = 0
        truncated = False
        for outcome in outcomes:
            block = _format_outcome(outcome)
            tokens = _approx_tokens(block)
            if running_tokens + tokens > budget_tokens:
                truncated = True
                break
            parts.append(block)
            path = outcome.get("path")
            if path:
                citations.append(str(path))
            running_tokens += tokens

        return SourceResult(text="\n\n".join(parts), citations=citations, truncated=truncated)


def _format_outcome(outcome: dict[str, Any]) -> str:
    return (
        f"### {outcome.get('question') or outcome.get('title') or 'Ask outcome'}\n"
        f"- Created: {outcome.get('created', '')}\n"
        f"- Confidence: {outcome.get('confidence', '')}\n\n"
        f"{outcome.get('summary', '')}"
    ).strip()
