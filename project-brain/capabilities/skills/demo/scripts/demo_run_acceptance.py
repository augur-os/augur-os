from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal

from src.config.paths import get_vault_dir
from src.lib.frontmatter_utils import parse_frontmatter, write_vault_frontmatter

from src.lib.ingest.meeting_memory import build_meeting_memory

DemoStatus = Literal["pass", "fail", "blocked", "reset"]
EvalRunner = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class DemoCase:
    case_id: str
    title: str
    live_flow: str
    acceptance_criteria: tuple[str, ...]


@dataclass(frozen=True)
class DemoEvidence:
    path: Path
    case_id: str
    command: str
    status: DemoStatus
    command_status: DemoStatus | None
    backend: str
    client: str | None
    duration_seconds: float | None
    output_path: Path | None
    failure_reason: str | None
    missing_prerequisite: str | None
    eval_link: str | None
    eval_run_id: str | None
    eval_status: str | None
    eval_error: str | None
    eval_success: bool | None
    partial: bool
    source_title: str
    source_file: Path
    useful_snippet: str
    route_mode: str | None
    route_engine_id: str | None
    fallback_engine_id: str | None
    cloud_used: bool | None
    needs_review: bool | None
    route_note: str | None


DEFAULT_CASES: tuple[DemoCase, ...] = (
    DemoCase(
        case_id="meeting-transcript",
        title="Meeting Transcript",
        live_flow="Capture a real meeting transcript and keep the result visible through Browse.",
        acceptance_criteria=(
            "The source card names the transcript file.",
            "The card shows the backend used for extraction.",
            "Useful meeting decisions or actions are visible without leaving Browse.",
        ),
    ),
    DemoCase(
        case_id="deck-slide-critique",
        title="Deck Slide Critique",
        live_flow="Capture a real deck or slide critique and keep the result visible through Browse.",
        acceptance_criteria=(
            "The source card names the deck or slide file.",
            "The card shows the backend used for critique.",
            "A useful critique snippet is visible without leaving Browse.",
        ),
    ),
)

TRANSCRIPT_ARTIFACT_TYPES = {
    "workflow-example-transcript",
    "demo-transcript",
}


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _demo_dir(vault_dir: Path | None = None) -> Path:
    return (vault_dir or get_vault_dir()) / "notes" / "examples"


def _legacy_demo_dir(vault_dir: Path | None = None) -> Path:
    return (vault_dir or get_vault_dir()) / "notes" / "demo"


def _demo_artifact_dirs(vault_dir: Path | None = None) -> list[Path]:
    primary = _demo_dir(vault_dir)
    legacy = _legacy_demo_dir(vault_dir)
    return [primary] if primary == legacy else [primary, legacy]


def demo_run_note_path(vault_dir: Path | None = None) -> Path:
    return _demo_dir(vault_dir) / "workflow-example-run.md"


def _render_case(case: DemoCase) -> str:
    criteria = "\n".join(f"- {criterion}" for criterion in case.acceptance_criteria)
    return f"""### {case.title}

- Case ID: `{case.case_id}`
- Live flow: {case.live_flow}

Acceptance criteria:
{criteria}
"""


def _render_note(
    state: DemoStatus | Literal["ready"] = "ready",
    reset_reason: str | None = None,
) -> str:
    cases = "\n".join(_render_case(case) for case in DEFAULT_CASES)
    reason = f"\nReset reason: {reset_reason}\n" if reset_reason else ""
    return f"""# Workflow Example Run

Workflow example actions stay on real Browse cards.

Current rehearsal state: {state}
{reason}
## Live Flow

Each workflow example writes a real vault artifact under `notes/examples/` so Browse can show the result as an ordinary file card.

## Criteria

{cases}"""


def _note_metadata() -> dict[str, object]:
    return {
        "title": "Workflow Example Run",
        "type": "workflow-example-acceptance",
        "pinned": True,
        "demo_cases": [case.case_id for case in DEFAULT_CASES],
        "x-augur-note-type": "file",
        "_source_type": "workflow-example-acceptance",
        "tags": ["example", "workflow-example", "acceptance"],
    }


def ensure_demo_run_note(vault_dir: Path | None = None) -> Path:
    path = demo_run_note_path(vault_dir)
    if not path.exists():
        write_vault_frontmatter(path, _note_metadata(), _render_note())
    return path


def reset_demo_run_state(
    reason: str,
    vault_dir: Path | None = None,
) -> Path:
    path = demo_run_note_path(vault_dir)
    write_vault_frontmatter(
        path,
        _note_metadata(),
        _render_note(state="reset", reset_reason=reason),
    )
    return path


