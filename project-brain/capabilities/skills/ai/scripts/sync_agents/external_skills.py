"""sync_agents/external_skills.py — External skill bundle loader (ADR-605 Phase 3).

Reads ``config/external_skills.yaml`` and resolves vendored skill bundles
(e.g. submoduled `vendor/skills/obsidian-skills/`) into a typed
``ExternalSkillBundle`` structure consumed by client adapters.

Each adapter implements ``distribute_external_skills(bundles)`` to copy or
convert bundle skills into its client-specific surface (Codex/OpenCode file
copies, Gemini converted exports, Copilot ``.github/instructions``,
Claude Code marketplace registration).

Shared helpers live here so each adapter override stays small. The mode
("file_copy", "convert_and_copy", "convert_to_instructions", "marketplace")
in ``bundle.targets[adapter_name]`` decides which helper runs.
"""
from __future__ import annotations

import re as _re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .constants import PROJECT_ROOT, logger


EXTERNAL_SKILLS_CONFIG = PROJECT_ROOT / "config" / "external_skills.yaml"


@dataclass
class ExternalSkillBundle:
    """A vendored bundle of external skills pinned to an upstream SHA."""

    id: str
    source: Path
    upstream: str
    pinned_sha: str
    skills: list[str] = field(default_factory=list)
    targets: dict[str, str] = field(default_factory=dict)

    def skill_dir(self, skill_name: str) -> Path:
        """Return the absolute source directory for a single skill."""
        return self.source / "skills" / skill_name


def _verify_pinned_sha(source: Path, expected_sha: str) -> None:
    """Compare the submodule's actual HEAD with the pinned SHA. Warns on mismatch."""
    try:
        result = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, FileNotFoundError) as exc:
        logger.warning(
            "External skills: failed to resolve HEAD of %s: %s", source, exc
        )
        return
    actual = (result.stdout or "").strip()
    if not actual:
        logger.warning(
            "External skills: %s has no resolvable HEAD (rc=%s, stderr=%s)",
            source,
            result.returncode,
            (result.stderr or "").strip(),
        )
        return
    if actual != expected_sha:
        logger.warning(
            "External skills: %s HEAD %s does not match pinned_sha %s — "
            "proceeding with whatever is checked out",
            source,
            actual[:10],
            expected_sha[:10],
        )


def load_external_bundles(
    config_path: Path | None = None,
    project_root: Path | None = None,
) -> list[ExternalSkillBundle]:
    """Load external skill bundles from ``config/external_skills.yaml``.

    Returns an empty list when the config is missing or unreadable.
    """
    root = project_root or PROJECT_ROOT
    path = config_path or (root / "config" / "external_skills.yaml")

    if not path.exists():
        return []

    try:
        import yaml as pyyaml
    except ImportError:
        logger.warning("External skills: PyYAML not available, skipping load")
        return []

    try:
        with open(path, encoding="utf-8") as f:
            data = pyyaml.safe_load(f) or {}
    except Exception as exc:
        logger.warning("External skills: failed to read %s: %s", path, exc)
        return []

    raw_bundles = data.get("external_skill_bundles") or []
    bundles: list[ExternalSkillBundle] = []

    for entry in raw_bundles:
        if not isinstance(entry, dict):
            continue
        bundle_id = str(entry.get("id") or "").strip()
        source_rel = str(entry.get("source") or "").strip()
        if not bundle_id or not source_rel:
            logger.warning(
                "External skills: skipping bundle missing id/source: %r", entry
            )
            continue

        source = (root / source_rel).resolve()
        if not source.exists():
            logger.warning(
                "External skills: source %s for bundle %s does not exist; "
                "skipping",
                source,
                bundle_id,
            )
            continue

        pinned_sha = str(entry.get("pinned_sha") or "").strip()
        upstream = str(entry.get("upstream") or "").strip()
        skills = [str(s).strip() for s in (entry.get("skills") or []) if s]
        targets_raw = entry.get("targets") or {}
        targets = {
            str(k).strip(): str(v).strip()
            for k, v in targets_raw.items()
            if k and v
        }

        if pinned_sha:
            _verify_pinned_sha(source, pinned_sha)

        bundles.append(
            ExternalSkillBundle(
                id=bundle_id,
                source=source,
                upstream=upstream,
                pinned_sha=pinned_sha,
                skills=skills,
                targets=targets,
            )
        )

    return bundles


# ---------------------------------------------------------------------------
# Shared distribution helpers
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = _re.compile(r"^---\n(.*?)\n---\n*", _re.DOTALL)


def _strip_frontmatter(raw: str) -> str:
    """Return body text with the leading YAML frontmatter block removed."""
    return _FRONTMATTER_RE.sub("", raw, count=1).strip()


