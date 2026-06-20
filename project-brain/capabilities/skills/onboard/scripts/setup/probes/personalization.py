"""Personalization setup probes."""

from __future__ import annotations

from src.config.paths import get_runtime_dir, get_vault_dir

from .helpers import count_markdown, done, pending, yaml_enabled
from ..types import ProbeResult


def private_skill() -> ProbeResult:
    vault_dir = get_vault_dir()
    manifest = next(_private_skill_manifests(vault_dir), None)
    if manifest is not None:
        try:
            detail = manifest.relative_to(vault_dir)
        except ValueError:
            detail = manifest
        return done(f"private skill exists: {detail}")
    return pending("no private skill found")


def _private_skill_manifests(vault_dir):
    for root, pattern in (
        (vault_dir / "skills", "*/SKILL.md"),
        (vault_dir / "capabilities" / "skills", "**/SKILL.md"),
    ):
        if not root.exists():
            continue
        for manifest in root.glob(pattern):
            if _is_visible_path(manifest.relative_to(root)):
                yield manifest


def _is_visible_path(path) -> bool:
    return not any(part.startswith(".") for part in path.parts)


def saved_prompt() -> ProbeResult:
    vault_dir = get_vault_dir()
    prompts = vault_dir / "prompts"
    legacy_count = count_markdown(prompts, exclude_readme=True)
    notes_count = _count_prompt_notes(vault_dir / "notes")
    count = legacy_count + notes_count
    if count > 0:
        return done(f"{count} saved prompt notes")
    return pending("no saved prompts beyond README")


def _count_prompt_notes(notes_dir) -> int:
    if not notes_dir.exists():
        return 0
    try:
        from src.lib.frontmatter_utils import parse_frontmatter
    except Exception:
        return 0

    count = 0
    for note in notes_dir.glob("*.md"):
        if note.name.lower() == "readme.md":
            continue
        try:
            metadata, _body = parse_frontmatter(note, include_sidecar_config=False)
        except Exception:
            continue
        if metadata.get("x-augur-note-type") == "prompt":
            count += 1
    return count


def first_ask() -> ProbeResult:
    history = get_runtime_dir() / "ask-history.jsonl"
    if history.exists() and history.read_text(encoding="utf-8").strip():
        return done("ask history exists")
    return pending("no /ask history recorded")


def integration() -> ProbeResult:
    from src.lib.brain_layout import vault_machine_dir

    runtime_integrations = get_runtime_dir() / "integrations"
    vault_integrations = vault_machine_dir(get_vault_dir(), "integrations")
    for directory in (runtime_integrations, vault_integrations):
        if not directory.exists():
            continue
        if any(yaml_enabled(path) for path in directory.glob("*.yaml")):
            return done("enabled integration found")
    return pending("no enabled integrations")
