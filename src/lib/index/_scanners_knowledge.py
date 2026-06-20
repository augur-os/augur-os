"""Knowledge category scanners for the unified RAG indexer.

Scanners:
  - index_skills()       -- managed project-brain/private-vault SKILL.md files
  - index_adrs()         -- get_adr_dir()/ADR-*.md
  - index_wiki()         -- compiled runtime wiki pages
  - index_prompts()      -- managed skills' prompts/*.md and assets/seeds/prompts/*.md
  - index_agents()       -- plugins/agents/*.md + registry.json
  - index_integrations() -- SKILL.md frontmatter integrations (CLIBridge/osascript)
  - index_commands()     -- managed skills' commands/*.md command docs
"""

# TODO_CLEANUP: This file is 855 lines — consider splitting into smaller modules

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.config.paths import get_managed_skill_source_dirs, get_project_root
from src.lib.frontmatter_utils import extract_relationships, parse_frontmatter
from src.lib.index.agent_profiles import agent_projection_metadata

try:
    from ._indexer_helpers import (
        _checksum,
        _mtime_iso,
        _classify_skill_dir,
        _discover_skill_dirs,
        _read_skill_config,
        _skill_overlay_metadata,
        _write_entry,
        humanize_slug,
        source_path_for,
    )
    from ._overlay import OverlayScope, overlay_entry_id, overlay_metadata, wiki_overlay_output_path
except ImportError:
    from _indexer_helpers import (
        _checksum,
        _mtime_iso,
        _classify_skill_dir,
        _discover_skill_dirs,
        _read_skill_config,
        _skill_overlay_metadata,
        _write_entry,
        humanize_slug,
        source_path_for,
    )
    from _overlay import OverlayScope, overlay_entry_id, overlay_metadata, wiki_overlay_output_path


# ---------------------------------------------------------------------------
# Skills scanner
# ---------------------------------------------------------------------------


def _client_from_source(source: str) -> str:
    """Map a source tag to a supported AI client label."""
    if source == "augur":
        return "augur"
    if source == "plugin-cache":
        return "claude"
    if source.startswith("claude-"):
        return "claude"
    if source.startswith("codex-"):
        return "codex"
    if source.startswith("gemini-"):
        return "gemini"
    if source.startswith("cursor-"):
        return "cursor"
    if source.startswith("copilot-"):
        return "copilot"
    if source.startswith("opencode-"):
        return "opencode"
    return source.split("-", 1)[0] if source else "unknown"


def _normalize_client_sources(primary_source: str, record: Any | None) -> list[str]:
    sources = list(getattr(record, "client_sources", ()) or ())
    if primary_source and primary_source not in sources:
        sources.insert(0, primary_source)
    return list(dict.fromkeys(str(source) for source in sources if source))


def _skill_clients_from_sources(client_sources: list[str], skill_client: str) -> list[str]:
    # Scope/source-root and brain-layer tokens are never real skill clients
    # (clients are augur, vault, codex, claude, ...). ADR-770's project-brain
    # layout introduced brain-type tokens (project/personal/team) that must not
    # leak into skill_clients.
    fake_overlay_clients = {
        "shared",
        "private",
        "project-brain",
        "shared-vault",
        "private-vault",
        "project",
        "personal",
        "team",
        "brain",
    }
    clients = [
        client
        for client in (_client_from_source(client_source) for client_source in client_sources)
        if client and client not in fake_overlay_clients
    ]
    if skill_client and skill_client not in fake_overlay_clients and skill_client not in clients:
        clients.insert(0, skill_client)
    return list(dict.fromkeys(clients))