def _iter_target_skills(bundles: list[ExternalSkillBundle], adapter_name: str):
    """Yield ``(bundle, skill_name, source_dir, mode)`` for skills targeted at ``adapter_name``."""
    for bundle in bundles:
        mode = bundle.targets.get(adapter_name)
        if not mode:
            continue
        for skill_name in bundle.skills:
            source_dir = bundle.skill_dir(skill_name)
            if not source_dir.exists():
                logger.warning(
                    "External skills: %s/%s missing source dir %s",
                    bundle.id,
                    skill_name,
                    source_dir,
                )
                continue
            yield bundle, skill_name, source_dir, mode


def _existing_subdir_skill_names(target_root: Path) -> set[str]:
    if not target_root.exists():
        return set()
    return {
        child.name
        for child in target_root.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    }


def _existing_instruction_skill_names(target_root: Path) -> set[str]:
    if not target_root.exists():
        return set()
    names: set[str] = set()
    for path in target_root.glob("*.instructions.md"):
        name = path.name.removesuffix(".instructions.md")
        if name:
            names.add(name)
    return names


def _configured_bundle_skill_names(bundles: list[ExternalSkillBundle]) -> set[str]:
    return {
        str(skill_name)
        for bundle in bundles
        for skill_name in bundle.skills
        if str(skill_name)
    }


def _remove_retired_subdir_exports(
    *,
    bundles: list[ExternalSkillBundle],
    target_root: Path,
    desired_names: set[str],
) -> None:
    for skill_name in sorted(_configured_bundle_skill_names(bundles) - desired_names):
        _remove_generated_path(target_root / skill_name)


def _remove_retired_instruction_exports(
    *,
    bundles: list[ExternalSkillBundle],
    target_root: Path,
    desired_names: set[str],
) -> None:
    for skill_name in sorted(_configured_bundle_skill_names(bundles) - desired_names):
        _remove_generated_path(target_root / f"{skill_name}.instructions.md")


def _allowed_external_skill_names(
    names: list[str],
    adapter_name: str,
    existing_names: set[str],
) -> set[str]:
    try:
        from src.lib.capabilities.export_filter import allowed_generated_names
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "External skills: capability policy unavailable for %s: %s",
            adapter_name,
            exc,
        )
        return {name for name in names if name in existing_names}
    return allowed_generated_names("skill", names, adapter_name, existing_names)


def _remove_generated_path(path: Path) -> None:
    try:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    except OSError as exc:
        logger.warning(
            "External skills: failed to remove denied export %s: %s",
            path,
            exc,
        )


def _distribute_via_file_copy(
    bundles: list[ExternalSkillBundle],
    *,
    adapter_name: str,
    target_root: Path,
    label: str,
) -> int:
    """Copy each targeted skill directory wholesale into ``target_root/<name>/``."""
    written = 0
    targeted = list(_iter_target_skills(bundles, adapter_name))
    desired_names = {
        skill_name
        for _bundle, skill_name, _source_dir, mode in targeted
        if mode == "file_copy"
    }
    _remove_retired_subdir_exports(
        bundles=bundles,
        target_root=target_root,
        desired_names=desired_names,
    )
    allowed = _allowed_external_skill_names(
        [skill_name for _bundle, skill_name, _source_dir, _mode in targeted],
        adapter_name,
        _existing_subdir_skill_names(target_root),
    )
    for _bundle, skill_name, source_dir, mode in targeted:
        if mode != "file_copy":
            continue
        target_dir = target_root / skill_name
        if skill_name not in allowed:
            _remove_generated_path(target_dir)
            continue
        try:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_dir, target_dir)
            written += 1
        except OSError as exc:
            logger.warning(
                "External skills: failed to copy %s -> %s: %s",
                source_dir,
                target_dir,
                exc,
            )
    if written:
        logger.info(
            "✅ Distributed %d external skill(s) to %s (%s)",
            written,
            target_root,
            label,
        )
    return written


def _distribute_for_gemini(
    bundles: list[ExternalSkillBundle],
    *,
    target_root: Path,
) -> int:
    """Convert SKILL.md files into ``.antigravity/plugins/<name>/SKILL.md`` (ADR-605).

    Mirrors the existing ``_sync_skill_exports`` behavior for Gemini: each
    skill becomes a subdirectory whose ``SKILL.md`` is the raw upstream file.
    Reference subdirs are also copied so paths inside SKILL.md stay valid.
    The ``.antigravity/plugins/`` tree is gitignored — outputs are local-only.
    """
    written = 0
    targeted = list(_iter_target_skills(bundles, "gemini"))
    desired_names = {
        skill_name
        for _bundle, skill_name, _source_dir, mode in targeted
        if mode == "convert_and_copy"
    }
    _remove_retired_subdir_exports(
        bundles=bundles,
        target_root=target_root,
        desired_names=desired_names,
    )
    allowed = _allowed_external_skill_names(
        [skill_name for _bundle, skill_name, _source_dir, _mode in targeted],
        "gemini",
        _existing_subdir_skill_names(target_root),
    )
    for _bundle, skill_name, source_dir, mode in targeted:
        if mode != "convert_and_copy":
            continue
        target_dir = target_root / skill_name
        if skill_name not in allowed:
            _remove_generated_path(target_dir)
            continue
        try:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_dir, target_dir)
            written += 1
        except OSError as exc:
            logger.warning(
                "External skills: failed to convert %s -> %s: %s",
                source_dir,
                target_dir,
                exc,
            )
    if written:
        logger.info(
            "✅ Distributed %d external skill(s) to %s (Gemini)",
            written,
            target_root,
        )
    return written


