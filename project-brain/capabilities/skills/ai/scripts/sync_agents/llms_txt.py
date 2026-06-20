"""
sync_agents/llms_txt.py

Generator for the repo-root `llms.txt` and `llms-full.txt` files (ADR-746).

These two files give any AI client landing in the Augur repository a
client-neutral doc map. Unlike the per-client constitution files
(`CLAUDE.md`, `CODEX.md`, `AGENTS.md`, ...), `llms.txt` is intentionally
generic — same content for every agent that walks the tree.

The module is pure text composition: no LLM calls, no external HTTP,
no database. It reads source files from `docs/` and writes through the
existing `src.lib.generated_artifacts.write_stable_text` helper so that
two consecutive generations produce byte-identical output and the
`sync_agents check` flow can detect drift the same way it does for the
per-client constitution files.
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

from pathlib import Path

from src.config.paths import get_project_root
from src.lib.generated_artifacts import write_stable_text

# --- Public file names at the repo root ---

LLMS_TXT_NAME = "llms.txt"
LLMS_FULL_TXT_NAME = "llms-full.txt"

# --- Size budgets (bytes), enforced by the generator (ADR-746) ---
#
# `_compose_full` inlines the load-bearing docs in priority order and gracefully
# truncates the lowest-priority body (with a pointer to the complete file) when a
# body would push the output past LLMS_FULL_TXT_MAX_BYTES. The file is therefore
# bounded *by construction*: human-authored docs can grow freely without breaking
# generation, and the size test asserts a guaranteed invariant rather than acting
# as a tripwire that fails on every doc edit.
#
# The ceiling was raised from the original 50 KB once the three curated docs
# alone reached that limit (making the spec's "inline all three in full" intent
# unsatisfiable). 96 KB (~24K tokens) stays trivially consumable by any modern AI
# client while leaving generous headroom for the curated set to grow.
LLMS_TXT_MAX_BYTES = 5 * 1024
LLMS_FULL_TXT_MAX_BYTES = 96 * 1024

# --- Template locations relative to the ai skill root ---

_TEMPLATE_SUBPATH = (
    "project-brain",
    "capabilities",
    "skills",
    "ai",
    "assets",
    "templates",
)
CONCISE_HEADER_NAME = "llms-txt-header.md"
FULL_HEADER_NAME = "llms-full-txt-header.md"

# --- Files inlined verbatim into llms-full.txt (spec section 4.3) ---

_INLINED_SOURCES: tuple[tuple[str, str], ...] = (
    ("docs/agent-topics/agent-rules.md", "docs/agent-topics/agent-rules.md"),
    ("docs/architecture-overview.md", "docs/architecture-overview.md"),
    ("docs/what-is-augur.md", "docs/what-is-augur.md"),
)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _templates_dir(project_root: Path) -> Path:
    """Return the directory holding the curated llms-txt header templates."""
    return project_root.joinpath(*_TEMPLATE_SUBPATH)


def _agent_topics_dir(project_root: Path) -> Path:
    return project_root / "docs" / "agent-topics"


def llms_txt_paths(project_root: Path | None = None) -> tuple[Path, Path]:
    """Return the two repo-root output paths in concise/full order."""
    root = Path(project_root) if project_root is not None else get_project_root()
    return root / LLMS_TXT_NAME, root / LLMS_FULL_TXT_NAME


# ---------------------------------------------------------------------------
# Source reading
# ---------------------------------------------------------------------------


def _load_header(template_path: Path) -> str:
    """Read a header template file.

    Raises FileNotFoundError if the template is missing — header templates are
    committed and required.
    """
    if not template_path.exists():
        raise FileNotFoundError(
            f"Missing llms-txt header template: {template_path}. "
            "Header templates ship under project-brain/capabilities/skills/ai/assets/templates/"
        )
    text = template_path.read_text(encoding="utf-8")
    # Strip the trailing newline so callers can compose with explicit blank lines.
    return text.rstrip("\n")


def _read_topic_title_and_purpose(md_path: Path) -> tuple[str, str]:
    """Extract a topic file's H1 title and a one-line purpose summary.

    The agent-topic files share a stable layout (see ADR-730):

        <optional auto-generated HTML comment block>
        # Title

        > **When to load**: <one-line purpose>

        ...

    We prefer the explicit "When to load" hint when present; otherwise the
    first prose paragraph after the H1. The HTML comment header injected by
    `write_generated_file` is skipped.
    """
    text = md_path.read_text(encoding="utf-8")

    title = ""
    purpose = ""

    in_html_comment = False
    saw_h1 = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        # Skip a leading auto-generated HTML comment block, if any.
        if in_html_comment:
            if "-->" in raw_line:
                in_html_comment = False
            continue
        if line.startswith("<!--"):
            if "-->" not in raw_line:
                in_html_comment = True
            continue
        if not saw_h1:
            if line.startswith("# "):
                title = line[2:].strip()
                saw_h1 = True
            continue
        # After H1: try to extract the "When to load" hint first, falling back
        # to the first plain prose paragraph.
        if line.startswith("> **When to load**"):
            after = line.split(":", 1)
            if len(after) == 2:
                purpose = after[1].strip().rstrip(".")
                break
            continue
        if not line:
            continue
        if line.startswith("#") or line.startswith(">") or line.startswith("```"):
            continue
        if line.startswith(("|", "-", "*", "**", "<")):
            continue
        purpose = line.rstrip(".")
        break

    if not title:
        title = md_path.stem
    return title, purpose


def _enumerate_agent_topics(docs_dir: Path) -> list[tuple[Path, str, str]]:
    """Return sorted list of (path, title, purpose) for `docs/agent-topics/*.md`.

    `agent-rules.md` is included; the composer pulls it to the top of the
    section so consumers can spot the canonical instructions file quickly.
    """
    if not docs_dir.exists():
        return []
    entries: list[tuple[Path, str, str]] = []
    for md_path in sorted(docs_dir.glob("*.md")):
        title, purpose = _read_topic_title_and_purpose(md_path)
        entries.append((md_path, title, purpose))
    return entries


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def _format_topic_line(project_root: Path, md_path: Path, purpose: str) -> str:
    rel = md_path.relative_to(project_root).as_posix()
    if purpose:
        return f"- {rel} — {purpose}"
    return f"- {rel}"


def _compose_concise(project_root: Path) -> str:
    """Compose the body of `llms.txt`.

    Layout follows spec section 4.2: title, hand-curated header, then sections
    for entry points, agent topics, ADRs, and references.
    """
    header_path = _templates_dir(project_root) / CONCISE_HEADER_NAME
    header_text = _load_header(header_path)

    topics = _enumerate_agent_topics(_agent_topics_dir(project_root))

    # Split agent-rules.md out so it leads the agent-topics block.
    rules_lines: list[str] = []
    other_topic_lines: list[str] = []
    for md_path, _title, purpose in topics:
        line = _format_topic_line(project_root, md_path, purpose)
        if md_path.name == "agent-rules.md":
            rules_lines.append(line)
        else:
            other_topic_lines.append(line)

    sections: list[str] = []
    sections.append("# Augur — Local Second Brain for Your AI Clients")
    sections.append("")
    sections.append(header_text)
    sections.append("")
    sections.append("## Entry points")
    sections.append("")
    sections.append("- README.md — repository overview and install entry")
    sections.append("- ROADMAP.md — release roadmap and milestone tracking")
    sections.append("- docs/what-is-augur.md — Augur vs. agents vs. LLM wrappers")
    sections.append(
        "- docs/architecture-overview.md — The Harness, five layers, "
        "runtime substrate"
    )
    sections.append("")
    sections.append("## Agent topics (load on demand)")
    sections.append("")
    if rules_lines:
        sections.extend(rules_lines)
    if other_topic_lines:
        sections.extend(other_topic_lines)
    sections.append("")
    sections.append("## ADRs")
    sections.append("")
    sections.append(
        "- project-brain/decisions/adrs/adrs-index.json — central JSON index of Architecture "
        "Decision Records"
    )
    sections.append("- docs/generated/adr-index.md — human-readable status summary")
    sections.append("- project-brain/decisions/adrs/ — full ADR markdown files (per ADR-811)")
    sections.append("")
    sections.append("## References")
    sections.append("")
    sections.append(
        "- docs/references/surface-decision-matrix.md — canonical map of "
        "skills, commands, MCP tools, and CLI surfaces"
    )
    sections.append(
        "- docs/references/agent-vs-mcp-checklist.md — when to use an agent "
        "vs. an MCP tool"
    )
    sections.append(
        "- docs/references/design-standards.md — UI/UX and code design standards"
    )
    sections.append("")
    sections.append("## Full version")
    sections.append("")
    sections.append(
        "- llms-full.txt — same map with `agent-rules.md`, "
        "`architecture-overview.md`, and `what-is-augur.md` inlined"
    )
    sections.append("")

    return "\n".join(sections)


def _compose_full(project_root: Path, concise_text: str) -> str:
    """Compose the body of `llms-full.txt`, bounded to LLMS_FULL_TXT_MAX_BYTES.

    Layout: compact pointer index, then inlined bodies of the load-bearing files
    in priority order (spec section 4.3). Each body is inlined in full when it
    fits the remaining budget. The first body that would overflow is truncated at
    a line boundary with a pointer to the complete file; any lower-priority body
    then falls back to a pointer-only stub. This keeps the output bounded by
    construction, so doc growth degrades gracefully instead of breaking
    generation (ADR-746).

    In the common case (the curated docs fit the budget) every body is inlined in
    full and the output is byte-identical to a naive full-inline composition.
    """
    text = "# Augur — Local Second Brain for Your AI Clients (Full)\n\n"
    text += _compact_full_pointer_index(concise_text).rstrip("\n") + "\n"

    budget_spent = False
    for rel_label, rel_path in _INLINED_SOURCES:
        source_path = project_root / rel_path
        if source_path.exists():
            body = source_path.read_text(encoding="utf-8").rstrip("\n")
        else:
            body = f"_(missing source file: {rel_label})_"

        section_header = f"\n---\n\n## Inlined: {rel_label}\n\n"
        full_section = f"{section_header}{body}\n"

        if not budget_spent and _byte_len(text + full_section) <= LLMS_FULL_TXT_MAX_BYTES:
            text += full_section
            continue

        # This body overflows (or the budget was already spent by an earlier
        # truncation). Emit a pointer so the consumer can still find the file.
        footer = (
            f"\n\n> _Truncated to fit the llms-full.txt {LLMS_FULL_TXT_MAX_BYTES // 1024} KB "
            f"budget — read the complete file at `{rel_path}`._\n"
        )
        pointer_only = (
            f"{section_header}_(Omitted to fit the size budget — "
            f"read the complete file at `{rel_path}`.)_\n"
        )

        if not budget_spent:
            available = LLMS_FULL_TXT_MAX_BYTES - _byte_len(text + section_header + footer)
            if available > 0:
                truncated = _close_open_code_fence(_truncate_on_line_boundary(body, available))
                text += f"{section_header}{truncated}{footer}"
                budget_spent = True
                continue
            budget_spent = True

        if _byte_len(text + pointer_only) <= LLMS_FULL_TXT_MAX_BYTES:
            text += pointer_only

    return text


def _byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def _truncate_on_line_boundary(text: str, max_bytes: int) -> str:
    """Longest prefix of `text` whose UTF-8 size is <= max_bytes, cut at a
    newline so a line (or a multibyte character) is never split mid-way."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    clipped = encoded[:max_bytes]
    newline = clipped.rfind(b"\n")
    if newline != -1:
        clipped = clipped[:newline]
    return clipped.decode("utf-8", errors="ignore")


