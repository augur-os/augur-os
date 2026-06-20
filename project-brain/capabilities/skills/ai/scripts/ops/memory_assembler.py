"""Multi-client memory discovery + assembly for Augur.

Scans per-client memory directories (Claude Code, Gemini, Codex, etc.),
discovers .md entries with YAML frontmatter, deduplicates and filters noise.

ADR-772: client-native memory is review *input*, not canonical state. The sync
path no longer auto-promotes raw client memory into a brain's ``memory/entries/``.
Discovery now feeds the **memory review queue** (:func:`collect_review_candidates`
/ :func:`to_review_candidates`), and promotion into canonical brain memory is an
explicit, reviewed action (``/workspace/memory-review`` / ``memory-review-approve``).

:func:`assemble` (and its ``assemble_to_vault`` / index generators) is retained
as an explicit library/migration utility — full bulk assembly with cross-client
index generation — but is no longer invoked by ``sync_agents`` or the nightly
loop. It produces:
  - Vault entries/ directory with prefixed, assembled copies
  - Linked client MEMORY.md indexes where a client supports them
  - Vault index (full markdown table)
  - Flat client indexes (inlined content)
  - Antigravity instruction section updates (import-style references)
"""
# TODO_CLEANUP: This file is 831 lines — consider splitting into smaller modules

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
import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

from src.config.paths import get_claude_native_memory_dir, get_memory_dir
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

log = logging.getLogger(__name__)

name = "auto-memory-sync"

_SKIP_FILES = {"MEMORY.md", "stale-entries-report.md"}
_VAULT_INDEX_BEGIN = "<!-- AUGUR-ASSEMBLED-INDEX:BEGIN -->"
_VAULT_INDEX_END = "<!-- AUGUR-ASSEMBLED-INDEX:END -->"


def _encode_project_path(project_root: Path) -> str:
    """Return the client-safe project path encoding used by Claude Code."""
    return str(project_root.resolve()).replace("\\", "-").replace("/", "-").replace(":", "-")


