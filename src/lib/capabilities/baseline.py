"""Deterministic capability baseline snapshot for diffing across runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .exposure_policy import CapabilityRecord


def build_baseline(records: list[CapabilityRecord]) -> dict[str, Any]:
    """Return a deterministic JSON-serializable snapshot of resolved records."""
    sorted_records = sorted(records, key=lambda record: record.id)
    return {
        "version": 1,
        "records": [
            {
                "id": record.id,
                "type": record.type,
                "owner_kind": record.owner_kind,
                "management": record.management,
                "classification_status": record.classification_status,
                "primary_surface": record.primary_surface,
                "preferred_client": record.preferred_client,
                "current_exposure": list(record.current_exposure),
                "export_to": list(record.export_to),
                "drift": list(record.drift),
            }
            for record in sorted_records
        ],
    }


def write_baseline(path: Path, snapshot: dict[str, Any]) -> None:
    """Write a baseline snapshot to ``path`` as deterministic JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_baseline(path: Path) -> dict[str, Any]:
    """Read a baseline snapshot back into a dict."""
    return json.loads(path.read_text(encoding="utf-8"))
