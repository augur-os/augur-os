"""Dream-cycle aggregator functions (ADR-744).

Three flag-only aggregators that surface compounding candidates for the
overnight dream cycle. None of these write to the vault — every result is a
*proposal* for the user (or the routine's judgment phase) to act on.

- ``dream_orphans``  — wiki pages with no inbound graph edges and few timeline entries
- ``dream_stale_pages`` — pages whose compiled truth lags the newest timeline `_at:`
- ``dream_merge_candidates`` — high-similarity page pairs (delegates similarity to
  the ingest skill's ``wiki_concept_merge`` near-duplicate predicate)

The functions accept ``vault_root`` and ``cache_root`` so they can be unit-tested
against a fixture tree. The MCP wrapper in ``scripts/mcp/__init__.py`` resolves
the real roots via ``src.config.paths.get_vault_dir`` and ``get_cache_dir``.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Timeline entry shape from ADR-740 (mirrors wiki_timeline._ENTRY_RE).
_TIMELINE_ENTRY_RE = re.compile(
    r"(?m)^- _at: (?P<at>\S+)\s+_source: (?P<source>\S+)\s*$"
)
_TIMELINE_HEADING_RE = re.compile(r"(?m)^## Timeline\s*$")
_NEXT_HEADING_RE = re.compile(r"(?m)^## ")
_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL
)
_FRONTMATTER_KV_RE = re.compile(r"(?m)^(?P<key>[A-Za-z_][A-Za-z0-9_]*):\s*(?P<value>.*)$")


# ----------------------------------------------------------------------------
# dream-orphans
# ----------------------------------------------------------------------------


def dream_orphans(
    *,
    vault_root: Path,
    cache_root: Path,
    max_timeline_entries: int = 3,
) -> dict[str, Any]:
    """Flag wiki pages with zero inbound graph edges and few timeline entries.

    Returns ``{"flagged": [{"slug", "inbound_edges", "timeline_entries"}, ...]}``.
    Flag-only — never deletes or rewrites a page.

    A page is flagged when **both** conditions hold:
      * its slug appears as a ``dst`` in zero edges in ``edges.jsonl``
      * its ``## Timeline`` section contains strictly fewer than
        ``max_timeline_entries`` entries

    A missing graph cache is treated as "no inbound edges anywhere" — every
    page passes the first condition, so the threshold becomes the sole gate.
    """
    inbound = _inbound_edge_counts(cache_root)
    flagged: list[dict[str, Any]] = []

    for page_path in _iter_wiki_pages(vault_root):
        slug = _slug_for(page_path)
        if slug is None:
            continue
        timeline_count = _timeline_entry_count(page_path)
        inbound_count = inbound.get(slug, 0)
        if inbound_count == 0 and timeline_count < max_timeline_entries:
            flagged.append(
                {
                    "slug": slug,
                    "inbound_edges": inbound_count,
                    "timeline_entries": timeline_count,
                }
            )

    flagged.sort(key=lambda entry: entry["slug"])
    return {"flagged": flagged}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _iter_wiki_pages(vault_root: Path):
    """Yield every wiki ``*.md`` file under the given vault root."""
    from src.lib.brain_layout import brain_wiki_dir

    wiki_dir = brain_wiki_dir(vault_root)
    if not wiki_dir.is_dir():
        return
    yield from sorted(wiki_dir.glob("*.md"))


def _slug_for(page_path: Path) -> str | None:
    """Return the slug for a wiki page — either from frontmatter or filename."""
    text = page_path.read_text(encoding="utf-8")
    fm_match = _FRONTMATTER_RE.match(text)
    if fm_match:
        for kv in _FRONTMATTER_KV_RE.finditer(fm_match.group("body")):
            if kv.group("key") == "slug":
                slug = kv.group("value").strip().strip('"').strip("'")
                if slug:
                    return slug
    # Fall back to the file's stem.
    return page_path.stem or None


def _timeline_section(text: str) -> str:
    """Extract the body between ``## Timeline`` and the next H2 heading."""
    match = _TIMELINE_HEADING_RE.search(text)
    if not match:
        return ""
    start = match.end()
    rest = text[start:]
    next_heading = _NEXT_HEADING_RE.search(rest)
    end = next_heading.start() if next_heading else len(rest)
    return rest[:end]


def _timeline_entry_count(page_path: Path) -> int:
    """Count ``- _at: ... _source: ...`` lines in the page's Timeline section."""
    text = page_path.read_text(encoding="utf-8")
    section = _timeline_section(text)
    return len(_TIMELINE_ENTRY_RE.findall(section))


def _inbound_edge_counts(cache_root: Path) -> dict[str, int]:
    """Count edges by ``dst`` from ``cache_root/graph/edges.jsonl``.

    Returns an empty mapping when the cache is absent — every dst then reads
    as 0 inbound. Tolerates malformed lines (skips them).
    """
    edges_path = cache_root / "graph" / "edges.jsonl"
    if not edges_path.is_file():
        return {}
    counts: dict[str, int] = {}
    for line in edges_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        dst = record.get("dst")
        if not dst:
            continue
        counts[dst] = counts.get(dst, 0) + 1
    return counts


