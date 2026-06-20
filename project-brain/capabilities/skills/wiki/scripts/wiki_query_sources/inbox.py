from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config.paths import get_runtime_dir
from src.lib.ingest.inbox_scan import scan_folder
from src.lib.ingest.inbox_store import InboxStore

from .base import SourceResult


_TEXT_EXTENSIONS = {".md", ".txt"}


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class InboxAdapter:
    kind = "inbox"

    def resolve(self, spec: dict, budget_tokens: int) -> SourceResult:
        store = InboxStore(get_runtime_dir() / "brain" / "inbox")
        folder_id = spec.get("folder_id")
        folders = [folder for folder in store.list_folders() if not folder_id or folder.id == folder_id]
        if not folders:
            return SourceResult(text="", citations=[], truncated=False)

        parts: list[str] = []
        citations: list[str] = []
        running_tokens = 0
        truncated = False
        max_items = int(spec.get("limit", 50))
        seen_items = 0

        for folder in folders:
            scan = scan_folder(folder.path)
            for item in scan.items:
                if seen_items >= max_items:
                    truncated = True
                    break
                block = _format_item(folder.name, item)
                tokens = _approx_tokens(block)
                if running_tokens + tokens > budget_tokens:
                    truncated = True
                    break
                parts.append(block)
                citations.append(str(item.path))
                running_tokens += tokens
                seen_items += 1
            if truncated:
                break

        return SourceResult(text="\n\n".join(parts), citations=citations, truncated=truncated)


def _format_item(folder_name: str, item: Any) -> str:
    item_path = Path(str(item.path))
    body = ""
    if item_path.suffix.lower() in _TEXT_EXTENSIONS and item_path.is_file():
        try:
            body = item_path.read_text(encoding="utf-8")[:4000]
        except OSError:
            body = ""
    status = "stable" if getattr(item, "stable", True) else "not stable"
    return (
        f"### {folder_name} / {getattr(item, 'name', item_path.name)}\n"
        f"- Type: {getattr(item, 'candidate_type', 'unknown')}\n"
        f"- Status: {status}\n\n"
        f"{body}"
    ).strip()
