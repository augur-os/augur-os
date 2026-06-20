"""
Agent discovery module (ADR-254).

Signal reader and manifest assembler for agent discovery.
Reads runtime signals (focus state, usage stats, git context) and assembles
a discovery manifest describing Augur's capabilities, hubs, and tools.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from src.mcp.augur_shared.config import get_project_root
from src.mcp.augur_shared.safe_subprocess import safe_run
from src.plugins.skill_discovery import discover_all_skills

_CLEANUP_FOCUS_VALUES = {"__cleanup__", "/__cleanup__"}


def read_signals(
    runtime_dir: Path,
    session_id: str | None = None,
) -> dict:
    """Read discovery signals from runtime state files.

    Reads focus state (per-session or global fallback), usage_stats.yaml,
    and git context (current branch).

    Per ADR-254 §1.2, per-session files in ``state/sessions/`` are the
    primary source.  The global ``focus_state.json`` is used only as a
    cold-start fallback when no session_id is provided or the session
    file is missing.

    Args:
        runtime_dir: Path to the state directory.
        session_id: Optional session identifier.  When provided, reads
            ``state/sessions/{session_id}.json`` first and falls back
            to the global file only if the session file is absent.

    Returns:
        Dict with keys: focus_state, usage_stats, git.
    """
    signals: dict[str, Any] = {}

    # Focus state — per-session first, global fallback (ADR-254 §1.2)
    focus_data = None
    if session_id:
        session_path = runtime_dir / "sessions" / f"{session_id}.json"
        try:
            with open(session_path) as f:
                focus_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    if focus_data is None:
        focus_path = runtime_dir / "focus_state.json"
        try:
            with open(focus_path) as f:
                focus_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    signals["focus_state"] = focus_data

    # Usage stats
    usage_path = runtime_dir / "usage_stats.yaml"
    try:
        with open(usage_path) as f:
            signals["usage_stats"] = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        signals["usage_stats"] = None

    # Git context
    signals["git"] = _read_git_context()

    return signals


def _clean_focus_value(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = value.strip()
    if cleaned in _CLEANUP_FOCUS_VALUES:
        return ""
    return cleaned


def _focus_skill_name(focus: dict[str, Any] | None) -> str:
    """Return the focused skill from current and legacy focus payload shapes."""
    if not isinstance(focus, dict):
        return ""
    for key in ("skill", "skill_name", "bundle", "page"):
        value = _clean_focus_value(focus.get(key))
        if value:
            return value
    return ""


def _focus_hub(focus: dict[str, Any] | None) -> str:
    if not isinstance(focus, dict):
        return ""
    return _clean_focus_value(focus.get("hub"))


def _has_meaningful_focus(focus: Any) -> bool:
    if not isinstance(focus, dict):
        return False
    current_page = focus.get("current_page")
    if isinstance(current_page, str) and current_page.strip() in _CLEANUP_FOCUS_VALUES:
        return False
    return bool(_focus_hub(focus) or _focus_skill_name(focus))


def infer_hub(
    signals: dict,
    explicit_hub: str | None = None,
    skills: list[dict] | None = None,
) -> str | None:
    """Infer the active hub from signals.

    Args:
        signals: Output of read_signals().
        explicit_hub: Explicit hub override — wins if provided.
        skills: Pre-scanned skills list to avoid redundant filesystem scan.

    Returns:
        Hub name string or None if no hub can be inferred.
    """
    if explicit_hub:
        return explicit_hub

    focus = signals.get("focus_state")
    if focus and isinstance(focus, dict):
        # Check hub field directly
        hub = _focus_hub(focus)
        if hub:
            return hub

        # Infer from skill name or page path
        skill = _focus_skill_name(focus)
        if skill:
            _skills = skills if skills is not None else _scan_skills()
            for s in _skills:
                if s["skill"] == skill:
                    return s["hub"]

    return None


def assemble_manifest(
    runtime_dir: Path,
    hub: str | None = None,
    tier: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Assemble a full discovery manifest.

    Args:
        runtime_dir: Path to the state directory.
        hub: Optional hub filter for recommended tools.
        tier: Optional tier filter (public/standard/internal).
        session_id: Optional session identifier for per-session focus
            state (ADR-254 §1.2).

    Returns:
        Discovery manifest dict.
    """
    signals = read_signals(runtime_dir, session_id=session_id)
    visible_skill_records = _scan_visible_skill_records()
    skills = _scan_skills()
    resolved_hub = infer_hub(signals, explicit_hub=hub, skills=skills)
    tool_counts = _count_tools_by_tier(skills)
    recommended = _get_recommended_tools(skills, resolved_hub, tier)
    inventory = _build_inventory_summary(visible_skill_records)

    # Collect unique hubs with their skills
    hub_map: dict[str, list[str]] = {}
    for s in skills:
        hub_map.setdefault(s["hub"], []).append(s["skill"])

    hubs_list = [
        {"id": h, "skills": sorted(sk_list)} for h, sk_list in sorted(hub_map.items(), key=lambda kv: kv[0] or "")
    ]

    return {
        "focus": {
            "hub": resolved_hub,
            "skill": _focus_skill_name(signals.get("focus_state")) or None,
            "signals": _summarize_signals(signals),
        },
        "recommended_tools": recommended,
        "manifest": {
            "name": "augur",
            "description": "Local-first personal knowledge and automation system",
            "capabilities": {
                "skills": len(visible_skill_records),
                "managed_skills": len(skills),
                "project_skills": inventory["skills_by_source_root"].get("project-brain", 0),
                "private_vault_skills": inventory["skills_by_source_root"].get("private-vault", 0),
                "plugin_cache_skills": inventory["skills_by_source_root"].get("plugin-cache", 0),
                "client_skills": inventory["skills_by_source_root"].get("external-client", 0),
                "hubs": len(hub_map),
                "tools": tool_counts,
            },
            "hubs": hubs_list,
            "cli": {
                "binary": "aug",
                "usage": "aug <tool-name> [--param value ...]",
            },
            "mcp": {
                "server": "augur",
                "transport": "stdio",
            },
        },
        "inventory": inventory,
    }


