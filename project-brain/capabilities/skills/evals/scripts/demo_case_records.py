"""Private record store for demo-case eval runs."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config.paths import get_documents_dir, get_documents_machine_dir

DEMO_CASE_EVAL_RECORD_SCHEMA = "demo_case.eval_record.v1"
_SAFE_COMPONENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class DemoCaseEvalRecord:
    run_id: str
    path: Path
    case_id: str
    scores: dict[str, int]


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _safe_slug(value: str, *, fallback: str) -> str:
    slug = _SAFE_COMPONENT_RE.sub("-", value.strip()).strip("._-")
    while ".." in slug:
        slug = slug.replace("..", ".")
    return slug or fallback


def _validate_private_write_root(root: Path) -> None:
    docs_root = Path(get_documents_dir())
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


def demo_case_eval_dir() -> Path:
    root = get_documents_machine_dir("evals") / "demo-runs"
    _validate_private_write_root(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _new_run_id(case_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    case_slug = _safe_slug(case_id, fallback="demo-case")
    return f"{case_slug}-{stamp}-{uuid.uuid4().hex[:8]}"


def write_demo_case_eval_record(
    *,
    case_id: str,
    evidence_path: Path,
    source_path: Path,
    scores: dict[str, int],
    findings: list[str],
) -> DemoCaseEvalRecord:
    if not case_id.strip():
        raise ValueError("case_id is required")

    root = demo_case_eval_dir()
    normalized_scores = {str(key): int(value) for key, value in scores.items()}
    normalized_findings = [str(finding) for finding in findings]

    for _ in range(20):
        run_id = _new_run_id(case_id)
        path = _private_child_path(root, f"{run_id}.json")
        payload: dict[str, Any] = {
            "_schema": DEMO_CASE_EVAL_RECORD_SCHEMA,
            "run_id": run_id,
            "case_id": case_id,
            "evidence_path": str(evidence_path),
            "source_path": str(source_path),
            "scores": normalized_scores,
            "findings": normalized_findings,
            "created_at": _utc_now_iso(),
        }
        try:
            with path.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
        except FileExistsError:
            continue
        return DemoCaseEvalRecord(
            run_id=run_id,
            path=path,
            case_id=case_id,
            scores=normalized_scores,
        )

    raise FileExistsError("unable to allocate a unique demo case eval run id")
