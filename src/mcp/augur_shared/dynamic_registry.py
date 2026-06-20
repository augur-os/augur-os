from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from src.mcp.augur_shared.client_surface import should_register_dynamic_markdown_resource
from src.mcp.augur_shared.compat import list_skills as registry_list_skills
from src.mcp.augur_shared.interfaces import SkillRecord

_dynamic_registered = False


@dataclass(frozen=True)
class PromptSpec:
    name: str
    trigger: str
    title: str
    description: str


def _slugify(text: str) -> str:
    """Normalize text into an MCP-compliant slug (^[a-zA-Z0-9_-]+$)."""
    # 1. Lowercase and replace common separators with spaces for better replacement later
    text = text.lower().replace("/", " ").replace(".", " ")
    # 2. Remove all non-alphanumeric/underscore/hyphen characters (excluding spaces)
    text = re.sub(r"[^a-z0-9\s_-]", "", text)
    # 3. Replace whitespace with dashes
    text = re.sub(r"\s+", "-", text)
    # 4. Strip leading/trailing dashes
    return text.strip("-")


def _build_prompt_specs(skill: SkillRecord) -> list[PromptSpec]:
    """Build unique MCP prompt specs for a skill's triggers.

    Command skills commonly expose both slash-style and bare triggers
    (for example ``/commands`` and ``commands``). Both normalize to the same
    MCP prompt name, so we keep the first occurrence and drop later duplicates.
    """
    seen_names: set[str] = set()
    specs: list[PromptSpec] = []
    skill_name = getattr(skill, "name", None) or skill.id
    description = str(getattr(skill, "description", "") or "").strip()
    for trigger in skill.triggers:
        trigger_slug = _slugify(trigger)
        if not trigger_slug:
            continue
        prompt_name = trigger_slug if trigger_slug == skill_name else f"{skill_name}_{trigger_slug}"
        if prompt_name in seen_names:
            continue
        seen_names.add(prompt_name)
        specs.append(
            PromptSpec(
                name=prompt_name,
                trigger=trigger,
                title=trigger,
                description=description,
            )
        )
    return specs


def _should_register_dynamic_skill(skill: SkillRecord) -> bool:
    """Only canonical Augur/plugin-cache skills should become MCP capabilities."""
    origin = str(getattr(skill, "origin", "") or "")
    if origin.endswith(("-local", "-global")):
        return False
    tier = getattr(skill, "tier", None)
    return not (isinstance(tier, int) and tier >= 2 and origin)


def register_dynamic_capabilities(
    *,
    mcp: FastMCP,
    skills_dir: Path,
    metrics: Any,
    logger: Any,
    **_kwargs: Any,
) -> None:
    """Dynamically register skills as MCP resources and prompts."""
    global _dynamic_registered
    if _dynamic_registered:
        return
    _dynamic_registered = True

    try:
        from .server import _get_discovery_client

        client_id = _get_discovery_client() or ""
    except ImportError:
        client_id = ""

    skip_prompts = client_id.lower() in ("gemini", "codex")

    logger.info("Registering dynamic Augur capabilities...")
    skills = [skill for skill in registry_list_skills(plugins_dir=skills_dir) if _should_register_dynamic_skill(skill)]
    skills_by_name = {skill.name: skill for skill in skills}
    _register_shared_resource_templates(mcp=mcp, skills_by_name=skills_by_name)
    used_names: set[str] = set()

    for skill in skills:
        if skill.name in used_names:
            continue

        used_names.add(skill.name)

        _register_skill_resources(
            mcp=mcp,
            skill_id=skill.name,
            skill=skill,
            metrics=metrics,
            skip_prompts=skip_prompts,
        )