def _source_metadata_from_skill(
    meta: dict[str, Any],
    *,
    skill_client: str,
    skill_origin: str,
    discovery_record: Any | None,
) -> tuple[str, str, str, str, str]:
    """Resolve browse/index ownership metadata for a skill entry."""
    source = str(getattr(discovery_record, "source", "") or "").strip()
    ownership = str(getattr(discovery_record, "ownership", "") or "").strip().lower()
    source_root = str(getattr(discovery_record, "source_root", "") or "").strip()
    # ADR-770: accept one-release legacy metadata but index it under the
    # canonical project-brain source root.
    if source_root == "shared-vault":
        source_root = "project-brain"
    if source == "shared-vault":
        source = "project-brain"

    if source_root == "repo":
        source_root = "project-brain"
        skill_client = "augur"
        skill_origin = "canonical"
    elif source_root == "vault":
        skill_client = "vault"
        skill_origin = "canonical"
    elif source_root == "project-brain":
        skill_client = "augur"
        skill_origin = "canonical"
    elif source_root == "private-vault":
        skill_client = "vault"
        skill_origin = "canonical"
    elif source_root == "plugin-cache":
        skill_client = "claude-plugin"
        skill_origin = "plugin-cache"
    elif source_root == "external-client" and source:
        client = _client_from_source(source)
        if client != "unknown":
            skill_client = client
        if source.endswith("-local"):
            skill_origin = "client-local"
        elif source.endswith("-global"):
            skill_origin = "client-global"

    if not source:
        frontmatter_source = str(meta.get("source") or "").strip()
        if frontmatter_source:
            source = frontmatter_source
        elif source_root in {"project-brain", "private-vault"}:
            source = source_root
        elif source_root == "vault" or skill_client == "vault":
            source = "vault"
        elif skill_origin == "canonical":
            source = "augur"
        elif skill_origin == "client-local" and skill_client != "unknown":
            source = f"{skill_client}-local"
        elif skill_origin == "client-global" and skill_client != "unknown":
            source = f"{skill_client}-global"
        elif skill_origin == "plugin-cache":
            source = "plugin-cache"
        else:
            source = "external"

    if not source_root:
        if source in {"project-brain", "private-vault"}:
            source_root = source
        elif source == "vault" or skill_client == "vault":
            source_root = "vault"
        elif skill_origin == "canonical" and skill_client == "augur":
            source_root = "project-brain"
        elif skill_origin == "canonical" and skill_client == "vault":
            source_root = "private-vault"
        elif skill_origin == "plugin-cache":
            source_root = "plugin-cache"
        elif skill_origin.startswith("client-") or source.endswith("-local") or source.endswith("-global"):
            source_root = "external-client"
        else:
            source_root = "external"

    if not ownership:
        raw_ownership = str(meta.get("ownership") or "").strip().lower()
        if source_root == "private-vault" or source == "private-vault":
            ownership = "user"
        elif source_root == "vault" or source == "vault" or skill_client == "vault":
            ownership = "user"
        elif skill_origin == "canonical":
            ownership = "adopted" if raw_ownership == "adopted" else "augur"
        else:
            ownership = "external"

    return source, ownership, source_root, skill_client, skill_origin


def _skill_demo_entries(skill_dir: Path, root: Path) -> list[str]:
    """Collect demo runbooks from a skill's ``demos/`` directory (rule 32).

    Each entry is encoded as a flat ``"Title|relative/path"`` string: flat
    string lists are the proven shape for structured skill metadata (mirrors
    ``client_sources``) — they survive the frontmatter YAML round-trip and the
    browse-index ``_metadata_text`` flattener, which comma-joins list items
    into the dashboard's string metadata map.
    """
    demos_dir = skill_dir / "demos"
    if not demos_dir.is_dir():
        return []
    entries: list[str] = []
    for demo_md in sorted(demos_dir.glob("*.md")):
        if not demo_md.is_file() or demo_md.name.lower() == "readme.md":
            continue
        try:
            demo_meta, _ = parse_frontmatter(demo_md)
        except Exception:
            demo_meta = {}
        title = str(demo_meta.get("title") or "").strip()
        if not title:
            stem = re.sub(r"^demo[_-]?\d*[_-]?", "", demo_md.stem) or demo_md.stem
            title = humanize_slug(stem)
        # Keep the "Title|path" encoding parseable after the comma-join
        # flatten: the separators must not appear inside the title.
        title = title.replace("|", "/").replace(",", " ").strip()
        entries.append(f"{title}|{source_path_for(demo_md, root)}")
    return entries