def _summarize_signals(signals: dict) -> dict:
    """Compact signal summary for the manifest focus section."""
    summary: dict[str, Any] = {}

    focus = signals.get("focus_state")
    if _has_meaningful_focus(focus):
        summary["has_focus"] = True
        hub = _focus_hub(focus)
        skill = _focus_skill_name(focus)
        if hub:
            summary["focus_hub"] = hub
        if skill:
            summary["focus_skill"] = skill
    else:
        summary["has_focus"] = False

    git = signals.get("git")
    if git and isinstance(git, dict):
        summary["git_branch"] = git.get("branch")

    usage = signals.get("usage_stats")
    if usage and isinstance(usage, dict):
        summary["has_usage_stats"] = True
    else:
        summary["has_usage_stats"] = False

    return summary


def _parse_skill_metadata(skill_md: Path) -> dict:
    """Read SKILL.md frontmatter, including optional sidecar config."""
    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError:
        return {}

    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except Exception:
        return {}
    if not isinstance(frontmatter, dict):
        return {}

    config_file = frontmatter.get("x-augur-config-file")
    if config_file and "x-augur-config" not in frontmatter:
        sidecar = skill_md.parent / str(config_file)
        try:
            sidecar_data = yaml.safe_load(sidecar.read_text(encoding="utf-8")) or {}
            if isinstance(sidecar_data, dict):
                frontmatter["x-augur-config"] = sidecar_data
        except (yaml.YAMLError, OSError):
            pass

    return frontmatter


def _scan_visible_skill_records() -> list[Any]:
    """Return every visible skill record across managed, plugin-cache, and client roots."""
    return list(discover_all_skills())


