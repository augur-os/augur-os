"""auto-command-help-coverage: repair missing help sections for command skills."""
from __future__ import annotations


import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import re
from pathlib import Path

import yaml

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, make_issue


name = "auto-command-help-coverage"

DIFFICULTY_SPEC = {
    0: "Surface scan — find command skills missing help sections",
    1: "Content check — derive examples, flags, and mode variants from existing docs",
    2: "Deep check — repair missing sections in-place",
}

_HELP_SECTIONS = ("Usage", "Examples", "Options", "Flags", "Mode Selection")
_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_HEADER_RE = re.compile(r"^#\s+(/[\w-]+)", re.MULTILINE)
_CODE_USAGE_RE = re.compile(r"^(/\S.*?)(?:\s{2,}#\s*(.+))?$")
_BULLET_USAGE_RE = re.compile(r"^-\s+`([^`]+)`\s*(?:[—-]\s*(.+))?$")
_FLAG_RE = re.compile(r"(--[a-z0-9-]+(?:\s+<[^>]+>)?)", re.IGNORECASE)
_COMMENT_SPLIT_RE = re.compile(r"\s{2,}#\s*")


def _iter_command_skill_files(project_root: Path) -> list[Path]:
    skill_files: list[Path] = []
    for skill_md in sorted((project_root / "project-brain" / "capabilities" / "skills").glob("*/SKILL.md")):
        frontmatter = _read_frontmatter(skill_md)
        if not frontmatter:
            continue
        if frontmatter.get("x-augur-hub") != "command":
            continue
        if frontmatter.get("x-augur-type") != "command":
            continue
        skill_files.append(skill_md)
    return skill_files


def _read_frontmatter(skill_md: Path) -> dict:
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    try:
        _, fm, _ = text.split("---", 2)
    except ValueError:
        return {}
    data = yaml.safe_load(fm) or {}
    return data if isinstance(data, dict) else {}


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---"):
        return ("", text)
    try:
        _, fm, body = text.split("---", 2)
    except ValueError:
        return ("", text)
    return (f"---{fm}---", body.lstrip("\n"))


def _section_names(body: str) -> set[str]:
    return {match.group(1).strip() for match in _SECTION_RE.finditer(body)}


def _command_name(body: str, skill_name: str) -> str:
    match = _HEADER_RE.search(body)
    if match:
        return match.group(1)
    return f"/{skill_name}"