def resolve_default_client_memory_plan(
    *,
    project_root: Path,
    home: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve default memory source and output locations for supported clients.

    This is intentionally client-neutral: Claude Code, Codex, Gemini, Cursor,
    Copilot, Kimi, and Antigravity are data entries in one plan. Individual
    clients may still need different output formats, but discovery and
    orchestration should not make Claude the architectural default.
    """
    root = Path(project_root).resolve()
    home_dir = Path(home).resolve() if home is not None else Path.home()
    env_map = env if env is not None else os.environ

    sources: dict[str, Path] = {}
    outputs: list[dict[str, Any]] = []

    claude_memory = (
        home_dir
        / ".claude"
        / "projects"
        / _encode_project_path(root)
        / "memory"
    )
    if claude_memory.is_dir():
        sources["claude-code"] = claude_memory
        outputs.append(
            {
                "client": "claude-code",
                "kind": "linked_index",
                "dir": claude_memory,
                "filename": "MEMORY.md",
                "budget": 190,
                "prepend_digest": True,
            }
        )

    codex_home = Path(env_map.get("CODEX_HOME", str(home_dir / ".codex")))
    if codex_home.is_dir():
        sources["codex"] = codex_home
        outputs.append(
            {
                "client": "codex",
                "kind": "flat_index",
                "path": codex_home / "augur-memory.md",
            }
        )

    gemini_memory = root / ".antigravity" / "memory"
    if gemini_memory.is_dir():
        sources["gemini"] = gemini_memory
    gemini_md = root / ".antigravity" / "ANTIGRAVITY.md"
    if gemini_md.exists():
        outputs.append(
            {
                "client": "gemini",
                "kind": "gemini_imports",
                "path": gemini_md,
            }
        )

    cursor_memory = root / ".cursor" / "memory"
    if cursor_memory.is_dir():
        sources["cursor"] = cursor_memory
        outputs.append(
            {
                "client": "cursor",
                "kind": "flat_index",
                "path": cursor_memory / "augur-memory.md",
            }
        )

    github_dir = root / ".github"
    if github_dir.is_dir():
        outputs.append(
            {
                "client": "copilot",
                "kind": "flat_index",
                "path": github_dir / "copilot-memory.md",
            }
        )

    kimi_home = home_dir / ".kimi"
    if kimi_home.is_dir():
        outputs.append(
            {
                "client": "kimi",
                "kind": "flat_index",
                "path": kimi_home / "augur-memory.md",
            }
        )

    antigravity_memory = root / ".antigravity" / "memory"
    if antigravity_memory.parent.is_dir():
        outputs.append(
            {
                "client": "antigravity",
                "kind": "flat_index",
                "path": antigravity_memory / "augur-memory.md",
            }
        )

    return {"sources": sources, "outputs": outputs}

# Patterns matched as commit noise
_NOISE_PATTERNS = [
    re.compile(r"^chore\(sync\):\s*regenerate", re.IGNORECASE),
    re.compile(r"^session\s+checkpoint", re.IGNORECASE),
    # Bare commit messages like "fix(scope): desc (abc1234, 5 files)"
    re.compile(
        r"^(fix|feat|chore|refactor|docs|style|test|ci|build|perf)\([^)]*\):\s*.+\([a-f0-9]+,\s*\d+\s+files?\)$",
        re.IGNORECASE,
    ),
]


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def _parse_frontmatter(path: Path) -> dict | None:
    """Parse YAML frontmatter from a .md file.

    Returns a dict with all frontmatter keys plus:
      - ``_body``: the markdown body after the closing ``---``
      - ``_raw``: the full raw file content

    Returns ``None`` if the file cannot be read or has no valid frontmatter.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        log.warning("Cannot read %s", path)
        return None

    if not content.startswith("---"):
        return None

    end = content.find("\n---", 4)
    if end == -1:
        return None

    yaml_block = content[4:end]
    body = content[end + 4:]  # skip \n---
    if body.startswith("\n"):
        body = body[1:]

    try:
        meta = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        log.warning("Invalid YAML frontmatter in %s", path)
        return None

    if not isinstance(meta, dict):
        return None

    meta["_body"] = body
    meta["_raw"] = content
    return meta


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_entries(memory_dir: Path, expected_client: str) -> list[dict]:
    """Find valid .md memory entries in a client directory.

    Skips files in ``_SKIP_FILES``, non-.md files, and files whose
    ``written-by`` frontmatter field does not match *expected_client*.

    Returns a list of normalised entry dicts with keys:
        name, type, written_by, created, updated, description,
        source_path, body, raw
    """
    if not memory_dir.is_dir():
        log.debug("Memory dir does not exist: %s", memory_dir)
        return []

    entries: list[dict] = []
    for md_file in sorted(memory_dir.glob("*.md")):
        if md_file.name in _SKIP_FILES:
            continue

        meta = _parse_frontmatter(md_file)
        if meta is None:
            log.debug("Skipping %s (no valid frontmatter)", md_file.name)
            continue

        written_by = meta.get("written-by", expected_client)
        if written_by != expected_client:
            log.debug(
                "Skipping %s (written-by=%s, expected=%s)",
                md_file.name,
                written_by,
                expected_client,
            )
            continue

        entries.append(
            {
                "name": meta.get("name", md_file.stem),
                "type": meta.get("type", "unknown"),
                "written_by": written_by,
                "created": str(meta.get("created", "")),
                "updated": str(meta.get("updated", "")),
                "description": str(meta.get("description", "")),
                "source_path": md_file,
                "body": meta.get("_body", ""),
                "raw": meta.get("_raw", ""),
            }
        )

    return entries


# ---------------------------------------------------------------------------
# Review candidates (ADR-772) — client memory as review *input*, not auto-promote
# ---------------------------------------------------------------------------


def to_review_candidates(entries: list[dict]) -> list:
    """Map discovered client memory entries to memory-review ``Candidate``s.

    Uses the assembler's canonical ``<client>_<source-filename>`` naming so an
    already-promoted (legacy auto-assembled) entry is detected as ``promoted``
    and a newly approved candidate reuses the same canonical filename.
    """
    from src.lib.memory_review import make_candidate

    candidates: list = []
    for entry in entries:
        source = entry.get("source_path")
        client = str(entry.get("written_by") or "user")
        name = str(entry.get("name") or (source.stem if source is not None else "entry"))
        candidates.append(
            make_candidate(
                client=client,
                name=name,
                description=str(entry.get("description") or ""),
                body=str(entry.get("body") or ""),
                kind=str(entry.get("type") or ""),
                source=f"client:{client}",
                origin=str(source) if source is not None else "",
                created=str(entry.get("updated") or entry.get("created") or ""),
                target_filename=(
                    f"{client}_{source.name}" if source is not None else None
                ),
            )
        )
    return candidates


_REVIEW_CLIENT_PREFIXES = {"claude-code", "codex", "gemini", "copilot", "cursor", "user", "augur", "agent"}


def _written_by_from_entry(path: Path, meta: dict) -> str:
    """Best-effort client attribution for an on-disk brain memory entry."""
    source = str(meta.get("source") or "")
    if source.startswith("client:"):
        return source.split(":", 1)[1] or "user"
    stem = path.stem
    if "_" in stem:
        prefix = stem.split("_", 1)[0]
        if prefix in _REVIEW_CLIENT_PREFIXES:
            return prefix
    return "user"


def reindex_brain_memory(memory_dir: Path) -> Path | None:
    """Rebuild the brain's ``MEMORY.md`` index table from its ``entries/`` dir.

    ADR-772: with auto-promotion removed, approved entries land in
    ``memory_dir/entries`` via the review gate. This keeps the human-readable
    vault index (``memory_dir/MEMORY.md``) in lockstep by regenerating the
    managed ``AUGUR-ASSEMBLED-INDEX`` block from the actual on-disk entries,
    preserving any user-curated content outside the block. Returns the index
    path, or ``None`` when there is no entries dir.
    """
    entries_dir = memory_dir / "entries"
    if not entries_dir.is_dir():
        return None

    entries: list[dict] = []
    for path in sorted(entries_dir.glob("*.md")):
        meta = _parse_frontmatter(path)
        if meta is None:
            continue
        entries.append(
            {
                "written_by": _written_by_from_entry(path, meta),
                "type": str(meta.get("type") or "unknown"),
                "name": str(meta.get("name") or path.stem),
                "description": str(meta.get("description") or ""),
                "updated": str(meta.get("reviewed_at") or meta.get("updated") or ""),
                "created": str(meta.get("created") or ""),
            }
        )

    index_path = memory_dir / "MEMORY.md"
    generated = generate_vault_index(entries)
    existing = index_path.read_text(encoding="utf-8") if index_path.exists() else ""
    index_path.write_text(merge_vault_index(existing, generated), encoding="utf-8")
    return index_path


def collect_review_candidates(project_roots: list[Path] | None = None) -> list:
    """Discover + quality-gate client memory across roots → review candidates.

    Client-native memory is keyed to the repo path the client ran in, so callers
    may pass several roots (e.g. a worktree and its main checkout). Candidates
    are de-duplicated by id across roots.
    """
    if not project_roots:
        project_roots = [get_memory_dir().parent]  # best-effort default

    seen: set[str] = set()
    out: list = []
    for project_root in project_roots:
        try:
            plan = resolve_default_client_memory_plan(project_root=Path(project_root))
        except Exception:
            continue
        discovered: list[dict] = []
        for client_id, memory_dir in plan.get("sources", {}).items():
            discovered.extend(discover_entries(memory_dir, client_id))
        gated = quality_gate(discovered)
        for cand in to_review_candidates(gated):
            if cand.id in seen:
                continue
            seen.add(cand.id)
            out.append(cand)
    return out


# ---------------------------------------------------------------------------
# Quality gate helpers
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Normalise text for deduplication.

    Strips commit hashes (7+ hex chars), file counts like ``5 files``,
    collapses whitespace, and lowercases.
    """
    text = re.sub(r"\b[a-f0-9]{7,}\b", "", text)
    text = re.sub(r"\d+\s+files?", "", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _is_noise(description: str) -> bool:
    """Return True if *description* matches a known noise pattern."""
    desc = description.strip()
    if not desc:
        return True
    return any(p.search(desc) for p in _NOISE_PATTERNS)


_SUPERSEDED_RE = re.compile(r"SUPERSEDED\s+by\s+(\S+)", re.IGNORECASE)


def _is_superseded(entry: dict) -> bool:
    """Return True if entry body or description contains a SUPERSEDED marker."""
    for field in ("description", "body"):
        text = entry.get(field, "")
        if _SUPERSEDED_RE.search(text):
            return True
    return False


def quality_gate(entries: list[dict]) -> list[dict]:
    """Filter noise, superseded entries, and deduplicate by normalised description."""
    seen: set[str] = set()
    result: list[dict] = []

    for entry in entries:
        desc = entry.get("description", "")
        if _is_noise(desc):
            log.debug("Noise filtered: %s", entry.get("name"))
            continue

        if _is_superseded(entry):
            log.info("Superseded filtered: %s", entry.get("name"))
            continue

        norm = _normalize(desc)
        if norm in seen:
            log.debug("Duplicate filtered: %s", entry.get("name"))
            continue

        seen.add(norm)
        result.append(entry)

    return result


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


_PSEUDO_FRONTMATTER_KEYS = {"_body", "_raw"}


def _parse_frontmatter_content(content: str) -> tuple[dict[str, Any], str] | None:
    """Parse YAML frontmatter from an in-memory markdown string."""
    if not content.startswith("---"):
        return None

    end = content.find("\n---", 4)
    if end == -1:
        return None

    yaml_block = content[4:end]
    body = content[end + 4:]
    if body.startswith("\n"):
        body = body[1:]

    try:
        meta = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        return None

    if not isinstance(meta, dict):
        return None
    return meta, body


def _dump_frontmatter_content(meta: dict[str, Any], body: str) -> str:
    yaml_block = yaml.dump(
        dict(meta),
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).rstrip("\n")
    parts = ["---", yaml_block, "---", ""]
    if body:
        parts.append(body)
    content = "\n".join(parts)
    if not content.endswith("\n"):
        content += "\n"
    return content


def _preserve_existing_system_frontmatter(content: str, target: Path) -> str:
    """Preserve graph/system fields already attached to assembled vault entries."""
    if not target.exists():
        return content

    existing = _parse_frontmatter(target)
    incoming = _parse_frontmatter_content(content)
    if existing is None or incoming is None:
        return content

    incoming_meta, body = incoming
    changed = False
    for key, value in existing.items():
        if key in _PSEUDO_FRONTMATTER_KEYS:
            continue
        if isinstance(key, str) and key.startswith("_") and key not in incoming_meta:
            incoming_meta[key] = value
            changed = True

    if not changed:
        return content
    return _dump_frontmatter_content(incoming_meta, body)


def assemble_to_vault(
    entries: list[dict], vault_memory_dir: Path
) -> list[Path]:
    """Copy entries to ``vault_memory_dir/entries/`` with client prefix.

    File naming: ``{client_id}_{original_filename}``.
    Each file keeps YAML frontmatter at line 1 and inserts the assembled-by
    HTML comment immediately after the closing frontmatter block.
    Skips writing when the target file already has identical content.

    Returns the list of paths that were written (new or changed).
    """
    out_dir = vault_memory_dir / "entries"
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for entry in entries:
        source: Path = entry["source_path"]
        client_id = entry["written_by"]
        target_name = f"{client_id}_{source.name}"
        target = out_dir / target_name

        header = f"<!-- ASSEMBLED by memory_assembler from {client_id} -->"
        raw = entry["raw"]
        if raw.startswith("---"):
            end = raw.find("\n---", 4)
            if end != -1:
                frontmatter = raw[: end + 4]
                body = raw[end + 4:]
                if body.startswith("\n"):
                    body = body[1:]
                content = frontmatter + "\n" + header + "\n\n" + body
            else:
                content = header + "\n" + raw
        else:
            content = header + "\n" + raw

        content = _preserve_existing_system_frontmatter(content, target)

        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if existing == content:
                continue

        target.write_text(content, encoding="utf-8")
        written.append(target)

    return written


# ---------------------------------------------------------------------------
# Index generation
# ---------------------------------------------------------------------------


def _prepend_digest_sections(memory_dir: Path, index_content: str) -> str:
    """Prepend agent-digest Hot/Warm sections before the Memory Index.

    Reads digest-hot.md and digest-warm.md from memory_dir (written by
    auto-agent-digest nightly loop) and inserts them between the
    ``# Augur Memory`` header and the entry list.

    If digest files don't exist, returns index_content unchanged.
    """
    sections = []

    hot_path = memory_dir / "digest-hot.md"
    if hot_path.exists():
        sections.append(hot_path.read_text().strip())

    warm_path = memory_dir / "digest-warm.md"
    if warm_path.exists():
        sections.append(warm_path.read_text().strip())

    if not sections:
        return index_content

    header = "# Augur Memory\n"
    if index_content.startswith(header):
        body = index_content[len(header):].lstrip("\n")
        return header + "\n" + "\n\n".join(sections) + "\n\n" + body
    return "\n\n".join(sections) + "\n\n" + index_content


def generate_linked_index(entries: list[dict], budget: int = 190) -> str:
    """Generate a curated linked memory index.

    Entries are sorted by ``updated`` (then ``created``) descending and
    rendered as ``[name](file.md) -- description`` links.  Truncated at
    *budget* lines.
    """

    def _sort_key(e: dict) -> str:
        return str(e.get("updated") or e.get("created") or "")

    sorted_entries = sorted(entries, key=_sort_key, reverse=True)

    lines = ["# Augur Memory", ""]
    for entry in sorted_entries[:budget]:
        source: Path = entry["source_path"]
        name = entry.get("name", source.stem)
        desc = entry.get("description", "")
        line = f"- [{name}]({source.name})"
        if desc:
            line += f" -- {desc}"
        lines.append(line)

    lines.append("")
    return "\n".join(lines)


def generate_claude_index(entries: list[dict], budget: int = 190) -> str:
    """Backward-compatible wrapper for Claude Code's linked index format."""
    return generate_linked_index(entries, budget=budget)


def generate_vault_index(entries: list[dict]) -> str:
    """Generate a full markdown table index for the vault.

    Columns: Date, Client, Type, Name, Description.
    """

    def _sort_key(e: dict) -> str:
        return str(e.get("updated") or e.get("created") or "")

    sorted_entries = sorted(entries, key=_sort_key, reverse=True)

    lines = [
        "# Augur Memory Index",
        "",
        "| Date | Client | Type | Name | Description |",
        "|------|--------|------|------|-------------|",
    ]
    for entry in sorted_entries:
        date = str(entry.get("updated") or entry.get("created") or "")
        client = entry.get("written_by", "")
        etype = entry.get("type", "")
        name = entry.get("name", "")
        desc = entry.get("description", "")
        lines.append(f"| {date} | {client} | {etype} | {name} | {desc} |")

    lines.append("")
    return "\n".join(lines)


def _has_existing_vault_memory_payload(vault_memory_dir: Path) -> bool:
    """Return True when the vault already contains durable assembled memory."""
    entries_dir = vault_memory_dir / "entries"
    try:
        if entries_dir.is_dir() and any(entries_dir.glob("*.md")):
            return True
    except OSError:
        return False

    vault_index = vault_memory_dir / "MEMORY.md"
    if not vault_index.exists():
        return False
    try:
        existing = vault_index.read_text(encoding="utf-8")
    except OSError:
        return False

    if _VAULT_INDEX_BEGIN in existing and _VAULT_INDEX_END in existing:
        _prefix, rest = existing.split(_VAULT_INDEX_BEGIN, 1)
        old_block, _suffix = rest.split(_VAULT_INDEX_END, 1)
        table_rows = [
            line for line in old_block.splitlines()
            if line.startswith("|") and "---" not in line
        ]
        return len(table_rows) > 1

    return bool(_legacy_preserved_vault_memory(existing))


def _legacy_preserved_vault_memory(existing: str) -> str:
    """Return user-curated content from a pre-marker vault MEMORY.md.

    Older versions wrote the generated table at the top of the durable memory
    file without markers. Preserve any sections after that table so sync does
    not erase curated decisions while migrating to a managed block.
    """
    if not existing.strip():
        return ""

    lines = existing.splitlines()
    if not lines or not lines[0].startswith("# Augur Memory Index"):
        return existing.strip()

    index = 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    while index < len(lines) and lines[index].startswith("|"):
        index += 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    return "\n".join(lines[index:]).strip()


def merge_vault_index(existing: str, generated_index: str) -> str:
    """Merge generated vault index with preserved curated memory sections."""
    managed_block = (
        f"{_VAULT_INDEX_BEGIN}\n"
        f"{generated_index.rstrip()}\n"
        f"{_VAULT_INDEX_END}\n"
    )

    if _VAULT_INDEX_BEGIN in existing and _VAULT_INDEX_END in existing:
        prefix, rest = existing.split(_VAULT_INDEX_BEGIN, 1)
        _old_block, suffix = rest.split(_VAULT_INDEX_END, 1)
        return f"{prefix.rstrip()}\n\n{managed_block}{suffix.lstrip()}"

    preserved = _legacy_preserved_vault_memory(existing)
    if not preserved:
        return managed_block
    return f"{managed_block}\n{preserved.rstrip()}\n"


def generate_flat_index(entries: list[dict]) -> str:
    """Generate a flat markdown index inlining all entry bodies.

    Designed for Codex, which prefers a single file with all content.
    """

    def _sort_key(e: dict) -> str:
        return str(e.get("updated") or e.get("created") or "")

    sorted_entries = sorted(entries, key=_sort_key, reverse=True)

    lines = ["# Augur Memory (flat)", ""]
    for entry in sorted_entries:
        name = entry.get("name", "")
        written_by = entry.get("written_by", "")
        desc = entry.get("description", "")
        body = entry.get("body", "").strip()

        lines.append(f"## {name}")
        lines.append(f"*Written by: {written_by}*")
        if desc:
            lines.append(f"\n{desc}")
        if body:
            lines.append(f"\n{body}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gemini integration
# ---------------------------------------------------------------------------


def _update_gemini_imports(
    entries: list[dict], gemini_md_path: Path
) -> None:
    """Replace the ``## Augur Memories`` section in GEMINI.md.

    Inserts ``@./memory/{filename}`` import lines for each entry and copies
    the referenced files into ``{gemini_md_path.parent}/memory/`` so the
    relative imports resolve. Creates the section if it does not exist.
    """
    if not gemini_md_path.exists():
        log.warning("GEMINI.md not found at %s", gemini_md_path)
        return

    content = gemini_md_path.read_text(encoding="utf-8")

    # Materialize referenced files in the directory the imports resolve against.
    # Cross-client entries get a header; entries already written by Gemini live
    # in this dir as their source and are skipped.
    gemini_memory_dir = gemini_md_path.parent / "memory"
    gemini_memory_dir.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        if entry.get("written_by") == "gemini":
            continue
        src: Path = entry["source_path"]
        target = gemini_memory_dir / src.name
        header = f"<!-- CROSS-CLIENT from {entry.get('written_by', 'unknown')} -->\n"
        body = entry.get("raw") or ""
        if not body and src.exists():
            try:
                body = src.read_text(encoding="utf-8")
            except OSError:
                body = ""
        new_content = header + body
        if target.exists():
            try:
                if target.read_text(encoding="utf-8") == new_content:
                    continue
            except OSError:
                pass
        target.write_text(new_content, encoding="utf-8")

    import_lines = []
    for entry in entries:
        source: Path = entry["source_path"]
        import_lines.append(f"@./memory/{source.name}")
    import_block = "\n".join(import_lines)

    section_header = "## Augur Memories"
    section_re = re.compile(
        r"(## Augur Memories\n)(.*?)(?=\n## |\Z)", re.DOTALL
    )

    if section_re.search(content):
        new_content = section_re.sub(
            f"{section_header}\n\n{import_block}\n", content
        )
    else:
        # Append section at end
        new_content = content.rstrip("\n") + f"\n\n{section_header}\n\n{import_block}\n"

    # Handle read-only generated files (e.g. GEMINI.md is 0o444)
    import os
    needs_restore = False
    if not os.access(gemini_md_path, os.W_OK):
        current_mode = gemini_md_path.stat().st_mode
        gemini_md_path.chmod(current_mode | 0o200)
        needs_restore = True

    gemini_md_path.write_text(new_content, encoding="utf-8")

    if needs_restore:
        gemini_md_path.chmod(0o444)


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def assemble(
    sources: dict[str, Path],
    vault_memory_dir: Path,
    claude_native_dir: Path | None = None,
    gemini_md_path: Path | None = None,
    codex_memory_path: Path | None = None,
    client_outputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Full assembly pipeline.

    Parameters
    ----------
    sources
        Mapping of ``{client_id: memory_dir_path}`` to scan.
    vault_memory_dir
        Target directory in the vault for assembled entries and index.
    claude_native_dir
        Legacy compatibility parameter. If provided, mapped to a linked
        ``MEMORY.md`` client output.
    gemini_md_path
        If provided, update the Augur Memories section in this file.
    codex_memory_path
        If provided, write the flat index to this file.
    client_outputs
        Generic output descriptors. Supported kinds: ``linked_index``,
        ``flat_index``, and ``gemini_imports``. Legacy client-specific
        parameters are mapped into this shape for compatibility.

    Returns
    -------
    dict
        Summary with keys: ``discovered``, ``after_quality_gate``,
        ``assembled_paths``, ``indexes_written``.
    """
    # 1. Discover
    all_entries: list[dict] = []
    for client_id, memory_dir in sources.items():
        found = discover_entries(memory_dir, client_id)
        log.info("Discovered %d entries from %s", len(found), client_id)
        all_entries.extend(found)

    # 2. Quality gate
    gated = quality_gate(all_entries)
    log.info(
        "Quality gate: %d -> %d entries", len(all_entries), len(gated)
    )

    if not gated and _has_existing_vault_memory_payload(vault_memory_dir):
        log.warning(
            "Skipping memory index refresh: discovery produced zero usable entries "
            "while %s already contains assembled memory payloads",
            vault_memory_dir,
        )
        return {
            "discovered": len(all_entries),
            "after_quality_gate": len(gated),
            "assembled_paths": [],
            "indexes_written": [],
            "skipped": "empty-discovery-preserved-existing-vault-memory",
        }

    # 3. Assemble to vault
    assembled = assemble_to_vault(gated, vault_memory_dir)

    # 4. Generate indexes
    indexes_written: list[str] = []

    # Vault index
    vault_index_path = vault_memory_dir / "MEMORY.md"
    generated_vault_index = generate_vault_index(gated)
    existing_vault_index = (
        vault_index_path.read_text(encoding="utf-8") if vault_index_path.exists() else ""
    )
    vault_index_path.write_text(
        merge_vault_index(existing_vault_index, generated_vault_index),
        encoding="utf-8",
    )
    indexes_written.append(str(vault_index_path))

    outputs = list(client_outputs or [])
    if claude_native_dir is not None:
        outputs.append(
            {
                "client": "claude-code",
                "kind": "linked_index",
                "dir": claude_native_dir,
                "filename": "MEMORY.md",
                "budget": 190,
                "prepend_digest": True,
            }
        )
    if gemini_md_path is not None:
        outputs.append(
            {
                "client": "gemini",
                "kind": "gemini_imports",
                "path": gemini_md_path,
            }
        )
    if codex_memory_path is not None:
        outputs.append(
            {
                "client": "codex",
                "kind": "flat_index",
                "path": codex_memory_path,
            }
        )

    for output in outputs:
        kind = str(output.get("kind", "")).strip()
        client = str(output.get("client", "")).strip() or "client"

        if kind == "linked_index":
            target_dir = Path(output["dir"])
            target_dir.mkdir(parents=True, exist_ok=True)

            # Copy cross-client entries into the target dir so index links resolve.
            for entry in gated:
                if entry["written_by"] == client:
                    continue
                src: Path = entry["source_path"]
                target = target_dir / src.name
                header = f"<!-- CROSS-CLIENT from {entry['written_by']} -->\n"
                content = header + entry.get("raw", "")
                if target.exists():
                    try:
                        if target.read_text(encoding="utf-8") == content:
                            continue
                    except OSError:
                        pass
                target.write_text(content, encoding="utf-8")

            filename = str(output.get("filename", "MEMORY.md"))
            index_path = target_dir / filename
            budget = int(output.get("budget", 190))
            index = generate_linked_index(gated, budget=budget)
            if output.get("prepend_digest"):
                index = _prepend_digest_sections(vault_memory_dir, index)
            index_path.write_text(index, encoding="utf-8")
            indexes_written.append(str(index_path))
            continue

        if kind == "gemini_imports":
            path = Path(output["path"])
            _update_gemini_imports(gated, path)
            indexes_written.append(str(path))
            continue

        if kind == "flat_index":
            path = Path(output["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(generate_flat_index(gated), encoding="utf-8")
            indexes_written.append(str(path))
            continue

        log.warning("Skipping unknown memory output kind for %s: %s", client, kind)

    # Staleness report — flag entries >90 days without update
    _generate_staleness_report(gated, vault_memory_dir)

    return {
        "discovered": len(all_entries),
        "after_quality_gate": len(gated),
        "assembled_paths": [str(p) for p in assembled],
        "indexes_written": indexes_written,
    }


def _generate_staleness_report(entries: list[dict], vault_dir: Path) -> None:
    """Write stale-entries-report.md for entries >90 days since last update."""
    from datetime import datetime, timedelta

    cutoff = datetime.now() - timedelta(days=90)
    stale: list[dict] = []

    for entry in entries:
        date_str = str(entry.get("updated") or entry.get("created") or "")
        if not date_str:
            stale.append(entry)
            continue
        try:
            entry_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
            if entry_date < cutoff:
                stale.append(entry)
        except ValueError:
            continue

    report_path = vault_dir / "stale-entries-report.md"
    if not stale:
        if report_path.exists():
            report_path.unlink()
        return

    lines = [
        "# Stale Memory Entries",
        f"\n*{len(stale)} entries not updated in 90+ days. Review and update or delete.*\n",
        "| Date | Client | Type | Name | Description |",
        "|------|--------|------|------|-------------|",
    ]
    for entry in stale:
        date = str(entry.get("updated") or entry.get("created") or "unknown")
        lines.append(
            f"| {date} | {entry.get('written_by', '?')} | {entry.get('type', '?')} "
            f"| {entry.get('name', '?')} | {entry.get('description', '')[:80]} |"
        )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Staleness report: %d entries >90d at %s", len(stale), report_path)


# ---------------------------------------------------------------------------
# OpsCommand protocol: scan / fix
# ---------------------------------------------------------------------------


def _parse_index_links(memory_md: Path) -> set[str]:
    """Extract filenames referenced in MEMORY.md link entries."""
    if not memory_md.exists():
        return set()
    try:
        content = memory_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    link_re = re.compile(r"\[.*?\]\(([^)]+\.md)\)")
    return {m.group(1) for m in link_re.finditer(content)}


def _linked_memory_dirs_from_plan(project_root: Path) -> list[Path]:
    dirs: list[Path] = []
    try:
        plan = resolve_default_client_memory_plan(project_root=project_root)
        for output in plan.get("outputs", []):
            if output.get("kind") != "linked_index":
                continue
            target_dir = output.get("dir")
            if target_dir is not None:
                dirs.append(Path(target_dir))
    except Exception:
        pass

    if not dirs:
        claude_native_dir = get_claude_native_memory_dir(project_root)
        if claude_native_dir is not None:
            dirs.append(claude_native_dir)

    return dirs


def scan(ctx: OpsContext) -> ScanResult:
    """Scan memory directories for sync issues.

    Checks:
    1. Memory files present but not listed in MEMORY.md index
    2. MEMORY.md links pointing to files that don't exist
    3. Vault entries directory out of sync with source memory files
    """
    memory_dir = get_memory_dir()
    issues: list[dict] = []
    items_scanned = 0

    # --- Check linked client MEMORY.md indexes vs actual files ---
    for linked_memory_dir in _linked_memory_dirs_from_plan(ctx.project_root):
        memory_md = linked_memory_dir / "MEMORY.md"
        indexed_files = _parse_index_links(memory_md)

        # Find actual .md files in the memory directory
        actual_files: set[str] = set()
        for md_file in linked_memory_dir.glob("*.md"):
            if md_file.name in _SKIP_FILES:
                continue
            actual_files.add(md_file.name)
            items_scanned += 1

        # Orphaned index entries (linked but file missing)
        for linked in sorted(indexed_files - actual_files):
            issues.append({
                "action": "orphaned-index-entry",
                "file": linked,
                "location": str(memory_md),
            })

        # Unindexed files (present but not linked in MEMORY.md)
        for unlinked in sorted(actual_files - indexed_files):
            issues.append({
                "action": "unindexed-memory-file",
                "file": unlinked,
                "location": str(linked_memory_dir),
            })

    # --- Check vault memory directory ---
    vault_memory_dir = memory_dir
    if vault_memory_dir.is_dir():
        entries_dir = vault_memory_dir / "entries"
        if entries_dir.is_dir():
            items_scanned += sum(1 for _ in entries_dir.glob("*.md"))

        vault_index = vault_memory_dir / "MEMORY.md"
        if not vault_index.exists() and items_scanned > 0:
            issues.append({
                "action": "missing-vault-index",
                "location": str(vault_memory_dir),
            })

    # --- Check for stale entries (>90 days) at higher difficulty ---
    if ctx.difficulty >= 1 and vault_memory_dir.is_dir():
        from datetime import datetime, timedelta

        cutoff = datetime.now() - timedelta(days=90)
        for md_file in vault_memory_dir.glob("entries/*.md"):
            meta = _parse_frontmatter(md_file)
            if meta is None:
                continue
            date_str = str(meta.get("updated") or meta.get("created") or "")
            if not date_str:
                issues.append({
                    "action": "stale-entry",
                    "file": md_file.name,
                    "reason": "no date metadata",
                })
                continue
            try:
                entry_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
                if entry_date < cutoff:
                    issues.append({
                        "action": "stale-entry",
                        "file": md_file.name,
                        "age_days": (datetime.now() - entry_date).days,
                    })
            except ValueError:
                continue

    if not issues:
        return ScanResult(
            issues=[],
            summary="Memory indexes are in sync",
            severity="info",
            items_scanned=items_scanned,
        )

    parts = []
    orphaned = sum(1 for i in issues if i["action"] == "orphaned-index-entry")
    unindexed = sum(1 for i in issues if i["action"] == "unindexed-memory-file")
    stale = sum(1 for i in issues if i["action"] == "stale-entry")
    missing_idx = sum(1 for i in issues if i["action"] == "missing-vault-index")
    if orphaned:
        parts.append(f"{orphaned} orphaned index entries")
    if unindexed:
        parts.append(f"{unindexed} unindexed memory files")
    if stale:
        parts.append(f"{stale} stale entries")
    if missing_idx:
        parts.append("missing vault index")

    return ScanResult(
        issues=issues,
        summary=f"Found {', '.join(parts)}",
        severity="warning",
        items_scanned=items_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix memory sync issues by running the full assembly pipeline."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would reassemble {len(issues)} memory sync issues",
        )

    memory_dir = get_memory_dir()

    plan = resolve_default_client_memory_plan(project_root=ctx.project_root)
    sources: dict[str, Path] = dict(plan["sources"])
    outputs: list[dict[str, Any]] = list(plan["outputs"])

    if not sources:
        return FixResult(
            success=False,
            summary="No client memory directories found to assemble from",
        )

    try:
        result = assemble(
            sources=sources,
            vault_memory_dir=memory_dir,
            client_outputs=outputs,
        )
    except Exception as exc:
        return FixResult(success=False, summary=f"Assembly failed: {exc}")

    changes = []
    if result.get("assembled_paths"):
        changes.append(f"Assembled {len(result['assembled_paths'])} entries")
    if result.get("indexes_written"):
        changes.append(f"Wrote {len(result['indexes_written'])} indexes")

    return FixResult(
        success=True,
        changes=changes,
        summary=(
            f"Assembled {result.get('after_quality_gate', 0)} entries "
            f"from {result.get('discovered', 0)} discovered"
        ),
        fix_type="sync",
    )
