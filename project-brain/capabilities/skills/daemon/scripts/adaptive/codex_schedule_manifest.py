"""Build the canonical Codex migration manifest for adaptive loops."""
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
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Mapping
import tomllib

import yaml

from .discovery import (
    AutoCommandEntry,
    normalize_scheduler,
    normalize_trigger,
    resolve_scheduler,
)
from src.config.paths import get_adaptive_loop_skill_dirs, get_project_root

WORKSPACE_TOKEN = "__PROJECT_ROOT__"  # pragma: allowlist secret

_STANDARD_CADENCES: dict[str, str] = {
    "testing": "weekly-sunday-03:00",
    "code-quality": "weekly-monday-03:00",
    "hardening": "weekly-tuesday-03:00",
    "knowledge-enrichment-nightly": "weekly-wednesday-03:00",
    "skill-standards": "weekly-thursday-03:00",
    "skill-quality": "weekly-friday-03:00",
    "observability": "weekly-saturday-03:00",
    "duplication": "weekly-saturday-03:20",
    "ui-quality": "weekly-saturday-03:40",
    "auto-agent-digest": "weekly-saturday-04:00",
    "file-organizer": "weekly-saturday-04:20",
    "page-health": "weekly-saturday-04:40",
}

_CADENCE_ORDER = {
    "weekly-sunday-03:00": 0,
    "weekly-monday-03:00": 1,
    "weekly-tuesday-03:00": 2,
    "weekly-wednesday-03:00": 3,
    "weekly-thursday-03:00": 4,
    "weekly-friday-03:00": 5,
    "weekly-saturday-03:00": 6,
    "weekly-saturday-03:20": 7,
    "weekly-saturday-03:40": 8,
    "weekly-saturday-04:00": 9,
    "weekly-saturday-04:20": 10,
    "weekly-saturday-04:40": 11,
    "nightly-03:55": 12,
    "every-15-minutes": 13,
    "hourly": 14,
}

_SPECIAL_FAMILY_SUPPORTED_TRIGGERS: dict[str, set[str]] = {
    "self-heal": {"continuous", "nightly"},
    "command-evolution": {"nightly", "post-execution"},
    "knowledge-enrichment": {"nightly", "weekly", "post-execution"},
}


@dataclass(frozen=True)
class ManifestUnit:
    """A Codex-owned loop schedule entry."""

    id: str
    loop: str
    mode: str
    source_commands: list[str]
    current_owner: str
    target_owner: str
    client: str
    runs_in: str
    cadence: str
    workspace: str
    prompt: str
    depends_on: list[str]
    cutover_state: str
    browse_title: str


def _read_frontmatter(skill_md: Path) -> dict[str, Any]:
    """Read YAML frontmatter from a SKILL.md file."""
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    try:
        end = text.index("---", 3)
    except ValueError as exc:
        raise ValueError(f"Malformed frontmatter in {skill_md}: missing closing ---") from exc
    try:
        parsed = yaml.safe_load(text[3:end])
    except Exception as exc:
        raise ValueError(f"Malformed frontmatter in {skill_md}: {exc}") from exc
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError(
            f"Malformed frontmatter in {skill_md}: expected YAML mapping, got {type(parsed).__name__}"
        )
    return parsed