def _safe_fragment(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return safe or "workflow-example-command"


def _unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    for index in range(2, 10_000):
        candidate = target.with_name(f"{target.stem}-{index}{target.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(
        f"Could not find available workflow example evidence path for {target}"
    )


def _unlink_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _cleanup_transcript_case_artifacts(
    *,
    source_path: Path,
    vault_dir: Path | None = None,
) -> None:
    root = _demo_dir(vault_dir)
    safe_stem = _safe_fragment(source_path.stem)
    transcript_dir = root / "transcripts"
    evidence_dir = root / "evidence"
    transcript_paths = {
        path
        for path in transcript_dir.glob(f"{safe_stem}-*.md")
        if path.is_file()
    }
    transcript_path_text = {str(path) for path in transcript_paths}
    source_path_text = str(source_path)

    for evidence_path in evidence_dir.glob("meeting-transcript-*.md"):
        if not evidence_path.is_file():
            continue
        try:
            metadata, _body = parse_frontmatter(evidence_path)
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if (
            metadata.get("source_file_path") == source_path_text
            or metadata.get("output_path") in transcript_path_text
        ):
            _unlink_if_exists(evidence_path)

    for transcript_path in transcript_paths:
        _unlink_if_exists(transcript_path)


def _case_for(case_id: str) -> DemoCase:
    for case in DEFAULT_CASES:
        if case.case_id == case_id:
            return case
    raise ValueError(f"Unknown demo case: {case_id}")


def _duration_ms(duration_seconds: float | None) -> int | None:
    if duration_seconds is None:
        return None
    return int(round(float(duration_seconds) * 1000))


def _default_eval_runner(**kwargs: Any) -> dict[str, Any]:
    from skills.evals.scripts.eval_ops import run_demo_case_eval

    return run_demo_case_eval(**kwargs)


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _bool_or_none(value: object) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _bool_route_text(value: bool | None) -> str:
    return str(value).lower() if value is not None else "unknown"


def _presentation_language(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        original = match.group(0)
        replacement = (
            "workflow examples" if original.lower().endswith("s") else "workflow example"
        )
        return replacement.capitalize() if original[:1].isupper() else replacement

    return re.sub(r"\bdemos?\b", replace, text)


def _route_note_for_result(
    result: Any,
    *,
    route_mode: str | None,
    route_engine_id: str | None,
) -> str | None:
    note = _string_or_none(getattr(result, "note", None))
    if note:
        return note
    if route_mode == "offline" and route_engine_id:
        return (
            f"Airplane mode ON: using local {route_engine_id}; "
            "cloud transcription disabled."
        )
    if route_mode == "regular" and route_engine_id:
        return (
            f"Airplane mode OFF: using {route_engine_id}; "
            "local Whisper is not the selected route."
        )
    return None


def _normalized_scores(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): score for key, score in value.items()}


def _normalized_findings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_presentation_language(str(item)) for item in value]


def _render_eval_section(
    *,
    eval_run_id: str | None,
    eval_link: str | None,
    eval_status: str | None,
    eval_error: str | None,
    eval_scores: dict[str, object],
    eval_findings: list[str],
) -> str:
    if not any(
        (eval_run_id, eval_link, eval_status, eval_error, eval_scores, eval_findings)
    ):
        return ""

    lines = ["", "## Workflow Example Eval", ""]
    if eval_status:
        lines.append(f"- Status: `{eval_status}`")
    if eval_run_id:
        lines.append(f"- Run ID: `{eval_run_id}`")
    if eval_link:
        lines.append(f"- Record: `{eval_link}`")
    if eval_error:
        lines.append(f"- Error: {eval_error}")
    if eval_scores:
        lines.extend(["", "Scores:", ""])
        lines.extend(f"- {key}: {value}" for key, value in eval_scores.items())
    if eval_findings:
        lines.extend(["", "Findings:", ""])
        lines.extend(f"- {finding}" for finding in eval_findings)
    return "\n".join(lines) + "\n"


def _render_evidence_body(
    *,
    case: DemoCase,
    command: str,
    status: DemoStatus,
    command_status: DemoStatus | None,
    backend: str,
    source_title: str,
    source_path: Path,
    snippet: str,
    client: str | None,
    duration_seconds: float | None,
    resolved_output_path: Path | None,
    failure_reason: str | None,
    missing_prerequisite: str | None,
    eval_link: str | None,
    eval_run_id: str | None,
    eval_status: str | None,
    eval_error: str | None,
    eval_scores: dict[str, object],
    eval_findings: list[str],
    route_mode: str | None = None,
    route_engine_id: str | None = None,
    fallback_engine_id: str | None = None,
    cloud_used: bool | None = None,
    needs_review: bool | None = None,
    route_note: str | None = None,
) -> str:
    duration_text = (
        f"{duration_seconds}s" if duration_seconds is not None else "unknown"
    )
    client_text = client or "None"
    output_text = str(resolved_output_path) if resolved_output_path else "None"
    command_status_line = ""
    if command_status is not None and command_status != status:
        command_status_line = f"- Command outcome: `{command_status}`\n"
    eval_section = _render_eval_section(
        eval_run_id=eval_run_id,
        eval_link=eval_link,
        eval_status=eval_status,
        eval_error=eval_error,
        eval_scores=eval_scores,
        eval_findings=eval_findings,
    )
    route_section = ""
    if any(
        value is not None
        for value in (
            route_mode,
            route_engine_id,
            fallback_engine_id,
            cloud_used,
            needs_review,
            route_note,
        )
    ):
        route_section = f"""
## Routing

- Mode: `{route_mode or "unknown"}`
- Selected engine: `{route_engine_id or "unknown"}`
- Fallback engine: `{fallback_engine_id or "none"}`
- Cloud used: `{_bool_route_text(cloud_used)}`
- Needs review: `{_bool_route_text(needs_review)}`
- Note: {route_note or "None"}
"""
    return f"""# Workflow Example Evidence: {case.title}

## Command

`{command}`

## Source

- File: `{source_path.name}`
- Title: `{source_title}`
- Source path: `{source_path}`
- Client: `{client_text}`
- Backend: `{backend}`
- Status: `{status}`
{command_status_line}- Duration: `{duration_text}`
- Output: `{output_text}`
- Failure reason: {failure_reason or "None"}
- Missing prerequisite: {missing_prerequisite or "None"}
- Eval: {eval_link or "None"}

{route_section}
## Useful Snippet

{snippet}
{eval_section}"""


