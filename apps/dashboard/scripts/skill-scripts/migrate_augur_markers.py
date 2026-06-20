#!/usr/bin/env python3
"""
Migrate all SKILL.md files to add @augur markers to Augur-extension frontmatter fields.

Part of ADR-040 implementation: marks Layer 2 (Augur Extensions) fields so the
exporter can strip them for portable export.

Usage:
    python3 migrate_augur_markers.py              # Dry run (shows changes)
    python3 migrate_augur_markers.py --apply       # Apply changes
    python3 migrate_augur_markers.py --check       # Check which files need migration
"""

import argparse
import re
import sys
from pathlib import Path


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Root of the project
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLUGINS_DIR = PROJECT_ROOT / "plugins"

# --- Layer 2 (Augur Extension) fields ---
# These are Augur-specific and should be marked with # @augur
# Top-level frontmatter keys that are ALWAYS Augur extensions
AUGUR_TOP_LEVEL_KEYS = {
    "tiers",
    "safety",
    "alignment",
    "category",
    "mode",
    "status",
    "license",
}

# Keys under 'dependencies:' that are Augur extensions
AUGUR_DEPENDENCY_KEYS = {
    "plugins",
    "mcp_servers",
    "context_provides",
    "context_requires",
}

# Keys under 'dependencies:' that are Standard Core (Layer 1)
STANDARD_DEPENDENCY_KEYS = {
    "python",
    "npm",
}

# Top-level 'mcp_servers:' is Augur extension (not under dependencies)
# Top-level 'dependencies:' needs special handling - if it ONLY has augur keys, mark it too


def find_all_skill_mds() -> list[Path]:
    """Find all SKILL.md files across all bundles."""
    return sorted(PLUGINS_DIR.glob("*/skills/*/SKILL.md"))


def extract_frontmatter(content: str) -> tuple[str | None, str | None, str | None]:
    """Split content into pre-frontmatter, frontmatter, and post-frontmatter.

    Returns (before, frontmatter, after) or (None, None, content) if no frontmatter.
    """
    if not content.startswith("---"):
        return None, None, content

    # Find the closing ---
    end_match = re.search(r'\n---\s*\n', content[3:])
    if not end_match:
        # Try end of file
        end_match = re.search(r'\n---\s*$', content[3:])
        if not end_match:
            return None, None, content

    end_pos = 3 + end_match.start() + len(end_match.group())
    frontmatter = content[3 : 3 + end_match.start()]
    after = content[end_pos:]

    return "---", frontmatter.strip(), after


def get_indent_level(line: str) -> int:
    """Count leading spaces."""
    return len(line) - len(line.lstrip())


def already_has_augur_markers(frontmatter: str) -> bool:
    """Check if frontmatter already has @augur markers."""
    return "# @augur" in frontmatter


