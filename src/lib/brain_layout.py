"""Per-brain storage layout resolution (vault reorg spec 2026-06-12).

Layouts:
- "knowledge" (legacy/default): content under knowledge/{notes,wiki,sources}.
- "domains": user domains at the brain root; machine content under _augur/.

Layout is declared in BRAIN.yaml (`layout: domains`); absence means legacy.
Takes roots as parameters so it stays import-cycle-free from src.config.paths.
"""

from __future__ import annotations

import functools
from pathlib import Path

import yaml

MACHINE_DIR = "_augur"

# Root brain-contract files that stay at the brain root in every layout.
ROOT_BRAIN_FILES = frozenset(
    {
        "AGENTS.md",
        "BRAIN.yaml",
        "HEARTBEAT.md",
        "IDENTITY.md",
        "MEMORY.md",
        "SOUL.md",
        "TOOLS.md",
        "USER.md",
    }
)


@functools.lru_cache(maxsize=8)
def brain_layout(root: Path) -> str:
    """Resolve a brain root's storage layout from its BRAIN.yaml.

    Cached per root; long-lived processes must restart (or call
    brain_layout.cache_clear()) after a BRAIN.yaml layout change.
    """
    brain_yaml = root / "BRAIN.yaml"
    if brain_yaml.is_file():
        try:
            data = yaml.safe_load(brain_yaml.read_text(encoding="utf-8")) or {}
        except Exception:
            return "knowledge"
        if isinstance(data, dict):
            return str(data.get("layout", "knowledge"))
    return "knowledge"


def _is_domains(root: Path) -> bool:
    return brain_layout(root) == "domains"


def brain_notes_root(root: Path) -> Path:
    """Root under which user notes live (the scan root for note scanners)."""
    return root if _is_domains(root) else root / "knowledge" / "notes"


def brain_capture_dir(root: Path) -> Path:
    """Where new captures (url/thought/prompt cards) land until filed."""
    return root / "inbox" if _is_domains(root) else root / "knowledge" / "notes"


def brain_knowledge_dir(root: Path) -> Path:
    """Machine knowledge dir (memory system lives under it in both layouts)."""
    return root / MACHINE_DIR / "knowledge" if _is_domains(root) else root / "knowledge"


def brain_wiki_dir(root: Path) -> Path:
    return root / "wiki" if _is_domains(root) else root / "knowledge" / "wiki"


def brain_sources_dir(root: Path) -> Path:
    return root / "sources" if _is_domains(root) else root / "knowledge" / "sources"


def vault_machine_dir(root: Path, name: str) -> Path:
    """Machine subdir (drafts, capabilities, config, memory, prompts, archive...)."""
    return root / MACHINE_DIR / name if _is_domains(root) else root / name


# Top-level machine dirs relocated under _augur/ in the domains layout.
# Invariant: this set mirrors the migration move map for join_brain_relative
# consumers (skill mapping-table joins). knowledge/, wiki/, and sources/ are
# intentionally absent — they route through the dedicated brain_*_dir helpers
# above (brain_knowledge_dir, brain_wiki_dir, brain_sources_dir), which encode
# their layout-specific destinations. Anyone extending _SKELETON_DIRS_DOMAINS
# in src/lib/brain_manifest.py must keep this set in sync.
MACHINE_TOP_DIRS = frozenset(
    {
        "config",
        "capabilities",
        "drafts",
        "prompts",
        "memory",
        "activity",
        "decisions",
        "instructions",
        "voice-memos",
        "archive",
        "system",
        "integrations",
    }
)


def join_brain_relative(root: Path, relative: Path) -> Path:
    """Join a brain-root-relative path, routing machine roots through _augur
    in the domains layout."""
    first = relative.parts[0] if relative.parts else ""
    if first in MACHINE_TOP_DIRS:
        return vault_machine_dir(root, first) / Path(*relative.parts[1:])
    return root / relative


def is_machine_path(root: Path, path: Path) -> bool:
    """True for paths content scanners must skip (both layouts).

    Matches: anything under _augur/, and the root-level brain-contract
    files (BRAIN.yaml, MEMORY.md, etc.) that are never user notes.
    """
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    if rel.parts and rel.parts[0] == MACHINE_DIR:
        return True
    return len(rel.parts) == 1 and rel.name in ROOT_BRAIN_FILES