def index_skills(root: Path, rag_dir: Path) -> int:
    """Scan all skill directories for SKILL.md and write pointer entries.

    Output layout:
        rag_dir/skills/{hub}/{source_root}/{skill_name}.md
    """
    import shutil

    category_dir = rag_dir / "skills"
    if category_dir.exists():
        shutil.rmtree(category_dir)
    count = 0

    discovery_records_by_path: dict[Path, Any] = {}
    try:
        from src.plugins.skill_discovery import discover_all_skills

        discovery_records_by_path = {
            Path(record.path).resolve(): record for record in discover_all_skills() if getattr(record, "path", None)
        }
    except Exception:
        discovery_records_by_path = {}

    for bundle_name, skill_dir in _discover_skill_dirs(root):
        discovery_record = discovery_records_by_path.get(Path(skill_dir).resolve())
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        meta, body = parse_frontmatter(skill_md)

        skill_name = meta.get("name") or skill_dir.name
        hub = bundle_name  # x-augur-hub removed by ADR-802

        source_path = source_path_for(skill_md, root)

        skill_client, skill_origin = _classify_skill_dir(skill_dir, root)
        source, ownership, source_root, skill_client, skill_origin = _source_metadata_from_skill(
            meta,
            skill_client=skill_client,
            skill_origin=skill_origin,
            discovery_record=discovery_record,
        )
        skill_overlay = _skill_overlay_metadata(skill_dir, root)
        if skill_overlay:
            source_root = skill_overlay["source_root"]
            if source_root == "private-vault":
                source = "private-vault"
                ownership = "user"
                skill_client = "vault"
                skill_origin = "canonical"
            elif source_root == "project-brain":
                source = "project-brain"
                ownership = "augur"
                skill_client = "augur"
                skill_origin = "canonical"
        client_sources = _normalize_client_sources(source, discovery_record)
        skill_clients = _skill_clients_from_sources(client_sources, skill_client)

        entry_meta: dict[str, Any] = {
            "id": f"skill:{source_root}:{skill_name}",
            "type": "skill",
            "hub": hub,
            "bundle": bundle_name,
            "name": skill_name,
            "source": source,
            "ownership": ownership,
            "source_root": source_root,
            "skill_client": skill_client,
            "skill_origin": skill_origin,
            "client_sources": client_sources,
            "skill_clients": skill_clients,
            "source_path": source_path,
            "description": meta.get("description", ""),
            "visibility": meta.get("visibility", ""),
            "tags": meta.get("tags") or [],
            "related": meta.get("related") or [],
            "checksum": _checksum(skill_md),
            "modified": _mtime_iso(skill_md),
        }
        demos = _skill_demo_entries(skill_dir, root)
        if demos:
            entry_meta["demos"] = demos
        if skill_overlay:
            entry_meta.update(skill_overlay)

        output_source_root = str(entry_meta.get("source_root") or "external")
        output_path = category_dir / hub / output_source_root / f"{skill_name}.md"
        _write_entry(output_path, entry_meta)
        count += 1

    return count


# ---------------------------------------------------------------------------
# ADRs scanner
# ---------------------------------------------------------------------------


def index_adrs(root: Path, rag_dir: Path) -> int:
    """Scan ADR records (live + archived) from the central index.

    Output layout:
        rag_dir/adrs/{name-lowercased}.md

    Post-ADR-642 there are no per-ADR ``.md`` files; entries are read from
    ``project-brain/decisions/adrs/adrs-index.json``. Live entries get a synthetic
    ``source_path`` of ``index://ADR-NNN``; archived entries get
    ``archive://ADR-NNN``. The unified RAG index needs a stable identifier,
    not an on-disk path.
    """
    import shutil
    from src.lib.adr_utils import get_adr_dir, scan_adrs

    decisions_dir = get_adr_dir()
    category_dir = rag_dir / "adrs"
    if category_dir.exists():
        shutil.rmtree(category_dir)
    count = 0

    if not decisions_dir.is_dir():
        return count

    central_index_rel = ""
    central_index_path = decisions_dir / "adrs-index.json"
    if central_index_path.exists():
        try:
            central_index_rel = str(central_index_path.relative_to(root))
        except ValueError:
            central_index_rel = str(central_index_path)

    for adr in scan_adrs(decisions_dir):
        name = Path(str(adr.get("filename") or f"ADR-{int(adr['number']):03d}")).stem
        if not name.startswith("ADR-"):
            name = f"ADR-{int(adr['number']):03d}"
        description = str(adr.get("description") or adr.get("title") or "")
        archived = bool(adr.get("archived", False))
        adr_label = f"ADR-{int(adr['number']):03d}"
        if adr.get("path"):
            # Legacy on-disk .md (back-compat).
            source_path = str(adr["path"])
            try:
                source_path = str(Path(source_path).relative_to(root))
            except ValueError:
                pass
        elif archived:
            source_path = f"archive://{adr_label}"
        else:
            source_path = f"index://{adr_label}"

        entry_meta: dict[str, Any] = {
            "type": "adr",
            "hub": adr.get("hub"),
            "name": name,
            "title": str(adr.get("title") or humanize_slug(name)),
            "source_path": source_path,
            "description": description,
            "status": adr.get("status", ""),
            "date": adr.get("date", ""),
            "tags": adr.get("tags") or [],
            "related": adr.get("related") or [],
            "archived": archived,
            "adr_number": adr_label,
        }
        if adr.get("archive_path"):
            entry_meta["archive_path"] = adr["archive_path"]
        if adr.get("archive_member"):
            entry_meta["archive_member"] = adr["archive_member"]
        # Tie freshness to the central index whenever the entry comes from there.
        if not adr.get("path") and central_index_path.exists():
            entry_meta["checksum"] = _checksum(central_index_path)
            entry_meta["modified"] = _mtime_iso(central_index_path)
            if central_index_rel:
                entry_meta["index_path"] = central_index_rel
        elif adr.get("path"):
            try:
                source_file = Path(str(adr["path"]))
                if source_file.exists():
                    entry_meta["checksum"] = _checksum(source_file)
                    entry_meta["modified"] = _mtime_iso(source_file)
            except OSError:
                pass

        output_path = category_dir / f"{name.lower()}.md"
        _write_entry(output_path, entry_meta, description)
        count += 1

    return count


