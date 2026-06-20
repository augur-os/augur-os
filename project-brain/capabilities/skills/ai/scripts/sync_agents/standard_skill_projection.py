"""Discovery helpers for standard multi-skill bundles.

Standard bundles keep their canonical source free of Augur frontmatter. A root
``DESCRIPTION.md`` describes the bundle, and each ``*/SKILL.md`` below it is a
client-usable skill.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml as _yaml


@dataclass(frozen=True)
class StandardSubskill:
    name: str
    path: Path
    title: str
    description: str


@dataclass(frozen=True)
class StandardSkillBundle:
    name: str
    path: Path
    title: str
    description: str
    subskills: list[StandardSubskill]


def _strip_frontmatter(raw: str) -> str:
    if not raw.startswith("---\n"):
        return raw
    try:
        end = raw.index("\n---", 4)
    except ValueError:
        return raw
    return raw[end + 4 :].lstrip("\n")


def _render_skill_frontmatter(
    name: str,
    description: str,
    allowed_tools: list[str] | None = None,
) -> str:
    metadata: dict[str, object] = {"name": name}
    if description:
        metadata["description"] = description
    if allowed_tools:
        metadata["allowed-tools"] = list(allowed_tools)
    return _yaml.safe_dump(
        metadata,
        sort_keys=False,
        allow_unicode=True,
    ).strip()


def _render_client_skill(
    name: str,
    description: str,
    body: str,
    allowed_tools: list[str] | None = None,
) -> str:
    return (
        f"---\n{_render_skill_frontmatter(name, description, allowed_tools)}\n---\n\n"
        f"{body.rstrip()}\n"
    )


def _heading_and_summary(path: Path) -> tuple[str, str]:
    body = _strip_frontmatter(path.read_text(encoding="utf-8"))
    title = path.stem
    summary = ""
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            if title == path.stem:
                title = stripped[2:].strip()
            continue
        summary = stripped
        break
    return title, summary


def is_standard_skill_bundle(root: Path) -> bool:
    return (root / "DESCRIPTION.md").is_file() and any(root.glob("*/SKILL.md"))


def discover_standard_skill_bundle(root: Path) -> StandardSkillBundle:
    description_path = root / "DESCRIPTION.md"
    if not description_path.is_file():
        raise FileNotFoundError(description_path)

    title, description = _heading_and_summary(description_path)
    subskills: list[StandardSubskill] = []
    for skill_path in sorted(root.glob("*/SKILL.md")):
        skill_title, skill_description = _heading_and_summary(skill_path)
        subskills.append(
            StandardSubskill(
                name=skill_path.parent.name,
                path=skill_path,
                title=skill_title,
                description=skill_description,
            )
        )

    if not subskills:
        raise ValueError(f"Standard skill bundle has no subskills: {root}")

    return StandardSkillBundle(
        name=root.name,
        path=root,
        title=title,
        description=description,
        subskills=subskills,
    )


def iter_standard_skill_bundles(skills_dir: Path) -> list[StandardSkillBundle]:
    bundles: list[StandardSkillBundle] = []
    for candidate in sorted(path for path in skills_dir.iterdir() if path.is_dir()):
        if not is_standard_skill_bundle(candidate):
            continue
        bundles.append(discover_standard_skill_bundle(candidate))
    return bundles


def iter_standard_skill_sources(
    skills_dir: Path,
) -> list[tuple[str, Path, str, str, str, bool]]:
    """Return ``skill_sync`` source tuples for standard bundle subskills."""
    sources: list[tuple[str, Path, str, str, str, bool]] = []
    for bundle in iter_standard_skill_bundles(skills_dir):
        for subskill in bundle.subskills:
            raw = subskill.path.read_text(encoding="utf-8")
            body = _strip_frontmatter(raw).strip()
            description = subskill.description or bundle.description
            if body:
                rendered = _render_client_skill(subskill.name, description, body)
                sources.append(
                    (
                        subskill.name,
                        subskill.path.parent,
                        rendered,
                        body,
                        description,
                        False,
                    )
                )
    return sources
