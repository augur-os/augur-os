#!/usr/bin/env python3
"""Migrate legacy multi-entry memory files to individual .md files with YAML frontmatter.

This is a one-time migration script for the multi-client memory system.

Steps:
  0. Verify source files exist and log counts
  1. Ensure frontmatter on existing project/feedback files (add written-by if missing)
  2. Split multi-entry files (patterns.md, decisions.md, preferences.md)
  3. Extract unique entries from patterns-archive.md
  4. Extract valuable entries from decisions-archive.md (filter commit noise)
  5. Migrate daily logs to vault system dir
  6. Delete empty stubs (learned-patterns.md, session-insights.md, user-preferences.md)
  7. Create vault system dir
  8. Run first assembly

Usage:
    PYTHONPATH="$PWD:$PWD/src/mcp" python3 scripts/migrate/migrate_memory.py --dry-run
    PYTHONPATH="$PWD:$PWD/src/mcp" python3 scripts/migrate/migrate_memory.py
"""
# TODO_CLEANUP: This file is 1072 lines — consider splitting into smaller modules

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src" / "mcp"))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Claude Code encodes a project's absolute path as the dir name under
# ~/.claude/projects/ by replacing path separators with "-" (e.g.
# /Users/<user>/Projects/Augur -> -Users-<user>-Projects-Augur). Derive it from
# PROJECT_ROOT so this is portable rather than hardcoding one machine's username.
_PROJECT_SLUG = str(PROJECT_ROOT.resolve()).replace("/", "-")
CLAUDE_NATIVE_DIR = Path.home() / ".claude" / "projects" / _PROJECT_SLUG / "memory"

DAILY_LOG_DIR = PROJECT_ROOT / "docs" / "memory" / "daily"

# Commit-only pattern: "verb(scope): desc (hash, N files)" with nothing substantial
_COMMIT_ONLY_RE = re.compile(
    r"^(fix|feat|docs|chore|refactor|perf|test|style|ci|build)"
    r"(\([^)]*\))?:\s*.+\([a-f0-9]{7,},?\s*\d+\s*files?\)\s*$"
)

# Noise patterns from the assembler
_NOISE_PATTERNS = [
    re.compile(r"^chore\(sync\):\s*regenerate", re.IGNORECASE),
    re.compile(r"^session\s+checkpoint", re.IGNORECASE),
    re.compile(r"^style\(", re.IGNORECASE),  # auto-format noise
]

