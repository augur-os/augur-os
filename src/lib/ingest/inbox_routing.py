from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class RouteDecision:
    route: str
    filename: str
    reason: str


def _slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value[:80].strip("-") or "imported-file"


def decide_route(*, source_name: str, title: str, body: str, content_type: str) -> RouteDecision:
    lowered = f"{source_name}\n{title}\n{body}".lower()
    suffix = Path(source_name).suffix.lower()
    if content_type == "audio" or suffix in {".mp3", ".wav", ".m4a", ".flac"}:
        route = "meetings"
        reason = "Audio meeting or recording detected."
    elif any(token in lowered for token in ["invoice", "receipt", "bank", "statement", "payment"]):
        route = "finance"
        reason = "Finance terms detected in extracted content."
    elif any(token in lowered for token in ["doctor", "medical", "health", "clinic", "insurance"]):
        route = "health"
        reason = "Health or insurance terms detected in extracted content."
    else:
        route = "inbox/review"
        reason = "No confident route matched."
    stem_source = title.strip() or Path(source_name).stem
    filename = f"{date.today().isoformat()}-{_slug(stem_source)}{suffix or '.md'}"
    return RouteDecision(route=route, filename=filename, reason=reason)
