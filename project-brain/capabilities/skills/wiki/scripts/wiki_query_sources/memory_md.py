from __future__ import annotations

import re

from src.config.paths import get_vault_dir

from .base import SourceResult


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _extract_section(content: str, title: str) -> str:
    match = re.search(
        rf"^## {re.escape(title)}\s*\n(.*?)(?=^## |\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(0) if match else ""


def _tail_truncate(content: str, budget_tokens: int) -> tuple[str, bool]:
    if _approx_tokens(content) <= budget_tokens:
        return content, False

    keep: list[str] = []
    running = 0
    for line in reversed(content.splitlines()):
        running += _approx_tokens(line + "\n")
        if running > budget_tokens:
            break
        keep.append(line)
    truncated = "\n".join(reversed(keep))
    return f"[... older content elided to fit budget ...]\n{truncated}", True


class MemoryMdAdapter:
    kind = "memory_md"

    def resolve(self, spec: dict, budget_tokens: int) -> SourceResult:
        path = get_vault_dir() / "memory" / "MEMORY.md"
        if not path.exists():
            return SourceResult(text="", citations=[], truncated=False)

        content = path.read_text(encoding="utf-8")
        section_filter = spec.get("section")
        if section_filter:
            content = _extract_section(content, str(section_filter))

        content, truncated = _tail_truncate(content, budget_tokens)
        return SourceResult(
            text=content,
            citations=[f"{path}:{len(content.splitlines())} lines"] if content else [],
            truncated=truncated,
        )
