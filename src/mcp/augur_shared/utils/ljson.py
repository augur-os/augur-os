"""
LJSON (Line JSON) Utility Module.

Provides robust functions for append-only JSON logging and reading.
Implements the pattern: prefix with newline to handle partial writes/truncation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.mcp.augur_shared.logging import get_entity_logger

logger = get_entity_logger("ljson")


def append(path: str | Path, data: dict[str, Any]) -> bool:
    """Append a dictionary as a JSON line to a file."""
    try:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        json_str = json.dumps(data, default=str)

        prefix = ""
        if file_path.exists() and file_path.stat().st_size > 0:
            prefix = "\n"

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"{prefix}{json_str}")

        return True
    except Exception as exc:
        logger.error(f"Failed to append to {path}: {exc}")
        return False


def read(path: str | Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Read JSON lines from a file, skipping malformed rows."""
    results: list[dict[str, Any]] = []
    file_path = Path(path)

    if not file_path.exists():
        return results

    try:
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    if line.endswith(","):
                        line = line[:-1]

                    parsed = json.loads(line)
                    results.append(parsed)
                except json.JSONDecodeError:
                    continue

                if limit is not None and len(results) >= limit:
                    break

    except Exception as exc:
        logger.error(f"Failed to read from {path}: {exc}")

    return results


def tail(path: str | Path, lines: int = 100) -> list[dict[str, Any]]:
    """Read the last N valid JSON lines from a file."""
    data = read(path)
    return data[-lines:] if lines > 0 else []
