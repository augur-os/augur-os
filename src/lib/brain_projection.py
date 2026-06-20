from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from src.lib.brain_context import ActiveBrainContext
from src.lib.brain_manifest import STANDARD_BRAIN_FILES, standard_brain_default_body
from src.lib.brain_registry_models import Brain, BrainType
from src.lib.frontmatter_utils import parse_frontmatter

if TYPE_CHECKING:
    from src.lib.brain_stack import BrainStack


@dataclass(frozen=True)
class BrainProjectionSources:
    rules: Path
    rules_label: str
    topics_root: Path
    topics_label: str
    skill_roots: tuple[Path, ...]
    agent_roots: tuple[Path, ...]
    policy_roots: tuple[Path, ...]
    workflow_roots: tuple[Path, ...]


@dataclass(frozen=True)
class StandardBrainFile:
    name: str
    path: Path
    label: str
    tier: BrainType
    brain_id: str


def resolve_brain_projection_sources(
    *,
    brain: Brain,
    attached_project: Path | None = None,
    project_root: Path | None = None,
) -> BrainProjectionSources:
    """Return brain-owned canonical roots used for AI-client projections.

    ADR-771 makes the brain layout the source model. During the ADR-770 physical
    migration window, repo docs can remain mapped project-brain sources instead
    of duplicated files under ``project-brain/``.
    """
    brain_root = Path(brain.data_root)
    project = attached_project or project_root
    project = project.resolve() if project is not None else None

    canonical_rules = brain_root / "instructions" / "agent-rules.md"
    canonical_topics = brain_root / "instructions" / "topics"
    if canonical_rules.is_file():
        rules = canonical_rules
        rules_label = _display_path(canonical_rules, project)
        topics_root = canonical_topics
        topics_label = _display_path(canonical_topics, project)
    else:
        mapped_root = (project / "docs" / "agent-topics") if project else None
        mapped_rules = mapped_root / "agent-rules.md" if mapped_root else None
        if brain.type is BrainType.PROJECT and mapped_rules is not None and mapped_rules.is_file():
            rules = mapped_rules
            rules_label = (
                "docs/agent-topics/agent-rules.md " "(mapped to project-brain/instructions/topics/agent-rules.md)"
            )
            topics_root = mapped_root
            topics_label = "docs/agent-topics (mapped to project-brain/instructions/topics)"
        elif mapped_rules is not None and mapped_rules.is_file():
            rules = mapped_rules
            rules_label = _display_path(mapped_rules, project)
            topics_root = mapped_root
            topics_label = _display_path(mapped_root, project)
        else:
            rules = canonical_rules
            rules_label = _display_path(canonical_rules, project)
            topics_root = canonical_topics
            topics_label = _display_path(canonical_topics, project)

    canonical_skills = brain_root / "capabilities" / "skills"
    skill_roots = _existing_or_declared(canonical_skills)
    if brain.type is BrainType.PROJECT and project is not None and not canonical_skills.is_dir():
        # ADR-770 fallback: the brain's own data_root is not yet physically
        # populated, so source skills from the attached project's project-brain.
        # When the brain data_root *does* carry skills (the normal case, and the
        # only correct source inside a git worktree whose attached_project is the
        # main checkout), keep brain_root so skills track the active tree like
        # agents/policies/workflows below — never the main checkout.
        skill_roots = (project / "project-brain" / "capabilities" / "skills",)

    return BrainProjectionSources(
        rules=rules,
        rules_label=rules_label,
        topics_root=topics_root,
        topics_label=topics_label,
        skill_roots=skill_roots,
        agent_roots=_existing_or_declared(brain_root / "capabilities" / "agents"),
        policy_roots=_existing_or_declared(brain_root / "policies"),
        workflow_roots=_existing_or_declared(brain_root / "workflows"),
    )


def collect_standard_brain_files(
    stack: BrainStack,
    *,
    project_root: Path | None = None,
) -> tuple[StandardBrainFile, ...]:
    """Return existing standard root files from least-specific to most-specific tier."""
    files: list[StandardBrainFile] = []
    seen_paths: set[Path] = set()
    for brain in stack.ordered():
        root = Path(brain.data_root)
        for name in STANDARD_BRAIN_FILES:
            path = root / name
            if not path.is_file():
                continue
            resolved = path.resolve(strict=False)
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            files.append(
                StandardBrainFile(
                    name=name,
                    path=path,
                    label=_display_path(path, project_root),
                    tier=brain.type,
                    brain_id=brain.id,
                )
            )
    return tuple(files)