def _eval_result_fields(evidence: DemoEvidence) -> dict[str, object]:
    fields: dict[str, object] = {}
    for key in ("eval_run_id", "eval_link", "eval_status", "eval_error"):
        value = getattr(evidence, key)
        if value is not None:
            fields[key] = value
    if evidence.eval_success is not None:
        fields["eval_success"] = evidence.eval_success
    if evidence.command_status is not None:
        fields["command_status"] = evidence.command_status
    if evidence.partial:
        fields["partial"] = True
    return fields


def _accepted_success(evidence: DemoEvidence) -> bool:
    return evidence.eval_success is not False


def _accepted_status(evidence: DemoEvidence) -> DemoStatus:
    return "fail" if evidence.eval_success is False else evidence.status


def write_demo_evidence(
    *,
    case_id: str,
    command: str,
    status: DemoStatus,
    backend: str,
    source_file: Path,
    useful_snippet: str,
    client: str | None = None,
    duration_seconds: float | None = None,
    output_path: Path | None = None,
    failure_reason: str | None = None,
    missing_prerequisite: str | None = None,
    eval_link: str | None = None,
    source_title: str | None = None,
    run_eval: bool = False,
    eval_runner: EvalRunner | None = None,
    vault_dir: Path | None = None,
    route_mode: str | None = None,
    route_engine_id: str | None = None,
    fallback_engine_id: str | None = None,
    cloud_used: bool | None = None,
    needs_review: bool | None = None,
    route_note: str | None = None,
) -> DemoEvidence:
    case = _case_for(case_id)
    source_path = Path(source_file)
    normalized_source_title = (source_title or "").strip() or source_path.name
    resolved_output_path = Path(output_path) if output_path is not None else None
    snippet = _presentation_language(
        useful_snippet.strip() or "No useful snippet was captured."
    )
    eval_run_id: str | None = None
    eval_status: str | None = None
    eval_error: str | None = None
    eval_success: bool | None = None
    route_partial = bool(needs_review or fallback_engine_id)
    partial = route_partial
    effective_status: DemoStatus = status
    command_status: DemoStatus | None = None
    eval_scores: dict[str, object] = {}
    eval_findings: list[str] = []
    path = _unique_path(
        _demo_dir(vault_dir)
        / "evidence"
        / f"{case_id}-{_safe_fragment(command)}-{_utc_stamp()}.md"
    )
    metadata = {
        "title": f"Workflow example evidence: {case.case_id}",
        "type": "workflow-example-evidence",
        "x-augur-note-type": "file",
        "_source_type": "workflow-example-evidence",
        "demo_case_id": case.case_id,
        "demo_command": command,
        "demo_status": effective_status,
        "command_status": command_status,
        "backend": backend,
        "client": client,
        "duration_seconds": duration_seconds,
        "output_path": str(resolved_output_path) if resolved_output_path else None,
        "failure_reason": failure_reason,
        "missing_prerequisite": missing_prerequisite,
        "eval_link": eval_link,
        "eval_run_id": eval_run_id,
        "eval_status": eval_status,
        "eval_error": eval_error,
        "eval_success": eval_success,
        "partial": True if partial else None,
        "source_title": normalized_source_title,
        "source_file_name": source_path.name,
        "source_file_path": str(source_path),
        "route_mode": route_mode,
        "route_engine_id": route_engine_id,
        "fallback_engine_id": fallback_engine_id,
        "cloud_used": cloud_used,
        "needs_review": needs_review,
        "route_note": route_note,
        "tags": ["example", "workflow-example-evidence", case.case_id],
    }
    body = _render_evidence_body(
        case=case,
        command=command,
        status=effective_status,
        command_status=command_status,
        backend=backend,
        source_title=normalized_source_title,
        source_path=source_path,
        snippet=snippet,
        client=client,
        duration_seconds=duration_seconds,
        resolved_output_path=resolved_output_path,
        failure_reason=failure_reason,
        missing_prerequisite=missing_prerequisite,
        eval_link=eval_link,
        eval_run_id=eval_run_id,
        eval_status=eval_status,
        eval_error=eval_error,
        eval_scores=eval_scores,
        eval_findings=eval_findings,
        route_mode=route_mode,
        route_engine_id=route_engine_id,
        fallback_engine_id=fallback_engine_id,
        cloud_used=cloud_used,
        needs_review=needs_review,
        route_note=route_note,
    )
    write_vault_frontmatter(path, metadata, body)

    if run_eval and status == "pass":
        runner = eval_runner or _default_eval_runner
        try:
            eval_result = runner(
                case_id=case.case_id,
                source_title=normalized_source_title,
                evidence_path=path,
                duration_ms=_duration_ms(duration_seconds),
                source_path=source_path,
            )
            eval_status = _string_or_none(eval_result.get("status"))
            eval_run_id = _string_or_none(eval_result.get("run_id"))
            eval_link = _string_or_none(eval_result.get("record_path")) or eval_link
            eval_scores = _normalized_scores(eval_result.get("scores"))
            eval_findings = _normalized_findings(eval_result.get("findings"))
            eval_success = eval_status == "pass"
            partial = route_partial or not eval_success
        except Exception as exc:  # noqa: BLE001 - record eval failure on the evidence card
            eval_status = "error"
            eval_error = str(exc)
            eval_success = False
            partial = True
            eval_findings = [f"Workflow example eval failed: {exc}"]

        if eval_success is False:
            effective_status = "fail"
            command_status = status

        metadata.update(
            {
                "demo_status": effective_status,
                "command_status": command_status,
                "eval_link": eval_link,
                "eval_run_id": eval_run_id,
                "eval_status": eval_status,
                "eval_error": eval_error,
                "eval_success": eval_success,
                "partial": True if partial else None,
            }
        )
        body = _render_evidence_body(
            case=case,
            command=command,
            status=effective_status,
            command_status=command_status,
            backend=backend,
            source_title=normalized_source_title,
            source_path=source_path,
            snippet=snippet,
            client=client,
            duration_seconds=duration_seconds,
            resolved_output_path=resolved_output_path,
            failure_reason=failure_reason,
            missing_prerequisite=missing_prerequisite,
            eval_link=eval_link,
            eval_run_id=eval_run_id,
            eval_status=eval_status,
            eval_error=eval_error,
            eval_scores=eval_scores,
            eval_findings=eval_findings,
            route_mode=route_mode,
            route_engine_id=route_engine_id,
            fallback_engine_id=fallback_engine_id,
            cloud_used=cloud_used,
            needs_review=needs_review,
            route_note=route_note,
        )
        write_vault_frontmatter(path, metadata, body)

    return DemoEvidence(
        path=path,
        case_id=case.case_id,
        command=command,
        status=effective_status,
        command_status=command_status,
        backend=backend,
        client=client,
        duration_seconds=duration_seconds,
        output_path=resolved_output_path,
        failure_reason=failure_reason,
        missing_prerequisite=missing_prerequisite,
        eval_link=eval_link,
        eval_run_id=eval_run_id,
        eval_status=eval_status,
        eval_error=eval_error,
        eval_success=eval_success,
        partial=partial,
        source_title=normalized_source_title,
        source_file=source_path,
        useful_snippet=snippet,
        route_mode=route_mode,
        route_engine_id=route_engine_id,
        fallback_engine_id=fallback_engine_id,
        cloud_used=cloud_used,
        needs_review=needs_review,
        route_note=route_note,
    )


