"""Wiki maintenance metadata for Browse wiki cards."""

import json
from datetime import datetime, timezone
from pathlib import Path

from .index_common import _metadata_text

_WEAK_WIKI_BATCH_EXTENSIONS = {
    ".gif",
    ".heic",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp3",
    ".mp4",
    ".png",
    ".svg",
    ".webp",
}
_WEAK_WIKI_BATCH_PATH_MARKERS = (
    "/apple/reminders/",
    "/config/",
    "/workflow",
    "/workflows/",
    "/notifications/",
    "/private/config/",
)


def _wiki_status_payload_for_browse() -> dict:
    """Return the existing wiki-status helper payload for Browse decoration."""
    try:
        from skills.wiki.scripts.wiki_status import build_wiki_status
    except Exception as exc:
        return {"error": f"wiki-status unavailable: {exc}"}

    try:
        payload = build_wiki_status()
    except Exception as exc:
        return {"error": f"wiki-status failed: {exc}"}
    return payload if isinstance(payload, dict) else {}


def _wiki_batch_sources(payload: dict) -> list[dict]:
    items = payload.get("items")
    if not isinstance(items, list):
        return []

    sources: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cluster_sources = item.get("cluster_sources")
        if isinstance(cluster_sources, list):
            sources.extend(source for source in cluster_sources if isinstance(source, dict))
            continue
        sources.append(item)
    return sources


def _wiki_batch_source_is_weak(source: dict) -> bool:
    source_path = str(source.get("source_path") or source.get("path") or "").replace("\\", "/").lower()
    title = str(source.get("title") or source.get("name") or "").strip().lower()
    suffix = Path(source_path).suffix.lower()
    if suffix in _WEAK_WIKI_BATCH_EXTENSIONS:
        return True
    if title == "unsectioned" or source_path.endswith("/unsectioned.md"):
        return True
    return any(marker in source_path for marker in _WEAK_WIKI_BATCH_PATH_MARKERS)


def _wiki_batch_quality_for_browse(status_payload: dict) -> dict[str, str]:
    """Summarize latest wiki-update batch quality for Browse status badges."""
    batches = status_payload.get("batches")
    if not isinstance(batches, dict):
        return {}
    last_batch = batches.get("last_batch")
    if not last_batch:
        return {}

    try:
        payload = json.loads(Path(str(last_batch)).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    sources = _wiki_batch_sources(payload)
    source_count = len(sources)
    if source_count == 0:
        return {}

    weak_count = sum(1 for source in sources if _wiki_batch_source_is_weak(source))
    if weak_count * 2 >= source_count:
        return {
            "quality": "weak",
            "reason": (
                f"{weak_count}/{source_count} low-signal sources; "
                "reindex refreshed Browse but no wiki pages were applied."
            ),
            "item_count": str(source_count),
            "weak_count": str(weak_count),
        }

    return {
        "quality": "review",
        "reason": f"{source_count} sources prepared for agent extraction review.",
        "item_count": str(source_count),
        "weak_count": str(weak_count),
    }


def _wiki_maintenance_metadata(last_indexed: str | None) -> dict[str, str]:
    status_payload = _wiki_status_payload_for_browse()
    if not status_payload:
        return {}

    compiler = status_payload.get("compiler") if isinstance(status_payload.get("compiler"), dict) else {}
    batches = status_payload.get("batches") if isinstance(status_payload.get("batches"), dict) else {}
    index = status_payload.get("index") if isinstance(status_payload.get("index"), dict) else {}
    quality = _wiki_batch_quality_for_browse(status_payload)
    pending_sources = str(compiler.get("sources_pending_or_changed") or "0")

    state = "current"
    if status_payload.get("error"):
        state = "status-error"
    elif quality.get("quality") == "weak" and pending_sources != "0":
        state = "no-apply"
    elif pending_sources != "0":
        state = "pending"
    elif status_payload.get("healthy") is False:
        state = str(status_payload.get("verdict") or "review")

    metadata: dict[str, str] = {
        "wikiMaintenanceState": state,
        "wikiMaintenanceCheckedAt": datetime.now(timezone.utc).isoformat(),
    }
    for key, raw_value in (
        ("wikiMaintenanceVerdict", status_payload.get("verdict")),
        ("wikiMaintenanceError", status_payload.get("error")),
        ("wikiPendingSources", pending_sources),
        ("wikiSourceTotal", compiler.get("sources_total")),
        ("wikiLastReindexedAt", last_indexed),
        ("wikiRagEntries", index.get("wiki_rag_entries")),
        ("wikiLastBatchPath", batches.get("last_batch")),
        ("wikiLastBatchHandle", batches.get("last_batch_handle")),
        ("wikiLastBatchCreated", batches.get("last_batch_created")),
        ("wikiLastBatchMode", batches.get("last_batch_mode")),
        ("wikiLastBatchQuality", quality.get("quality")),
        ("wikiLastBatchReason", quality.get("reason")),
        ("wikiLastBatchItemCount", quality.get("item_count")),
        ("wikiLastBatchWeakCount", quality.get("weak_count")),
    ):
        value = _metadata_text(raw_value)
        if value:
            metadata[key] = value
    return metadata
