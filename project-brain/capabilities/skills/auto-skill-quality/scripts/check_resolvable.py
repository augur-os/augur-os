"""check-resolvable: skill-coverage audit for ADR-741.

Detects unrouted intents, routing collisions, orphaned skills, and stale
capability entries across the Augur skill catalog. Read-only. Deterministic
string + tag analysis. No LLM calls. Writes JSON to
`get_runtime_dir()/quality/resolvable-report.json`.

See `docs/superpowers/specs/2026-05-13-check-resolvable-design.md` for
the algorithm and report schema.
"""

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

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

logger = logging.getLogger(__name__)

AUDITOR_VERSION = "1.1"

# Stop-words trimmed before bigram extraction. Tight list keeps phrase
# fidelity for collision detection.
STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "such",
        "that",
        "the",
        "their",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "were",
        "will",
        "with",
        "use",
        "uses",
        "used",
        "via",
        "your",
        "you",
        "we",
        "our",
        "us",
        "any",
        "all",
        "via",
        "across",
        "based",
        "when",
        "where",
        "how",
        "which",
        "while",
        "without",
    }
)

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9\-]*")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SkillFacts:
    """Per-skill extracted facts used by the four detection passes."""

    skill_id: str
    skill_path: Path
    hub: str | None = None
    description: str = ""
    description_phrases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    declared_commands: list[str] = field(default_factory=list)
    declared_mcp_tools: list[str] = field(default_factory=list)
    declared_dashboard_pages: list[str] = field(default_factory=list)
    has_routine: bool = False


@dataclass
class SurfaceFacts:
    """Per-capability_exposure entry extracted facts."""

    tool_id: str
    primary_surface: str | None = None
    export_to: list[str] = field(default_factory=list)
    owner_kind: str | None = None
    management: str | None = None
    primary_skill: str | None = None  # explicit ownership hint if present


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def _coerce_id_list(value: object) -> list[str]:
    """Normalize an Augur frontmatter list (strings OR `{id: ...}` dicts) to ids.

    Augur skills mix two shapes for `x-augur-commands` / `x-augur-mcp-tools`:
    - plain string list: ``[cmd_a, cmd_b]``
    - dict list with metadata: ``[{id: cmd_a, type: workflow, ...}, ...]``

    Returns a deduped, order-preserving list of bare ids.
    """
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        ident: str | None = None
        if isinstance(item, str):
            ident = item.strip() or None
        elif isinstance(item, dict):
            raw_id = item.get("id") or item.get("name")
            if raw_id is not None:
                ident = str(raw_id).strip() or None
        if ident and ident not in seen:
            seen.add(ident)
            out.append(ident)
    return out


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML frontmatter from a SKILL.md body. Returns {} if absent."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    raw = text[3:end]
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _read_skill_facts(skill_md: Path) -> SkillFacts | None:
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    fm = _parse_frontmatter(text)
    if not fm:
        return None

    name = fm.get("name") or skill_md.parent.name
    facts = SkillFacts(skill_id=str(name), skill_path=skill_md.parent)
    facts.hub = fm.get("x-augur-hub")
    facts.description = (fm.get("description") or "").strip()
    facts.description_phrases = _phrases_from_text(facts.description)

    tags = fm.get("x-augur-tags") or []
    if isinstance(tags, list):
        facts.tags = [
            str(t).strip().lower()
            for t in tags
            if isinstance(t, (str, int, float)) and str(t).strip()
        ]

    facts.declared_commands = _coerce_id_list(fm.get("x-augur-commands"))

    # Also gather commands declared under x-augur-config.commands[].id (canonical Augur shape).
    cfg = fm.get("x-augur-config") or {}
    if isinstance(cfg, dict):
        for cmd_id in _coerce_id_list(cfg.get("commands")):
            if cmd_id not in facts.declared_commands:
                facts.declared_commands.append(cmd_id)

    facts.declared_mcp_tools = _coerce_id_list(fm.get("x-augur-mcp-tools"))
    facts.declared_dashboard_pages = _coerce_id_list(fm.get("x-augur-dashboard-pages"))

    # A skill wired via a scheduled routine/loop (daemon-invoked) is not an
    # orphan even when it declares no command/mcp-tool/page surfaces.
    facts.has_routine = bool(fm.get("x-augur-routine") or fm.get("x-augur-loop"))

    return facts


