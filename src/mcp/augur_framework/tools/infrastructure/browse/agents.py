"""Agent and ADR listing tools."""

import json
import re

import yaml
from src.config.paths import get_project_root
from src.lib.frontmatter_utils import parse_frontmatter
from src.lib.index.agent_profiles import agent_projection_metadata


async def list_agents_impl() -> str:
    """List all subagent profiles from plugins/agents/ definitions and registry."""
    project_root = get_project_root()
    agents_dir = project_root / "plugins" / "agents"
    items = []

    # Load registry.json for enrichment (role, tools, tiers, safety)
    registry: dict = {}
    registry_path = agents_dir / "registry.json"
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(errors="ignore")).get("agents", {})
        except Exception:
            pass

    # 1. Core agents from plugins/agents/*.md (YAML frontmatter)
    if agents_dir.exists():
        for agent_file in sorted(agents_dir.glob("*.md")):
            if agent_file.name == "README.md":
                continue
            try:
                fm, _ = parse_frontmatter(agent_file)
            except Exception:
                continue
            if not isinstance(fm, dict):
                continue
            agent_id = agent_file.stem
            name = fm.get("name", agent_id)
            description = fm.get("description", "")
            mode = fm.get("mode", "unknown")
            model = fm.get("model", "unknown")

            # Enrich from registry
            reg_entry = registry.get(agent_id, {})
            role = reg_entry.get("role", "unknown")
            tools = reg_entry.get("tools", [])
            tiers = reg_entry.get("tiers", {})
            tier_names = sorted(tiers.keys()) if tiers else []

            item = {
                "id": f"agents/{agent_id}",
                "title": name,
                "description": description,
                "hub": "system",
                "path": str(agent_file),
                "tier": role,
                "mode": mode,
                "model": model,
                "tools": tools,
                "available_tiers": tier_names,
            }
            item.update(agent_projection_metadata(project_root, name=agent_id, frontmatter=fm))
            items.append(item)

    # 2. Plugin-contributed agents (in registry but no .md file)
    seen_ids = {item["id"] for item in items}
    for agent_id, reg_entry in sorted(registry.items()):
        canonical_id = f"agents/{agent_id}"
        if canonical_id in seen_ids:
            continue
        if not isinstance(reg_entry, dict):
            continue
        # Plugin agents have "source": "plugin" in registry
        source = reg_entry.get("source", "")
        plugin = reg_entry.get("plugin", "")
        model = reg_entry.get("defaultModel", "unknown")
        item = {
            "id": canonical_id,
            "title": agent_id,
            "description": reg_entry.get("description", ""),
            "hub": "system",
            "path": str(registry_path),
            "tier": reg_entry.get("role", "unknown"),
            "mode": "auto",
            "model": model,
            "tools": reg_entry.get("tools", []),
            "available_tiers": sorted(reg_entry.get("tiers", {}).keys()),
            "source": source,
            "plugin": plugin,
        }
        item.update(
            agent_projection_metadata(
                project_root,
                name=agent_id,
                frontmatter={
                    "model": model,
                    "default_model": model,
                    "x-augur-master": reg_entry.get("x-augur-master", ""),
                },
            )
        )
        items.append(item)

    return json.dumps({"items": items, "count": len(items)})