def detect_codex_schedule_states(
    schedule_ids: Iterable[str],
    *,
    home: Path | None = None,
    codex_home: Path | None = None,
) -> dict[str, str]:
    """Detect installed Codex automation state for Augur-managed schedules."""
    if home is not None and codex_home is not None:
        raise ValueError("Pass either home or codex_home, not both")
    resolved_codex_home = codex_home or ((home or Path.home()) / ".codex")
    states: dict[str, str] = {}
    for schedule_id in schedule_ids:
        automation_toml = resolved_codex_home / "automations" / schedule_id / "automation.toml"
        if not automation_toml.is_file():
            states[schedule_id] = "not-installed"
            continue
        try:
            payload = tomllib.loads(automation_toml.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError:
            states[schedule_id] = "invalid"
            continue
        managed_by = payload.get("managed_by")
        if not isinstance(managed_by, str) or managed_by.strip().lower() != "augur":
            states[schedule_id] = "not-installed"
            continue
        status = payload.get("status")
        states[schedule_id] = (
            "active"
            if isinstance(status, str) and status.strip().lower() == "active"
            else "disabled"
        )
    return states


def _build_metadata_registry(project_root: Path | None = None) -> dict[str, AutoCommandEntry]:
    """Build the adaptive registry from skill metadata without importing callables."""
    root = project_root or get_project_root()
    registry: dict[str, AutoCommandEntry] = {}
    all_skills: list[dict[str, Any]] = []

    source_dirs = get_adaptive_loop_skill_dirs(root)
    if not source_dirs:
        raise ValueError(f"No adaptive loop skill source directories found for: {root}")

    for skills_dir in source_dirs:
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue
            frontmatter = _read_frontmatter(skill_md)
            all_skills.append(
                {
                    "name": frontmatter.get("name") or skill_dir.name,
                    "path": skill_dir,
                    "commands": frontmatter.get("x-augur-commands"),
                    "loop_config": frontmatter.get("x-augur-loop")
                    if isinstance(frontmatter.get("x-augur-loop"), dict)
                    else {},
                }
            )

    for rec in all_skills:
        plugin_root = rec["path"]
        commands = rec["commands"] if isinstance(rec["commands"], list) else []
        if not commands:
            continue

        for cmd in commands:
            if not isinstance(cmd, dict):
                continue
            if cmd.get("protocol") != "scan-fix":
                continue

            cmd_id = cmd.get("id")
            if not cmd_id:
                continue

            loop_config = cmd.get("loop", {})
            if not isinstance(loop_config, dict):
                loop_config = {}

            loop_name = loop_config.get("name") or rec["loop_config"].get("name")
            if not loop_name:
                continue

            module_name = cmd.get("callable") or plugin_root.name
            module_config = loop_config.get("config", {})
            if not isinstance(module_config, dict):
                module_config = {}

            trigger = normalize_trigger(
                loop_config.get("trigger", rec["loop_config"].get("trigger", "nightly"))
            )
            registry[cmd_id] = AutoCommandEntry(
                name=cmd_id,
                module=SimpleNamespace(name=module_name),
                loop_name=loop_name,
                tier=loop_config.get("tier", rec["loop_config"].get("tier", 0)),
                trigger=trigger,
                scheduler=resolve_scheduler(loop_config, rec["loop_config"]),
                plugin_root=plugin_root,
                config=module_config,
                initial_trust=float(loop_config.get("trust", rec["loop_config"].get("trust", 0.0))),
            )

    seen_ids = set(registry.keys())
    for rec in all_skills:
        loop_config = rec["loop_config"]
        if not loop_config or not isinstance(loop_config, dict):
            continue

        cmd_name = rec["name"] or rec["path"].name
        if cmd_name in seen_ids:
            continue

        loop_name = loop_config.get("name")
        if not loop_name:
            continue

        module_config = loop_config.get("config", {})
        if not isinstance(module_config, dict):
            module_config = {}

        trigger = normalize_trigger(loop_config.get("trigger", "nightly"))
        registry[cmd_name] = AutoCommandEntry(
            name=cmd_name,
            module=SimpleNamespace(name=rec["path"].name),
            loop_name=loop_name,
            tier=loop_config.get("tier", 0),
            trigger=trigger,
            scheduler=resolve_scheduler(loop_config),
            plugin_root=rec["path"],
            config=module_config,
            initial_trust=float(loop_config.get("trust", 0.0)),
        )
        seen_ids.add(cmd_name)

    return registry


def _unit_id(loop_name: str, trigger: str) -> str:
    if loop_name == "self-heal" and trigger == "nightly":
        return "codex-dev-loop-self-heal-validate"
    if loop_name == "knowledge-enrichment" and trigger == "nightly":
        return "codex-knowledge-enrichment-nightly"
    if loop_name == "knowledge-enrichment" and trigger == "drain":
        return "codex-knowledge-enrichment-drain"
    if loop_name == "command-evolution" and trigger == "drain":
        return "codex-command-evolution-drain"
    return f"codex-dev-loop-{loop_name}"


def _cadence_for(loop_name: str, trigger: str, unit_id: str) -> str:
    if unit_id == "codex-dev-loop-self-heal-validate":
        return "nightly-03:55"
    if unit_id == "codex-command-evolution-drain":
        return "every-15-minutes"
    if unit_id == "codex-knowledge-enrichment-drain":
        return "hourly"
    if unit_id == "codex-knowledge-enrichment-nightly":
        return _STANDARD_CADENCES["knowledge-enrichment-nightly"]
    return _STANDARD_CADENCES.get(loop_name, "nightly-03:00" if trigger == "nightly" else "continuous")


def _prompt_for(loop_name: str, trigger: str, unit_id: str) -> str:
    if unit_id == "codex-dev-loop-self-heal-validate":
        return "/routines run self-heal --validate"
    if unit_id == "codex-command-evolution-drain":
        return "/routines run command-evolution --drain"
    if unit_id == "codex-knowledge-enrichment-nightly":
        return "/routines run knowledge-enrichment"
    if unit_id == "codex-knowledge-enrichment-drain":
        return "/routines run knowledge-enrichment --drain"
    return f"/routines run {loop_name}"


def _build_unit(
    entry_group: list[tuple[str, AutoCommandEntry]],
    trigger: str,
    unit_id: str,
    workspace: Path,
    schedule_states: Mapping[str, str] | None = None,
) -> ManifestUnit:
    source_commands = sorted(command_id for command_id, _ in entry_group)
    loop_name = entry_group[0][1].loop_name
    cadence = _cadence_for(loop_name, trigger, unit_id)
    prompt = _prompt_for(loop_name, trigger, unit_id)
    mode = "drain" if unit_id in {"codex-command-evolution-drain", "codex-knowledge-enrichment-drain"} else "nightly"
    schedulers = sorted({
        normalize_scheduler(entry.scheduler) or "unknown"
        for _, entry in entry_group
    })
    current_owner = schedulers[0] if len(schedulers) == 1 else "mixed"
    browse_title_map = {
        "codex-dev-loop-self-heal-validate": "Self Heal Validate",
        "codex-command-evolution-drain": "Command Evolution Drain",
        "codex-knowledge-enrichment-nightly": "Knowledge Enrichment Nightly",
        "codex-knowledge-enrichment-drain": "Knowledge Enrichment Drain",
    }
    return ManifestUnit(
        id=unit_id,
        loop=loop_name,
        mode=mode,
        source_commands=source_commands,
        current_owner=current_owner,
        target_owner="codex",
        client="codex",
        runs_in="local",
        cadence=cadence,
        workspace=WORKSPACE_TOKEN,
        prompt=prompt,
        depends_on=[],
        cutover_state=(schedule_states or {}).get(unit_id, "not-installed"),
        browse_title=browse_title_map.get(unit_id, loop_name.replace("-", " ").title()),
    )


def _canonical_family_entries(
    registry: dict[str, AutoCommandEntry],
    loop_name: str,
) -> list[tuple[str, AutoCommandEntry]]:
    return sorted(
        (
            command_id,
            entry,
        )
        for command_id, entry in registry.items()
        if entry.loop_name == loop_name
        and not (loop_name == "self-heal" and normalize_trigger(entry.trigger) == "continuous")
    )


def _group_entries_by_trigger(
    registry: dict[str, AutoCommandEntry],
    loop_name: str,
) -> dict[str, list[tuple[str, AutoCommandEntry]]]:
    grouped: dict[str, list[tuple[str, AutoCommandEntry]]] = {}
    for command_id, entry in registry.items():
        if entry.loop_name != loop_name:
            continue
        if loop_name == "self-heal" and normalize_trigger(entry.trigger) == "continuous":
            continue
        grouped.setdefault(normalize_trigger(entry.trigger), []).append((command_id, entry))
    return {
        trigger: sorted(entries, key=lambda item: item[0])
        for trigger, entries in grouped.items()
    }


def _validate_special_family_triggers(registry: dict[str, AutoCommandEntry]) -> None:
    invalid: list[str] = []
    for family, supported_triggers in _SPECIAL_FAMILY_SUPPORTED_TRIGGERS.items():
        seen = sorted(
            {
                normalize_trigger(entry.trigger)
                for entry in registry.values()
                if entry.loop_name == family
            }
        )
        unsupported = [trigger for trigger in seen if trigger not in supported_triggers]
        if unsupported:
            invalid.append(
                f"{family} -> unsupported trigger(s): {', '.join(unsupported)} "
                f"(supported: {', '.join(sorted(supported_triggers))})"
            )
    if invalid:
        raise ValueError(
            "Codex schedule manifest invariant violation: "
            + "; ".join(invalid)
        )


def build_codex_schedule_manifest(
    registry: dict[str, AutoCommandEntry],
    project_root: Path | None = None,
    schedule_states: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Return the canonical Codex migration manifest derived from auto commands."""
    workspace = project_root or get_project_root()
    _validate_special_family_triggers(registry)
    rows: list[ManifestUnit] = []
    command_evolution_entries = _canonical_family_entries(registry, "command-evolution")
    if command_evolution_entries:
        drain_sources = [
            item
            for item in command_evolution_entries
            if normalize_trigger(item[1].trigger) in {"post-execution", "nightly"}
        ]
        if drain_sources:
            rows.append(
                _build_unit(
                    drain_sources,
                    "drain",
                    "codex-command-evolution-drain",
                    workspace,
                    schedule_states,
                )
            )

    knowledge_enrichment_by_trigger = _group_entries_by_trigger(registry, "knowledge-enrichment")
    if knowledge_enrichment_by_trigger:
        nightly_sources = sorted(
            [
                item
                for trigger, entries in knowledge_enrichment_by_trigger.items()
                if trigger in {"nightly", "weekly"}
                for item in entries
            ],
            key=lambda item: item[0],
        )
        drain_sources = sorted(
            [
                item
                for trigger, entries in knowledge_enrichment_by_trigger.items()
                if trigger == "post-execution"
                for item in entries
            ],
            key=lambda item: item[0],
        )
        if nightly_sources:
            rows.append(
                _build_unit(
                    nightly_sources,
                    "nightly",
                    "codex-knowledge-enrichment-nightly",
                    workspace,
                    schedule_states,
                )
            )
        if drain_sources:
            rows.append(
                _build_unit(
                    drain_sources,
                    "drain",
                    "codex-knowledge-enrichment-drain",
                    workspace,
                    schedule_states,
                )
            )

    self_heal_by_trigger = _group_entries_by_trigger(registry, "self-heal")
    nightly_self_heal_sources = sorted(
        [
            item
            for trigger, entries in self_heal_by_trigger.items()
            if trigger == "nightly"
            for item in entries
        ],
        key=lambda item: item[0],
    )
    if nightly_self_heal_sources:
        rows.append(
            _build_unit(
                nightly_self_heal_sources,
                "nightly",
                "codex-dev-loop-self-heal-validate",
                workspace,
                schedule_states,
            )
        )

    ignored_families = {"command-evolution", "knowledge-enrichment", "self-heal"}
    grouped_regular: dict[tuple[str, str], list[tuple[str, AutoCommandEntry]]] = {}
    for command_id, entry in registry.items():
        if entry.loop_name in ignored_families:
            continue
        grouped_regular.setdefault(
            (entry.loop_name, normalize_trigger(entry.trigger)),
            [],
        ).append((command_id, entry))

    regular_trigger_map: dict[str, set[str]] = {}
    for loop_name, trigger in grouped_regular:
        regular_trigger_map.setdefault(loop_name, set()).add(trigger)
    invalid_regular_trigger_loops = {
        loop_name: sorted(triggers)
        for loop_name, triggers in regular_trigger_map.items()
        if any(trigger != "nightly" for trigger in triggers)
    }
    if invalid_regular_trigger_loops:
        details = ", ".join(
            f"{loop_name} -> {', '.join(triggers)}"
            for loop_name, triggers in sorted(invalid_regular_trigger_loops.items())
        )
        raise ValueError(
            "Codex schedule manifest invariant violation: regular loops only "
            "support nightly triggers; found unsupported trigger(s): "
            f"{details}"
        )

    for (loop_name, trigger), entry_group in sorted(grouped_regular.items()):
        rows.append(
            _build_unit(
                sorted(entry_group, key=lambda item: item[0]),
                trigger,
                _unit_id(loop_name, trigger),
                workspace,
                schedule_states,
            )
        )

    rows.sort(key=lambda unit: (_CADENCE_ORDER.get(unit.cadence, 99), unit.id))
    return [asdict(row) for row in rows]


def build_codex_schedule_manifest_from_project(
    project_root: Path | None = None,
    schedule_states: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Build the Codex manifest directly from skill metadata."""
    registry = _build_metadata_registry(project_root)
    return build_codex_schedule_manifest(
        registry,
        project_root=project_root,
        schedule_states=schedule_states,
    )
