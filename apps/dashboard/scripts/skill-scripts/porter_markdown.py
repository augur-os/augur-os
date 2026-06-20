"""
Skill Porter Markdown Processing

Frontmatter parsing/dumping, section splitting, SKILL.md trimming,
and storage tree extraction/parsing.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def parse_frontmatter(markdown: str) -> tuple[dict[str, Any], str, bool]:
    """Return (frontmatter_dict, body, had_frontmatter)."""
    if not markdown.startswith("---"):
        return {}, markdown, False

    parts = markdown.split("---", 2)
    if len(parts) < 3:
        return {}, markdown, False

    raw_fm = parts[1].strip()
    body = parts[2].lstrip("\n")

    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(raw_fm) or {}
        if isinstance(parsed, dict):
            return parsed, body, True
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        logger.debug("Failed to parse YAML frontmatter: %s", exc)

    fm: dict[str, Any] = {}
    for line in raw_fm.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        fm[k.strip()] = v.strip()
    return fm, body, True


def dump_frontmatter(frontmatter: dict[str, Any]) -> str:
    try:
        import yaml  # type: ignore

        dumped = yaml.safe_dump(frontmatter, sort_keys=False).strip()
        return f"---\n{dumped}\n---\n\n"
    except Exception:
        lines = ["---"]
        for k, v in frontmatter.items():
            if v is None:
                continue
            lines.append(f"{k}: {v}")
        lines.append("---\n")
        return "\n".join(lines) + "\n"


def extract_title(markdown_body: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", markdown_body, flags=re.MULTILINE)
    if match:
        return match.group(1).strip()
    return fallback


def split_sections(markdown_body: str) -> tuple[list[str], dict[str, list[str]]]:
    """Return (preamble_lines, sections_by_heading_lower)."""
    lines = markdown_body.splitlines()
    preamble: list[str] = []
    sections: dict[str, list[str]] = {}

    idx = 0
    # Capture preamble: first H1 + content until first H2.
    while idx < len(lines):
        line = lines[idx]
        if line.startswith("## "):
            break
        preamble.append(line)
        idx += 1

    current_heading: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_heading, current_lines
        if current_heading is None:
            return
        sections[current_heading] = current_lines
        current_heading = None
        current_lines = []

    while idx < len(lines):
        line = lines[idx]
        if line.startswith("## "):
            flush()
            current_heading = line[3:].strip().lower()
            current_lines = [line]
        else:
            if current_heading is None:
                # Should not happen, but be safe.
                preamble.append(line)
            else:
                current_lines.append(line)
        idx += 1

    flush()
    return preamble, sections


def extract_commands(markdown_body: str) -> list[str]:
    """Extract command patterns from the '## Commands' section tables."""
    _, sections = split_sections(markdown_body)
    commands_section = sections.get("commands")
    if not commands_section:
        return []

    commands: list[str] = []
    seen: set[str] = set()
    for line in commands_section:
        if "`" not in line or not line.lstrip().startswith("|"):
            continue
        match = re.search(r"`([^`]+)`", line)
        if not match:
            continue
        cmd = match.group(1).strip()
        if not cmd or cmd.lower() == "command":
            continue
        if cmd in seen:
            continue
        seen.add(cmd)
        commands.append(cmd)
    return commands


def normalize_description(value: str) -> str:
    if not value:
        return ""
    if "Triggers" not in value:
        return value.strip().rstrip(" .-")
    return value.split("Triggers", 1)[0].strip().rstrip(" .-")


def ensure_triggers_in_description(description: str, commands: list[str]) -> str:
    if not description:
        description = "Imported skill."
    if "Triggers" in description:
        return description
    triggers = [c for c in commands if len(c) <= 60][:10]
    if not triggers:
        return description
    quoted = ", ".join(f"\"{t}\"" for t in triggers)
    return f"{description}. Triggers - {quoted}."


def trim_skill_markdown(markdown: str, dest_skill_slug: str) -> tuple[str, bool, int]:
    frontmatter, body, had_fm = parse_frontmatter(markdown)
    original_lines = len(markdown.splitlines())

    title = extract_title(body, dest_skill_slug)
    commands = extract_commands(body)

    description = frontmatter.get("description")
    if isinstance(description, str):
        base_desc = normalize_description(description)
    else:
        base_desc = ""

    base_desc = base_desc or title
    frontmatter["name"] = dest_skill_slug
    frontmatter["description"] = ensure_triggers_in_description(base_desc, commands)

    preamble, sections = split_sections(body)

    # Keep a minimal set of sections, dropping lower-priority ones if needed.
    preferred = [
        "overview",
        "storage",
        "commands",
        "modules",
        "module loading",
        "workflow",
        "quick start",
        "references",
    ]

    kept_sections: list[list[str]] = []
    for key in preferred:
        if key in sections:
            kept_sections.append(sections[key])

    trimmed_body_lines = preamble[:]
    for section_lines in kept_sections:
        if trimmed_body_lines and trimmed_body_lines[-1].strip() != "":
            trimmed_body_lines.append("")
        trimmed_body_lines.extend(section_lines)

    footer = [
        "",
        "---",
        "",
        "## Full Documentation",
        "See `references/imported-full-skill.md` for the complete imported SKILL.md.",
    ]
    trimmed_body_lines.extend(footer)

    # Enforce ~100 line budget (excluding frontmatter).
    MAX_BODY_LINES = 100
    while len(trimmed_body_lines) > MAX_BODY_LINES and kept_sections:
        # Drop from the end of preferred list first (lowest priority).
        kept_sections.pop()
        # Rebuild.
        trimmed_body_lines = preamble[:]
        for section_lines in kept_sections:
            if trimmed_body_lines and trimmed_body_lines[-1].strip() != "":
                trimmed_body_lines.append("")
            trimmed_body_lines.extend(section_lines)
        trimmed_body_lines.extend(footer)

        # Avoid infinite loops if preamble alone is huge.
        if not kept_sections:
            break

    if len(trimmed_body_lines) > MAX_BODY_LINES:
        # Hard truncate to keep file small and predictable.
        trimmed_body_lines = trimmed_body_lines[: MAX_BODY_LINES - 3] + ["", "_(Trimmed for brevity.)_", ""] + footer

    trimmed = dump_frontmatter(frontmatter) + "\n".join(trimmed_body_lines).rstrip() + "\n"

    # If original already small, we still normalized frontmatter. Consider that "trimmed" only
    # if we moved content out due to size.
    did_trim = original_lines > (MAX_BODY_LINES + 20)
    return trimmed, did_trim, original_lines


def extract_storage_tree(markdown: str) -> list[str]:
    """Extract lines from the first triple-backtick block under '## Storage'."""
    _, body, _ = parse_frontmatter(markdown)
    lines = body.splitlines()

    start = None
    for i, line in enumerate(lines):
        if line.strip().lower() == "## storage":
            start = i
            break
    if start is None:
        return []

    # Find the first code block after Storage.
    in_block = False
    block_lines: list[str] = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if stripped.startswith("```") and not in_block:
            in_block = True
            continue
        if stripped.startswith("```") and in_block:
            break
        if in_block:
            block_lines.append(line.rstrip("\n"))

    return [line for line in block_lines if line.strip()]


def parse_storage_paths(tree_lines: list[str]) -> tuple[list[Path], list[Path]]:
    """Return (dirs, files) paths relative to the skill data dir.

    Parses a typical tree-like storage block, preserving nesting:

      skill/
      +-- a/
      |   +-- b.txt
      +-- c.md
    """
    dirs: set[Path] = set()
    files: set[Path] = set()

    stack: list[str] = []

    for raw in tree_lines:
        line = raw.rstrip("\n")
        if not line.strip():
            continue

        # Ignore the root label line (e.g., "skill-name/").
        if "\u251c\u2500\u2500" not in line and "\u2514\u2500\u2500" not in line:
            continue

        m = re.search(r"(\u251c\u2500\u2500|\u2514\u2500\u2500)\s+", line)
        if not m:
            continue

        prefix = line[: m.start()]
        depth = max(0, len(prefix) // 4)

        name_part = line[m.end() :]
        if "#" in name_part:
            name_part = name_part.split("#", 1)[0]
        name_part = name_part.strip()
        if not name_part:
            continue

        is_dir = name_part.endswith("/")
        name = name_part.rstrip("/").strip()
        if not name:
            continue

        # Align stack to parent depth.
        if depth < len(stack):
            stack = stack[:depth]

        rel = Path(*stack, name)

        if is_dir or "." not in Path(name).name:
            dirs.add(rel)
            # Descend into this directory for subsequent children.
            stack = stack[:depth] + [name]
        else:
            files.add(rel)
            dirs.add(rel.parent)

    # Ensure parents exist.
    expanded_dirs: set[Path] = set()
    for d in dirs:
        cur = d
        while str(cur) not in (".", ""):
            expanded_dirs.add(cur)
            cur = cur.parent

    return sorted(expanded_dirs), sorted({f for f in files if str(f) not in (".", "")})