def _parse_iso(timestamp: str) -> datetime | None:
    """Parse an ISO-8601 timestamp, tolerating both ``...Z`` and ``...+00:00``."""
    if not timestamp:
        return None
    cleaned = timestamp.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _newest_timeline_at(page_path: Path) -> datetime | None:
    """Return the most recent ``_at:`` from the page's Timeline section."""
    text = page_path.read_text(encoding="utf-8")
    section = _timeline_section(text)
    newest: datetime | None = None
    for match in _TIMELINE_ENTRY_RE.finditer(section):
        ts = _parse_iso(match.group("at"))
        if ts is None:
            continue
        if newest is None or ts > newest:
            newest = ts
    return newest


def _compiled_at(page_path: Path) -> datetime | None:
    """Return the page's ``_last_compiled_at:`` frontmatter value, if present."""
    text = page_path.read_text(encoding="utf-8")
    fm_match = _FRONTMATTER_RE.match(text)
    if not fm_match:
        return None
    for kv in _FRONTMATTER_KV_RE.finditer(fm_match.group("body")):
        if kv.group("key") == "_last_compiled_at":
            return _parse_iso(kv.group("value").strip().strip('"').strip("'"))
    return None


# ----------------------------------------------------------------------------
# dream-stale-pages
# ----------------------------------------------------------------------------