def _register_shared_resource_templates(
    *,
    mcp: FastMCP,
    skills_by_name: dict[str, SkillRecord],
) -> None:
    """Register a small set of parameterized resource templates."""

    def _resolve_skill(skill: str) -> SkillRecord | None:
        return skills_by_name.get(skill)

    @mcp.resource(
        "augur://skill/{skill}/overview",
        name="skill-overview",
        description="Read a skill overview by skill id.",
        mime_type="text/markdown",
    )
    def get_skill_overview(skill: str) -> str:
        entry = _resolve_skill(skill)
        if entry is None:
            return f"Skill not found: {skill}"
        return (entry.path / "SKILL.md").read_text(encoding="utf-8")

    @mcp.resource(
        "augur://skill/{skill}/module/{module}",
        name="skill-module",
        description="Read a top-level module markdown file for a skill.",
        mime_type="text/markdown",
    )
    def get_skill_module(skill: str, module: str) -> str:
        entry = _resolve_skill(skill)
        if entry is None:
            return f"Skill not found: {skill}"
        module_file = entry.path / "modules" / f"{module}.md"
        if not module_file.exists():
            return f"Module not found: {skill}/{module}"
        return module_file.read_text(encoding="utf-8")

    @mcp.resource(
        "augur://skill/{skill}/reference/{reference}",
        name="skill-reference",
        description="Read a top-level reference markdown file for a skill.",
        mime_type="text/markdown",
    )
    def get_skill_reference(skill: str, reference: str) -> str:
        entry = _resolve_skill(skill)
        if entry is None:
            return f"Skill not found: {skill}"
        reference_file = entry.path / "references" / f"{reference}.md"
        if not reference_file.exists():
            return f"Reference not found: {skill}/{reference}"
        return reference_file.read_text(encoding="utf-8")


def _register_skill_resources(
    *,
    mcp: FastMCP,
    skill_id: str,
    skill: SkillRecord,
    metrics: Any,
    skip_prompts: bool = False,
) -> None:
    # 1. Register Skill Overview Resource
    def _make_overview_func(path: Path):
        def get_overview() -> str:
            return path.read_text()

        return get_overview

    # Use explicit name to avoid "get_overview" collision across skills
    overview_uri = f"augur://{skill_id}/overview"
    mcp.resource(overview_uri, name=f"{skill_id}/overview")(_make_overview_func(skill.path / "SKILL.md"))

    # 2. Register Modules as Resources
    modules_dir = skill.path / "modules"
    if modules_dir.exists():
        for module_file in modules_dir.glob("*.md"):
            if not should_register_dynamic_markdown_resource(module_file):
                continue
            module_name = module_file.stem
            uri = f"augur://{skill_id}/modules/{module_name}"

            def _make_module_func(path: Path):
                def get_module_content() -> str:
                    return path.read_text()

                return get_module_content

            # Use explicit name to avoid "get_module_content" collision
            mcp.resource(uri, name=f"{skill_id}/modules/{module_name}")(_make_module_func(module_file))

    # 3. Register References as Resources
    refs_dir = skill.path / "references"
    if refs_dir.exists():
        for ref_file in refs_dir.glob("*.md"):
            if not should_register_dynamic_markdown_resource(ref_file):
                continue
            ref_name = ref_file.stem
            uri = f"augur://{skill_id}/references/{ref_name}"

            def _make_ref_func(path: Path):
                def get_ref_content() -> str:
                    return path.read_text()

                return get_ref_content

            # Use explicit name to avoid "get_ref_content" collision
            mcp.resource(uri, name=f"{skill_id}/references/{ref_name}")(_make_ref_func(ref_file))

    # 4. Register Triggers as Prompts
    if not skip_prompts:
        for spec in _build_prompt_specs(skill):

            def _make_prompt_func(s_name: str, trig: str):
                def prompt_func() -> str:
                    return (
                        f"I want to use the {s_name} skill for: {trig}. "
                        "Please load the relevant modules and help me with this task."
                    )

                return prompt_func

            mcp.prompt(
                name=spec.name,
                title=spec.title,
                description=spec.description,
            )(_make_prompt_func(skill_id, spec.trigger))

    # 5. Script-as-tool registration removed.
    # All legitimate tools are statically registered in domain/core/infrastructure
    # modules with curated names and descriptions. Blindly registering every .py
    # script created ~150 tools with bad names (e.g. daemon___init__,
    # apple_apple_notes) and no descriptions.