def _default_transcribe(source_path: Path) -> Any:
    from src.lib.routing import transcribe

    return transcribe(str(source_path))


def _artifact_metadata(
    *,
    title: str,
    artifact_type: str,
    source_path: Path | None = None,
    transcript_path: Path | None = None,
    tags: list[str] | None = None,
    **extra: object,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "title": title,
        "type": artifact_type,
        "x-augur-note-type": "file",
        "_source_type": artifact_type,
        "tags": tags or ["example", "workflow-example", artifact_type],
    }
    if source_path is not None:
        metadata["source_file_name"] = source_path.name
        metadata["source_file_path"] = str(source_path)
    if transcript_path is not None:
        metadata["transcript_path"] = str(transcript_path)
    metadata.update(extra)
    return metadata


def _transcript_body(
    *,
    source_path: Path,
    transcript: str,
    method: str,
    backend: str,
    duration_seconds: float | None,
    media_duration_seconds: float | None = None,
    route_mode: str | None = None,
    route_engine_id: str | None = None,
    fallback_engine_id: str | None = None,
    cloud_used: bool | None = None,
    needs_review: bool | None = None,
    route_note: str | None = None,
) -> str:
    duration = duration_seconds if duration_seconds is not None else "unknown"
    media_duration = (
        media_duration_seconds if media_duration_seconds is not None else "unknown"
    )
    raw_transcript = transcript.strip()
    presentation_preview = _presentation_language(raw_transcript)
    return f"""# Transcript: {source_path.name}

- Source path: `{source_path}`
- Method: `{method}`
- Backend: `{backend}`
- Run duration seconds: `{duration}`
- Media duration seconds: `{media_duration}`

## Routing

- Mode: `{route_mode or "unknown"}`
- Selected engine: `{route_engine_id or "unknown"}`
- Fallback engine: `{fallback_engine_id or "none"}`
- Cloud used: `{_bool_route_text(cloud_used)}`
- Needs review: `{_bool_route_text(needs_review)}`
- Note: {route_note or "None"}

## Presentation Preview

{presentation_preview}

## Transcript

{raw_transcript}
"""


def _useful_snippet(text: str, limit: int = 260) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _display_source_title(source_title: str | None, fallback: Path) -> str:
    return (source_title or "").strip() or fallback.name


def _source_context_snippet(
    source_title: str,
    text: str,
    *,
    route_mode: str | None = None,
    route_engine_id: str | None = None,
    fallback_engine_id: str | None = None,
    cloud_used: bool | None = None,
    route_note: str | None = None,
    limit: int = 360,
) -> str:
    route_parts: list[str] = []
    if route_mode:
        route_parts.append(f"Route mode: {route_mode}.")
    if route_engine_id:
        route_parts.append(f"Selected engine: {route_engine_id}.")
    if fallback_engine_id:
        route_parts.append(f"Fallback engine: {fallback_engine_id}.")
    if cloud_used is not None:
        route_parts.append(f"Cloud used: {_bool_route_text(cloud_used)}.")
    if route_note:
        route_parts.append(route_note)
    combined = " ".join([*route_parts, text])
    snippet = _useful_snippet(combined, limit=limit)
    title = source_title.strip()
    if not title:
        return snippet
    return f"Source: {title}. {snippet}"