def render_standard_brain_files_context(
    stack: BrainStack,
    *,
    project_root: Path | None = None,
    max_bytes: int = 8000,
) -> str:
    """Render compact standard brain-root file context for client instructions."""
    files = collect_standard_brain_files(stack, project_root=project_root)
    if not files or max_bytes <= 0:
        return ""

    # Pointer-only projection (size budget): list the brain-authored source files
    # and where they live, instead of embedding each body inline. Read the source
    # for full content. Files with an empty body are skipped as noise.
    lines = [
        "## Standard Brain Files",
        "",
        "Brain-authored source files (generated client files remain projections). " "Read the source for full content:",
        "",
    ]
    if _byte_len(_join_lines(lines)) > max_bytes:
        return ""

    pointer_added = False
    for item in files:
        body = _markdown_body(item.path).strip()
        if not body:
            continue
        default_body = standard_brain_default_body(item.name)
        if default_body is not None and body == default_body.strip():
            # Unfilled scaffold placeholder — skip to keep projections compact.
            continue
        candidate_line = f"- {_tier_label(item.tier)} / {item.name} — `{item.label}`"
        candidate = _join_lines([*lines, candidate_line])
        if _byte_len(candidate) > max_bytes:
            continue
        lines.append(candidate_line)
        pointer_added = True
    return _join_lines(lines) if pointer_added else ""


def render_augur_context_envelope(context: ActiveBrainContext) -> str:
    """Render the compact client-neutral Augur context envelope."""
    return yaml.safe_dump({"augur": context.to_header_dict()}, sort_keys=False)


def render_augur_stack_envelope(stack: BrainStack) -> str:
    """Render the client-neutral Augur envelope for the full tier stack.

    Superset of the single-brain envelope: keeps ``active_brain`` (= the most
    specific tier, for back-compat) and adds a ``stack`` block exposing the
    Global / User / Project tiers (ADR-781 Phase 2a).
    """
    most_specific = stack.most_specific()
    augur: dict[str, object] = {
        "active_brain": _envelope_tier(most_specific),
        "stack": _stack_block(stack),
    }
    if stack.project is not None:
        augur["attached_project"] = stack.project.to_header_dict()["attached_project"]
    else:
        augur["attached_project"] = None
    augur["generated_projection"] = True
    return yaml.safe_dump({"augur": augur}, sort_keys=False)


def _stack_block(stack: BrainStack) -> dict[str, object]:
    block: dict[str, object] = {"global": _envelope_tier(stack.global_brain)}
    if stack.user_brain is not None:
        block["user"] = _envelope_tier(stack.user_brain)
    if stack.project is not None:
        block["project"] = _envelope_tier(stack.project.active_brain)
    return block


def _envelope_tier(brain: Brain) -> dict[str, str]:
    return {
        "id": brain.id,
        "type": brain.type.value,
        "root": str(brain.data_root),
    }


def _existing_or_declared(path: Path) -> tuple[Path, ...]:
    return (path,)


def _markdown_body(path: Path) -> str:
    try:
        _meta, body = parse_frontmatter(path, include_sidecar_config=False)
    except OSError:
        return ""
    return body


def _join_lines(lines: list[str]) -> str:
    text = "\n".join(lines).rstrip()
    return f"{text}\n" if text else ""


def _byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def _tier_label(tier: BrainType) -> str:
    return {
        BrainType.GLOBAL: "Global",
        BrainType.PERSONAL: "User",
        BrainType.TEAM: "Team",
        BrainType.PROJECT: "Project",
    }.get(tier, tier.value.title())


def _display_path(path: Path, project_root: Path | None) -> str:
    if project_root is not None:
        try:
            return path.resolve().relative_to(project_root.resolve()).as_posix()
        except ValueError:
            pass
        except OSError:
            pass
    return path.as_posix()
