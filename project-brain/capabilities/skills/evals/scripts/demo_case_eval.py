"""Deterministic local scoring for demo-case eval outputs."""

from __future__ import annotations

from dataclasses import dataclass

GENERIC_PHRASES = (
    "innovative ai solution",
    "many benefits",
    "great opportunities",
    "streamline workflows",
    "streamlines workflows",
    "unlock value",
    "unlocks value",
)
CONCRETE_TERMS = (
    "openvino",
    "offline",
    "claude",
    "gemini",
    "browse",
    "slide",
    "metadata",
    "transcript",
)
MEETING_TRANSCRIPT_TERMS = (
    "transcript",
    "decision",
    "decisions",
    "action",
    "actions",
    "meeting",
    "source",
    "offline",
    "openvino",
    "browse",
    "route",
    "local",
    "cloud",
    "whisper",
    "faster-whisper",
    "gemini",
)
JUDGE_READY_TERMS = (
    "named",
    "names",
    "cited",
    "cites",
    "flagged",
    "flags",
    "risk",
    "risks",
    "empty",
    "missing",
)
PASS_SPEED_SCORE = 3


@dataclass(frozen=True)
class DemoCaseConfig:
    concrete_terms: tuple[str, ...]
    max_pass_duration_ms: int


CASE_CONFIGS = {
    "deck-slide-critique": DemoCaseConfig(
        concrete_terms=CONCRETE_TERMS,
        max_pass_duration_ms=15_000,
    ),
    "meeting-transcript": DemoCaseConfig(
        concrete_terms=MEETING_TRANSCRIPT_TERMS,
        max_pass_duration_ms=90_000,
    ),
}


@dataclass(frozen=True)
class DemoCaseScore:
    case_id: str
    grounding: int
    specificity: int
    judge_readiness: int
    speed: int
    scores: dict[str, int]
    findings: list[str]
    pass_status: str


def _clamp_score(value: int) -> int:
    return max(1, min(5, value))


def _speed_score(duration_ms: int | None, *, max_pass_duration_ms: int) -> int:
    if duration_ms is None:
        return 3
    if duration_ms < 0:
        return 1
    if duration_ms <= 2_000:
        return 5
    if duration_ms <= 5_000:
        return 4
    if duration_ms <= max_pass_duration_ms:
        return 3
    if duration_ms <= max_pass_duration_ms * 2:
        return 2
    return 1


def score_demo_output(
    *,
    case_id: str,
    source_title: str,
    output_text: str,
    duration_ms: int | None,
) -> DemoCaseScore:
    config = CASE_CONFIGS.get(case_id)
    supported_case = config is not None
    concrete_terms = config.concrete_terms if config else ()
    max_pass_duration_ms = config.max_pass_duration_ms if config else 15_000

    text = output_text.lower()
    normalized_source_title = source_title.strip()
    source = normalized_source_title.lower()
    source_hit = bool(source and source in text)
    value_text = text.replace(source, "") if source else text
    generic_hits = [phrase for phrase in GENERIC_PHRASES if phrase in value_text]
    concrete_hits = {term for term in concrete_terms if term in value_text}
    judge_hits = {term for term in JUDGE_READY_TERMS if term in value_text}

    grounding = 1
    if source_hit:
        grounding += 2
    grounding += min(2, len(concrete_hits) // 2)

    specificity = 1 + min(4, len(concrete_hits) // 2)
    judge_readiness = (grounding + specificity) // 2
    if judge_hits:
        judge_readiness += 1

    if generic_hits:
        grounding -= 2
        specificity -= 2
        judge_readiness -= 2

    speed = _speed_score(duration_ms, max_pass_duration_ms=max_pass_duration_ms)
    scores = {
        "grounding": _clamp_score(grounding),
        "specificity": _clamp_score(specificity),
        "judge_readiness": _clamp_score(judge_readiness),
        "speed": speed,
    }

    findings: list[str] = []
    if not supported_case:
        findings.append(f"Unsupported demo case_id: {case_id}.")
    if generic_hits:
        findings.append(f"Generic demo language detected: {', '.join(generic_hits)}.")
    if not source:
        findings.append("Source title is required for demo grounding.")
    elif not source_hit:
        findings.append(f"Output did not name the source title: {source_title}.")
    if duration_ms is not None and duration_ms < 0:
        findings.append(f"Invalid negative duration_ms: {duration_ms}.")
    elif speed < PASS_SPEED_SCORE:
        findings.append(f"Demo duration was too slow: {duration_ms} ms.")
    if concrete_hits:
        findings.append(
            f"Concrete demo terms found: {', '.join(sorted(concrete_hits))}."
        )

    pass_status = (
        "pass"
        if (
            supported_case
            and not generic_hits
            and bool(source)
            and source_hit
            and scores["grounding"] >= 3
            and scores["specificity"] >= 3
            and scores["judge_readiness"] >= 3
            and scores["speed"] >= PASS_SPEED_SCORE
        )
        else "fail"
    )

    return DemoCaseScore(
        case_id=case_id,
        grounding=scores["grounding"],
        specificity=scores["specificity"],
        judge_readiness=scores["judge_readiness"],
        speed=scores["speed"],
        scores=scores,
        findings=findings,
        pass_status=pass_status,
    )