def run_transcript_case(
    source_path: Path,
    *,
    transcribe: Callable[[Path], Any] = _default_transcribe,
    source_title: str | None = None,
    run_eval: bool = False,
    eval_runner: EvalRunner | None = None,
    vault_dir: Path | None = None,
    replace_existing: bool = False,
) -> dict[str, object]:
    normalized_source_path = Path(source_path).expanduser()
    if not normalized_source_path.exists():
        missing = f"Source media is missing: {normalized_source_path}"
        evidence = write_demo_evidence(
            case_id="meeting-transcript",
            command="Transcript",
            status="blocked",
            backend="offline-transcription",
            source_file=normalized_source_path,
            source_title=source_title,
            useful_snippet=missing,
            failure_reason=missing,
            missing_prerequisite=(
                "Missing real local media file; provide one before running transcript."
            ),
            vault_dir=vault_dir,
        )
        return {
            "success": False,
            "status": "blocked",
            "source_path": str(normalized_source_path),
            "evidence_path": str(evidence.path),
            "failure_reason": missing,
            "missing_prerequisite": evidence.missing_prerequisite,
        }

    started_at = time.perf_counter()
    try:
        result = transcribe(normalized_source_path)
    except Exception as exc:
        duration_seconds = time.perf_counter() - started_at
        failure = str(exc)
        evidence = write_demo_evidence(
            case_id="meeting-transcript",
            command="Transcript",
            status="fail",
            backend="offline-transcription",
            duration_seconds=duration_seconds,
            source_file=normalized_source_path,
            source_title=source_title,
            useful_snippet=f"Transcription failed: {failure}",
            failure_reason=failure,
            missing_prerequisite="Offline transcription route must be configured and runnable.",
            vault_dir=vault_dir,
        )
        return {
            "success": False,
            "status": "fail",
            "source_path": str(normalized_source_path),
            "evidence_path": str(evidence.path),
            "duration_seconds": duration_seconds,
            "failure_reason": failure,
            "missing_prerequisite": evidence.missing_prerequisite,
        }

    backend = str(getattr(result, "backend", "") or "offline-transcription")
    method = str(getattr(result, "method", "") or "offline")
    route_mode = _string_or_none(getattr(result, "route_mode", None))
    route_engine_id = _string_or_none(getattr(result, "route_engine_id", None))
    fallback_engine_id = _string_or_none(getattr(result, "fallback_engine_id", None))
    cloud_used = _bool_or_none(getattr(result, "cloud_used", None))
    needs_review = _bool_or_none(getattr(result, "needs_review", None))
    route_note = _route_note_for_result(
        result,
        route_mode=route_mode,
        route_engine_id=route_engine_id,
    )
    duration_seconds = time.perf_counter() - started_at
    media_duration_seconds = getattr(result, "duration_s", None)
    transcript = str(getattr(result, "transcript", "") or "")
    if not bool(getattr(result, "success", False)) or not transcript.strip():
        failure = str(
            getattr(result, "error", "")
            or "Offline transcription produced no transcript."
        )
        evidence = write_demo_evidence(
            case_id="meeting-transcript",
            command="Transcript",
            status="blocked",
            backend=backend,
            duration_seconds=duration_seconds,
            source_file=normalized_source_path,
            source_title=source_title,
            useful_snippet=f"Transcription blocked: {failure}",
            failure_reason=failure,
            missing_prerequisite=(
                "Offline transcription backend must be available for this media file."
            ),
            vault_dir=vault_dir,
            route_mode=route_mode,
            route_engine_id=route_engine_id,
            fallback_engine_id=fallback_engine_id,
            cloud_used=cloud_used,
            needs_review=needs_review,
            route_note=route_note,
        )
        return {
            "success": False,
            "status": "blocked",
            "source_path": str(normalized_source_path),
            "evidence_path": str(evidence.path),
            "backend": backend,
            "method": method,
            "duration_seconds": duration_seconds,
            "media_duration_seconds": media_duration_seconds,
            "failure_reason": failure,
            "missing_prerequisite": evidence.missing_prerequisite,
            "route_mode": route_mode,
            "route_engine_id": route_engine_id,
            "fallback_engine_id": fallback_engine_id,
            "cloud_used": cloud_used,
            "needs_review": needs_review,
            "route_note": route_note,
        }

    display_title = _display_source_title(source_title, normalized_source_path)
    if replace_existing:
        _cleanup_transcript_case_artifacts(
            source_path=normalized_source_path,
            vault_dir=vault_dir,
        )
    transcript_path = _unique_path(
        _demo_dir(vault_dir)
        / "transcripts"
        / f"{_safe_fragment(normalized_source_path.stem)}-{_utc_stamp()}.md"
    )
    write_vault_frontmatter(
        transcript_path,
        _artifact_metadata(
            title=f"{display_title} Transcript",
            artifact_type="workflow-example-transcript",
            source_path=normalized_source_path,
            backend=backend,
            method=method,
            duration_seconds=duration_seconds,
            media_duration_seconds=media_duration_seconds,
            route_mode=route_mode,
            route_engine_id=route_engine_id,
            fallback_engine_id=fallback_engine_id,
            cloud_used=cloud_used,
            needs_review=needs_review,
            route_note=route_note,
            tags=["example", "workflow-example", "transcript", "meeting-transcript"],
        ),
        _transcript_body(
            source_path=normalized_source_path,
            transcript=transcript,
            method=method,
            backend=backend,
            duration_seconds=duration_seconds,
            media_duration_seconds=media_duration_seconds,
            route_mode=route_mode,
            route_engine_id=route_engine_id,
            fallback_engine_id=fallback_engine_id,
            cloud_used=cloud_used,
            needs_review=needs_review,
            route_note=route_note,
        ),
    )
    evidence = write_demo_evidence(
        case_id="meeting-transcript",
        command="Transcript",
        status="pass",
        backend=backend,
        duration_seconds=duration_seconds,
        output_path=transcript_path,
        source_file=normalized_source_path,
        source_title=display_title,
        useful_snippet=_source_context_snippet(
            display_title,
            transcript,
            route_mode=route_mode,
            route_engine_id=route_engine_id,
            fallback_engine_id=fallback_engine_id,
            cloud_used=cloud_used,
            route_note=route_note,
        ),
        run_eval=run_eval,
        eval_runner=eval_runner,
        vault_dir=vault_dir,
        route_mode=route_mode,
        route_engine_id=route_engine_id,
        fallback_engine_id=fallback_engine_id,
        cloud_used=cloud_used,
        needs_review=needs_review,
        route_note=route_note,
    )
    return {
        "success": _accepted_success(evidence),
        "status": _accepted_status(evidence),
        "source_path": str(normalized_source_path),
        "transcript_path": str(transcript_path),
        "evidence_path": str(evidence.path),
        "backend": backend,
        "method": method,
        "duration_seconds": duration_seconds,
        "media_duration_seconds": media_duration_seconds,
        "snippet": evidence.useful_snippet,
        "source_title": evidence.source_title,
        "route_mode": route_mode,
        "route_engine_id": route_engine_id,
        "fallback_engine_id": fallback_engine_id,
        "cloud_used": cloud_used,
        "needs_review": needs_review,
        "route_note": route_note,
        **_eval_result_fields(evidence),
    }


