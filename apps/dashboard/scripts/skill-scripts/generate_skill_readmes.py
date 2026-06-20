#!/usr/bin/env python3
"""
Generate per-skill augur/README.md files from SKILL.md.

Goal: Keep user-facing skill docs (supported commands + prompt examples) in sync as
skills evolve.

Usage:
  python apps/dashboard/scripts/skill-scripts/generate_skill_readmes.py
  python apps/dashboard/scripts/skill-scripts/generate_skill_readmes.py --check
  python apps/dashboard/scripts/skill-scripts/generate_skill_readmes.py --skill knowledge
"""

from __future__ import annotations

import argparse
import re
import sys
import yaml
from dataclasses import dataclass
from pathlib import Path


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _find_repo_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / ".git").exists():
            return parent
        if (parent / "plugins").exists() and (parent / "src").exists():
            return parent
    return start


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
PACKAGES_DIR = REPO_ROOT / "plugins"
PLUGINS_DIR = REPO_ROOT / "plugins"
SKILL_ROOTS = [root for root in (PLUGINS_DIR, PACKAGES_DIR) if root.exists()]


AUTO_HEADER = (
    "<!--\n"
    "  AUTO-GENERATED FILE\n"
    "  - Source: SKILL.md\n"
    "  - Generator: apps/dashboard/scripts/skill-scripts/generate_skill_readmes.py\n"
    "  - Do not edit by hand; update SKILL.md instead.\n"
    "-->\n\n"
)


@dataclass(frozen=True)
class CommandDef:
    group: str | None
    pattern: str
    action: str | None


PLACEHOLDER_EXAMPLES: dict[str, str] = {
    "url": "https://example.com",
    "github-url": "https://github.com/example/repo",
    "description": "a local-first expense tracker with CSV import",
    "path": "~/Documents/example",
    "question": "What did we decide about the roadmap?",
    "query": "vector database performance",
    "company": "ExampleCo",
    "title": "Leading a high-stakes migration",
    "topic": "launching my new product",
    "feature": "new CLI export command",
    "release": "v1.2.0",
    "content": "a short update about our latest release",
    "category": "AI",
    "type": "startup",
    "idea": "An AI tool that summarizes meeting notes",
    "a": "Idea A",
    "b": "Idea B",
    "name": "Jane Doe",
    "contact": "Jane Doe",
    "recipe": "Chicken Shawarma",
    "job": "Senior Backend Engineer at ExampleCo",
    "status": "interviewing",
    "reminder": "Follow up with Jane Doe",
    "days": "7",
    "file": "meeting.m4a",
}


def parse_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    """Return (frontmatter, body)."""
    if not markdown.startswith("---"):
        return {}, markdown

    parts = markdown.split("---", 2)
    if len(parts) < 3:
        return {}, markdown

    raw = parts[1].strip()
    body = parts[2].lstrip("\n")

    try:
        parsed = yaml.safe_load(raw) or {}
    except Exception:
        return {}, body
    
    if not isinstance(parsed, dict):
        return {}, body
        
    return {str(k): str(v) for k, v in parsed.items()}, body


def extract_triggers(description: str) -> list[str]:
    """Extract triggers from description if they follow the 'Triggers:' label."""
    if "Triggers:" not in description:
        return []
    
    parts = description.split("Triggers:", 1)
    trigger_part = parts[1].strip()

    # If there are quotes, assume they are the primary delimiters
    quoted = re.findall(r'"([^"]+)"', trigger_part)
    if quoted:
        return quoted
    
    # Fall back to comma-splitting if no quotes found
    # but only up to the next paragraph/newline or end of string
    trigger_lines = []
    for line in trigger_part.splitlines():
        if not line.strip():
            break
        trigger_lines.append(line.strip())

    if trigger_lines:
        trigger_text = " ".join(trigger_lines)
        return [t.strip() for t in trigger_text.split(",") if t.strip()]
    
    return []


def clean_description(description: str) -> str:
    if "Triggers" not in description:
        return description.strip()
    return description.split("Triggers", 1)[0].rstrip(" .-").strip()


def split_commands_section(lines: list[str]) -> tuple[int | None, int | None]:
    start = None
    for idx, line in enumerate(lines):
        if line.strip() == "## Commands":
            start = idx
            break
    if start is None:
        return None, None

    end = None
    for idx in range(start + 1, len(lines)):
        if re.match(r"^##\s+\S", lines[idx]):
            end = idx
            break
    if end is None:
        end = len(lines)
    return start, end


def parse_commands(commands_lines: list[str]) -> list[CommandDef]:
    commands: list[CommandDef] = []
    seen: set[str] = set()

    current_group: str | None = None
    for raw in commands_lines:
        line = raw.rstrip("\n")

        group_match = re.match(r"^###\s+(.+)$", line.strip())
        if group_match:
            current_group = group_match.group(1).strip()
            continue

        if not line.lstrip().startswith("|"):
            continue
        if "`" not in line:
            continue

        # Parse markdown table row.
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells:
            continue
        if cells[0].lower() == "command":
            continue
        if re.fullmatch(r"-+", cells[0].replace(" ", "")):
            continue

        cmd_match = re.search(r"`([^`]+)`", cells[0])
        if not cmd_match:
            continue

        cmd = cmd_match.group(1).strip()
        if cmd in seen:
            continue
        seen.add(cmd)

        action = None
        if len(cells) >= 2:
            action = " | ".join(cells[1:]).strip() or None

        commands.append(CommandDef(group=current_group, pattern=cmd, action=action))

    return commands