def _close_open_code_fence(text: str) -> str:
    """If truncation left an unbalanced ``` fence, append a closing fence so the
    inlined markdown stays well-formed."""
    fences = sum(1 for line in text.splitlines() if line.lstrip().startswith("```"))
    if fences % 2 == 1:
        return f"{text}\n```"
    return text


def _compact_full_pointer_index(concise_text: str) -> str:
    """Keep the concise file's navigational sections without duplicate prose."""
    lines = _demote_top_heading(concise_text).splitlines()
    try:
        entry_idx = lines.index("## Entry points")
    except ValueError:
        return _demote_top_heading(concise_text)
    try:
        full_idx = lines.index("## Full version")
    except ValueError:
        full_idx = len(lines)

    title = lines[0] if lines else "## Augur"
    compact = [title, "", *lines[entry_idx:full_idx]]
    return "\n".join(compact).rstrip("\n")


def _demote_top_heading(text: str) -> str:
    """Demote a leading `# Title` to `## Title` so we keep a single root H1."""
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("# "):
            lines[idx] = "#" + line  # `# x` -> `## x`
            break
        if line.strip() and not line.startswith("<!--"):
            break
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def compose_llms_files(project_root: Path | None = None) -> dict[Path, str]:
    """Return a mapping of {output_path: text} for the two llms files.

    Used by both `generate_llms_files` (which writes) and by `check_mode`
    (which compares against on-disk content).
    """
    root = Path(project_root) if project_root is not None else get_project_root()
    concise_path, full_path = llms_txt_paths(root)
    concise_text = _compose_concise(root)
    full_text = _compose_full(root, concise_text)
    return {concise_path: concise_text, full_path: full_text}