def index_wiki(
    wiki_dir: Path,
    rag_dir: Path,
    *,
    shared_wiki_dir: Path | None = None,
    root: Path | None = None,
) -> int:
    """Scan vault wiki pages and write pointer entries.

    Output layout:
        rag_dir/wiki/{scope}/{relative-path-from-wiki-root}

    ``source_path`` is stored project-root-relative (POSIX) for in-repo pages so
    the machine-shared index resolves correctly from any checkout/worktree
    (ADR-270/759); external (private-vault) pages stay absolute.
    """
    import shutil

    root = (root or get_project_root()).resolve()
    category_dir = rag_dir / "wiki"
    if category_dir.exists():
        shutil.rmtree(category_dir)
    count = 0

    roots: list[tuple[OverlayScope, Path]] = []
    if shared_wiki_dir is not None:
        roots.append(("shared", shared_wiki_dir))
    roots.append(("private", wiki_dir))

    for scope, root_dir in roots:
        if not root_dir.is_dir():
            continue
        for wiki_file in sorted(root_dir.rglob("*.md")):
            if wiki_file.is_symlink() or wiki_file.name == "index.md":
                continue
            meta, body = parse_frontmatter(wiki_file)
            title = meta.get("title") or wiki_file.stem.replace("-", " ").title()
            description = meta.get("description") or ""
            if not description:
                for block in body.split("\n\n"):
                    stripped = block.strip()
                    if stripped and not stripped.startswith("#") and not stripped.startswith("- "):
                        description = " ".join(stripped.split())[:300]
                        break

            rel = wiki_file.relative_to(root_dir)
            entry_rel = rel.with_suffix("")
            entry_name = "/".join(entry_rel.parts)
            output_path = wiki_overlay_output_path(category_dir, scope, rel)
            relationships = extract_relationships(meta)
            relationship_targets = list(
                dict.fromkeys(target for field_targets in relationships.values() for target in field_targets)
            )

            entry_meta: dict[str, Any] = {
                "id": overlay_entry_id("wiki", scope, rel),
                "type": "wiki",
                "hub": meta.get("hub", "workspace"),
                "name": entry_name,
                "title": title,
                "source_path": source_path_for(wiki_file, root),
                "description": description,
                "tags": meta.get("tags") or [],
                "checksum": _checksum(wiki_file),
                "modified": _mtime_iso(wiki_file),
                **overlay_metadata(scope=scope, rel=rel),
            }
            if relationships:
                entry_meta["relationships"] = relationships
                entry_meta["relationship_targets"] = relationship_targets

            _write_entry(output_path, entry_meta)
            count += 1

    return count


# ---------------------------------------------------------------------------
# Prompts scanner
# ---------------------------------------------------------------------------


