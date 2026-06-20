"""Audio transcript classifier: heuristic first, LLM-assisted on uncertainty."""
from __future__ import annotations

import re
from typing import Any

_SPEAKER_TAG_RE = re.compile(r"^\s*\[[A-Za-z][A-Za-z0-9 _\-]*\]", re.MULTILINE)
_FIRST_PERSON_RE = re.compile(r"\b(I|I'm|I'll|I'd|my|me|myself)\b", re.IGNORECASE)
_DIALOGUE_QUESTION_RE = re.compile(
    r"\b(?:you|your|why|what|when|where|how|isn['’]?t|aren['’]?t|didn['’]?t)\b[^?]{0,120}\?",
    re.IGNORECASE,
)


def _first_person_density(text: str) -> float:
    tokens = re.findall(r"\b[\w']+\b", text or "")
    if not tokens:
        return 0.0
    return len(_FIRST_PERSON_RE.findall(text)) / len(tokens)


def _dialogue_question_count(text: str) -> int:
    """Count question turns that strongly suggest a second speaker.

    Whisper without diarization often returns short interviews or podcasts as a
    single text stream. Those transcripts can look first-person heavy, so we use
    repeated second-person questions as a tier-0 signal for conversation audio.
    """
    return len(_DIALOGUE_QUESTION_RE.findall(text or ""))


def classify_heuristic(
    text: str,
    segments: list[dict],
    duration_seconds: float,
    speaker_count: int,
) -> dict[str, Any]:
    """Classify a transcript without LLM access."""
    del segments
    score_meeting = 0.0
    score_voice = 0.0
    reasons: list[str] = []

    if speaker_count >= 2:
        score_meeting += 0.65
        reasons.append(f"speaker_count={speaker_count} >= 2")
    elif speaker_count == 1:
        score_voice += 0.1
        reasons.append("single speaker labeled")

    speaker_tag_hits = len(_SPEAKER_TAG_RE.findall(text or ""))
    if speaker_tag_hits >= 2:
        score_meeting += 0.45
        reasons.append(f"speaker_tags={speaker_tag_hits}")

    dialogue_questions = _dialogue_question_count(text)
    if dialogue_questions >= 3 and duration_seconds >= 60:
        score_meeting += 0.95
        reasons.append(f"dialogue_questions={dialogue_questions}")

    first_person_density = _first_person_density(text)
    if first_person_density >= 0.03:
        score_voice += 0.65
        reasons.append(f"first_person_density={first_person_density:.3f}")

    if duration_seconds <= 360:
        score_voice += 0.25
        reasons.append("duration <= 6min")
    elif duration_seconds >= 1200:
        score_meeting += 0.3
        reasons.append("duration >= 20min")

    if score_meeting > score_voice:
        decision = "meeting"
        confidence = score_meeting
    else:
        decision = "voice-memo"
        confidence = score_voice

    if score_meeting + score_voice < 0.4:
        confidence = min(confidence, 0.5)
        reasons.append("low total signal")

    return {
        "type": decision,
        "confidence": round(min(confidence, 1.0), 3),
        "reasoning": "; ".join(reasons) or "no_features",
    }


def build_llm_dispatch_payload(text: str, duration_seconds: float, speaker_count: int) -> dict[str, Any]:
    """Build the LLM-Assisted MCP callback payload."""
    return {
        "needs_llm": True,
        "task": "audio-classify",
        "transcript_preview": (text or "")[:2000],
        "transcript_full_length_chars": len(text or ""),
        "duration_seconds": duration_seconds,
        "speaker_count": speaker_count,
        "instructions": (
            "Decide whether this transcript is a personal voice memo or a meeting recording. "
            "Return JSON with type (voice-memo | meeting), confidence (0..1), and reasoning."
        ),
        "expected_result_schema": {
            "type": "string (voice-memo | meeting)",
            "confidence": "number 0..1",
            "reasoning": "string",
        },
    }