def add_augur_markers(frontmatter: str) -> str:
    """Add # @augur markers to Augur extension fields in frontmatter.

    Strategy:
    - For multi-line blocks (tiers, safety, alignment): use @augur-start/@augur-end
    - For single-line fields (category, mode, status): use inline # @augur
    - For dependencies: mark only augur sub-keys, keep python/npm unmarked
    - For top-level mcp_servers: use @augur-start/@augur-end
    """
    lines = frontmatter.split("\n")
    result = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            # Check if it's a comment that's part of an augur block
            # (handled by block detection below)
            result.append(line)
            i += 1
            continue

        # Get the key at this level
        key_match = re.match(r'^(\w[\w-]*)\s*:', line)

        if key_match:
            key = key_match.group(1)
            indent = get_indent_level(line)

            # Only process top-level keys (indent == 0)
            if indent == 0:
                if key in AUGUR_TOP_LEVEL_KEYS:
                    # Check if this is a single-line value or a block
                    value_part = line[key_match.end() :].strip()

                    if value_part and not value_part.startswith("|") and not value_part.startswith(">"):
                        # Single-line value - inline marker
                        if "# @augur" not in line:
                            # Pad to align markers nicely
                            padded = line.ljust(55)
                            result.append(f"{padded} # @augur")
                        else:
                            result.append(line)
                        i += 1
                        continue
                    else:
                        # Multi-line block - find extent and wrap with @augur-start/@augur-end
                        block_lines = [line]
                        j = i + 1
                        while j < len(lines):
                            next_line = lines[j]
                            next_stripped = next_line.strip()

                            # Empty line might be part of block or separator
                            if not next_stripped:
                                # Check if next non-empty line is still indented
                                k = j + 1
                                while k < len(lines) and not lines[k].strip():
                                    k += 1
                                if k < len(lines) and get_indent_level(lines[k]) > 0:
                                    block_lines.append(next_line)
                                    j += 1
                                    continue
                                else:
                                    break

                            # If indented, it's part of this block
                            if get_indent_level(next_line) > 0:
                                block_lines.append(next_line)
                                j += 1
                            else:
                                # New top-level key - block ends
                                break

                        # Wrap the block
                        # Add comment before the key line
                        first_line = block_lines[0]
                        padded_first = first_line.ljust(55)
                        result.append(f"{padded_first} # @augur-start")
                        for bl in block_lines[1:]:
                            if bl.strip():  # non-empty lines
                                padded_bl = bl.ljust(55)
                                result.append(f"{padded_bl} # @augur")
                            else:
                                result.append(bl)
                        result.append(f"{'':55} # @augur-end")
                        i = j
                        continue

                elif key == "mcp_servers":
                    # Top-level mcp_servers is augur extension
                    value_part = line[key_match.end() :].strip()

                    if value_part and not value_part.startswith("\n"):
                        # Could be single line like "mcp_servers: []"
                        # Or start of list on same line
                        if value_part in ("[]", ""):
                            padded = line.ljust(55)
                            result.append(f"{padded} # @augur")
                            i += 1
                            continue

                    # Multi-line block
                    block_lines = [line]
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j]
                        if not next_line.strip():
                            break
                        if get_indent_level(next_line) > 0 or next_line.strip().startswith("-"):
                            block_lines.append(next_line)
                            j += 1
                        else:
                            break

                    if len(block_lines) == 1:
                        padded = block_lines[0].ljust(55)
                        result.append(f"{padded} # @augur")
                    else:
                        padded_first = block_lines[0].ljust(55)
                        result.append(f"{padded_first} # @augur-start")
                        for bl in block_lines[1:]:
                            if bl.strip():
                                padded_bl = bl.ljust(55)
                                result.append(f"{padded_bl} # @augur")
                            else:
                                result.append(bl)
                        result.append(f"{'':55} # @augur-end")
                    i = j
                    continue

                elif key == "dependencies":
                    # Special handling: some sub-keys are augur, some are standard
                    value_part = line[key_match.end() :].strip()

                    if value_part and value_part != "":
                        # Inline value - unusual for dependencies, just append
                        result.append(line)
                        i += 1
                        continue

                    # Multi-line block - process each sub-key individually
                    result.append(line)  # 'dependencies:' header stays unmarked
                    j = i + 1
                    while j < len(lines):
                        next_line = lines[j]
                        next_stripped = next_line.strip()

                        if not next_stripped:
                            result.append(next_line)
                            j += 1
                            continue

                        next_indent = get_indent_level(next_line)
                        if next_indent == 0:
                            break  # New top-level key

                        # Check if this sub-key is augur or standard
                        sub_key_match = re.match(r'^\s+(\w[\w-]*)\s*:', next_line)
                        if sub_key_match and next_indent <= 4:
                            sub_key = sub_key_match.group(1)

                            if sub_key in AUGUR_DEPENDENCY_KEYS:
                                # This sub-key and its children are augur
                                sub_block = [next_line]
                                k = j + 1
                                while k < len(lines):
                                    sub_next = lines[k]
                                    if not sub_next.strip():
                                        # Check if block continues
                                        kk = k + 1
                                        while kk < len(lines) and not lines[kk].strip():
                                            kk += 1
                                        if kk < len(lines) and get_indent_level(lines[kk]) > next_indent:
                                            sub_block.append(sub_next)
                                            k += 1
                                            continue
                                        break
                                    if get_indent_level(sub_next) > next_indent:
                                        sub_block.append(sub_next)
                                        k += 1
                                    else:
                                        break

                                for sb in sub_block:
                                    if sb.strip():
                                        padded_sb = sb.ljust(55)
                                        result.append(f"{padded_sb} # @augur")
                                    else:
                                        result.append(sb)
                                j = k
                                continue
                            else:
                                # Standard key (python, npm) - no marker
                                sub_block = [next_line]
                                k = j + 1
                                while k < len(lines):
                                    sub_next = lines[k]
                                    if not sub_next.strip():
                                        break
                                    if get_indent_level(sub_next) > next_indent:
                                        sub_block.append(sub_next)
                                        k += 1
                                    else:
                                        break

                                for sb in sub_block:
                                    result.append(sb)
                                j = k
                                continue

                        # Indented content under dependencies but not a recognized sub-key
                        result.append(next_line)
                        j += 1

                    i = j
                    continue

                else:
                    # Standard Core key - no marker needed
                    result.append(line)
                    i += 1
                    continue
            else:
                # Indented key (part of a block) - already handled by block detection
                result.append(line)
                i += 1
                continue
        else:
            result.append(line)
            i += 1
            continue

    return "\n".join(result)


