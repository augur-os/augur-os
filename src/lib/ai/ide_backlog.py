"""IDE Backlog Manager - Saves instructions to filesystem for IDE access."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from src.config.paths import get_runtime_dir
except ImportError:
    # Fallback if paths module not available
    def get_runtime_dir() -> Path:
        import os

        state_dir = os.environ.get("AUGUR_STATE")
        if state_dir:
            return Path(state_dir)
        return Path.home() / "Library" / "Application Support" / "Augur" / "state"


def get_ide_backlog_dir() -> Path:
    """Get the IDE backlog directory."""
    runtime_dir = get_runtime_dir()
    backlog_dir = runtime_dir / "ide-backlog"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    return backlog_dir


def save_instruction(
    ide: str,
    action: str,
    content: str,
    params: dict[str, Any] | None = None,
    filename: str | None = None,
) -> Path:
    """Save instruction to IDE backlog folder."""
    backlog_dir = get_ide_backlog_dir()

    # Generate filename if not provided
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{ide}-{action}-{timestamp}.md"

    # Ensure .md extension
    if not filename.endswith(".md"):
        filename = f"{filename}.md"

    file_path = backlog_dir / filename

    # Add metadata header
    metadata = {
        "ide": ide,
        "action": action,
        "created": datetime.now().isoformat(),
        "params": params or {},
    }

    # Write file with metadata comment
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("<!--\n")
        f.write(f"IDE: {ide}\n")
        f.write(f"Action: {action}\n")
        f.write(f"Created: {metadata['created']}\n")
        f.write(f"Params: {json.dumps(params or {}, indent=2)}\n")
        f.write("-->\n\n")
        f.write(content)

    return file_path


def list_instructions(ide: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """List instructions in backlog."""
    backlog_dir = get_ide_backlog_dir()

    if not backlog_dir.exists():
        return []

    instructions = []
    for file_path in sorted(backlog_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        if ide and not file_path.name.startswith(f"{ide}-"):
            continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Extract metadata from comment
                metadata = {
                    "filename": file_path.name,
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                }

                # Try to parse metadata from comment
                if content.startswith("<!--"):
                    lines = content.split("\n")
                    for line in lines[1:5]:  # First few lines after <!--
                        if ":" in line:
                            key, value = line.split(":", 1)
                            metadata[key.strip().lower()] = value.strip()

                instructions.append(metadata)
        except Exception:
            continue

        if len(instructions) >= limit:
            break

    return instructions


def get_latest_instruction(ide: str | None = None) -> dict[str, Any] | None:
    """Get the latest instruction."""
    instructions = list_instructions(ide=ide, limit=1)
    return instructions[0] if instructions else None