# Stubs to delete
STUB_FILES = ["learned-patterns.md", "session-insights.md", "user-preferences.md"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def slugify(text: str, max_len: int = 50) -> str:
    """Create a filesystem-safe slug from text."""
    # Remove date prefix like [2026-03-08]
    text = re.sub(r"^\[\d{4}-\d{2}-\d{2}\]\s*", "", text)
    # Remove [claude-native] tags
    text = re.sub(r"\[claude-native\]\s*", "", text)
    # Take first ~max_len meaningful chars
    text = text[:max_len]
    # Lowercase, replace non-alnum with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)
    return slug or "unknown"


def normalize_for_dedup(text: str) -> str:
    """Normalize text for deduplication — strip hashes, file counts, collapse whitespace."""
    text = re.sub(r"\([a-f0-9]{7,},?\s*\d+\s*files?\)", "", text)
    text = re.sub(r"\b[a-f0-9]{7,}\b", "", text)
    text = re.sub(r"\d+\s+files?", "", text)
    return " ".join(text.split()).strip().lower()


def is_noise(text: str) -> bool:
    """Check if an entry is noise (commit-only or known noise pattern)."""
    text = text.strip()
    if not text:
        return True
    if _COMMIT_ONLY_RE.match(text):
        return True
    return any(p.search(text) for p in _NOISE_PATTERNS)


def has_frontmatter(path: Path) -> bool:
    """Check if a file has YAML frontmatter."""
    try:
        content = path.read_text(encoding="utf-8")
        return content.startswith("---\n")
    except (OSError, UnicodeDecodeError):
        return False


def get_frontmatter_field(path: Path, field: str) -> str | None:
    """Extract a specific field from YAML frontmatter."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    if not content.startswith("---\n"):
        return None

    end = content.find("\n---\n", 4)
    if end == -1:
        return None

    yaml_block = content[4:end]
    for line in yaml_block.split("\n"):
        if line.startswith(f"{field}:"):
            return line[len(field) + 1:].strip().strip('"').strip("'")
    return None


def write_entry_file(
    target_dir: Path,
    filename: str,
    name: str,
    entry_type: str,
    description: str,
    body: str,
    written_by: str = "claude-code",
    created: str = "",
    dry_run: bool = False,
) -> bool:
    """Write a single memory entry .md file with YAML frontmatter.

    Returns True if the file was written (or would be written in dry-run).
    """
    if not created:
        created = datetime.now().strftime("%Y-%m-%d")

    # Escape description for YAML safety (colons, special chars)
    safe_desc = description.replace('"', '\\"')

    content = f"""---
name: {name}
type: {entry_type}
written-by: {written_by}
created: {created}
updated: {created}
description: "{safe_desc}"
---

{body.strip()}
"""

    target = target_dir / filename
    if target.exists():
        return False

    if dry_run:
        print(f"  [DRY-RUN] Would write: {filename}")
        return True

    target.write_text(content, encoding="utf-8")
    return True


def parse_dated_entry(line: str) -> tuple[str, str]:
    """Parse a '- [YYYY-MM-DD] ...' line into (date, text)."""
    m = re.match(r"^-\s*\[(\d{4}-\d{2}-\d{2})\]\s*(.*)", line)
    if m:
        return m.group(1), m.group(2).strip()
    return "", line.lstrip("- ").strip()


def parse_undated_entry(line: str) -> str:
    """Parse an undated bullet entry '- ...'."""
    return line.lstrip("- ").strip()


# ---------------------------------------------------------------------------
# Step 0: Verify
# ---------------------------------------------------------------------------


def step0_verify() -> dict:
    """Enumerate and verify source files."""
    print("\n=== Step 0: Verify source files ===")

    sources = {
        "patterns.md": CLAUDE_NATIVE_DIR / "patterns.md",
        "decisions.md": CLAUDE_NATIVE_DIR / "decisions.md",
        "preferences.md": CLAUDE_NATIVE_DIR / "preferences.md",
        "patterns-archive.md": CLAUDE_NATIVE_DIR / "patterns-archive.md",
        "decisions-archive.md": CLAUDE_NATIVE_DIR / "decisions-archive.md",
    }

    # Add project/feedback files
    project_files = list(CLAUDE_NATIVE_DIR.glob("project_*.md"))
    feedback_files = list(CLAUDE_NATIVE_DIR.glob("feedback_*.md"))

    stats = {
        "project_files": len(project_files),
        "feedback_files": len(feedback_files),
    }

    for name, path in sources.items():
        if path.exists():
            size = path.stat().st_size
            lines = path.read_text(encoding="utf-8").count("\n")
            print(f"  OK: {name} ({lines} lines, {size} bytes)")
            stats[name] = {"lines": lines, "size": size}
        else:
            print(f"  MISSING: {name}")
            stats[name] = None

    print(f"  Project files: {len(project_files)}")
    print(f"  Feedback files: {len(feedback_files)}")

    # Daily logs
    if DAILY_LOG_DIR.exists():
        daily_count = len(list(DAILY_LOG_DIR.glob("*.md")))
        print(f"  Daily logs: {daily_count}")
        stats["daily_logs"] = daily_count
    else:
        print("  Daily logs: directory not found")
        stats["daily_logs"] = 0

    return stats


# ---------------------------------------------------------------------------
# Step 1: Ensure frontmatter on existing files
# ---------------------------------------------------------------------------


def step1_ensure_frontmatter(dry_run: bool) -> int:
    """Ensure written-by field exists on project/feedback files."""
    print("\n=== Step 1: Ensure frontmatter on existing files ===")

    count = 0
    for pattern in ["project_*.md", "feedback_*.md"]:
        for md_file in sorted(CLAUDE_NATIVE_DIR.glob(pattern)):
            if not has_frontmatter(md_file):
                print(f"  SKIP (no frontmatter): {md_file.name}")
                continue

            written_by = get_frontmatter_field(md_file, "written-by")
            if written_by:
                continue  # Already has written-by

            # Add written-by to existing frontmatter
            content = md_file.read_text(encoding="utf-8")
            # Insert after first ---\n
            insertion = "written-by: claude-code\n"
            end_idx = content.find("\n---\n", 4)
            if end_idx == -1:
                continue

            new_content = content[:end_idx] + "\n" + insertion + content[end_idx:]

            if dry_run:
                print(f"  [DRY-RUN] Would add written-by to: {md_file.name}")
            else:
                md_file.write_text(new_content, encoding="utf-8")
                print(f"  Added written-by to: {md_file.name}")
            count += 1

    print(f"  Updated {count} files")
    return count


# ---------------------------------------------------------------------------
# Step 2: Split multi-entry files
# ---------------------------------------------------------------------------


def _split_multi_entry_file(
    source_path: Path,
    entry_type: str,
    target_dir: Path,
    seen_normalized: set,
    dry_run: bool,
) -> int:
    """Split a multi-entry file into individual .md files."""
    if not source_path.exists():
        print(f"  SKIP (not found): {source_path.name}")
        return 0

    content = source_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    count = 0
    for line in lines:
        line = line.strip()
        if not line.startswith("- "):
            continue

        date, text = parse_dated_entry(line)
        if not text:
            text = parse_undated_entry(line)
        if not text:
            continue

        # Skip noise
        if is_noise(text):
            continue

        # Dedup
        norm = normalize_for_dedup(text)
        if norm in seen_normalized:
            continue
        seen_normalized.add(norm)

        # Remove [claude-native] tag from text for file content
        clean_text = re.sub(r"\[claude-native\]\s*", "", text).strip()

        slug = slugify(clean_text)
        filename = f"{entry_type}_{slug}.md"

        # Truncate description for frontmatter (first line, max 200 chars)
        desc_text = clean_text[:200].replace("\n", " ")

        written = write_entry_file(
            target_dir=target_dir,
            filename=filename,
            name=slug,
            entry_type=entry_type,
            description=desc_text,
            body=clean_text,
            written_by="claude-code",
            created=date or datetime.now().strftime("%Y-%m-%d"),
            dry_run=dry_run,
        )
        if written:
            count += 1

    # Delete source file
    if count > 0 and not dry_run:
        source_path.unlink()
        print(f"  Deleted source: {source_path.name}")
    elif count > 0 and dry_run:
        print(f"  [DRY-RUN] Would delete: {source_path.name}")

    return count


def step2_split_multi_entry(dry_run: bool) -> int:
    """Split patterns.md, decisions.md, preferences.md into individual files."""
    print("\n=== Step 2: Split multi-entry files ===")

    seen = set()
    total = 0

    for filename, entry_type in [
        ("patterns.md", "feedback"),
        ("decisions.md", "feedback"),
        ("preferences.md", "preference"),
    ]:
        source = CLAUDE_NATIVE_DIR / filename
        count = _split_multi_entry_file(
            source, entry_type, CLAUDE_NATIVE_DIR, seen, dry_run
        )
        print(f"  {filename}: {count} entries created")
        total += count

    print(f"  Total: {total} entries")
    return total


# ---------------------------------------------------------------------------
# Step 3: Extract from patterns-archive.md
# ---------------------------------------------------------------------------


def step3_extract_patterns_archive(dry_run: bool) -> int:
    """Extract unique entries from patterns-archive.md."""
    print("\n=== Step 3: Extract from patterns-archive.md ===")

    source = CLAUDE_NATIVE_DIR / "patterns-archive.md"
    if not source.exists():
        print("  SKIP: patterns-archive.md not found")
        return 0

    content = source.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Collect all entries (dated and undated bullets)
    entries: list[tuple[str, str]] = []  # (date, text)
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- ["):
            date, text = parse_dated_entry(line)
            entries.append((date, text))
        elif line.startswith("- "):
            text = parse_undated_entry(line)
            if text:
                entries.append(("", text))

    # Deduplicate
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for date, text in entries:
        norm = normalize_for_dedup(text)
        if norm in seen or not norm or len(norm) < 10:
            continue
        seen.add(norm)
        if not is_noise(text):
            unique.append((date, text))

    print(f"  Found {len(entries)} total entries, {len(unique)} unique after dedup")

    count = 0
    for date, text in unique:
        slug = slugify(text)
        filename = f"feedback_{slug}.md"
        desc = text[:200].replace("\n", " ")

        written = write_entry_file(
            target_dir=CLAUDE_NATIVE_DIR,
            filename=filename,
            name=slug,
            entry_type="feedback",
            description=desc,
            body=text,
            written_by="claude-code",
            created=date or "2026-02-01",
            dry_run=dry_run,
        )
        if written:
            count += 1

    # Delete source
    if not dry_run:
        source.unlink()
        print(f"  Deleted source: patterns-archive.md")
    else:
        print(f"  [DRY-RUN] Would delete: patterns-archive.md")

    print(f"  Created {count} entry files")
    return count


# ---------------------------------------------------------------------------
# Step 4: Extract from decisions-archive.md
# ---------------------------------------------------------------------------


def step4_extract_decisions_archive(dry_run: bool) -> int:
    """Extract valuable entries from decisions-archive.md, filtering commit noise."""
    print("\n=== Step 4: Extract from decisions-archive.md ===")

    source = CLAUDE_NATIVE_DIR / "decisions-archive.md"
    if not source.exists():
        print("  SKIP: decisions-archive.md not found")
        return 0

    content = source.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Get existing project/feedback descriptions for dedup
    existing_descs: set[str] = set()
    for pattern in ["project_*.md", "feedback_*.md"]:
        for md_file in CLAUDE_NATIVE_DIR.glob(pattern):
            desc = get_frontmatter_field(md_file, "description")
            if desc:
                existing_descs.add(normalize_for_dedup(desc))

    # Also load recently-created entries from steps 2-3
    # (they're in the directory now even if from this run)
    for md_file in CLAUDE_NATIVE_DIR.glob("*.md"):
        if md_file.name == "MEMORY.md" or md_file.name == source.name:
            continue
        desc = get_frontmatter_field(md_file, "description")
        if desc:
            existing_descs.add(normalize_for_dedup(desc))

    total_entries = 0
    noise_filtered = 0
    commit_filtered = 0
    dedup_filtered = 0
    claude_native_filtered = 0
    valuable: list[tuple[str, str, str]] = []  # (date, text, written_by)
    seen: set[str] = set()

    for line in lines:
        line = line.strip()
        if not line.startswith("- ["):
            continue

        total_entries += 1
        date, text = parse_dated_entry(line)
        if not text:
            continue

        # Filter bare commit messages
        if _COMMIT_ONLY_RE.match(text):
            commit_filtered += 1
            continue

        # Filter noise
        if is_noise(text):
            noise_filtered += 1
            continue

        # Determine written-by
        has_native_tag = "[claude-native]" in text
        clean_text = re.sub(r"\[claude-native\]\s*", "", text).strip()

        # Dedup against existing files
        norm = normalize_for_dedup(clean_text)
        if norm in existing_descs or norm in seen:
            dedup_filtered += 1
            continue
        seen.add(norm)

        # Skip entries that are really just commit descriptions with hashes
        # Even without the (hash, N files) suffix, many have embedded hashes
        if re.match(
            r"^(fix|feat|docs|chore|refactor|perf|test|style|ci|build)\(",
            clean_text,
        ) and re.search(r"\([a-f0-9]{7,}", clean_text):
            commit_filtered += 1
            continue

        written_by = "claude-code" if has_native_tag else "augur-system"
        valuable.append((date, clean_text, written_by))

    print(f"  Total entries: {total_entries}")
    print(f"  Commit noise filtered: {commit_filtered}")
    print(f"  Other noise filtered: {noise_filtered}")
    print(f"  Duplicates filtered: {dedup_filtered}")
    print(f"  Valuable entries: {len(valuable)}")

    count = 0
    for date, text, written_by in valuable:
        slug = slugify(text)
        filename = f"feedback_{slug}.md"
        desc = text[:200].replace("\n", " ")

        written = write_entry_file(
            target_dir=CLAUDE_NATIVE_DIR,
            filename=filename,
            name=slug,
            entry_type="feedback",
            description=desc,
            body=text,
            written_by=written_by,
            created=date or "2026-02-01",
            dry_run=dry_run,
        )
        if written:
            count += 1

    # Delete source
    if not dry_run:
        source.unlink()
        print(f"  Deleted source: decisions-archive.md")
    else:
        print(f"  [DRY-RUN] Would delete: decisions-archive.md")

    print(f"  Created {count} entry files")
    return count


# ---------------------------------------------------------------------------
# Step 5: Migrate daily logs
# ---------------------------------------------------------------------------


def step5_migrate_daily_logs(dry_run: bool) -> int:
    """Extract structured entries from daily logs to vault system dir."""
    print("\n=== Step 5: Migrate daily logs ===")

    if not DAILY_LOG_DIR.exists():
        print("  SKIP: daily log directory not found")
        return 0

    try:
        from src.config.paths import get_vault_dir
        vault_system_dir = get_vault_dir() / "memory" / "system"
    except ImportError:
        vault_system_dir = Path.home() / "Vault" / "Augur" / "memory" / "system"

    if not dry_run:
        vault_system_dir.mkdir(parents=True, exist_ok=True)

    # Build dedup set from existing claude native entries
    existing_descs: set[str] = set()
    for md_file in CLAUDE_NATIVE_DIR.glob("*.md"):
        if md_file.name == "MEMORY.md":
            continue
        desc = get_frontmatter_field(md_file, "description")
        if desc:
            existing_descs.add(normalize_for_dedup(desc))

    # Parse daily logs for structured markers
    entry_re = re.compile(
        r"##\s*(Decision|Pattern|Preference):\s*(.+?)(?=\n##|\Z)",
        re.DOTALL,
    )

    count = 0
    seen: set[str] = set()

    for log_file in sorted(DAILY_LOG_DIR.glob("*.md")):
        date = log_file.stem  # YYYY-MM-DD
        content = log_file.read_text(encoding="utf-8")

        for match in entry_re.finditer(content):
            marker_type = match.group(1).lower()
            text = match.group(2).strip()

            # Take first line only (rest is often a commit hash line)
            first_line = text.split("\n")[0].strip()
            if not first_line:
                continue

            # Filter noise
            if is_noise(first_line):
                continue

            # Dedup
            norm = normalize_for_dedup(first_line)
            if norm in existing_descs or norm in seen:
                continue
            if len(norm) < 10:
                continue
            seen.add(norm)

            # Map marker type to entry type
            entry_type = "feedback"
            if marker_type == "preference":
                entry_type = "preference"

            slug = slugify(first_line)
            filename = f"{entry_type}_{slug}.md"
            desc = first_line[:200].replace("\n", " ")

            written = write_entry_file(
                target_dir=vault_system_dir,
                filename=filename,
                name=slug,
                entry_type=entry_type,
                description=desc,
                body=first_line,
                written_by="augur-system",
                created=date,
                dry_run=dry_run,
            )
            if written:
                count += 1

    print(f"  Created {count} entries in vault system dir")
    return count


# ---------------------------------------------------------------------------
# Step 6: Delete stubs
# ---------------------------------------------------------------------------


def step6_delete_stubs(dry_run: bool) -> int:
    """Delete empty stub files."""
    print("\n=== Step 6: Delete empty stubs ===")

    count = 0
    for name in STUB_FILES:
        path = CLAUDE_NATIVE_DIR / name
        if path.exists():
            if dry_run:
                print(f"  [DRY-RUN] Would delete: {name}")
            else:
                path.unlink()
                print(f"  Deleted: {name}")
            count += 1
        else:
            print(f"  Already gone: {name}")

    return count


# ---------------------------------------------------------------------------
# Step 7: Create vault system dir
# ---------------------------------------------------------------------------


def step7_create_vault_system_dir(dry_run: bool) -> None:
    """Ensure vault system memory directory exists."""
    print("\n=== Step 7: Create vault system dir ===")

    try:
        from src.config.paths import get_vault_dir
        vault_system_dir = get_vault_dir() / "memory" / "system"
    except ImportError:
        vault_system_dir = Path.home() / "Vault" / "Augur" / "memory" / "system"

    if vault_system_dir.exists():
        print(f"  Already exists: {vault_system_dir}")
    elif dry_run:
        print(f"  [DRY-RUN] Would create: {vault_system_dir}")
    else:
        vault_system_dir.mkdir(parents=True, exist_ok=True)
        print(f"  Created: {vault_system_dir}")


# ---------------------------------------------------------------------------
# Step 8: Run first assembly
# ---------------------------------------------------------------------------


def step8_run_assembly(dry_run: bool) -> dict | None:
    """Run the memory assembler to populate vault and generate indexes."""
    print("\n=== Step 8: Run first assembly ===")

    if dry_run:
        print("  [DRY-RUN] Would run memory assembler")
        return None

    try:
        assembler_dir = PROJECT_ROOT / ".claude" / "skills" / "auto-memory-sync" / "scripts"
        if str(assembler_dir) not in sys.path:
            sys.path.insert(0, str(assembler_dir))
        from memory_assembler import assemble

        from src.config.paths import get_vault_dir
        vault_memory_dir = get_vault_dir() / "memory"

        # Build sources dict
        sources: dict[str, Path] = {}
        if CLAUDE_NATIVE_DIR.is_dir():
            sources["claude-code"] = CLAUDE_NATIVE_DIR

        gemini_memory = PROJECT_ROOT / ".gemini" / "memory"
        if gemini_memory.is_dir():
            sources["gemini"] = gemini_memory

        if not sources:
            print("  No client memory dirs found")
            return None

        result = assemble(
            sources=sources,
            vault_memory_dir=vault_memory_dir,
            claude_native_dir=CLAUDE_NATIVE_DIR,
        )

        print(f"  Discovered: {result['discovered']} entries")
        print(f"  After quality gate: {result['after_quality_gate']} entries")
        print(f"  Assembled: {len(result['assembled_paths'])} files")
        print(f"  Indexes: {len(result['indexes_written'])} written")

        return result

    except Exception as e:
        print(f"  Assembly failed: {e}")
        import traceback
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Migrate legacy multi-entry memory files to individual .md files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()
    dry_run = args.dry_run

    print("=" * 60)
    print("Augur Memory Migration")
    if dry_run:
        print("MODE: DRY RUN (no files will be modified)")
    else:
        print("MODE: LIVE (files will be created/deleted)")
    print("=" * 60)

    if not CLAUDE_NATIVE_DIR.exists():
        print(f"\nERROR: Claude native memory dir not found: {CLAUDE_NATIVE_DIR}")
        return 1

    # Step 0: Verify
    step0_verify()

    # Step 1: Ensure frontmatter
    step1_count = step1_ensure_frontmatter(dry_run)

    # Step 2: Split multi-entry files
    step2_count = step2_split_multi_entry(dry_run)

    # Step 3: Extract patterns archive
    step3_count = step3_extract_patterns_archive(dry_run)

    # Step 4: Extract decisions archive
    step4_count = step4_extract_decisions_archive(dry_run)

    # Step 5: Migrate daily logs
    step5_count = step5_migrate_daily_logs(dry_run)

    # Step 6: Delete stubs
    step6_count = step6_delete_stubs(dry_run)

    # Step 7: Create vault system dir
    step7_create_vault_system_dir(dry_run)

    # Step 8: Run assembly
    assembly_result = step8_run_assembly(dry_run)

    # Summary
    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"  Step 1 (frontmatter): {step1_count} files updated")
    print(f"  Step 2 (split multi): {step2_count} entries created")
    print(f"  Step 3 (patterns archive): {step3_count} entries created")
    print(f"  Step 4 (decisions archive): {step4_count} entries created")
    print(f"  Step 5 (daily logs): {step5_count} entries created")
    print(f"  Step 6 (stubs deleted): {step6_count} files")
    total_created = step2_count + step3_count + step4_count + step5_count
    print(f"  TOTAL entries created: {total_created}")

    if assembly_result:
        print(f"  Assembly: {assembly_result['after_quality_gate']} entries indexed")

    if dry_run:
        print("\n  (DRY RUN - no changes were made)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
