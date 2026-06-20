from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from src.config.paths import get_pending_enrichment_queue_path
from src.lib.brain_layout import brain_capture_dir
from src.lib.frontmatter_utils import write_vault_frontmatter

from src.lib.ingest.inbox_routing import RouteDecision
from src.lib.ingest.meeting_memory import build_meeting_memory
from src.lib.ingest.pending_enrichment_queue import enqueue


def _unique_card_path(target: Path) -> Path:
    if not target.exists():
        return target
    for index in range(2, 10_000):
        candidate = target.with_name(f"{target.stem}-{index}{target.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find available source card path for {target}")


def _format_summary_callout(body: str) -> str:
    summary = body[:800] or "No readable summary was captured."
    return "\n".join(f"> {line}" if line else ">" for line in summary.splitlines())


def _compute_content_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def write_source_card(
    *,
    vault_dir: Path,
    title: str,
    body: str,
    decision: RouteDecision,
    original_path: str,
    final_path: str | None,
    extracted_path: str | None,
    extraction_method: str,
    hardware_backend: str,
    confidence: str,
    content_type: str,
    escalation_reason: str | None = None,
    cloud_used: bool = False,
    cloud_provider: str | None = None,
    cloud_model: str | None = None,
    content_hash: str | None = None,
) -> Path:
    target = _unique_card_path(brain_capture_dir(vault_dir) / f"{Path(decision.filename).stem}.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    summary_callout = _format_summary_callout(body)

    metadata = {
        "title": title,
        "source_type": "file",
        "x-augur-note-type": "file",
        "x-augur-note-source": decision.route,
        "content_type": content_type,
        "original_path": original_path,
        "final_path": final_path,
        "extracted_path": extracted_path,
        "extraction_method": extraction_method,
        "hardware_backend": hardware_backend,
        "confidence": confidence,
        "cloud_used": cloud_used,
        "cloud_provider": cloud_provider,
        "cloud_model": cloud_model,
        "escalation_reason": escalation_reason,
        "route": decision.route,
        "tags": ["inbox", decision.route.replace("/", "-")],
        "_source_type": "inbox-file",
    }
    metadata["content_hash"] = content_hash or _compute_content_hash(
        {
            "title": title,
            "body": body,
            "route": decision.route,
            "filename": decision.filename,
            "reason": decision.reason,
            "original_path": original_path,
            "final_path": final_path,
            "extracted_path": extracted_path,
            "extraction_method": extraction_method,
            "hardware_backend": hardware_backend,
            "confidence": confidence,
            "cloud_used": cloud_used,
            "cloud_provider": cloud_provider,
            "cloud_model": cloud_model,
            "escalation_reason": escalation_reason,
            "content_type": content_type,
            "summary_callout": summary_callout,
        }
    )
    meeting_section = ""
    if content_type == "audio":
        meeting = build_meeting_memory(body)
        actions = "\n".join(f"- [ ] {item}" for item in meeting["next_actions"])
        decisions = "\n".join(f"- {item}" for item in meeting["decisions"])
        meeting_section = f"""

## Meeting Memory

{meeting["summary"]}

### Decisions

{decisions or "- None detected"}

### Action Items

{actions or "- [ ] Review transcript for actions"}
"""

    card_body = f"""# {title}

> [!summary]
{summary_callout}

## Routing

- Destination: `{decision.route}`
- Reason: {decision.reason}
- Original: `{original_path}`
- Final: `{final_path or ''}`
- Extracted: `{extracted_path or ''}`

## Processing Evidence

- Method: `{extraction_method}`
- Backend: `{hardware_backend}`
- Confidence: `{confidence}`
- Cloud used: `{str(cloud_used).lower()}`
- Cloud provider: `{cloud_provider or ''}`
- Cloud model: `{cloud_model or ''}`
- Escalation reason: {escalation_reason or ''}
{meeting_section}
"""
    write_vault_frontmatter(target, metadata, card_body)

    try:
        enqueue(get_pending_enrichment_queue_path(), note_path=target, reason="new")
    except Exception:  # noqa: BLE001 — enrichment queue must never block note capture
        pass

    # ADR-738 — emit typed edges as part of the source-card write.
    try:
        import sys as _sys

        _graph_scripts = str(Path(__file__).resolve().parents[2] / "graph" / "scripts")
        if _graph_scripts not in _sys.path:
            _sys.path.insert(0, _graph_scripts)
        import graph_ops  # type: ignore[import-not-found]

        graph_ops.index_page_from_write_path(target, source_type="file")
    except Exception:  # noqa: BLE001 — graph is best-effort, never breaks ingest
        pass

    return target