def index_prompts(root: Path, rag_dir: Path) -> int:
    """Scan skill prompts/*.md, seed prompts, and vault prompt cards.

    Skill prompt files may be stubs; when a prompt lacks an explicit or
    body-derived description we fall back to a name-based description. Vault
    prompt cards (``<vault>/prompts/*.md``, ADR-748) are scanned after the
    skill loop so user-saved prompts join the same Browse "prompts"
    category. Every entry stores the prompt text in the index file's body
    section (read back as ``_body``) and carries ``placeholders`` in
    frontmatter so the dashboard Trigger button has a payload to dispatch.

    Output layout:
        rag_dir/prompts/{hub}/{prompt-id}.md          (skill prompts)
        rag_dir/prompts/{hub}/vault/{prompt-id}.md    (vault prompt cards)
    """
    import shutil

    from skills.ingest.scripts.prompt_cards import extract_placeholders
    from src.config.paths import get_vault_dir
    from src.lib.brain_layout import brain_notes_root, is_machine_path

    category_dir = rag_dir / "prompts"
    if category_dir.exists():
        shutil.rmtree(category_dir)
    count = 0

    seen: set[tuple[str, str, str]] = set()
    for bundle_name, skill_dir in _discover_skill_dirs(root):
        skill_name = skill_dir.name

        prompt_dirs = (
            skill_dir / "prompts",
            skill_dir / "assets" / "seeds" / "prompts",
        )
        for prompts_dir in prompt_dirs:
            if not prompts_dir.is_dir():
                continue

            for prompt_file in sorted(prompts_dir.glob("*.md")):
                # TODO_BUG: parse_frontmatter is unguarded here — a malformed
                # skill prompt .md aborts the whole index_prompts() run. The
                # vault loop below guards this; the skill loop should too.
                meta, body = parse_frontmatter(prompt_file)

                prompt_id = meta.get("id") or prompt_file.stem
                action_name = meta.get("action", prompt_id)
                seen_key = (bundle_name, skill_name, str(prompt_id))
                if seen_key in seen:
                    continue
                seen.add(seen_key)

                # Prefer explicit metadata, then extract from body (skip stubs and XML)
                description = str(meta.get("description") or "").strip()
                if not description:
                    for line in body.splitlines():
                        stripped = line.strip()
                        if (
                            stripped
                            and not stripped.startswith("#")
                            and not stripped.startswith("<")
                            and "TODO" not in stripped
                        ):
                            description = stripped
                            break

                # Final fallback: build from action name
                if not description:
                    readable = str(action_name).replace("-", " ").replace("_", " ")
                    description = f"{readable} · {skill_name} prompt"

                source_path = source_path_for(prompt_file, root)

                related = meta.get("related") or []
                skill_ref = f"skills/{bundle_name}/{skill_name}"
                if skill_ref not in related:
                    related = [skill_ref, *related]

                entry_meta: dict[str, Any] = {
                    "type": "prompt",
                    "hub": bundle_name,
                    "bundle": bundle_name,
                    "skill": skill_name,
                    "name": prompt_id,
                    "source": "skill",
                    "source_path": source_path,
                    "description": description,
                    "placeholders": ",".join(extract_placeholders(body)),
                    "dispatch": meta.get("dispatch", ""),
                    "tags": meta.get("tags") or [],
                    "related": related,
                    "checksum": _checksum(prompt_file),
                    "modified": _mtime_iso(prompt_file),
                }

                output_path = category_dir / bundle_name / f"{prompt_id}.md"
                _write_entry(output_path, entry_meta, body)
                count += 1

    # ── Vault prompt cards (ADR-748 + ADR-751) ────────────────────────
    # Per ADR-751, user-saved prompts are capture cards with
    # `x-augur-note-type: prompt` frontmatter (alongside other note kinds
    # like url-ingest cards). write_prompt_card lands them in the brain's
    # capture dir, but the inbox-triage routine (ADR-810) later files cards
    # into domain folders — so scan the WHOLE notes root recursively, not just
    # the capture dir, otherwise a triggerable prompt drops out of the Prompts
    # tab the moment it is filed. is_machine_path() excludes _augur/ and the
    # root brain-contract files; the note-type filter below keeps non-prompt
    # notes out. They join the Browse "prompts" category under hub "workspace",
    # written to a distinct `vault/` subdir so a vault prompt id never
    # overwrites a skill prompt with the same id in the same hub.
    vault_root = get_vault_dir()
    vault_notes_root = brain_notes_root(vault_root)
    if vault_notes_root.is_dir():
        for prompt_file in sorted(vault_notes_root.rglob("*.md")):
            if prompt_file.is_symlink() or is_machine_path(vault_root, prompt_file):
                continue
            # The vault is user-editable: a malformed .md (bad YAML, binary
            # file) must skip that one card, not abort the whole run.
            try:
                meta, body = parse_frontmatter(prompt_file)
            except Exception:
                continue

            # Filter to prompt-type notes only — notes/ also holds url-ingest
            # cards and other kinds that are scanned by their own scanners.
            if str(meta.get("x-augur-note-type") or "").strip() != "prompt":
                continue

            prompt_id = meta.get("id") or prompt_file.stem

            description = str(meta.get("description") or "").strip()
            if not description:
                for line in body.splitlines():
                    stripped = line.strip()
                    if (
                        stripped
                        and not stripped.startswith("#")
                        and not stripped.startswith("<")
                        and "TODO" not in stripped
                    ):
                        description = stripped
                        break
            if not description:
                readable = str(meta.get("label") or prompt_id).replace("-", " ").replace("_", " ")
                description = f"{readable} · vault prompt"

            # write_prompt_card stamps `source: vault` (a string) in the
            # card frontmatter; honor it, but fall back to "vault" when the
            # field is absent or a structured value (older cards used a
            # `source:` object for citation metadata).
            raw_source = meta.get("source")
            card_source = raw_source if isinstance(raw_source, str) and raw_source else "vault"

            entry_meta: dict[str, Any] = {
                "type": "prompt",
                "hub": "workspace",
                "bundle": "vault",
                "skill": None,
                "name": prompt_id,
                "source": card_source,
                "source_path": source_path_for(prompt_file, root),
                "description": description,
                "placeholders": ",".join(extract_placeholders(body)),
                "source_url": meta.get("source_url", ""),
                "tags": meta.get("tags") or [],
                "related": [],
                "checksum": _checksum(prompt_file),
                "modified": _mtime_iso(prompt_file),
            }

            output_path = category_dir / "brain" / "vault" / f"{prompt_id}.md"
            _write_entry(output_path, entry_meta, body)
            count += 1

    return count