def _scan_skills(skill_roots: Iterable[Path]) -> list[SkillFacts]:
    """Walk skill roots, parse each SKILL.md, return a list of SkillFacts."""
    seen_paths: set[Path] = set()
    out: list[SkillFacts] = []
    for root in skill_roots:
        if not root or not root.is_dir():
            continue
        for skill_dir in sorted(root.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            try:
                resolved = skill_dir.resolve()
            except OSError:
                continue
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue
            facts = _read_skill_facts(skill_md)
            if facts is not None:
                out.append(facts)
    return out


def _scan_capability_yaml(path: Path) -> list[SurfaceFacts]:
    """Parse `capability_exposure.yaml`, return one SurfaceFacts per capability."""
    if not path.is_file():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    caps = data.get("capabilities", {}) if isinstance(data, dict) else {}
    out: list[SurfaceFacts] = []
    for tool_id, entry in caps.items():
        if not isinstance(entry, dict):
            continue
        export = entry.get("export_to", [])
        export_list = [str(x) for x in export] if isinstance(export, list) else []
        out.append(
            SurfaceFacts(
                tool_id=str(tool_id),
                primary_surface=entry.get("primary_surface"),
                export_to=export_list,
                owner_kind=entry.get("owner_kind"),
                management=entry.get("management"),
                primary_skill=entry.get("primary_skill"),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Phrase extraction
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    return [t for t in _WORD_RE.findall(text.lower()) if t not in STOPWORDS and len(t) > 2]


def _phrases_from_text(text: str) -> list[str]:
    """Return bigrams from text (filtered for stop-words). Order preserved, deduped."""
    tokens = _tokenize(text)
    seen: set[str] = set()
    out: list[str] = []
    for i in range(len(tokens) - 1):
        phrase = f"{tokens[i]} {tokens[i + 1]}"
        if phrase in seen:
            continue
        seen.add(phrase)
        out.append(phrase)
    return out


# ---------------------------------------------------------------------------
# Detection passes
# ---------------------------------------------------------------------------


def _surface_tool_ids(surfaces: list[SurfaceFacts]) -> set[str]:
    """Return the bare tool/command ids declared in capability_exposure.yaml.

    capability_exposure keys are namespaced ('mcp-tool:foo', 'command:adr').
    Return both the namespaced form and the bare form for matching against
    a skill's `x-augur-mcp-tools` / `x-augur-commands` declarations.
    """
    ids: set[str] = set()
    for surf in surfaces:
        ids.add(surf.tool_id)
        if ":" in surf.tool_id:
            ids.add(surf.tool_id.split(":", 1)[1])
    return ids


def _detect_unrouted(
    skills: list[SkillFacts], surfaces: list[SurfaceFacts]
) -> list[dict]:
    """Skills whose declared commands/MCP tools have NO matching surface.

    Dashboard pages are intentionally excluded: capability_exposure.yaml models
    commands/mcp-tools/workflows/skills/etc. but not pages, and page mounts have
    their own source-file verification (`_verify_dashboard_mounts`). Checking
    declared pages against capability_exposure produced false positives (ADR-796).
    """
    surface_ids = _surface_tool_ids(surfaces)
    findings: list[dict] = []
    for s in skills:
        declared = list(s.declared_commands) + list(s.declared_mcp_tools)
        if not declared:
            continue
        for item in declared:
            # Some skills list mcp tools with prefix; check both.
            if item in surface_ids:
                continue
            if f"mcp-tool:{item}" in surface_ids:
                continue
            if f"command:{item}" in surface_ids:
                continue
            findings.append(
                {
                    "skill_id": s.skill_id,
                    "intent_phrase": item,
                    "remediation": (
                        "Add a matching entry to config/system/capability_exposure.yaml "
                        "(or remove the declaration from this skill's SKILL.md)."
                    ),
                }
            )
    findings.sort(key=lambda f: (f["skill_id"], f["intent_phrase"]))
    return findings


def _detect_collisions(
    skills: list[SkillFacts], surfaces: list[SurfaceFacts]
) -> list[dict]:
    """Description bigrams shared by 2+ skills without explicit ownership.

    Category tags (x-augur-tags) are intentionally NOT a collision signal: tags
    exist to GROUP skills (e.g. every routine-* skill is tagged 'autoloop'), so
    sharing one is correct, not a routing conflict (ADR-796). Genuine collisions
    surface as shared distinctive description phrases (or shared declared
    commands), which this still detects."""
    explicit_owners: dict[str, str] = {}
    for surf in surfaces:
        if surf.primary_skill:
            explicit_owners[surf.tool_id] = surf.primary_skill

    phrase_owners: dict[str, set[str]] = {}
    for s in skills:
        for phrase in s.description_phrases:
            phrase_owners.setdefault(phrase, set()).add(s.skill_id)

    findings: list[dict] = []
    for phrase, owners in phrase_owners.items():
        if len(owners) < 2:
            continue
        # Skip if ANY capability entry explicitly owns the phrase.
        if any(phrase == key or phrase in key for key in explicit_owners):
            continue
        findings.append(
            {
                "phrase": phrase,
                "skill_ids": sorted(owners),
                "remediation": (
                    "Declare explicit ownership via `primary_skill:` in "
                    "config/system/capability_exposure.yaml, or differentiate "
                    "the skills' descriptions/tags."
                ),
            }
        )
    findings.sort(key=lambda f: (-len(f["skill_ids"]), f["phrase"]))
    return findings


def _detect_orphans(
    skills: list[SkillFacts], surfaces: list[SurfaceFacts]
) -> list[dict]:
    """Skills with no wiring at all: no declared surface, no routine/loop, and no
    capability entry referencing them.

    A skill wired only via a scheduled routine/loop (daemon-invoked) is NOT an
    orphan — it has no command/mcp-tool/page surface but is still reachable
    (ADR-796)."""
    surface_owners = {surf.primary_skill for surf in surfaces if surf.primary_skill}
    findings: list[dict] = []
    for s in skills:
        has_declared = bool(
            s.declared_commands or s.declared_mcp_tools or s.declared_dashboard_pages
        )
        referenced_by_capability = s.skill_id in surface_owners
        if has_declared or referenced_by_capability or s.has_routine:
            continue
        findings.append(
            {
                "skill_id": s.skill_id,
                "remediation": (
                    "Wire at least one surface (command, MCP tool, or dashboard page) "
                    "in the skill's SKILL.md frontmatter, or move the skill to staging."
                ),
            }
        )
    findings.sort(key=lambda f: f["skill_id"])
    return findings


def _detect_stale(
    skills: list[SkillFacts], surfaces: list[SurfaceFacts]
) -> list[dict]:
    """Capability entries pointing to non-existent skills / MCP tools / commands."""
    skill_ids = {s.skill_id for s in skills}
    all_declared_mcp = {tool for s in skills for tool in s.declared_mcp_tools}
    all_declared_cmds = {cmd for s in skills for cmd in s.declared_commands}

    findings: list[dict] = []
    for surf in surfaces:
        # Stale primary_skill reference.
        if surf.primary_skill and surf.primary_skill not in skill_ids:
            findings.append(
                {
                    "tool_id": surf.tool_id,
                    "remediation": (
                        f"primary_skill '{surf.primary_skill}' is not in the live skill "
                        "catalog; remove the entry or correct the skill id."
                    ),
                }
            )
            continue

        # Tool-id-shaped staleness: an mcp-tool: entry whose bare id is not declared
        # by any skill AND is not augur-framework-owned (those live outside skills).
        if surf.tool_id.startswith("mcp-tool:"):
            bare = surf.tool_id.split(":", 1)[1]
            # Augur framework tools are generated outside skill frontmatter; treat
            # owner_kind=augur AND management=generated as authoritative.
            if surf.owner_kind == "augur" and surf.management == "generated":
                continue
            if bare in all_declared_mcp:
                continue
            findings.append(
                {
                    "tool_id": surf.tool_id,
                    "remediation": (
                        f"MCP tool '{bare}' is not declared by any skill's "
                        "x-augur-mcp-tools; remove from capability_exposure.yaml "
                        "or wire the skill that owns it."
                    ),
                }
            )
        elif surf.tool_id.startswith("command:"):
            bare = surf.tool_id.split(":", 1)[1]
            if surf.owner_kind == "augur" and surf.management == "generated":
                continue
            if bare in all_declared_cmds:
                continue
            findings.append(
                {
                    "tool_id": surf.tool_id,
                    "remediation": (
                        f"Command '{bare}' is not declared by any skill's "
                        "x-augur-commands; remove from capability_exposure.yaml "
                        "or wire the skill that owns it."
                    ),
                }
            )
    findings.sort(key=lambda f: f["tool_id"])
    return findings


def _command_is_tracked_deprecated(skill_path: Path, command_id: str) -> bool:
    """True if commands/<id>.md explicitly marks itself deprecated.

    A command whose body declares x-augur-deprecated: true (or names a successor
    via x-augur-deprecated-in-favor-of) is an intentional, tracked transition
    alias — not silent drift — and must be excluded from the retired-alias guard.
    """
    body = skill_path / "commands" / f"{command_id}.md"
    try:
        text = body.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    fm = _parse_frontmatter(text)
    if fm.get("x-augur-deprecated") is True:
        return True
    return bool(fm.get("x-augur-deprecated-in-favor-of"))


def _command_export_flag(skill_path: Path, command_id: str) -> bool | None:
    """Read x-augur-export-command from a skill's commands/<id>.md body.

    Returns True/False if the flag is present, None if the body file or flag
    is absent (absent flag is treated as 'not a retired alias').
    """
    body = skill_path / "commands" / f"{command_id}.md"
    try:
        text = body.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        logger.debug(
            "retired-alias check: body unreadable for %s/%s",
            skill_path.name,
            command_id,
        )
        return None
    fm = _parse_frontmatter(text)
    value = fm.get("x-augur-export-command")
    if isinstance(value, bool):
        return value
    return None


def _detect_retired_aliases(skills: list[SkillFacts]) -> list[dict]:
    """Commands advertised in x-augur-commands whose body sets x-augur-export-command: false (ADR-796).

    A command id registered in x-augur-commands but whose body file opts out of
    command export is a retired alias still being advertised (ADR-796). The
    router command (export-command: true) is never flagged.
    """
    findings: list[dict] = []
    for s in skills:
        for cmd_id in s.declared_commands:
            if _command_is_tracked_deprecated(s.skill_path, cmd_id):
                continue
            if _command_export_flag(s.skill_path, cmd_id) is False:
                findings.append(
                    {
                        "skill_id": s.skill_id,
                        "command_id": cmd_id,
                        "remediation": (
                            f"'{cmd_id}' is registered in x-augur-commands but its "
                            f"body sets x-augur-export-command: false. Remove the "
                            f"x-augur-commands entry (the body stays as a router "
                            f"dispatch target). See ADR-796."
                        ),
                    }
                )
    findings.sort(key=lambda f: (f["skill_id"], f["command_id"]))
    return findings


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def _compose_report(
    skills: list[SkillFacts],
    surfaces: list[SurfaceFacts],
    unrouted: list[dict],
    collisions: list[dict],
    orphans: list[dict],
    stale: list[dict],
    retired_aliases: list[dict],
) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "auditor_version": AUDITOR_VERSION,
        "summary": {
            "skills_scanned": len(skills),
            "surfaces_scanned": len(surfaces),
            "findings": {
                "unrouted_intents": len(unrouted),
                "routing_collisions": len(collisions),
                "orphaned_skills": len(orphans),
                "stale_capability_entries": len(stale),
                "retired_aliases": len(retired_aliases),
            },
        },
        "findings": {
            "unrouted_intents": unrouted,
            "routing_collisions": collisions,
            "orphaned_skills": orphans,
            "stale_capability_entries": stale,
            "retired_aliases": retired_aliases,
        },
    }


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def _report_path() -> Path:
    from src.config.paths import get_runtime_dir

    return get_runtime_dir() / "quality" / "resolvable-report.json"


def run_audit(
    skill_roots: Iterable[Path] | None = None,
    capability_yaml: Path | None = None,
    *,
    write: bool = True,
    report_path: Path | None = None,
) -> dict:
    """Run the full audit. Returns the report dict; optionally writes it.

    Args:
        skill_roots: skill source dirs to scan. Defaults to
            `get_managed_skill_source_dirs()`.
        capability_yaml: path to capability_exposure.yaml. Defaults to
            `<project_root>/config/system/capability_exposure.yaml`.
        write: when True, writes the report to `report_path`.
        report_path: target file. Defaults to
            `get_runtime_dir()/quality/resolvable-report.json`.
    """
    from src.config.paths import get_managed_skill_source_dirs, get_project_root

    if skill_roots is None:
        skill_roots = get_managed_skill_source_dirs()
    if capability_yaml is None:
        capability_yaml = (
            get_project_root() / "config" / "system" / "capability_exposure.yaml"
        )

    skills = _scan_skills(list(skill_roots))
    surfaces = _scan_capability_yaml(capability_yaml)

    unrouted = _detect_unrouted(skills, surfaces)
    collisions = _detect_collisions(skills, surfaces)
    orphans = _detect_orphans(skills, surfaces)
    stale = _detect_stale(skills, surfaces)
    retired_aliases = _detect_retired_aliases(skills)

    report = _compose_report(skills, surfaces, unrouted, collisions, orphans, stale, retired_aliases)

    if write:
        target = report_path or _report_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        logger.info("check-resolvable wrote report to %s", target)

    return report


def main() -> int:
    """CLI entry — prints the JSON report to stdout."""
    report = run_audit()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
