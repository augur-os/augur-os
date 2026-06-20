"""
LJSON (Line JSON) Utility Module.

Provides robust functions for append-only JSON logging and reading.
Implements the pattern: prefix with newline to handle partial writes/truncation gracefully.
"""

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.logging import get_entity_logger

logger = get_entity_logger("ljson")

# Thread-safe lock for file append operations
_append_lock = threading.Lock()


def append(path: Union[str, Path], data: Dict[str, Any]) -> bool:
    """
    Append a dictionary as a JSON line to a file.

    Uses a newline prefix strategy to ensure data integrity even if the
    previous write was interrupted (preventing mashed lines).

    Args:
        path: File path to append to.
        data: Dictionary to serialize and append.

    Returns:
        True if successful, False otherwise.
    """
    try:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        json_str = json.dumps(data, default=str)

        with _append_lock:
            # Only prepend newline if file exists and is not empty
            prefix = "\n"
            if not file_path.exists() or file_path.stat().st_size == 0:
                prefix = ""

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"{prefix}{json_str}")

        return True
    except Exception as e:
        logger.error(f"Failed to append to {path}: {e}")
        return False


def read(path: Union[str, Path], limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Read JSON lines from a file.

    Robustly handles empty lines and malformed lines (skips them).

    Args:
        path: File path to read from.
        limit: Max number of records to return (from the end if needed, but currently just total limit).
               Note: For huge files, a reverse reader would be better for 'tail',
               but standard read is fine for now.

    Returns:
        List of parsed dictionaries.
    """
    results: List[Dict[str, Any]] = []
    file_path = Path(path)

    if not file_path.exists():
        return results

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    # Handle potential trailing commas from manual edits
                    if line.endswith(","):
                        line = line[:-1]

                    parsed = json.loads(line)
                    results.append(parsed)
                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue

    except Exception as e:
        logger.error(f"Failed to read from {path}: {e}")

    return results


def tail(path: Union[str, Path], lines: int = 100) -> List[Dict[str, Any]]:
    """
    Read the last N valid JSON lines from a file.

    Args:
        path: File path.
        lines: Number of lines to return.

    Returns:
        List of dicts.
    """
    data = read(path)
    return data[-lines:] if lines > 0 else []