def generate_llms_files(project_root: Path | None = None) -> tuple[Path, Path]:
    """Generate `llms.txt` and `llms-full.txt` at the repo root.

    Returns the two written paths in (concise, full) order. Writes go through
    `write_stable_text` so unchanged files are not rewritten and two
    consecutive runs produce byte-identical output.
    """
    root = Path(project_root) if project_root is not None else get_project_root()
    composed = compose_llms_files(root)
    concise_path, full_path = llms_txt_paths(root)
    write_stable_text(concise_path, composed[concise_path])
    write_stable_text(full_path, composed[full_path])
    return concise_path, full_path


# ---------------------------------------------------------------------------
# Drift detection (consumed by sync_agents.modes.check_mode)
# ---------------------------------------------------------------------------


def llms_files_drift(project_root: Path | None = None) -> list[Path]:
    """Return paths whose on-disk content drifts from the generator output.

    An empty list means both files are up to date. A non-empty list is what
    `sync_agents check` should surface as stale.
    """
    root = Path(project_root) if project_root is not None else get_project_root()
    composed = compose_llms_files(root)
    drift: list[Path] = []
    for path, expected in composed.items():
        if not path.exists():
            drift.append(path)
            continue
        try:
            current = path.read_text(encoding="utf-8")
        except OSError:
            drift.append(path)
            continue
        if current != expected:
            drift.append(path)
    return drift
