from __future__ import annotations

from pathlib import Path

from skills.knowledge.scripts.mcp import _read_projects_file

from .base import SourceResult


_TEXT_EXTENSIONS = {".md", ".txt"}


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class LinkedFolderAdapter:
    kind = "linked_folder"

    def resolve(self, spec: dict, budget_tokens: int) -> SourceResult:
        project_id = spec.get("project_id")
        entries = [
            entry
            for entry in _read_projects_file()
            if isinstance(entry, dict) and (not project_id or entry.get("id") == project_id)
        ]
        if not entries:
            return SourceResult(text="", citations=[], truncated=False)

        parts: list[str] = []
        citations: list[str] = []
        running_tokens = 0
        truncated = False
        max_files = int(spec.get("limit", 50))
        seen_files = 0

        for entry in entries:
            root = Path(str(entry.get("path", ""))).expanduser().resolve(strict=False)
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*")):
                if seen_files >= max_files:
                    truncated = True
                    break
                if not path.is_file() or path.suffix.lower() not in _TEXT_EXTENSIONS:
                    continue
                body = path.read_text(encoding="utf-8")[:4000]
                block = f"### {entry.get('name') or entry.get('id') or root.name} / {path.name}\n\n{body}"
                tokens = _approx_tokens(block)
                if running_tokens + tokens > budget_tokens:
                    truncated = True
                    break
                parts.append(block)
                citations.append(str(path))
                running_tokens += tokens
                seen_files += 1
            if truncated:
                break

        return SourceResult(text="\n\n".join(parts), citations=citations, truncated=truncated)
