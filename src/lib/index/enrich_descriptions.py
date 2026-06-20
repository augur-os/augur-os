"""Post-processing enrichment pass for RAG index descriptions.

Reads all category index entries from rag_dir/{category}/*.md and fills
empty or stub descriptions using source file content extraction (Tier 1)
or body text summarization (Tier 2).

Tier 1 (code-extractable, no LLM):
  - scripts: Python docstring, shell comment
  - api-routes: JSDoc or first comment from route.ts
  - tests: Python docstring or Jest describe() text
  - vault: First non-heading paragraph from .md body
  - prompts: Instruction intent from body (between <instructions> tags)
  - agents: role/instructions from YAML config
  - documents: Format + readable path (already handled by transforms)

Tier 2 (LLM-summarized, optional):
  - vault/documents/prompts items still empty after Tier 1

Usage:
  python3 enrich_descriptions.py [--rag-dir PATH] [--dry-run] [--category NAME]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config.paths import get_project_root, get_rag_dir
from src.lib.frontmatter_utils import parse_frontmatter, write_frontmatter


def _is_stub_description(desc: str) -> bool:
    """Return True if description is empty, a stub, or a leaked XML tag."""
    if not desc or not desc.strip():
        return True
    d = desc.strip()
    if d.startswith("<"):  # leaked XML like <instructions>
        return True
    if "TODO" in d:
        return True
    # Mechanical templates that don't convey meaning
    if re.match(r"^(pytest|jest|Python|Shell) (test|script) for \w+$", d):
        return True
    if re.match(r"^(GET|POST|PUT|DELETE|PATCH),?\s*endpoint$", d):
        return True
    return False


def _extract_python_docstring(path: Path) -> str:
    """Extract first line of first docstring from a Python file."""
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")[:3000]
        m = re.search(r'"""(.*?)"""', src, re.DOTALL)
        if not m:
            m = re.search(r"'''(.*?)'''", src, re.DOTALL)
        if m:
            first_line = m.group(1).strip().split("\n")[0].strip()
            if first_line and len(first_line) > 5 and "TODO" not in first_line:
                return first_line
    except Exception:
        pass
    return ""


def _extract_shell_comment(path: Path) -> str:
    """Extract first meaningful comment from a shell script."""
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore")[:2000].splitlines()
        for line in lines[1:6]:  # skip shebang
            if line.startswith("#") and line.strip() != "#":
                desc = line.lstrip("# ").strip()
                if len(desc) > 5:
                    return desc
    except Exception:
        pass
    return ""


def _extract_jsdoc(path: Path) -> str:
    """Extract description from JSDoc comment or first // comment in a .ts file."""
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")[:4000]
        # JSDoc: /** ... */
        m = re.search(r"/\*\*\s*\n?\s*\*?\s*(.+?)[\n*]", src)
        if m:
            desc = m.group(1).strip().rstrip("*").strip()
            if len(desc) > 10:
                return desc
        # Fallback: first meaningful // comment
        for line in src.splitlines():
            stripped = line.strip()
            if stripped.startswith("//") and not stripped.startswith("///"):
                desc = stripped.lstrip("/ ").strip()
                if len(desc) > 10:
                    return desc
    except Exception:
        pass
    return ""


def _extract_jest_describe(path: Path) -> str:
    """Extract the describe() label from a Jest test file."""
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")[:3000]
        m = re.search(r"""describe\(["'](.+?)["']""", src)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return ""


def _extract_md_first_paragraph(path: Path) -> str:
    """Extract first non-heading, non-metadata paragraph from a markdown file."""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")[:3000]
        # Strip frontmatter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                content = content[end + 3 :]

        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            if stripped.startswith("**") and ":" in stripped:  # metadata lines
                continue
            if stripped.startswith("|") or stripped.startswith("-"):  # tables/lists
                continue
            if stripped.startswith("<"):  # XML tags
                continue
            if len(stripped) > 15:
                return stripped[:300]
    except Exception:
        pass
    return ""


def _extract_prompt_intent(body: str) -> str:
    """Extract a meaningful description from a prompt template body."""
    # Try to get text between <instructions> tags
    m = re.search(r"<instructions>(.*?)</instructions>", body, re.DOTALL)
    text = m.group(1).strip() if m else body.strip()

    # Get first meaningful sentence
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("<") or stripped.startswith("#"):
            continue
        if len(stripped) > 15 and "TODO" not in stripped:
            # Truncate to first sentence
            for sep in [". ", ".\n", "— ", " - "]:
                idx = stripped.find(sep)
                if 15 < idx < 200:
                    return stripped[: idx + 1].strip()
            return stripped[:200].strip()
    return ""