def _latest_transcript_for_source(
    *,
    source_path: Path | None,
    vault_dir: Path | None = None,
) -> Path | None:
    if source_path is None:
        return None
    normalized_source = str(Path(source_path).expanduser())
    candidates: list[Path] = []
    for root in _demo_artifact_dirs(vault_dir):
        transcript_dir = root / "transcripts"
        if not transcript_dir.is_dir():
            continue
        for transcript_path in transcript_dir.glob("*.md"):
            try:
                metadata, _ = parse_frontmatter(transcript_path)
            except (OSError, UnicodeDecodeError, ValueError):
                continue
            if metadata.get("type") not in TRANSCRIPT_ARTIFACT_TYPES:
                continue
            if str(metadata.get("source_file_path") or "") == normalized_source:
                candidates.append(transcript_path)
    return max(
        candidates, key=lambda path: (path.stat().st_mtime_ns, path.name), default=None
    )


def _resolve_transcript_path(
    *,
    source_path: Path | None,
    transcript_path: Path | None,
    vault_dir: Path | None = None,
) -> Path | None:
    if transcript_path is not None:
        normalized = Path(transcript_path).expanduser()
        return normalized if normalized.exists() else None
    return _latest_transcript_for_source(source_path=source_path, vault_dir=vault_dir)


def _blocked_transcript_evidence(
    *,
    command: str,
    source_path: Path | None,
    transcript_path: Path | None,
    failure_reason: str | None = None,
    missing_prerequisite: str,
    useful_snippet: str | None = None,
    vault_dir: Path | None,
) -> dict[str, object]:
    source_file = source_path or transcript_path or Path("missing-transcript.md")
    failure = failure_reason or missing_prerequisite
    evidence = write_demo_evidence(
        case_id="meeting-transcript",
        command=command,
        status="blocked",
        backend="local-transcript",
        source_file=source_file,
        useful_snippet=useful_snippet or failure,
        failure_reason=failure,
        missing_prerequisite=missing_prerequisite,
        vault_dir=vault_dir,
    )
    return {
        "success": False,
        "status": "blocked",
        "source_path": str(source_path) if source_path else None,
        "transcript_path": str(transcript_path) if transcript_path else None,
        "evidence_path": str(evidence.path),
        "failure_reason": failure,
        "missing_prerequisite": missing_prerequisite,
    }


def _load_valid_transcript(
    *,
    command: str,
    source_path: Path | None,
    transcript_path: Path,
    vault_dir: Path | None,
) -> tuple[dict[str, object], str] | dict[str, object]:
    try:
        metadata, body = parse_frontmatter(transcript_path)
    except (OSError, UnicodeDecodeError) as exc:
        failure = f"Could not read transcript `{transcript_path}`: {exc}"
        return _blocked_transcript_evidence(
            command=command,
            source_path=source_path,
            transcript_path=transcript_path,
            failure_reason=failure,
            missing_prerequisite=(
                "Provide a readable workflow-example-transcript artifact."
            ),
            vault_dir=vault_dir,
        )

    if metadata.get("type") not in TRANSCRIPT_ARTIFACT_TYPES:
        failure = (
            f"Transcript path `{transcript_path}` is not a workflow-example-transcript artifact."
        )
        return _blocked_transcript_evidence(
            command=command,
            source_path=source_path,
            transcript_path=transcript_path,
            failure_reason=failure,
            missing_prerequisite=(
                "Provide a transcript artifact with frontmatter type workflow-example-transcript."
            ),
            vault_dir=vault_dir,
        )

    metadata_source = metadata.get("source_file_path")
    if source_path is not None and not metadata_source:
        failure = (
            f"Transcript `{transcript_path}` has no source_file_path to match "
            f"`{source_path}`."
        )
        return _blocked_transcript_evidence(
            command=command,
            source_path=source_path,
            transcript_path=transcript_path,
            failure_reason=failure,
            missing_prerequisite=(
                "Provide a transcript linked to the requested media source."
            ),
            vault_dir=vault_dir,
        )
    if source_path is not None and str(metadata_source) != str(source_path):
        failure = (
            f"Transcript source `{metadata_source}` does not match requested "
            f"source `{source_path}`."
        )
        return _blocked_transcript_evidence(
            command=command,
            source_path=source_path,
            transcript_path=transcript_path,
            failure_reason=failure,
            missing_prerequisite=(
                "Provide a transcript artifact linked to the requested source_path."
            ),
            vault_dir=vault_dir,
        )

    return metadata, body