# ---------------------------------------------------------------------------
# Agents scanner
# ---------------------------------------------------------------------------


def index_agents(root: Path, rag_dir: Path) -> int:
    """Scan configured subagent profiles and write pointer entries.

    Sources (in priority order):
      1. plugins/agents/*.md — canonical subagent definitions (YAML frontmatter)
      2. plugins/agents/registry.json — enrichment with role, tools, tiers

    Output layout:
        rag_dir/agents/{agent-name}.md
    """
    import shutil

    category_dir = rag_dir / "agents"
    if category_dir.exists():
        shutil.rmtree(category_dir)
    count = 0
    seen: set[str] = set()

    # Load registry.json for enrichment
    registry_data: dict[str, dict] = {}
    registry_file = root / "plugins" / "agents" / "registry.json"
    if registry_file.exists():
        try:
            import json as _json

            agents_list = _json.loads(registry_file.read_text(encoding="utf-8"))
            if isinstance(agents_list, list):
                for agent in agents_list:
                    aname = agent.get("name", "")
                    if aname:
                        registry_data[aname] = agent
        except Exception:
            pass

    # ── Source 1: plugins/agents/*.md — canonical subagent profiles ───
    agents_dir = root / "plugins" / "agents"
    if agents_dir.exists():
        for md_file in sorted(agents_dir.glob("*.md")):
            if md_file.name == "README.md":
                continue
            try:
                meta, _ = parse_frontmatter(md_file)
                name = meta.get("name", md_file.stem)
                if not name or name in seen:
                    continue
                seen.add(name)

                description = meta.get("description", "")
                model = meta.get("model", "")
                mode = meta.get("mode", "")

                # Enrich from registry
                reg = registry_data.get(name, {})
                role = reg.get("role", "executor")
                tools = reg.get("tools", [])

                entry_meta: dict[str, Any] = {
                    "type": "agent",
                    "hub": "dev",
                    "name": name,
                    "source_path": str(md_file.relative_to(root)),
                    "description": description,
                    "tier": role,
                    "mode": mode,
                    "model": model,
                    "tool_count": str(len(tools)),
                    "checksum": _checksum(md_file),
                    "modified": _mtime_iso(md_file),
                }
                entry_meta.update(agent_projection_metadata(root, name=name, frontmatter=meta))

                output_path = category_dir / f"{name}.md"
                _write_entry(output_path, entry_meta, "")
                count += 1
            except Exception:
                continue

    # ── Source 2: registry-only agents (no .md file, e.g. plugin agents) ─
    for agent_name, agent in registry_data.items():
        if agent_name in seen:
            continue
        seen.add(agent_name)

        description = agent.get("description", "")
        model = agent.get("default_model", "")
        mode = agent.get("mode", "")
        tools = agent.get("tools", [])
        role = agent.get("role", "executor")

        entry_meta = {
            "type": "agent",
            "hub": "dev",
            "name": agent_name,
            "source_path": str(registry_file.relative_to(root)) if registry_file.exists() else "",
            "description": description,
            "tier": role,
            "mode": mode,
            "model": model,
            "tool_count": str(len(tools)),
            "checksum": _checksum(registry_file) if registry_file.exists() else "",
            "modified": _mtime_iso(registry_file) if registry_file.exists() else "",
        }
        entry_meta.update(
            agent_projection_metadata(
                root,
                name=agent_name,
                frontmatter={
                    "model": model,
                    "default_model": model,
                    "x-augur-master": agent.get("x-augur-master", ""),
                },
            )
        )

        output_path = category_dir / f"{agent_name}.md"
        _write_entry(output_path, entry_meta, "")
        count += 1

    return count