def process_skill_md(path: Path, apply: bool = False) -> tuple[bool, str]:
    """Process a single SKILL.md file.

    Returns (changed, message).
    """
    content = path.read_text()

    before, frontmatter, after = extract_frontmatter(content)

    if frontmatter is None:
        return False, "  SKIP: No frontmatter found"

    if already_has_augur_markers(frontmatter):
        return False, "  SKIP: Already has @augur markers"

    # Check if there are any augur extension fields
    has_augur_fields = False
    for key in AUGUR_TOP_LEVEL_KEYS:
        if re.search(rf'^{key}\s*:', frontmatter, re.MULTILINE):
            has_augur_fields = True
            break

    if not has_augur_fields:
        # Check for top-level mcp_servers
        if re.search(r'^mcp_servers\s*:', frontmatter, re.MULTILINE):
            has_augur_fields = True
        # Check for augur dependency sub-keys
        if not has_augur_fields:
            for dep_key in AUGUR_DEPENDENCY_KEYS:
                if re.search(rf'^\s+{dep_key}\s*:', frontmatter, re.MULTILINE):
                    has_augur_fields = True
                    break

    if not has_augur_fields:
        return False, "  SKIP: No Augur extension fields in frontmatter"

    # Add markers
    new_frontmatter = add_augur_markers(frontmatter)

    if new_frontmatter == frontmatter:
        return False, "  SKIP: No changes needed"

    # Reconstruct the file
    new_content = f"---\n{new_frontmatter}\n---\n{after}"

    if apply:
        path.write_text(new_content)
        return True, "  UPDATED: Added @augur markers"
    else:
        return True, "  WOULD UPDATE: Has Augur extension fields"


def main():
    parser = argparse.ArgumentParser(description="Migrate SKILL.md files to add @augur markers")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    parser.add_argument("--check", action="store_true", help="Just check which files need migration")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    skill_mds = find_all_skill_mds()
    _out(f"Found {len(skill_mds)} SKILL.md files\n")

    changed = 0
    skipped = 0
    errors = 0

    for path in skill_mds:
        rel_path = path.relative_to(PROJECT_ROOT)

        try:
            was_changed, message = process_skill_md(path, apply=args.apply)

            if was_changed:
                changed += 1
                _out(f"{'✅' if args.apply else '🔄'} {rel_path}")
                if args.verbose:
                    _out(message)
            else:
                skipped += 1
                if args.verbose or args.check:
                    _out(f"⏭️  {rel_path}")
                    _out(message)
        except Exception as e:
            errors += 1
            _out(f"❌ {rel_path}: {e}")

    _out(f"\n{'='*60}")
    _out(f"Results: {changed} {'updated' if args.apply else 'would update'}, {skipped} skipped, {errors} errors")

    if not args.apply and changed > 0:
        _out("\nRun with --apply to apply changes")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
