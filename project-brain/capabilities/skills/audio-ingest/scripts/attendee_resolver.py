"""Resolve meeting speakers to person-entity slugs via the graph skill."""
from __future__ import annotations

import re
from typing import Optional

_BRACKET_NAME_RE = re.compile(r"^\s*\[([A-Z][A-Za-z0-9 _\-]*)\]", re.MULTILINE)
_DIALOGUE_QUESTION_RE = re.compile(
    r"\b(?:you|your|why|what|when|where|how|isn['’]?t|aren['’]?t|didn['’]?t)\b[^?]{0,120}\?",
    re.IGNORECASE,
)


def extract_speaker_names_from_text(text: str) -> list[str]:
    """Return distinct bracket-tagged speaker names in first-seen order."""
    names: list[str] = []
    for match in _BRACKET_NAME_RE.findall(text or ""):
        name = match.strip()
        if name and name not in names:
            names.append(name)
    return names


def _segment_speaker_names(segments: list[dict]) -> list[str]:
    names: list[str] = []
    for segment in segments or []:
        name = str(segment.get("speaker") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def infer_attendee_count(
    *,
    text: str,
    segments: list[dict],
    attendee_slugs: list[str],
    duration_seconds: float,
) -> int:
    """Return resolved attendee count, falling back to observable dialogue signals."""
    if attendee_slugs:
        return len(attendee_slugs)

    bracket_names = extract_speaker_names_from_text(text)
    if bracket_names:
        return len(bracket_names)

    segment_names = _segment_speaker_names(segments)
    if segment_names:
        return len(segment_names)

    dialogue_questions = len(_DIALOGUE_QUESTION_RE.findall(text or ""))
    if dialogue_questions >= 3 and duration_seconds >= 60:
        return 2

    return 0


def _lookup_entity(name: str) -> Optional[tuple[str, float]]:
    """Look up a person entity by name, if a graph reader is available."""
    try:
        from skills.graph.scripts.entity_lookup import resolve_entity_by_name  # type: ignore
    except Exception as exc:
        raise RuntimeError("graph skill entity lookup is not available") from exc
    return resolve_entity_by_name(name, entity_type="person")


def resolve_speakers(speaker_names: list[str], min_confidence: float = 0.8) -> list[str]:
    """Resolve speaker names to entity slugs, degrading to [] if graph is unavailable."""
    resolved: list[str] = []
    for name in speaker_names:
        try:
            hit = _lookup_entity(name)
        except Exception:
            return []
        if hit and hit[1] >= min_confidence and hit[0] not in resolved:
            resolved.append(hit[0])
    return resolved
