"""Skill + command enrichment caches for Browse cards.

Combined into a single pass over SKILL.md files with a 10-minute TTL.
This avoids 3 separate loops (list_skills + score_all_skills + page counts)
that previously caused ~11s cold-start on every browse load.

Non-blocking: on cold cache, returns empty dict immediately and populates
in a background thread. Next request will have enriched data.
"""

import threading
import time as _time

from src.config.paths import (
    get_all_client_skill_dirs,
    get_project_root,
)
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.staged_skill_catalog import find_skill_file

# ── Skill enrichment cache (group/release + quality + page counts) ────
_skill_enrichment_cache: dict[str, dict[str, str]] = {}
_skill_enrichment_ts: float = 0.0
_SKILL_ENRICHMENT_TTL = 600.0  # 10 minutes
_skill_enrichment_populating = False
_command_enrichment_cache: dict[str, dict[str, str]] = {}
_command_enrichment_ts: float = 0.0
_command_enrichment_populating = False


def _load_install_registry() -> dict[str, dict]:
    """Load the import skill's install registry and build a skill-name lookup.

    Returns a dict mapping each installed skill name to its registry entry data,
    so enrichment can tag external inventory with ownership/installMethod metadata.
    """
    try:
        import yaml

        registry_path = find_skill_file(get_project_root(), "import", "scripts", "data", "registry.yaml")
        if registry_path is None or not registry_path.is_file():
            return {}
        with open(registry_path) as f:
            registry = yaml.safe_load(f) or {}

        entries = registry.get("entries", [])
        if not isinstance(entries, list):
            return {}

        lookup: dict[str, dict] = {}
        for entry in entries:
            install_method = entry.get("install_method", "")
            source_url = entry.get("source_url", "")
            for skill_name in entry.get("skills", []):
                lookup[skill_name] = {
                    "ownership": "external",
                    "installMethod": install_method,
                    "sourceUrl": source_url,
                }
        return lookup
    except Exception:
        return {}


def _populate_skill_enrichment() -> None:
    """Populate the skill enrichment cache (called in background thread on cold cache)."""
    global _skill_enrichment_cache, _skill_enrichment_ts, _skill_enrichment_populating

    enrichment: dict[str, dict[str, str]] = {}

    # 1. Quality scores (has its own 60s cache internally)
    try:
        from src.lib.skill_scorer import score_all_skills

        scored = score_all_skills()
        for s in scored.get("skills", []):
            name = s["name"]
            enrichment.setdefault(name, {})
            enrichment[name]["qualityTier"] = str(s["tier"])
            enrichment[name]["qualityScore"] = str(s["score"])
    except Exception:
        pass

    # 2. Single pass over SKILL.md for visibility + page counts
    try:
        root = get_project_root()
        for _sd in get_all_client_skill_dirs(root):
            for skill_md_path in _sd.glob("*/SKILL.md"):
                try:
                    fm, _ = parse_frontmatter(skill_md_path)
                    skill_name = fm.get("name", "")
                    if not skill_name:
                        continue
                    enrichment.setdefault(skill_name, {})
                    # Skill planning metadata
                    # x-augur-visibility removed in Track 4 of the
                    # cross-client bundle migration; no longer enriched.
                    group = fm.get("x-augur-group", "")
                    if group:
                        enrichment[skill_name]["group"] = str(group)
                    release = fm.get("x-augur-release", "")
                    if release:
                        enrichment[skill_name]["release"] = str(release)
                    # Page counts
                    config = fm.get("x-augur-config") or {}
                    pages = (config.get("contributions") or {}).get("pages") or []
                    page_types = [p.get("page_type", "auto") for p in pages if isinstance(p, dict)]
                    custom_count = sum(1 for pt in page_types if pt == "custom")
                    enrichment[skill_name]["pages"] = str(len(pages))
                    enrichment[skill_name]["customPages"] = str(custom_count)
                except Exception:
                    pass
    except Exception:
        pass

    # 3. Cross-reference install registry for Community badge metadata.
    install_lookup = _load_install_registry()
    for skill_name, entry_data in install_lookup.items():
        enrichment.setdefault(skill_name, {})
        enrichment[skill_name].setdefault("ownership", entry_data["ownership"])
        enrichment[skill_name]["installMethod"] = entry_data.get("installMethod", "")
        if entry_data.get("sourceUrl"):
            enrichment[skill_name]["sourceUrl"] = entry_data["sourceUrl"]

    _skill_enrichment_cache = enrichment
    _skill_enrichment_ts = _time.time()
    _skill_enrichment_populating = False


def _get_skill_enrichment() -> dict[str, dict[str, str]]:
    """Return combined visibility + quality + page counts per skill, cached.

    Non-blocking: if cache is cold, returns empty dict and kicks off
    background population. The next browse request will have enrichment.
    """
    global _skill_enrichment_populating

    if _skill_enrichment_cache and _time.time() - _skill_enrichment_ts < _SKILL_ENRICHMENT_TTL:
        return _skill_enrichment_cache

    # Cache is cold or expired — return whatever we have and populate in background
    if not _skill_enrichment_populating:
        _skill_enrichment_populating = True
        threading.Thread(target=_populate_skill_enrichment, daemon=True).start()

    return _skill_enrichment_cache


def _populate_command_enrichment() -> None:
    """Populate command score enrichment for Browse command cards."""
    global _command_enrichment_cache, _command_enrichment_ts, _command_enrichment_populating

    enrichment: dict[str, dict[str, str]] = {}
    try:
        from src.lib.command_scorer import score_all_commands

        for command in score_all_commands().get("commands", []):
            dimensions = command.get("dimensions") or {}
            command_id = str(command["id"])
            enrichment[command_id] = {
                "qualityTier": str(command["tier"]),
                "qualityScore": str(command["score"]),
                "kpiStatus": str(command.get("kpiStatus", "untested")),
                "docsScore": str(dimensions.get("docs", "")),
                "wiringScore": str(dimensions.get("wiring", "")),
            }
    except Exception:
        pass

    _command_enrichment_cache = enrichment
    _command_enrichment_ts = _time.time()
    _command_enrichment_populating = False


def _get_command_enrichment() -> dict[str, dict[str, str]]:
    """Return cached command score enrichment and refresh it in the background."""
    global _command_enrichment_populating

    if _command_enrichment_cache and _time.time() - _command_enrichment_ts < _SKILL_ENRICHMENT_TTL:
        return _command_enrichment_cache

    if not _command_enrichment_populating:
        _command_enrichment_populating = True
        threading.Thread(target=_populate_command_enrichment, daemon=True).start()

    return _command_enrichment_cache
