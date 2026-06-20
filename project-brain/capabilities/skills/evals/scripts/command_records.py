"""Command eval records: run envelopes, scorecards, and aggregate metrics."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_documents_dir, get_documents_machine_dir

COMMAND_RUN_SCHEMA = "command.run.v1"
COMMAND_SCORECARD_SCHEMA = "command.scorecard.v1"
REVIEW_DIMENSIONS = (
    "content_quality",
    "source_grounding",
    "ux_observability",
    "routing_correctness",
)
VALID_RATINGS = {"pass", "warn", "fail", "not_applicable"}
_ISO_DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:T.*)?$")
_SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
COUNT_SEMANTICS = {
    "pass_count": "cards with no warn/fail dimensions",
    "warn_count": "cards with at least one warn dimension",
    "fail_count": "cards with at least one fail dimension",
    "card_rollup": "mutually exclusive card severity",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def command_evals_root() -> Path:
    return get_documents_machine_dir("evals") / "commands"


def command_runs_dir() -> Path:
    return command_evals_root() / "runs"


def command_scorecards_dir() -> Path:
    return command_evals_root() / "scorecards"


def command_reports_dir() -> Path:
    return command_evals_root() / "reports"


def _day_from_started_at(started_at: str) -> str:
    if "/" in started_at or "\\" in started_at:
        raise ValueError("started_at must not contain path separators")
    match = _ISO_DATE_PREFIX_RE.match(started_at)
    if not match:
        raise ValueError("started_at must begin with an ISO date shaped YYYY-MM-DD")
    day = match.group(1)
    try:
        date.fromisoformat(day)
    except ValueError as exc:
        raise ValueError("started_at must contain a valid ISO date") from exc
    return day


def _validate_safe_run_id(run_id: str) -> str:
    if not run_id:
        raise ValueError("run_id must not be empty")
    if "/" in run_id or "\\" in run_id or ".." in run_id:
        raise ValueError("run_id must be a safe path component")
    if Path(run_id).is_absolute() or not _SAFE_RUN_ID_RE.fullmatch(run_id):
        raise ValueError("run_id must be a safe path component")
    return run_id


def _validate_private_write_root(root: Path) -> None:
    docs_root = get_documents_dir()
    docs_root_abs = docs_root.absolute()
    root_abs = root.absolute()
    try:
        relative_root = root_abs.relative_to(docs_root_abs)
    except ValueError as exc:
        raise ValueError(f"refusing to write outside private root: {root}") from exc

    current = docs_root
    if current.is_symlink():
        raise ValueError(f"private write root contains symlink: {current}")
    for part in relative_root.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"private write root contains symlink: {current}")


def _private_child_path(root: Path, filename: str) -> Path:
    if Path(filename).is_absolute() or Path(filename).name != filename:
        raise ValueError("filename must be a safe path component")
    _validate_private_write_root(root)
    path = root / filename
    try:
        path.absolute().relative_to(root.absolute())
    except ValueError as exc:
        raise ValueError(f"refusing to write outside private root: {root}") from exc
    return path


def build_run_envelope(
    *,
    command: str,
    client: str,
    input_class: str,
    chosen_route: str,
    started_at: str | None = None,
    duration_ms: int = 0,
    phases: list[dict[str, Any]] | None = None,
    quality_flags: list[str] | None = None,
    warnings: list[str] | None = None,
    outputs: dict[str, Any] | None = None,
    requires_human_review: bool = True,
    private_artifact_refs: list[str] | None = None,
) -> dict[str, Any]:
    if not command.strip():
        raise ValueError("command is required")
    if not client.strip():
        raise ValueError("client is required")
    if not input_class.strip():
        raise ValueError("input_class is required")
    if not chosen_route.strip():
        raise ValueError("chosen_route is required")
    return {
        "_schema": COMMAND_RUN_SCHEMA,
        "command": command.strip().lstrip("/"),
        "client": client.strip(),
        "input_class": input_class.strip(),
        "chosen_route": chosen_route.strip(),
        "started_at": started_at or utc_now_iso(),
        "duration_ms": int(duration_ms),
        "phases": phases or [],
        "quality_flags": quality_flags or [],
        "warnings": warnings or [],
        "outputs": outputs or {},
        "requires_human_review": bool(requires_human_review),
        "private_artifact_refs": private_artifact_refs or [],
    }


def write_run_envelope(envelope: dict[str, Any], *, run_id: str | None = None) -> Path:
    if envelope.get("_schema") != COMMAND_RUN_SCHEMA:
        raise ValueError(f"expected {COMMAND_RUN_SCHEMA}")
    started = str(envelope.get("started_at") or utc_now_iso())
    day = _day_from_started_at(started)
    path = _private_child_path(command_runs_dir(), f"{day}.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(envelope)
    if run_id:
        row["run_id"] = run_id
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n")
    return path


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + 5 :]
    data = yaml.safe_load(raw) or {}
    return data if isinstance(data, dict) else {}, body.lstrip("\n")


def read_scorecard(path: Path) -> dict[str, Any]:
    frontmatter, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    if frontmatter.get("_schema") != COMMAND_SCORECARD_SCHEMA:
        raise ValueError(f"{path} is not a {COMMAND_SCORECARD_SCHEMA} file")
    scores = {
        key: str(frontmatter.get(key, "not_applicable")).strip().lower()
        for key in REVIEW_DIMENSIONS
    }
    invalid = {key: value for key, value in scores.items() if value not in VALID_RATINGS}
    if invalid:
        raise ValueError(f"invalid score ratings: {invalid}")
    return {
        "path": str(path),
        "run_id": str(frontmatter.get("run_id") or ""),
        "command": str(frontmatter.get("command") or ""),
        "reviewer": str(frontmatter.get("reviewer") or ""),
        "reviewed_at": str(frontmatter.get("reviewed_at") or ""),
        "scores": scores,
        "duration_rating": str(frontmatter.get("duration_rating") or ""),
        "notes": body,
    }


def read_scorecards(root: Path | None = None) -> list[dict[str, Any]]:
    score_root = root or command_scorecards_dir()
    if not score_root.exists():
        return []
    return [read_scorecard(path) for path in sorted(score_root.rglob("*.md"))]


def aggregate_scorecards(scorecards: list[dict[str, Any]]) -> dict[str, Any]:
    by_command: dict[str, dict[str, int]] = {}
    card_rollup = {"pass": 0, "warn": 0, "fail": 0}
    dimension_counts = {rating: 0 for rating in sorted(VALID_RATINGS)}
    pass_count = 0
    warn_count = 0
    fail_count = 0
    for card in scorecards:
        command = card.get("command") or "unknown"
        bucket = by_command.setdefault(str(command), {"total": 0, "pass": 0, "warn": 0, "fail": 0})
        bucket["total"] += 1
        scores = card.get("scores") or {}
        values = {str(value).strip().lower() for value in scores.values()}
        for value in scores.values():
            rating = str(value).strip().lower()
            dimension_counts[rating] = dimension_counts.get(rating, 0) + 1
        has_fail = "fail" in values
        has_warn = "warn" in values
        if has_fail:
            fail_count += 1
            bucket["fail"] += 1
            card_rollup["fail"] += 1
        if has_warn:
            warn_count += 1
            bucket["warn"] += 1
        if not has_fail and not has_warn:
            pass_count += 1
            bucket["pass"] += 1
            card_rollup["pass"] += 1
        elif has_warn and not has_fail:
            card_rollup["warn"] += 1
    total = len(scorecards)
    return {
        "_schema": "command.aggregate.v1",
        "total": total,
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "pass_rate": (pass_count / total) if total else 0.0,
        "count_semantics": COUNT_SEMANTICS,
        "card_rollup": card_rollup,
        "dimension_counts": dimension_counts,
        "by_command": by_command,
    }


def write_aggregate_report(scorecards: list[dict[str, Any]], *, run_id: str | None = None) -> Path:
    run_id = run_id or utc_now_iso().replace(":", "-")
    run_id = _validate_safe_run_id(run_id)
    report = aggregate_scorecards(scorecards)
    path = _private_child_path(command_reports_dir(), f"{run_id}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return path