_TRANSCRIPT_CONTENT_PLACEHOLDERS = {
    "",
    "no transcript was captured",
    "no transcript text was captured",
    "none captured",
}


def _transcript_content_for_meeting_memory(transcript_body: str) -> str:
    lines = transcript_body.splitlines()
    section_start: int | None = None
    for index, line in enumerate(lines):
        if line.strip().lower() == "## transcript":
            section_start = index + 1
            break
    content_lines = lines[section_start:] if section_start is not None else lines
    if section_start is not None:
        for index, line in enumerate(content_lines):
            stripped = line.strip()
            if stripped.startswith("## "):
                content_lines = content_lines[:index]
                break

    cleaned: list[str] = []
    metadata_prefixes = (
        "- source path:",
        "- method:",
        "- backend:",
        "- duration seconds:",
        "source path:",
        "method:",
        "backend:",
        "duration seconds:",
    )
    for line in content_lines:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        lowered = text.lower()
        if lowered.startswith(metadata_prefixes):
            continue
        normalized = text.strip(" -`").rstrip(".").lower()
        if normalized in _TRANSCRIPT_CONTENT_PLACEHOLDERS:
            continue
        cleaned.append(text)
    return "\n".join(cleaned).strip()


def _meeting_memory_to_markdown(
    memory: dict[str, list[str] | str],
    *,
    transcript_path: Path,
) -> str:
    summary = str(memory.get("summary") or "No transcript summary was captured.")
    decisions = memory.get("decisions") or []
    next_actions = memory.get("next_actions") or []
    decision_lines = "\n".join(f"- {item}" for item in decisions) or "- None captured."
    action_lines = "\n".join(f"- {item}" for item in next_actions) or "- None captured."
    return f"""# Meeting Memory

Source transcript: `{transcript_path}`

## Summary

{summary}

## Decisions

{decision_lines}

## Action Items

{action_lines}
"""


_MEETING_MEMORY_PLACEHOLDERS = {
    "",
    "no transcript summary was captured",
    "none captured",
}


def _real_meeting_memory_text(value: object) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    normalized = text.strip(" -").rstrip(".").lower()
    if normalized in _MEETING_MEMORY_PLACEHOLDERS:
        return None
    return text or None


def _real_meeting_memory_items(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        text for item in value if (text := _real_meeting_memory_text(item)) is not None
    ]


def _meeting_memory_score_text(memory: dict[str, list[str] | str]) -> str:
    parts: list[str] = []
    summary = _real_meeting_memory_text(memory.get("summary"))
    if summary is not None:
        parts.append(summary)
    parts.extend(_real_meeting_memory_items(memory.get("decisions")))
    parts.extend(_real_meeting_memory_items(memory.get("next_actions")))
    return " ".join(parts) or "No meeting memory content was captured."


def run_meeting_memory_case(
    source_path: Path | None = None,
    transcript_path: Path | None = None,
    *,
    source_title: str | None = None,
    run_eval: bool = False,
    eval_runner: EvalRunner | None = None,
    vault_dir: Path | None = None,
) -> dict[str, object]:
    normalized_source_path = Path(source_path).expanduser() if source_path else None
    normalized_transcript_path = (
        Path(transcript_path).expanduser() if transcript_path else None
    )
    resolved_transcript = _resolve_transcript_path(
        source_path=normalized_source_path,
        transcript_path=normalized_transcript_path,
        vault_dir=vault_dir,
    )
    if resolved_transcript is None:
        return _blocked_transcript_evidence(
            command="Meeting Memory",
            source_path=normalized_source_path,
            transcript_path=normalized_transcript_path,
            missing_prerequisite=(
                "Run the transcript workflow example first or provide an existing transcript_path."
            ),
            vault_dir=vault_dir,
        )

    parsed = _load_valid_transcript(
        command="Meeting Memory",
        source_path=normalized_source_path,
        transcript_path=resolved_transcript,
        vault_dir=vault_dir,
    )
    if isinstance(parsed, dict):
        return parsed
    transcript_metadata, transcript_body = parsed
    if normalized_source_path is None and transcript_metadata.get("source_file_path"):
        normalized_source_path = Path(str(transcript_metadata["source_file_path"]))
    memory = build_meeting_memory(
        _transcript_content_for_meeting_memory(transcript_body)
    )
    memory_path = _unique_path(
        _demo_dir(vault_dir)
        / "meeting-memory"
        / (
            f"{_safe_fragment((normalized_source_path or resolved_transcript).stem)}"
            f"-{_utc_stamp()}.md"
        )
    )
    body = _meeting_memory_to_markdown(memory, transcript_path=resolved_transcript)
    source_file = normalized_source_path or resolved_transcript
    display_title = _display_source_title(source_title, source_file)
    write_vault_frontmatter(
        memory_path,
        _artifact_metadata(
            title=f"Meeting Memory: {source_file.name}",
            artifact_type="workflow-example-meeting-memory",
            source_path=normalized_source_path,
            transcript_path=resolved_transcript,
            tags=[
                "example",
                "workflow-example",
                "meeting-memory",
                "meeting-transcript",
            ],
        ),
        body,
    )
    evidence = write_demo_evidence(
        case_id="meeting-transcript",
        command="Meeting Memory",
        status="pass",
        backend="local-meeting-memory",
        output_path=memory_path,
        source_file=source_file,
        source_title=display_title,
        useful_snippet=_source_context_snippet(
            display_title,
            _meeting_memory_score_text(memory),
        ),
        run_eval=run_eval,
        eval_runner=eval_runner,
        vault_dir=vault_dir,
    )
    return {
        "success": _accepted_success(evidence),
        "status": _accepted_status(evidence),
        "source_path": str(normalized_source_path) if normalized_source_path else None,
        "transcript_path": str(resolved_transcript),
        "memory_path": str(memory_path),
        "evidence_path": str(evidence.path),
        "summary": memory.get("summary"),
        "decisions": memory.get("decisions"),
        "next_actions": memory.get("next_actions"),
        "source_title": evidence.source_title,
        **_eval_result_fields(evidence),
    }