async def list_adrs_impl() -> str:
    """List all ADRs from the project ADR central index.

    Reads ``project-brain/decisions/adrs/adrs-index.json`` (the post-ADR-642 single source of
    truth) and returns both live and archived rows. Live rows get
    ``archived: false`` and a synthetic ``index://ADR-NNN`` path; archived
    rows get ``archived: true`` and ``archive://ADR-NNN``. Falls back to
    the legacy archived-only sidecar + on-disk ``ADR-*.md`` files for
    environments that haven't migrated yet.
    """
    from src.lib.adr_utils import get_adr_dir, load_adrs_index

    decisions_dir = get_adr_dir()
    items: list[dict] = []
    seen_numbers: set[str] = set()
    if not decisions_dir.exists():
        return json.dumps({"items": [], "count": 0})

    # 1. Central index — both live and archived entries.
    for entry in load_adrs_index(decisions_dir):
        adr_label = str(entry.get("adr_number") or "")
        num_match = re.match(r"ADR-(\d+)", adr_label, re.IGNORECASE)
        adr_num = num_match.group(1) if num_match else ""
        normalised = adr_num.zfill(3) if adr_num else ""
        if normalised:
            if normalised in seen_numbers:
                continue
            seen_numbers.add(normalised)
        archived = entry.get("state") == "archived"
        title = entry.get("title", "")
        hub = entry.get("hub") or "system"
        tags = entry.get("tags") or []
        path = f"archive://{adr_label}" if archived else f"index://{adr_label}"
        items.append(
            {
                "id": f"adr-{adr_num}" if adr_num else adr_label.lower(),
                "title": f"{adr_label}: {title}" if title else adr_label,
                "description": entry.get("decision_summary") or "",
                "hub": hub,
                "path": path,
                "status": entry.get("status") or ("Implemented" if archived else "Proposed"),
                "date": str(entry.get("date", "")),
                "adr_number": adr_num or adr_label,
                "archived": archived,
                "tags": list(tags) if isinstance(tags, list) else [],
            }
        )

    # 2. Legacy fallback: live ADR-*.md files for environments that haven't
    #    migrated to the central index yet.
    for adr_file in sorted(decisions_dir.glob("*.md")):
        if adr_file.name == "TEMPLATE.md":
            continue
        content = adr_file.read_text(errors="ignore")
        fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        fm: dict = {}
        if fm_match:
            try:
                fm = yaml.safe_load(fm_match.group(1)) or {}
            except Exception:
                pass
        name_match = re.match(r"adr-(\d+)", adr_file.stem, re.IGNORECASE)
        adr_num = name_match.group(1) if name_match else None
        normalised = adr_num.zfill(3) if adr_num else ""
        if normalised and normalised in seen_numbers:
            continue
        if normalised:
            seen_numbers.add(normalised)
        adr_id = f"adr-{adr_num}" if adr_num else adr_file.stem
        title = fm.get("title", adr_file.stem.replace("-", " ").title())
        adr_label = f"ADR-{adr_num}" if adr_num else adr_file.stem
        status = fm.get("status", "unknown")
        hub = fm.get("hub", "system")
        date = fm.get("date", "")
        items.append(
            {
                "id": adr_id,
                "title": f"{adr_label}: {title}",
                "description": fm.get("description", ""),
                "hub": hub if hub else "system",
                "path": str(adr_file),
                "status": status,
                "date": str(date),
                "adr_number": adr_num or adr_file.stem,
                "archived": False,
            }
        )

    # 3. Legacy fallback: archived-only sidecar (pre-ADR-642).
    legacy_index = decisions_dir / "archive" / "archived-adrs-index.json"
    if legacy_index.exists():
        try:
            archive_entries = json.loads(legacy_index.read_text(errors="ignore"))
        except Exception:
            archive_entries = []
        if isinstance(archive_entries, list):
            for entry in archive_entries:
                if not isinstance(entry, dict):
                    continue
                adr_label = entry.get("adr_number") or ""
                num_match = re.match(r"ADR-(\d+)", str(adr_label), re.IGNORECASE)
                adr_num = num_match.group(1) if num_match else ""
                normalised = adr_num.zfill(3) if adr_num else ""
                if normalised and normalised in seen_numbers:
                    continue
                if normalised:
                    seen_numbers.add(normalised)
                title = entry.get("title", "")
                hub = entry.get("hub") or "system"
                tags = entry.get("tags") or []
                items.append(
                    {
                        "id": f"adr-{adr_num}" if adr_num else str(adr_label).lower(),
                        "title": (f"{adr_label}: {title}" if title else str(adr_label)),
                        "description": "",
                        "hub": hub,
                        "path": (f"archive://{adr_label}" if adr_label else "archive://unknown"),
                        "status": entry.get("status", "Implemented"),
                        "date": str(entry.get("date", "")),
                        "adr_number": adr_num or str(adr_label),
                        "archived": True,
                        "tags": list(tags) if isinstance(tags, list) else [],
                    }
                )

    return json.dumps({"items": items, "count": len(items)})