def _scan_skills() -> list[dict]:
    """Scan canonical managed skill records and enrich from SKILL.md frontmatter.

    Returns:
        List of dicts with keys: skill, hub, tools, tiers.
    """
    results: list[dict] = []
    for record in discover_all_skills(tiers=(0,)):
        skill_dir = Path(record.path)
        skill_md = skill_dir / "SKILL.md"
        frontmatter = _parse_skill_metadata(skill_md)

        config = frontmatter.get("x-augur-config", {}) if frontmatter else {}
        if not isinstance(config, dict):
            config = {}

        skill_name = str(getattr(record, "name", "") or skill_dir.name).strip()
        if not skill_name:
            continue
        hub = str(getattr(record, "hub", "") or "").strip() or None

        mcp_section = config.get("mcp", {}) or {}
        if not isinstance(mcp_section, dict):
            mcp_section = {}

        fm_mcp_tools = frontmatter.get("x-augur-mcp-tools") if frontmatter else None
        if isinstance(fm_mcp_tools, list):
            tools = fm_mcp_tools
        else:
            tools = list(getattr(record, "mcp_tools", ()) or [])
            if not tools:
                tools = mcp_section.get("tools", []) or config.get("mcp_tools", []) or []

        fm_mcp_tiers = frontmatter.get("x-augur-mcp-tiers") if frontmatter else None
        if isinstance(fm_mcp_tiers, dict):
            tiers = fm_mcp_tiers
        else:
            tiers = mcp_section.get("tiers", {}) or {}

        results.append(
            {
                "skill": skill_name,
                "hub": hub,
                "tools": tools,
                "tiers": tiers,
            }
        )

    return results


def _build_inventory_summary(records: list[Any]) -> dict[str, Any]:
    """Build source-scoped counts so manifest numbers cannot be mistaken for stale data."""
    source_counts = Counter(str(getattr(record, "source_root", "") or "unknown") for record in records)
    tier_counts = Counter(f"tier-{getattr(record, 'tier', 'unknown')}" for record in records)

    return {
        "project_root": str(get_project_root()),
        "skill_scope": "all-visible",
        "managed_skill_scope": "tier-0",
        "skills_by_source_root": dict(sorted(source_counts.items())),
        "skills_by_tier": dict(sorted(tier_counts.items())),
    }


def _build_tier_map(tiers: dict) -> dict[str, str]:
    """Build a tool-name to tier-name mapping from a tiers declaration."""
    result: dict[str, str] = {}
    for tier_name, tier_tools in tiers.items():
        if isinstance(tier_tools, list):
            for t in tier_tools:
                result[t] = tier_name
    return result


def _count_tools_by_tier(skills: list[dict]) -> dict[str, int]:
    """Count tools by tier across all skills.

    Tools without an explicit tier assignment default to 'standard'.
    """
    counts = {"public": 0, "standard": 0, "internal": 0}

    for skill in skills:
        tiers = skill.get("tiers", {}) or {}
        tools = skill.get("tools", []) or []
        tool_tier_map = _build_tier_map(tiers)

        for tool in tools:
            tier = tool_tier_map.get(tool, "standard")
            if tier in counts:
                counts[tier] += 1
            else:
                counts["standard"] += 1

    return counts


def _get_recommended_tools(
    skills: list[dict],
    hub: str | None,
    tier: str | None,
) -> list[dict]:
    """Filter tools by hub and tier, returning recommended tool list."""
    results: list[dict] = []

    for skill in skills:
        skill_hub = skill.get("hub", "")
        tools = skill.get("tools", []) or []
        tiers = skill.get("tiers", {}) or {}

        # Hub filter
        if hub and skill_hub != hub:
            continue

        tool_tier_map = _build_tier_map(tiers)

        for tool in tools:
            tool_tier = tool_tier_map.get(tool, "standard")

            # Tier filter
            if tier and tool_tier != tier:
                continue

            results.append(
                {
                    "name": tool,
                    "skill": skill["skill"],
                    "hub": skill_hub,
                    "tier": tool_tier,
                }
            )

    return results


def _read_git_context() -> dict[str, Any]:
    """Read git branch via subprocess.

    Returns:
        Dict with branch key, or empty dict on failure.
    """
    try:
        result = safe_run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(get_project_root()),
        )
        if result.returncode == 0:
            return {"branch": result.stdout.strip()}
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return {}