def _distribute_for_copilot(
    bundles: list[ExternalSkillBundle],
    *,
    target_root: Path,
) -> int:
    """Render SKILL.md into ``.github/instructions/<name>.instructions.md`` (ADR-605)."""
    written = 0
    targeted = list(_iter_target_skills(bundles, "copilot"))
    desired_names = {
        skill_name
        for _bundle, skill_name, _source_dir, mode in targeted
        if mode == "convert_to_instructions"
    }
    _remove_retired_instruction_exports(
        bundles=bundles,
        target_root=target_root,
        desired_names=desired_names,
    )
    allowed = _allowed_external_skill_names(
        [skill_name for _bundle, skill_name, _source_dir, _mode in targeted],
        "copilot",
        _existing_instruction_skill_names(target_root),
    )
    for _bundle, skill_name, source_dir, mode in targeted:
        if mode != "convert_to_instructions":
            continue
        target_file = target_root / f"{skill_name}.instructions.md"
        if skill_name not in allowed:
            _remove_generated_path(target_file)
            continue
        skill_md = source_dir / "SKILL.md"
        if not skill_md.exists():
            logger.warning(
                "External skills: %s missing SKILL.md (copilot)", source_dir
            )
            continue
        try:
            raw = skill_md.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("External skills: cannot read %s: %s", skill_md, exc)
            continue

        body = _strip_frontmatter(raw)
        if not body:
            body = raw.strip()

        target_root.mkdir(parents=True, exist_ok=True)
        header = (
            f"<!-- AUGUR-GENERATED source=external/{skill_name}/SKILL.md -->\n"
        )
        try:
            target_file.write_text(header + body + "\n", encoding="utf-8")
            written += 1
        except OSError as exc:
            logger.warning(
                "External skills: failed to write %s: %s", target_file, exc
            )
    if written:
        logger.info(
            "✅ Distributed %d external skill(s) to %s (Copilot)",
            written,
            target_root,
        )
    return written


def _register_marketplace_for_claude_code(
    bundles: list[ExternalSkillBundle],
    *,
    home_marketplaces: Path | None = None,
) -> int:
    """Register vendored bundles in Claude Code's known_marketplaces.json (ADR-605).

    Claude Code installs marketplaces from a global ``known_marketplaces.json``
    keyed by marketplace name. We add a ``directory`` source pointing at the
    vendored submodule path so users can run
    ``/plugin install <skill>@<bundle-id>``.
    """
    import json
    from datetime import datetime, timezone

    if home_marketplaces is None:
        home_marketplaces = (
            Path.home() / ".claude" / "plugins" / "known_marketplaces.json"
        )

    targeted = [b for b in bundles if b.targets.get("claude_code") == "marketplace"]
    if not targeted:
        return 0

    if not home_marketplaces.parent.exists():
        # Claude Code not installed locally — skip silently rather than
        # creating a partial state for an absent client.
        logger.info(
            "External skills: %s missing; skipping marketplace registration",
            home_marketplaces.parent,
        )
        return 0

    try:
        if home_marketplaces.exists():
            data = json.loads(home_marketplaces.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        else:
            data = {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "External skills: cannot parse %s: %s", home_marketplaces, exc
        )
        return 0

    changed = 0
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    for bundle in targeted:
        marketplace_name = bundle.id.split("-")[-1] if "-" in bundle.id else bundle.id
        # Use bundle.id as the canonical key — kepano-obsidian-skills.
        key = bundle.id
        desired = {
            "source": {
                "source": "directory",
                "path": str(bundle.source),
            },
            "installLocation": str(bundle.source),
            "lastUpdated": timestamp,
        }
        existing = data.get(key)
        # Only rewrite when source/installLocation drift (don't churn timestamp).
        if (
            isinstance(existing, dict)
            and existing.get("source") == desired["source"]
            and existing.get("installLocation") == desired["installLocation"]
        ):
            continue
        if isinstance(existing, dict) and "lastUpdated" in existing:
            desired["lastUpdated"] = existing["lastUpdated"]
        data[key] = desired
        changed += 1
        # Silence "marketplace_name unused" while preserving rationale comment.
        del marketplace_name

    if changed:
        try:
            home_marketplaces.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
            logger.info(
                "✅ Registered %d external bundle(s) in %s",
                changed,
                home_marketplaces,
            )
        except OSError as exc:
            logger.warning(
                "External skills: failed to write %s: %s",
                home_marketplaces,
                exc,
            )
            return 0
    return changed