def _extract_section(body: str, title: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(title)}\s*$\n(?P<content>.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(body)
    return match.group("content").strip("\n") if match else ""


def _normalize_desc(text: str) -> str:
    return " ".join(text.strip().split())


def _extract_usage_entries(body: str, command_name: str) -> list[dict]:
    usage = _extract_section(body, "Usage")
    entries: list[dict] = []
    seen: set[str] = set()
    if usage:
        for raw_line in usage.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            code_match = _CODE_USAGE_RE.match(line)
            bullet_match = _BULLET_USAGE_RE.match(line)
            command = ""
            description = ""
            if bullet_match:
                command = bullet_match.group(1).strip()
                description = _normalize_desc(bullet_match.group(2) or "")
            elif code_match:
                command = code_match.group(1).strip()
                description = _normalize_desc(code_match.group(2) or "")
                if not description and "#" in line:
                    split = _COMMENT_SPLIT_RE.split(line, maxsplit=1)
                    if len(split) == 2:
                        command = split[0].strip()
                        description = _normalize_desc(split[1])
                if not description and " — " in command:
                    split = re.split(r"\s+—\s+", command, maxsplit=1)
                    if len(split) == 2:
                        command = split[0].strip()
                        description = _normalize_desc(split[1])
            if command and command.startswith("/"):
                key = command.lower()
                if key not in seen:
                    entries.append({"command": command, "description": description})
                    seen.add(key)
    if not entries:
        entries.append({"command": command_name, "description": "Default command invocation"})
    return entries


def _flag_descriptions(body: str) -> dict[str, str]:
    descriptions: dict[str, str] = {}
    candidate_sections = [
        _extract_section(body, "Usage"),
        _extract_section(body, "Examples"),
        _extract_section(body, "Options"),
        _extract_section(body, "Flags"),
        _extract_section(body, "Mode Selection"),
    ]
    for section in candidate_sections:
        if not section:
            continue
        for raw_line in section.splitlines():
            line = raw_line.strip()
            if not line or set(line) <= {"|", "-"}:
                continue
            if "--" not in line:
                continue
            flags = _FLAG_RE.findall(line)
            if not flags:
                continue
            desc = ""
            bullet_match = _BULLET_USAGE_RE.match(line)
            if bullet_match:
                desc = _normalize_desc(bullet_match.group(2) or "")
            elif "|" in line and line.count("|") >= 3:
                parts = [part.strip() for part in line.strip("|").split("|")]
                if len(parts) >= 2:
                    desc = _normalize_desc(parts[1])
            elif "—" in line:
                desc = _normalize_desc(line.split("—", 1)[1])
            elif " - " in line:
                desc = _normalize_desc(line.split(" - ", 1)[1])
            elif "#" in line:
                split = _COMMENT_SPLIT_RE.split(line, maxsplit=1)
                if len(split) == 2:
                    desc = _normalize_desc(split[1])
            for flag in flags:
                descriptions.setdefault(flag.strip(), desc or "Document this flag behavior.")
    return descriptions


def _mode_label(entry: dict, command_name: str) -> str | None:
    suffix = entry["command"][len(command_name):].strip() if entry["command"].startswith(command_name) else ""
    if not suffix:
        return "*(none)*"
    token = suffix.split()[0]
    if token.startswith("--"):
        return token
    if token.isalpha() or "-" in token:
        return token
    return None


def _mode_rows(entries: list[dict], command_name: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    has_variant = False
    for entry in entries:
        label = _mode_label(entry, command_name)
        if label is None:
            continue
        if label != "*(none)*":
            has_variant = True
        if label in seen:
            continue
        seen.add(label)
        rows.append({
            "label": label,
            "example": entry["command"],
            "description": entry["description"] or "Documented command variant",
        })
    if not has_variant:
        return []
    return rows


def _missing_sections(body: str, command_name: str) -> tuple[list[str], list[dict], dict[str, str], list[dict]]:
    sections = _section_names(body)
    entries = _extract_usage_entries(body, command_name)
    flags = _flag_descriptions(body)
    modes = _mode_rows(entries, command_name)
    missing: list[str] = []
    if "Usage" not in sections:
        missing.append("Usage")
    if "Examples" not in sections and entries:
        missing.append("Examples")
    if "Options" not in sections and "Flags" not in sections and flags:
        missing.append("Options")
    if "Mode Selection" not in sections and len(modes) > 1:
        missing.append("Mode Selection")
    return (missing, entries, flags, modes)


def _render_usage(entries: list[dict]) -> str:
    commands = "\n".join(entry["command"] for entry in entries)
    return f"## Usage\n\n```bash\n{commands}\n```"


def _render_examples(entries: list[dict]) -> str:
    lines = ["## Examples", ""]
    for entry in entries[:4]:
        lines.append(f"- `{entry['command']}` — {entry['description'] or 'Example invocation'}")
    return "\n".join(lines)


def _render_options(flags: dict[str, str]) -> str:
    lines = [
        "## Options",
        "",
        "| Flag | Description |",
        "|------|-------------|",
    ]
    for flag, desc in sorted(flags.items()):
        lines.append(f"| `{flag}` | {desc} |")
    return "\n".join(lines)


def _render_mode_selection(rows: list[dict]) -> str:
    lines = [
        "## Mode Selection",
        "",
        "| Argument | Example | Description |",
        "|----------|---------|-------------|",
    ]
    for row in rows:
        lines.append(
            f"| `{row['label']}` | `{row['example']}` | {row['description']} |"
        )
    return "\n".join(lines)


def _insert_sections(body: str, sections: list[str]) -> str:
    marker = "## Additional resources"
    insert_at = body.find(marker)
    payload = "\n\n".join(section.strip() for section in sections if section.strip())
    if not payload:
        return body
    if insert_at == -1:
        return body.rstrip() + "\n\n" + payload + "\n"
    prefix = body[:insert_at].rstrip()
    suffix = body[insert_at:].lstrip("\n")
    return prefix + "\n\n" + payload + "\n\n" + suffix


def _apply_fix(text: str, skill_name: str) -> tuple[str, list[str]]:
    _, body = _split_frontmatter(text)
    command_name = _command_name(body, skill_name)
    missing, entries, flags, modes = _missing_sections(body, command_name)
    if not missing:
        return (text, [])

    additions: list[str] = []
    if "Usage" in missing:
        additions.append(_render_usage(entries))
    if "Examples" in missing:
        additions.append(_render_examples(entries))
    if "Options" in missing:
        additions.append(_render_options(flags))
    if "Mode Selection" in missing:
        additions.append(_render_mode_selection(modes))

    updated_body = _insert_sections(body, additions)
    frontmatter, _ = _split_frontmatter(text)
    if frontmatter:
        return (frontmatter + "\n\n" + updated_body.lstrip("\n"), missing)
    return (updated_body, missing)


def scan(ctx: OpsContext) -> ScanResult:
    issues: list[dict] = []
    for skill_md in _iter_command_skill_files(ctx.project_root):
        body = _split_frontmatter(skill_md.read_text(encoding="utf-8"))[1]
        skill_name = skill_md.parent.name
        command_name = _command_name(body, skill_name)
        missing, _, _, _ = _missing_sections(body, command_name)
        if not missing:
            continue
        issues.append(make_issue(
            category=name,
            path=str(skill_md.relative_to(ctx.project_root)),
            detail=(
                f"{skill_name} is missing command help sections: {', '.join(missing)}. "
                f"Next: derive them from the existing skill body so `--help` output is complete."
            ),
            root_cause_type="documentation_gap",
            fixability="auto",
            skill=skill_name,
            command=command_name,
            missing_sections=missing,
        ))

    if not issues:
        return ScanResult(
            issues=[],
            summary="All command skills have complete help coverage",
            severity="info",
            health="verified",
        )

    return ScanResult(
        issues=issues,
        summary=f"Found {len(issues)} command skill(s) with incomplete help coverage",
        severity="warning",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} command help fix(es)")

    changes: list[str] = []
    actions: list[dict] = []
    for issue in issues:
        rel_path = issue.get("path", "")
        if not rel_path:
            continue
        skill_md = ctx.project_root / rel_path
        if not skill_md.exists():
            continue
        original = skill_md.read_text(encoding="utf-8")
        updated, added = _apply_fix(original, issue.get("skill") or skill_md.parent.name)
        if not added or updated == original:
            continue
        skill_md.write_text(updated, encoding="utf-8")
        changes.append(rel_path)
        actions.append({
            "file": rel_path,
            "added_sections": added,
            "status": "fixed",
        })

    if not changes:
        return FixResult(success=True, summary="No command help changes were required", fix_type="verified")

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=f"Repaired command help coverage in {len(changes)} skill file(s)",
        fix_type="code-fix",
    )
