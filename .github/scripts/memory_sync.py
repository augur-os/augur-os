#!/usr/bin/env python3
from __future__ import annotations

"""
Memory Sync - Augur memory management (ADR-057)

Legacy pipeline replaced by multi-client memory assembler.
This module retains utility functions used by sync_agents and tests,
and a main() that delegates to the assembler.

Usage:
    python3 .github/scripts/memory_sync.py           # run assembler
    python3 .github/scripts/memory_sync.py --dry-run  # show what would happen
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.config.paths import get_memory_dir
    MEMORY_DIR = Path(get_memory_dir())
except ImportError:
    MEMORY_DIR = PROJECT_ROOT / "docs" / "memory"

MEMORY_FILE = MEMORY_DIR / "MEMORY.md"

# ADR-164: Noise patterns — entries matching these are never written to MEMORY.md
NOISE_PATTERNS = [
    re.compile(r"^chore\(sync\): regenerate", re.IGNORECASE),
    re.compile(r"^chore\(sync\): update generated", re.IGNORECASE),
    re.compile(r"^Session checkpoint created", re.IGNORECASE),
]

# ADR-164: Commit-only pattern — entries that are just git log with no insight
# Matches: "verb(scope): desc (hash, N files)" or "verb: desc (hash, N files)"
_COMMIT_ONLY_RE = re.compile(
    r"^(fix|feat|docs|chore|refactor|perf|test)(\(.*?\))?:.*\([a-f0-9]{7,},?\s*\d+\s*files?\)\s*$"
)


def normalize_entry(text: str) -> str:
    """Normalize an entry for dedup comparison (ADR-164).

    Strips commit hashes and file counts, collapses whitespace.
    """
    text = re.sub(r"\([a-f0-9]{7,},?\s*\d+\s*files?\)", "", text)
    return " ".join(text.split()).strip()


def _is_noise(text: str) -> bool:
    """Return True if the entry matches a noise pattern (ADR-164).

    Catches: chore(sync) regenerate, session checkpoints, and commit-only
    entries (just a git log line with hash+files and no architectural insight).
    """
    if any(pat.search(text) for pat in NOISE_PATTERNS):
        return True
    if _COMMIT_ONLY_RE.match(text):
        return True
    return False


def _classify_entry(text: str) -> str | None:
    """Classify entry by conventional-commit prefix. Returns category or None."""
    m = re.match(r"^(chore|fix|feat|docs|refactor|perf|test)\b", text)
    return m.group(1) if m else None


def _parse_entry_date(line: str) -> datetime | None:
    """Extract the date from a memory entry line like '- [2026-02-25] ...'."""
    m = re.match(r"^-\s*\[(\d{4}-\d{2}-\d{2})\]", line)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%d")
        except ValueError:
            return None
    return None


def _entry_text(line: str) -> str:
    """Extract the text portion after '- [date] ' from a memory entry line."""
    m = re.match(r"^-\s*\[\d{4}-\d{2}-\d{2}\]\s*", line)
    return line[m.end():] if m else line.lstrip("- ")


def _extract_entry_lines(content: str) -> list[str]:
    """Extract all '- [date] ...' entry lines from content."""
    return [line for line in content.split("\n") if line.startswith("- [")]


# ---------------------------------------------------------------------------
# Agent Sync (ADR-057)
# ---------------------------------------------------------------------------


def get_claude_native_memory_dir() -> Path | None:
    """Resolve the Claude Code native auto-memory directory.

    Returns the path to ~/.claude/projects/-{encoded_path}/memory/,
    or None if the directory doesn't exist (Claude Code not configured).
    """
    from src.config.paths import get_claude_native_memory_dir as _get_claude_native_memory_dir

    return _get_claude_native_memory_dir(PROJECT_ROOT, create=True)


def _is_curated_index(content: str) -> bool:
    """Detect if MEMORY.md uses the curated index format (links to .md files).

    The curated format has entries like:
      - [date] [tag] [name](file.md) -- description
    The old format has entries like:
      - [date] [tag] Raw text description...

    If the file contains markdown links to .md files, it's a curated index
    that should NOT be overwritten by the flat canonical format.
    """
    return bool(re.search(r"\[[\w_-]+\]\([\w_-]+\.md\)", content))


def main():
    parser = argparse.ArgumentParser(
        description="Memory Sync - surfaces client memory as review candidates (ADR-772)"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without making changes")
    # Legacy flags kept for backward-compat (ignored)
    parser.add_argument("--sync", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--ci", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--cleanup-only", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()

    print("=" * 60)
    print("Augur Memory Sync (review-gated — ADR-772)")
    print("=" * 60)

    if args.dry_run:
        print("DRY RUN: would refresh the memory review queue (no canonical writes)")
        return

    # ADR-772: client memory is review *input*, not auto-promoted. Surface the
    # pending candidate count instead of writing canonical entries; promotion
    # happens via /brain/memory-review or the memory-review-approve MCP tool.
    try:
        assembler_dir = PROJECT_ROOT / "project-brain" / "capabilities" / "skills" / "ai" / "scripts" / "ops"
        if str(assembler_dir) not in sys.path:
            sys.path.insert(0, str(assembler_dir))
        from memory_assembler import collect_review_candidates

        from src.lib.brain_write_routing import resolve_write_target
        from src.lib.memory_review import build_queue

        candidates = collect_review_candidates([PROJECT_ROOT])
        if not candidates:
            print("No client memory candidates found")
            return

        target = resolve_write_target(cwd=PROJECT_ROOT)
        snapshot = build_queue(target=target, client_candidates=candidates)
        counts = snapshot["counts"]

        print(f"\nReview queue (brain={target.brain.id}):")
        print(f"  Pending review: {counts['pending']}")
        print(f"  Already promoted: {counts['promoted']}")
        print(f"  Rejected: {counts['rejected']}")
        print("  Approve candidates at /brain/memory-review")

    except Exception as e:
        print(f"Memory review refresh failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Memory sync complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