# ---------------------------------------------------------------------------
# Integrations scanner
# ---------------------------------------------------------------------------


def index_integrations(root: Path, rag_dir: Path) -> int:
    """Scan for skills that bridge to external systems.

    Detection signals (any match qualifies):
    1. SKILL.md frontmatter ``x-augur-cli-integrations`` list
    2. SKILL.md frontmatter ``x-augur-integration-type`` field
    3. MCP scripts using CLIBridge or osascript (legacy fallback)

    Output layout:
        rag_dir/integrations/{bundle}/{skill-name}.md
    """
    import re as _re
    import shutil

    import yaml as _yaml_local

    category_dir = rag_dir / "integrations"
    if category_dir.exists():
        shutil.rmtree(category_dir)

    count = 0

    for bundle_name, skill_dir in _discover_skill_dirs(root):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue

        # ---- Read full frontmatter for integration declarations ----
        fm: dict = {}
        try:
            content = skill_md.read_text(encoding="utf-8")
            if content.startswith("---"):
                end = content.index("---", 3)
                fm = _yaml_local.safe_load(content[3:end]) or {}
                if not isinstance(fm, dict):
                    fm = {}
        except Exception:
            pass

        cli_integrations = fm.get("x-augur-cli-integrations") or []
        integration_type = fm.get("x-augur-integration-type", "")

        # ---- Also check MCP code for CLIBridge / osascript (legacy) ----
        mcp_init = skill_dir / "scripts" / "mcp" / "__init__.py"
        mcp_source = ""
        if mcp_init.exists():
            try:
                mcp_source = mcp_init.read_text(errors="ignore")
            except Exception:
                pass

        uses_cli_bridge = "CLIBridge" in mcp_source
        uses_osascript = "osascript" in mcp_source

        # Skip skills that have no integration signal at all
        if not cli_integrations and not integration_type and not uses_cli_bridge and not uses_osascript:
            continue

        data = _read_skill_config(skill_md)

        # ---- Build CLI tools list from frontmatter first, MCP code second ----
        cli_tools: list[str] = []
        install_hints: list[str] = []
        if cli_integrations and isinstance(cli_integrations, list):
            for entry in cli_integrations:
                if isinstance(entry, dict):
                    name = entry.get("name", "")
                    if name and name not in cli_tools:
                        cli_tools.append(name)
                    hint = entry.get("install", "")
                    if hint:
                        install_hints.append(hint)

        # Supplement from MCP code patterns
        if mcp_source:
            for name in _re.findall(r'CLIBridge\(\s*"([^"]+)"', mcp_source):
                if name not in cli_tools:
                    cli_tools.append(name)
            if uses_osascript and "osascript" not in cli_tools:
                cli_tools.append("osascript")
            for name in _re.findall(r'shutil\.which\(\s*"([^"]+)"', mcp_source):
                if name not in cli_tools:
                    cli_tools.append(name)
            for hint in _re.findall(r'install_hint\s*=\s*"([^"]+)"', mcp_source):
                if hint not in install_hints:
                    install_hints.append(hint)

        # ---- MCP tools from x-augur-config or x-augur-mcp-tools ----
        mcp_tools: list[str] = []
        mcp_tools_fm = fm.get("x-augur-mcp-tools") or []
        if isinstance(mcp_tools_fm, list):
            mcp_tools = [t for t in mcp_tools_fm if isinstance(t, str)]
        if not mcp_tools:
            mcp_section = data.get("mcp", {})
            if isinstance(mcp_section, dict):
                raw = mcp_section.get("tools", [])
                if isinstance(raw, list):
                    mcp_tools = [t for t in raw if isinstance(t, str) and not t.startswith("id:")]

        skill_name = skill_dir.name
        try:
            source_path = str(skill_md.relative_to(root))
        except ValueError:
            source_path = str(skill_md)
        raw_name = fm.get("name") or data.get("name", skill_name)
        display_name = raw_name.replace("-", " ").replace("_", " ").title()
        fm_desc = fm.get("description", "")
        services = cli_tools if cli_tools else ([integration_type] if integration_type else [])
        description = fm_desc or f"CLI bridge: {', '.join(services)}" if services else fm_desc

        related = [f"skills/{bundle_name}/{skill_name}"]
        body_lines = []
        if cli_tools:
            body_lines.append(f"CLI tools: {', '.join(cli_tools)}")
        if install_hints:
            body_lines.append(f"Install: {'; '.join(install_hints)}")
        if integration_type:
            body_lines.append(f"Integration type: {integration_type}")
        if mcp_tools:
            body_lines.append(f"MCP tools: {', '.join(mcp_tools[:10])}")
            if len(mcp_tools) > 10:
                body_lines.append(f"... and {len(mcp_tools) - 10} more")

        entry_meta: dict[str, Any] = {
            "type": "integration",
            "hub": bundle_name,
            "name": display_name,
            "source_path": source_path,
            "description": description,
            "scope": "local",
            "cli_tools": ", ".join(cli_tools) if cli_tools else "",
            "tool_count": str(len(mcp_tools)),
            "related": related,
            "checksum": _checksum(skill_md),
            "modified": _mtime_iso(skill_md),
        }
        if integration_type:
            entry_meta["integration_type"] = integration_type

        output_path = category_dir / bundle_name / f"{skill_name}.md"
        _write_entry(output_path, entry_meta, "\n".join(body_lines))
        count += 1

    return count