def enrich_category(rag_dir: Path, category: str, project_root: Path, dry_run: bool = False) -> int:
    """Enrich descriptions for all entries in a category. Returns count of enriched entries."""
    cat_dir = rag_dir / category
    if not cat_dir.exists():
        return 0

    enriched = 0
    for entry_file in sorted(cat_dir.rglob("*.md")):
        meta, body = parse_frontmatter(entry_file)
        if not meta:
            continue

        description = meta.get("description", "")
        if not _is_stub_description(description):
            continue

        source_path_str = meta.get("source_path", "")
        source_path = Path(source_path_str) if source_path_str else None
        # Try project-relative resolution
        if source_path and not source_path.is_absolute():
            source_path = project_root / source_path

        new_desc = ""

        if category == "scripts":
            if source_path and source_path.exists():
                if source_path.suffix == ".py":
                    new_desc = _extract_python_docstring(source_path)
                elif source_path.suffix == ".sh":
                    new_desc = _extract_shell_comment(source_path)

        elif category == "api-routes":
            if source_path and source_path.exists():
                new_desc = _extract_jsdoc(source_path)

        elif category == "tests":
            if source_path and source_path.exists():
                if source_path.suffix == ".py":
                    new_desc = _extract_python_docstring(source_path)
                else:
                    new_desc = _extract_jest_describe(source_path)

        elif category == "vault":
            if source_path and source_path.exists():
                new_desc = _extract_md_first_paragraph(source_path)
            if not new_desc and body:
                # Use the index body as fallback
                for line in body.splitlines():
                    stripped = line.strip()
                    if (
                        stripped
                        and not stripped.startswith("#")
                        and not stripped.startswith("<")
                        and len(stripped) > 15
                    ):
                        new_desc = stripped[:300]
                        break

        elif category == "prompts":
            if body:
                new_desc = _extract_prompt_intent(body)
            elif source_path and source_path.exists():
                try:
                    content = source_path.read_text(encoding="utf-8", errors="ignore")[:3000]
                    new_desc = _extract_prompt_intent(content)
                except Exception:
                    pass

        elif category == "agents":
            # Try instructions field from the index body or source
            if body:
                first_line = body.strip().split("\n")[0].strip()
                if first_line and len(first_line) > 10 and not first_line.startswith("#"):
                    new_desc = first_line[:200]

        elif category == "adrs":
            # Extract first prose paragraph after title/metadata
            if body:
                for line in body.splitlines():
                    stripped = line.strip()
                    if (
                        stripped
                        and not stripped.startswith("#")
                        and not stripped.startswith("**")
                        and not stripped.startswith("|")
                        and not stripped.startswith("-")
                        and not stripped.startswith("<")
                        and len(stripped) > 20
                    ):
                        new_desc = stripped[:300]
                        break

        # Skip if new description is also a stub
        if new_desc and _is_stub_description(new_desc):
            new_desc = ""

        if new_desc and new_desc != description:
            if dry_run:
                name = meta.get("name", entry_file.stem)
                print(f"  [{category}] {name}: '{description}' -> '{new_desc[:80]}'")
            else:
                meta["description"] = new_desc
                write_frontmatter(entry_file, meta, body)
            enriched += 1

    return enriched


ALL_CATEGORIES = [
    "skills",
    "blocks",
    "pages",
    "documents",
    "mcp-tools",
    "vault",
    "integrations",
    "prompts",
    "commands",
    "agents",
    "adrs",
    "tests",
    "api-routes",
    "scripts",
    "logs",
]


def enrich_all(rag_dir: Path, project_root: Path, dry_run: bool = False) -> dict[str, int]:
    """Run enrichment across all categories. Returns {category: enriched_count}."""
    stats: dict[str, int] = {}
    for category in ALL_CATEGORIES:
        count = enrich_category(rag_dir, category, project_root, dry_run=dry_run)
        stats[category] = count
    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Enrich RAG index descriptions")
    parser.add_argument("--rag-dir", type=Path, default=None)
    parser.add_argument("--category", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = get_project_root()
    rag = args.rag_dir or get_rag_dir()

    if args.category:
        count = enrich_category(rag, args.category, root, dry_run=args.dry_run)
        print(f"Enriched {count} {args.category} entries")
    else:
        stats = enrich_all(rag, root, dry_run=args.dry_run)
        total = sum(stats.values())
        print(f"Enriched {total} entries across {len(stats)} categories")
        for cat, count in stats.items():
            if count > 0:
                print(f"  {cat}: {count}")
