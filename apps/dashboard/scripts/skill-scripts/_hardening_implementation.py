"""Implementation prompt generation for the Hardening ADR Generator (ADR-065).

Generates the implementation prompt section with team structure,
execution plan, and file inference for each dimension.
"""

import re
from pathlib import Path
from typing import Any

from ._hardening_constants import DIMENSION_AGENT_MAP, SCOPE_LABELS
from ._hardening_report import (
    _action_signal_conflict_note,
    _dimension_label_map,
    get_selected_dimensions,
    get_user_choices,
)
from ._hardening_sections import _build_execution_phases


# ---------------------------------------------------------------------------
# File inference
# ---------------------------------------------------------------------------


def _infer_files_for_dimension(
    dim_id: str,
    hub_id: str,
    plugin_id: str,
    skill_id: str,
    scoped_skills: list[str] | None,
    findings: list[str],
    project_root: Path,
) -> list[str]:
    """Infer likely edit targets using real plugin structure (augur-first)."""

    def _rel(path: Path) -> str:
        try:
            return path.relative_to(project_root).as_posix()
        except Exception:
            return path.as_posix()

    def _discover_hub_skill_roots() -> list[Path]:
        roots: list[Path] = []
        skills_dir = project_root / "plugins" / plugin_id / "skills"
        owner_root = skills_dir / skill_id if skill_id else None
        if owner_root and owner_root.exists() and not scoped_skills:
            roots.append(owner_root)
        if not skills_dir.exists():
            return roots

        scoped_set = {s for s in (scoped_skills or []) if s}
        if scoped_set:
            for scoped_skill in sorted(scoped_set):
                candidate = skills_dir / scoped_skill
                if candidate.exists() and candidate.is_dir() and candidate not in roots:
                    roots.append(candidate)
            if roots:
                return roots

        try:
            import yaml as _yaml
        except Exception:
            return roots

        for candidate in sorted(skills_dir.iterdir()):
            if not candidate.is_dir():
                continue
            augur_yaml = candidate / "augur.yaml"
            if not augur_yaml.exists():
                continue
            try:
                data = _yaml.safe_load(augur_yaml.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
            contributes_to = str(data.get("contributes_to", "") or "").strip()
            hub_cfg = data.get("hub", {}) if isinstance(data.get("hub"), dict) else {}
            owns_hub = str(hub_cfg.get("id", "") or "").strip() == hub_id
            if contributes_to == hub_id or owns_hub:
                if candidate not in roots:
                    roots.append(candidate)

        return roots

    def _extract_hub_routes() -> list[str]:
        routes: list[str] = []
        for finding in findings:
            for match in re.findall(r"/[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*", str(finding)):
                if match == f"/{hub_id}" or match.startswith(f"/{hub_id}/"):
                    if match not in routes:
                        routes.append(match)
        return routes

    def _resolve_page_targets(roots: list[Path], limit: int = 3) -> list[str]:
        targets: list[str] = []
        routes = _extract_hub_routes()
        for route in routes:
            parts = route.strip("/").split("/")
            subparts = parts[1:] if len(parts) > 1 else []
            for root in roots:
                for base in (root / "augur" / "dashboard", root / "dashboard"):
                    candidate_subpaths: list[list[str]] = [subparts]
                    # Mounted routes may include a skill segment (e.g. /observability/daemon/health)
                    # while source files are rooted at skill/dashboard/health/page.tsx.
                    if subparts and subparts[0] == root.name:
                        candidate_subpaths.append(subparts[1:])
                    for candidate in candidate_subpaths:
                        page_path = base.joinpath(*candidate, "page.tsx") if candidate else base / "page.tsx"
                        if page_path.exists():
                            rel = _rel(page_path)
                            if rel not in targets:
                                targets.append(rel)
        if targets:
            return targets[:limit]

        for root in roots:
            for base in (root / "augur" / "dashboard", root / "dashboard"):
                if base.exists():
                    rel = _rel(base)
                    if rel not in targets:
                        targets.append(rel)
        return targets[:limit]

    roots = _discover_hub_skill_roots()
    if not roots:
        fallback = project_root / "plugins" / plugin_id / "skills" / skill_id
        roots = [fallback]

    manifests = [_rel(root / "augur.yaml") for root in roots if (root / "augur.yaml").exists()]
    mcp_modules = [
        _rel(root / "scripts" / "mcp" / "__init__.py")
        for root in roots
        if (root / "scripts" / "mcp" / "__init__.py").exists()
    ]
    dashboard_dirs = [
        _rel(root / "augur" / "dashboard")
        for root in roots
        if (root / "augur" / "dashboard").exists()
    ]
    api_dirs = [
        _rel(root / "augur" / "api")
        for root in roots
        if (root / "augur" / "api").exists()
    ]
    data_dirs = [
        _rel(root / "augur" / "data")
        for root in roots
        if (root / "augur" / "data").exists()
    ]

    if dim_id in ("ui_compliance", "performance"):
        targets = _resolve_page_targets(roots)
        if targets:
            return targets
        return (dashboard_dirs or manifests or [_rel(roots[0])])[:3]

    if dim_id == "page_coverage":
        return (dashboard_dirs or manifests or [_rel(roots[0])])[:3]

    if dim_id == "api_completeness":
        return (api_dirs or manifests or [_rel(roots[0])])[:3]

    if dim_id == "mcp_tool_wiring":
        targets = mcp_modules + manifests
        return (targets or [_rel(roots[0])])[:3]

    if dim_id == "user_value":
        targets = api_dirs + data_dirs + manifests
        return (targets or [_rel(roots[0])])[:3]

    if dim_id == "workflows":
        workflow_dirs: list[str] = []
        for root in roots:
            for path in (root / "assets" / "actions", root / "augur" / "data" / "prompts"):
                if path.exists():
                    rel = _rel(path)
                    if rel not in workflow_dirs:
                        workflow_dirs.append(rel)
        return (workflow_dirs or manifests or [_rel(roots[0])])[:3]

    if dim_id == "cross_hub_connectivity":
        return (_resolve_page_targets(roots) or dashboard_dirs or manifests or [_rel(roots[0])])[:3]

    if dim_id == "action_buttons":
        return (manifests + data_dirs or [_rel(roots[0])])[:3]

    if dim_id == "wow_effect":
        targets = _resolve_page_targets(roots) + manifests
        deduped: list[str] = []
        for t in targets:
            if t not in deduped:
                deduped.append(t)
        return (deduped or dashboard_dirs or manifests or [_rel(roots[0])])[:3]

    return [_rel(roots[0])]


# ---------------------------------------------------------------------------
# Implementation Prompt Generation
# ---------------------------------------------------------------------------


def generate_implementation_prompt(report: dict[str, Any], adr_number: int) -> str:
    """Generate the full implementation prompt section with team structure."""
    # Import here to avoid circular dependency at module level
    from src.config.paths import get_project_root
    from src.lib.adr_utils import get_adr_dir

    hub_id = report.get("audit", {}).get("hub_id", "unknown")
    hub_title = report.get("audit", {}).get("hub_title", "Unknown")
    skill_id = report.get("audit", {}).get("skill_id", hub_id)
    plugin_id = report.get("audit", {}).get("plugin_id", "lifestyle")
    dimensions = get_selected_dimensions(report)
    user_choices = get_user_choices(report)
    phases = _build_execution_phases(report, dimensions)
    project_root = get_project_root()
    audit_url = str(report.get("audit", {}).get("url", "") or f"http://localhost:3000/{hub_id}")
    conflict_note = _action_signal_conflict_note(report)
    adr_slug = str(
        report.get("audit", {}).get("adr_slug")
        or report.get("audit", {}).get("report_id")
        or hub_id
    ).replace("_", "-")
    scope = str(report.get("audit", {}).get("scope", "hub") or "hub")
    extension_id = str(report.get("audit", {}).get("extension_id", "") or "")
    scoped_skills_raw = report.get("audit", {}).get("scoped_skills", [])
    scoped_skills = [str(s).strip() for s in scoped_skills_raw if str(s).strip()] if isinstance(scoped_skills_raw, list) else []
    if scope == "extension" and extension_id and not scoped_skills:
        scoped_skills = [extension_id]

    team_name = f"adr-{adr_number:03d}-{adr_slug}-hardening"

    lines = [
        "## Implementation Prompt",
        "",
        "> Paste this into Claude Code to execute this ADR using Agent Teams.",
        "> Auto-generated by `generate_hardening_adr.py` from ADR-065.",
        "",
        f"You are implementing **ADR-{adr_number:03d}: {hub_title} Hardening**.",
        "",
        f"Read the full ADR: `{get_adr_dir()}/ADR-{adr_number:03d}-{adr_slug}-hardening.md`",
        "",
        f"User-selected scope: **{SCOPE_LABELS.get(user_choices['scope'], user_choices['scope'])}**.",
    ]
    if user_choices["skip_dimensions"]:
        labels = _dimension_label_map(report)
        skip_labels = [labels.get(dim_id, dim_id) for dim_id in user_choices["skip_dimensions"]]
        lines.extend(
            [
                f"Skipped dimensions: {', '.join(skip_labels)}.",
                "",
            ]
        )
    else:
        lines.append("")
    if conflict_note:
        lines.extend(
            [
                f"Scoring confidence note: {conflict_note}",
                "Execution gate: complete reconciliation first, then re-run hardening audit + ADR generation before executing later phases.",
                "",
            ]
        )

    # Offload protocol section
    lines.extend(
        [
            "### Offload Protocol (ADR-054)",
            "",
            "Before dispatching each step, check if it can be offloaded to a cheap CLI:",
            "",
            "1. Resolve the default client from runtime `preferences.yaml` via ClientResolver",
            "2. Resolve the CLI command from vault `config/ai/cli_agents.yaml`",
            "3. If the step's tier is `low`, use that CLI for the current work directory and target files",
            "4. Review the JSON output",
            "5. Record the verdict (accept / fix / escalate)",
            "6. If no CLI is configured OR tier is `medium`/`high` -> do the step yourself",
            "",
        ]
    )

    # Team orchestration section
    lines.extend(
        [
            "### Team Orchestration",
            "",
            "Create a team and spawn teammates to execute the plan below:",
            "",
            f'1. **Create team**: `TeamCreate(team_name="{team_name}", description="Implementing ADR-{adr_number:03d}: {hub_title} Hardening")`',
            "2. **Create tasks**: For each step in the Execution Plan, create a task via `TaskCreate`. Set `blocked_by` for PIPELINE dependencies.",
            "3. **Spawn teammates**: For each unique agent role, spawn a teammate:",
            "   ```",
            f'   Task(subagent_type="general-purpose", team_name="{team_name}", name="{{role}}",',
            '        model="{tier-model}", prompt="You are \'{{role}}\' on the {team_name} team.',
            "        Read your profile: .claude/agents/{{role}}.md",
            "        Check TaskList for your assigned tasks. After each task: TaskUpdate to complete,",
            '        SendMessage to team lead. If blocked, move to next available task.")',
            "   ```",
            "4. **Profile loading**: Each teammate MUST read `.claude/agents/{name}.md` for iron laws and constraints",
            "5. **Communication**: Teammates use `SendMessage` to report completion, request reviews, and debate",
            "6. **Dependencies**: PARALLEL phases -> spawn all at once. PIPELINE phases -> use task blocking",
            "7. **Shutdown**: When all phases pass, send `shutdown_request` to all teammates",
            "",
            "**Model mapping**: `low` -> haiku, `medium` -> sonnet, `high` -> opus",
            "",
        ]
    )

    # Execution plan
    lines.extend(
        [
            "### Execution Plan",
            "",
            f"**Team name**: `{team_name}`",
            "",
        ]
    )

    # Generate phase tables
    for phase in phases:
        phase_num = int(phase.get("display_num", 0) or 0)
        phase_key = str(phase.get("key", ""))
        phase_label = str(phase.get("title", ""))
        dims = phase.get("dims", [])
        phase_agents = {DIMENSION_AGENT_MAP.get(dim_id, {"agent": "developer"}).get("agent", "developer") for dim_id, _ in dims}
        can_parallel = len(phase_agents) > 1
        is_provisional = bool(phase.get("provisional"))

        if phase_key == "reconciliation":
            strategy = "PIPELINE"
        elif phase_key == "phase1":
            has_wow = any(dim_id == "wow_effect" for dim_id, _ in dims)
            if has_wow and len(dims) > 1 and can_parallel:
                strategy = "MIXED (lock wow-effect acceptance criteria first, then parallelize remaining critical dimensions)"
            elif has_wow and len(dims) > 1 and not can_parallel:
                strategy = "PIPELINE (wow-effect first, then sequential critical fixes by the same agent)"
            elif len(dims) > 1 and can_parallel:
                strategy = "PARALLEL"
            else:
                strategy = "PIPELINE"
        else:
            strategy = "PARALLEL" if len(dims) > 1 and can_parallel else "PIPELINE"
        if is_provisional and phase_key != "reconciliation":
            strategy = f"{strategy} (provisional until post-reconciliation rerun)"

        lines.extend(
            [
                f"#### Phase {phase_num}: {phase_label}",
                f"**Strategy**: {strategy}",
                "",
            ]
        )
        if phase_num > 1:
            lines.append(f"Dependency: complete Phase {phase_num - 1} and merge results before starting.")
            lines.append("")
        if is_provisional and phase_key != "reconciliation":
            lines.append("Do not execute this phase until reconciliation is complete and the ADR is regenerated.")
            lines.append("")
        lines.extend(
            [
                "| Step | Agent | Tier | Task | Files |",
                "|------|-------|------|------|-------|",
            ]
        )

        if phase_key == "reconciliation":
            files_str = ", ".join(
                [
                    "`skills/frontend/scripts/pattern_compliance_audit.py`",
                    "`skills/frontend/scripts/generate_hardening_adr.py`",
                    "`skills/frontend/scripts/_hardening_report.py`",
                ]
            )
            task_desc = "Reconcile action semantics across User Value, Workflows, and Action Buttons; regenerate aligned findings"
            lines.append(f"| {phase_num}.1 | architect | medium | {task_desc} | {files_str} |")
            lines.append("")
            continue

        phase_step_counter = 0
        for dim_id, dim_data in dims:
            phase_step_counter += 1
            mapping = DIMENSION_AGENT_MAP.get(dim_id, {"agent": "developer", "tier": "medium", "chains": []})
            agent = mapping["agent"]
            tier = mapping["tier"]
            label = dim_data.get("label", dim_id)
            score = dim_data.get("score", 0)
            findings = dim_data.get("findings", [])
            chains = mapping.get("chains", [])

            # Build task description
            if dim_id == "wow_effect" and score >= 90:
                task_desc = f"Preserve {label} ({score}/100) with live demo validation"
            else:
                task_desc = f"Fix {label} ({score}/100)"
            if findings:
                first_finding = findings[0]
                if len(first_finding) > 60:
                    first_finding = first_finding[:57] + "..."
                task_desc += f": {first_finding}"

            # Determine affected files
            files = _infer_files_for_dimension(
                dim_id=dim_id,
                hub_id=hub_id,
                plugin_id=plugin_id,
                skill_id=skill_id,
                scoped_skills=scoped_skills,
                findings=findings,
                project_root=project_root,
            )
            files_str = ", ".join(f"`{f}`" for f in files[:3])
            if chains:
                task_desc += " (Chains: " + ", ".join(f"`{c}`" for c in chains) + ")"

            lines.append(f"| {phase_num}.{phase_step_counter} | {agent} | {tier} | {task_desc} | {files_str} |")

        lines.append("")

    # Verification phase
    lines.extend(
        [
            "#### Final Phase: Verification",
            "",
            "| Step | Agent | Tier | Task |",
            "|------|-------|------|------|",
            "| V.1 | validator | low | Run all tests, verify no regressions |",
            f"| V.2 | frontend | low | Browser validation: open {audit_url} in Chrome MCP, screenshot each tab, check console for runtime errors, verify auth gates render cleanly |",
            "| V.3 | devops | low | MCP validation: cross-check all `mcp_tool` refs in `augur.yaml` against the current MCP tool registry/exposed server tools |",
            "| V.4 | architect | low | Verify ADR intent matches implementation |",
            "",
        ]
    )

    # Completion criteria
    lines.extend(
        [
            "### Completion Criteria",
            "",
        ]
    )

    flattened_dims = [item for phase in phases if phase.get("key") != "reconciliation" for item in phase.get("dims", [])]
    added_wow_hard_checks = False
    for dim_id, dim_data in flattened_dims:
        label = dim_data.get("label", dim_id)
        score = dim_data.get("score", 0)
        if dim_id == "wow_effect" and score >= 90:
            lines.append(
                f"- [ ] {label} maintained at >= 95/100 with a verified live demo flow"
            )
            if not added_wow_hard_checks:
                lines.append("- [ ] Wow candidate is confirmed in hub UI source (action label/id binding), not manifest-only")
                lines.append("- [ ] Wow demo includes before/after screenshots showing visible output")
                added_wow_hard_checks = True
        else:
            lines.append(f"- [ ] {label} improved from {score}/100 to >= 90")
    if conflict_note:
        lines.append("- [ ] Action scoring semantics reconciled across User Value, Workflows, and Action Buttons")
        lines.append("- [ ] Hardening audit re-run and ADR regenerated after reconciliation")

    lines.extend(
        [
            "- [ ] All phases executed",
            "- [ ] All tests pass (`pytest tests/`, `npm run build`)",
            "- [ ] Browser validation: page renders in Chrome MCP with zero console errors",
            "- [ ] MCP validation: all tool references in `augur.yaml` resolve to registered tools",
            "- [ ] No orphaned files or broken references",
            "- [ ] Every skill with dashboard contributions has an `augur.yaml` manifest (required for discovery and mount)",
            "- [ ] No structural integrity issues (`structural_issues` in audit report is empty)",
            f"- [ ] ADR-{adr_number:03d} status updated to Accepted",
            "",
        ]
    )

    return "\n".join(lines)