_PLACEHOLDER_RE = re.compile(r"\[([^\]]+)\]")


def _example_for_placeholder(raw_key: str) -> str:
    key = raw_key.strip()

    # Numeric ranges like [1-5] or [0-10]
    numeric_range = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", key)
    if numeric_range:
        return numeric_range.group(2)

    normalized = key.lower()
    return PLACEHOLDER_EXAMPLES.get(normalized, f"<{key}>")


def _example_for_placeholder_in_command(raw_key: str, command: str) -> str:
    key = raw_key.strip()
    normalized = key.lower()

    if normalized == "name":
        lowered = command.lower().strip()
        if "skill" in lowered or lowered.startswith("scaffold:") or lowered.startswith("validate skill"):
            return "expense-tracker"
        return "Jane Doe"

    # Prefer the global mapping for everything else.
    return _example_for_placeholder(key)


def command_to_example(command: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return _example_for_placeholder_in_command(match.group(1), command)

    return _PLACEHOLDER_RE.sub(replace, command)


def build_prompt_examples_section(commands: list[CommandDef], triggers: list[str]) -> str:
    lines: list[str] = ["## Prompt Examples", ""]

    if not commands and not triggers:
        lines.append("_No prompt examples available._")
        lines.append("")
        return "\n".join(lines)

    if commands:
        lines.append("Use these commands as copy/paste starters:")
        lines.append("")

        grouped: dict[str | None, list[CommandDef]] = {}
        group_order: list[str | None] = []
        for cmd in commands:
            if cmd.group not in grouped:
                group_order.append(cmd.group)
                grouped[cmd.group] = []
            grouped[cmd.group].append(cmd)

        for group in group_order:
            if group is not None:
                lines.append(f"### {group}")
                lines.append("")
            for cmd in grouped[group]:
                lines.append(f"- `{command_to_example(cmd.pattern)}`")
            lines.append("")

    if triggers:
        lines.append("Other trigger phrases that should route to this skill:")
        lines.append("")
        for t in triggers:
            lines.append(f"- `{t}`")
        lines.append("")

    return "\n".join(lines)


def generate_readme(skill_dir: Path) -> str:
    skill_md_path = skill_dir / "SKILL.md"
    raw = skill_md_path.read_text(encoding="utf-8")

    frontmatter, body = parse_frontmatter(raw)
    description = clean_description(frontmatter.get("description", ""))
    triggers = extract_triggers(frontmatter.get("description", ""))

    body_lines = body.splitlines()

    if description:
        # Insert description right under the first H1 for better README ergonomics.
        out_lines: list[str] = []
        inserted = False
        for line in body_lines:
            out_lines.append(line)
            if not inserted and re.match(r"^#\s+", line):
                out_lines.append("")
                out_lines.append(description)
                out_lines.append("")
                inserted = True
        body_lines = out_lines

    start, end = split_commands_section(body_lines)
    commands: list[CommandDef] = []
    if start is not None and end is not None:
        commands = parse_commands(body_lines[start + 1 : end])

    prompt_examples = build_prompt_examples_section(commands=commands, triggers=triggers)

    # Insert prompt examples right after Commands section (before next H2).
    if start is not None and end is not None:
        updated = body_lines[:end] + ["", prompt_examples.rstrip(), ""] + body_lines[end:]
        body_with_examples = "\n".join(updated).rstrip() + "\n"
    else:
        body_with_examples = (body.rstrip() + "\n\n" + prompt_examples).rstrip() + "\n"

    return AUTO_HEADER + body_with_examples


def list_skill_dirs() -> list[Path]:
    dirs: list[Path] = []
    for root in SKILL_ROOTS:
        if root.name == "plugins":
            # Legacy plugin bundle layout: plugins/{bundle}/skills/{skill}/SKILL.md
            candidates = root.glob("*/skills/*/SKILL.md")
        else:
            # Fallback to recursive scan for legacy layouts
            candidates = root.rglob("SKILL.md")
        for skill_file in sorted(candidates):
            d = skill_file.parent
            if d.name == "augur-mcp":
                continue
            dirs.append(d)
    return dirs


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate per-skill augur/README.md files from SKILL.md")
    parser.add_argument("--skill", help="Only generate for this skill directory name (e.g. job-analyzer)")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; fail if any augur/README.md is out of date",
    )
    args = parser.parse_args()

    skill_dirs = list_skill_dirs()
    if args.skill:
        skill_dirs = [d for d in skill_dirs if d.name == args.skill]
        if not skill_dirs:
            roots = ", ".join(str(r) for r in SKILL_ROOTS) or str(REPO_ROOT)
            _out(f"Error: skill '{args.skill}' not found under {roots}", file=sys.stderr)
            return 2

    dirty: list[str] = []
    for skill_dir in skill_dirs:
        target = skill_dir / "augur" / "README.md"
        generated = generate_readme(skill_dir)

        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current != generated:
            if args.check:
                dirty.append(str(target.relative_to(REPO_ROOT)))
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(generated, encoding="utf-8")
                _out(f"✅ Wrote {target.relative_to(REPO_ROOT)}")

    if args.check:
        if dirty:
            _out("augur/README.md files out of date:", file=sys.stderr)
            for p in dirty:
                _out(f" - {p}", file=sys.stderr)
            _out(
                "\nRun: python project-brain/capabilities/skills/mcp-app-factory/scripts/generate_skill_readmes.py",
                file=sys.stderr,
            )
            return 1
        _out("✅ All skill augur/README.md files are up to date.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
