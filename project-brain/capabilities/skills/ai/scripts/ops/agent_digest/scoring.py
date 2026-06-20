# skills/auto-agent-digest/scripts/scoring.py
"""Directive scoring engine for the agent-digest nightly loop.

Scores directives by violation frequency with recency decay and boost multipliers.
Produces ranked, token-capped directive lists for Hot tier.
"""

from __future__ import annotations

from datetime import datetime, timezone

TOKEN_BUDGET_HOT = 500
TOKEN_BUDGET_WARM = 500

EVENT_WEIGHTS: dict[str, float] = {
    "user_correction": 5.0,
    "flag": 4.0,
    "pattern_violation": 3.0,
    "hook_rejection": 2.0,
}

REPEATED_THRESHOLD = 3
REPEATED_BOOST = 1.3
FLAG_BOOST = 1.5


def recency_decay(days_old: float) -> float:
    """Return decay multiplier based on event age in days."""
    if days_old <= 2:
        return 1.0
    if days_old <= 5:
        return 0.7
    if days_old <= 7:
        return 0.4
    return 0.0


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


def score_directives(
    events: list[dict],
    reference_date: datetime | None = None,
) -> dict[str, dict]:
    """Score directives from events. Returns {directive_id: {score, count, events}}."""
    ref = reference_date or datetime.now(timezone.utc)
    grouped: dict[str, list[dict]] = {}
    for event in events:
        rule = event.get("rule", "unknown")
        grouped.setdefault(rule, []).append(event)

    result = {}
    for directive_id, directive_events in grouped.items():
        total_score = 0.0
        for event in directive_events:
            ts = datetime.fromisoformat(event["ts"].replace("Z", "+00:00"))
            days_old = (ref - ts).total_seconds() / 86400
            decay = recency_decay(days_old)
            if decay == 0.0:
                continue
            weight = EVENT_WEIGHTS.get(event.get("type", ""), 1.0)
            event_score = weight * decay
            if event.get("priority") == "boost":
                event_score *= FLAG_BOOST
            total_score += event_score

        count = len(directive_events)
        if count >= REPEATED_THRESHOLD:
            total_score *= REPEATED_BOOST

        if total_score > 0:
            result[directive_id] = {
                "score": round(total_score, 2),
                "count": count,
                "events": directive_events,
            }

    return result


def format_hot_directive(label: str, sources: list[str], count: int) -> str:
    """Format a single Hot tier directive line."""
    source_str = ", ".join(sources)
    return f"- **{label}** [{source_str}] (violated {count}x this week)"


def select_top_directives(
    scored: dict[str, dict],
    directive_map: dict[str, dict],
    budget: int = TOKEN_BUDGET_HOT,
) -> list[str]:
    """Select top directives that fit within token budget. Returns formatted lines."""
    ranked = sorted(scored.items(), key=lambda x: x[1]["score"], reverse=True)
    lines = []
    used_tokens = 0
    for directive_id, data in ranked:
        info = directive_map.get(directive_id, {})
        label = info.get("label", directive_id)
        sources = info.get("sources", [])
        description = info.get("description", "")
        line = f"- **{label}** — {description} [{', '.join(sources)}] (violated {data['count']}x this week)"
        line_tokens = estimate_tokens(line)
        if used_tokens + line_tokens > budget:
            remaining = len(ranked) - len(lines)
            if remaining > 0:
                lines.append(f"- *+ {remaining} more directives below threshold*")
            break
        lines.append(line)
        used_tokens += line_tokens
    return lines