def dream_stale_pages(
    *,
    vault_root: Path,
    gap_days: int = 14,
) -> dict[str, Any]:
    """Flag wiki pages whose compiled truth lags the newest timeline entry.

    Returns ``{"flagged": [{"slug", "last_compiled_at", "latest_timeline_at",
    "gap_days"}, ...]}``. Flag-only.

    A page is flagged when its newest ``_at:`` in the ``## Timeline`` section
    is newer than its ``_last_compiled_at:`` frontmatter value by strictly more
    than ``gap_days``. Pages without ``_last_compiled_at:`` are skipped (no
    anchor to compare against).
    """
    flagged: list[dict[str, Any]] = []

    for page_path in _iter_wiki_pages(vault_root):
        slug = _slug_for(page_path)
        if slug is None:
            continue
        compiled_at = _compiled_at(page_path)
        if compiled_at is None:
            continue
        newest = _newest_timeline_at(page_path)
        if newest is None or newest <= compiled_at:
            continue
        gap = (newest - compiled_at).total_seconds() / 86400.0
        if gap <= gap_days:
            continue
        flagged.append(
            {
                "slug": slug,
                "last_compiled_at": compiled_at.astimezone(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "latest_timeline_at": newest.astimezone(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "gap_days": round(gap, 2),
            }
        )

    flagged.sort(key=lambda entry: -entry["gap_days"])
    return {"flagged": flagged}


# ----------------------------------------------------------------------------
# dream-merge-candidates
# ----------------------------------------------------------------------------


_FRONTMATTER_ALIAS_BLOCK_RE = re.compile(
    r"(?m)^aliases:\s*\n(?P<lines>(?:[ \t]+-[^\n]*\n)+)"
)
_FRONTMATTER_ALIAS_ITEM_RE = re.compile(r"(?m)^[ \t]+-\s*(?P<value>.+?)\s*$")
_TITLE_HEADING_RE = re.compile(r"(?m)^#\s+(?P<title>.+?)\s*$")


def dream_merge_candidates(*, vault_root: Path) -> dict[str, Any]:
    """Surface wiki page pairs that the wiki near-duplicate predicate flags.

    Delegates the similarity decision to
    ``project-brain/capabilities/skills/wiki/scripts/wiki_concept_merge.py:
    _are_near_duplicate_concepts``. Loads that sibling module via
    ``importlib.util`` so dream does not depend on the wiki package layout.

    Returns ``{"candidates": [{"left_slug", "right_slug", "shared_tokens",
    "jaccard"}, ...]}``. Flag-only — the user (or the routine's judgment
    phase) decides whether to merge.
    """
    near_duplicate, tokens_of = _load_concept_merge_predicate()
    pages = []
    for page_path in _iter_wiki_pages(vault_root):
        slug = _slug_for(page_path)
        if slug is None:
            continue
        title = _title_for(page_path) or slug.replace("-", " ").title()
        aliases = _aliases_for(page_path)
        pages.append(_PageConcept(slug=slug, title=title, aliases=aliases))

    candidates: list[dict[str, Any]] = []
    for i, left in enumerate(pages):
        for right in pages[i + 1:]:
            if not near_duplicate(left, right):
                continue
            left_tokens = tokens_of(left)
            right_tokens = tokens_of(right)
            overlap = left_tokens & right_tokens
            union = left_tokens | right_tokens
            jaccard = len(overlap) / len(union) if union else 0.0
            candidates.append(
                {
                    "left_slug": left.slug,
                    "right_slug": right.slug,
                    "shared_tokens": sorted(overlap),
                    "jaccard": round(jaccard, 3),
                }
            )

    candidates.sort(key=lambda entry: (-entry["jaccard"], entry["left_slug"]))
    return {"candidates": candidates}


class _PageConcept:
    """Duck-typed shim for ``wiki_concept_merge._are_near_duplicate_concepts``.

    The predicate only reads ``.title``, ``.slug``, and ``.aliases``; we don't
    need to construct a full ``ExtractedConcept`` (which requires evidence,
    summary, queries, and other fields the predicate ignores).
    """

    __slots__ = ("slug", "title", "aliases")

    def __init__(self, *, slug: str, title: str, aliases: list[str]):
        self.slug = slug
        self.title = title
        self.aliases = aliases


def _load_concept_merge_predicate():
    """Load wiki_concept_merge via importlib and return its predicates."""
    here = Path(__file__).resolve()
    project_root = _find_project_root(here)
    if project_root is None:
        raise RuntimeError(
            "Unable to locate Augur project root from dream aggregator"
        )
    module_path = (
        project_root
        / "project-brain"
        / "capabilities"
        / "skills"
        / "wiki"
        / "scripts"
        / "wiki_concept_merge.py"
    )
    if not module_path.is_file():
        raise RuntimeError(f"wiki_concept_merge.py not found at {module_path}")
    import importlib.util
    import sys

    # The sibling module does `from skills.wiki.scripts.wiki_concept_models
    # import ExtractedConcept, ...` at top-level — load with the project root
    # and project-brain/capabilities both on sys.path so that import resolves.
    for entry in reversed(
        (
            str(project_root),
            str(project_root / "project-brain"),
            str(project_root / "src" / "mcp"),
        )
    ):
        if entry in sys.path:
            sys.path.remove(entry)
        sys.path.insert(0, entry)

    module_name = "_dream_loaded_wiki_concept_merge"
    cached = sys.modules.get(module_name)
    if cached is not None:
        return cached._are_near_duplicate_concepts, cached._concept_identity_tokens

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to spec wiki_concept_merge")
    module = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE exec — dataclasses' forward-ref resolution
    # reads sys.modules[cls.__module__].__dict__, so an unregistered module
    # raises AttributeError during the @dataclass decoration of MergedConcept.
    sys.modules[module_name] = module
    import_aliases = _install_ingest_import_aliases(project_root)
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    finally:
        _restore_modules(import_aliases)
    return module._are_near_duplicate_concepts, module._concept_identity_tokens


def _install_ingest_import_aliases(project_root: Path) -> dict[str, object | None]:
    """Temporarily route ``skills.wiki`` imports to project-brain.

    Broad pytest runs can import a top-level ``tests/skills`` package before
    dream loads the wiki predicate. The dynamic import below must still bind
    to Augur's project-brain skill package, then restore the caller's import
    state after the module has loaded.
    """
    import sys
    import types

    package_paths = {
        "skills": project_root / "project-brain" / "capabilities" / "skills",
        "skills.wiki": project_root / "project-brain" / "capabilities" / "skills" / "wiki",
        "skills.wiki.scripts": project_root / "project-brain" / "capabilities" / "skills" / "wiki" / "scripts",
        "skills.wiki.scripts.wiki_concept_models": None,
    }
    originals = {name: sys.modules.get(name) for name in package_paths}
    for name, path in package_paths.items():
        if path is None:
            sys.modules.pop(name, None)
            continue
        package = types.ModuleType(name)
        package.__path__ = [str(path)]
        package.__package__ = name
        sys.modules[name] = package
    return originals


def _restore_modules(originals: dict[str, object | None]) -> None:
    import sys

    for name, original in originals.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


def _find_project_root(start: Path) -> Path | None:
    for candidate in (start.parent, *start.parents):
        if (
            (candidate / "pyproject.toml").is_file()
            and (candidate / "src" / "config" / "paths.py").is_file()
        ):
            return candidate
    return None


def _title_for(page_path: Path) -> str | None:
    text = page_path.read_text(encoding="utf-8")
    fm_match = _FRONTMATTER_RE.match(text)
    if fm_match:
        for kv in _FRONTMATTER_KV_RE.finditer(fm_match.group("body")):
            if kv.group("key") == "title":
                value = kv.group("value").strip().strip('"').strip("'")
                if value:
                    return value
    body = text[fm_match.end():] if fm_match else text
    heading_match = _TITLE_HEADING_RE.search(body)
    return heading_match.group("title").strip() if heading_match else None


def _aliases_for(page_path: Path) -> list[str]:
    text = page_path.read_text(encoding="utf-8")
    fm_match = _FRONTMATTER_RE.match(text)
    if not fm_match:
        return []
    block_match = _FRONTMATTER_ALIAS_BLOCK_RE.search(fm_match.group("body") + "\n")
    if not block_match:
        return []
    return [
        item.group("value").strip().strip('"').strip("'")
        for item in _FRONTMATTER_ALIAS_ITEM_RE.finditer(block_match.group("lines"))
        if item.group("value").strip()
    ]


__all__ = [
    "dream_orphans",
    "dream_stale_pages",
    "dream_merge_candidates",
]