def _question_tokens(question: str) -> set[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "from",
        "key",
        "of",
        "the",
        "to",
        "was",
        "were",
        "what",
    }
    tokens = {
        token
        for token in re.findall(r"[a-zA-Z0-9]{3,}", question.lower())
        if token not in stopwords
    }
    tokens.update(token[:-1] for token in list(tokens) if token.endswith("s"))
    return tokens


def _transcript_answer(transcript_text: str, question: str) -> str:
    tokens = _question_tokens(question)
    lines = [
        line.strip(" -")
        for line in re.split(r"(?<=[.!?])\s+|\n+", transcript_text)
        if line.strip(" -")
    ]
    useful_lines = [line for line in lines if not line.startswith("#")]
    if not tokens:
        selected = useful_lines[:4]
        return " ".join(selected).strip() or "No useful transcript text was available."
    matches = [
        line
        for line in useful_lines
        if tokens.intersection(re.findall(r"[a-zA-Z0-9]+", line.lower()))
    ]
    if not matches:
        return ""
    return " ".join(matches[:4]).strip()


def run_ask_transcript_case(
    source_path: Path | None = None,
    transcript_path: Path | None = None,
    question: str = "What are the key decisions and actions?",
    *,
    source_title: str | None = None,
    run_eval: bool = False,
    eval_runner: EvalRunner | None = None,
    vault_dir: Path | None = None,
) -> dict[str, object]:
    normalized_source_path = Path(source_path).expanduser() if source_path else None
    normalized_transcript_path = (
        Path(transcript_path).expanduser() if transcript_path else None
    )
    resolved_transcript = _resolve_transcript_path(
        source_path=normalized_source_path,
        transcript_path=normalized_transcript_path,
        vault_dir=vault_dir,
    )
    if resolved_transcript is None:
        return _blocked_transcript_evidence(
            command="Ask From Transcript",
            source_path=normalized_source_path,
            transcript_path=normalized_transcript_path,
            missing_prerequisite=(
                "Run the transcript workflow example first or provide an existing transcript_path."
            ),
            vault_dir=vault_dir,
        )

    parsed = _load_valid_transcript(
        command="Ask From Transcript",
        source_path=normalized_source_path,
        transcript_path=resolved_transcript,
        vault_dir=vault_dir,
    )
    if isinstance(parsed, dict):
        return parsed
    transcript_metadata, transcript_body = parsed
    if normalized_source_path is None and transcript_metadata.get("source_file_path"):
        normalized_source_path = Path(str(transcript_metadata["source_file_path"]))
    normalized_question = question.strip() or "What are the key decisions and actions?"
    answer = _transcript_answer(transcript_body, normalized_question)
    if not answer:
        snippet = _useful_snippet(transcript_body)
        return _blocked_transcript_evidence(
            command="Ask From Transcript",
            source_path=normalized_source_path,
            transcript_path=resolved_transcript,
            failure_reason=(
                f"No transcript evidence matched question `{normalized_question}` "
                f"in `{resolved_transcript}`."
            ),
            missing_prerequisite=(
                "Ask a question with terms present as whole words in the transcript."
            ),
            useful_snippet=(
                "No transcript evidence matched the question.\n\n"
                f"Transcript snippet: {snippet}"
            ),
            vault_dir=vault_dir,
        )
    answer_path = _unique_path(
        _demo_dir(vault_dir)
        / "transcript-answers"
        / (
            f"{_safe_fragment((normalized_source_path or resolved_transcript).stem)}"
            f"-{_utc_stamp()}.md"
        )
    )
    body = f"""# Ask From Transcript

Source transcript: `{resolved_transcript}`

## Question

{normalized_question}

## Answer

{answer}
"""
    source_file = normalized_source_path or resolved_transcript
    display_title = _display_source_title(source_title, source_file)
    write_vault_frontmatter(
        answer_path,
        _artifact_metadata(
            title=f"Ask From Transcript: {source_file.name}",
            artifact_type="workflow-example-transcript-answer",
            source_path=normalized_source_path,
            transcript_path=resolved_transcript,
            question=normalized_question,
            tags=[
                "example",
                "workflow-example",
                "transcript-answer",
                "meeting-transcript",
            ],
        ),
        body,
    )
    evidence = write_demo_evidence(
        case_id="meeting-transcript",
        command="Ask From Transcript",
        status="pass",
        backend="local-transcript-retrieval",
        output_path=answer_path,
        source_file=source_file,
        source_title=display_title,
        useful_snippet=_source_context_snippet(display_title, answer),
        run_eval=run_eval,
        eval_runner=eval_runner,
        vault_dir=vault_dir,
    )
    return {
        "success": _accepted_success(evidence),
        "status": _accepted_status(evidence),
        "source_path": str(normalized_source_path) if normalized_source_path else None,
        "transcript_path": str(resolved_transcript),
        "answer_path": str(answer_path),
        "evidence_path": str(evidence.path),
        "question": normalized_question,
        "answer": answer,
        "source_title": evidence.source_title,
        **_eval_result_fields(evidence),
    }