# ---------------------------------------------------------------------------
# Commands scanner
# ---------------------------------------------------------------------------


def index_commands(root: Path, rag_dir: Path) -> int:
    """Scan canonical skill command docs.

    Output layout:
        rag_dir/commands/{command-name}.md
    """
    import shutil

    category_dir = rag_dir / "commands"
    if category_dir.exists():
        shutil.rmtree(category_dir)
    count = 0
    seen_commands: set[str] = set()

    for skills_dir in get_managed_skill_source_dirs(root):
        if not skills_dir.is_dir():
            continue
        for skill_dir in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            commands_dir = skill_dir / "commands"
            if not commands_dir.is_dir():
                continue

            for command_file in sorted(commands_dir.glob("*.md")):
                if not command_file.is_file():
                    continue

                meta, _body = parse_frontmatter(command_file)
                if meta.get("skill"):
                    continue

                skill_meta, _skill_body = parse_frontmatter(skill_md)
                hub = skill_dir.name  # x-augur-hub removed by ADR-802
                skill_name = skill_meta.get("name") or skill_dir.name
                command_name = str(meta.get("id") or command_file.stem)
                if command_name in seen_commands:
                    continue
                seen_commands.add(command_name)
                category = str(meta.get("visibility", "")).upper() or (
                    "DEV"
                    if hub in {"studio", "dev"}
                    else "CORE" if hub == "command" else "OPS" if hub == "adaptive" else "APP"
                )
                try:
                    source_path = command_file.relative_to(root).as_posix()
                except ValueError:
                    source_path = command_file.as_posix()

                related = [f"skills/{hub}/{skill_dir.name}"]

                entry_meta: dict[str, Any] = {
                    "type": "command",
                    "hub": hub,
                    "name": command_name,
                    "title": f"/{command_name}",
                    "source_path": source_path,
                    "description": meta.get("description", ""),
                    "category": category,
                    "skill": skill_name,
                    "related": related,
                    "checksum": _checksum(command_file),
                    "modified": _mtime_iso(command_file),
                }

                output_path = category_dir / f"{command_name}.md"
                _write_entry(output_path, entry_meta)
                count += 1

    return count
