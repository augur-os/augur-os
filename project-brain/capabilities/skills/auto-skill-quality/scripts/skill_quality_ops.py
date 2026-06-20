"""Auto skill quality — improve skill scores toward tier A across all dimensions.

OpsCommand module: scan() scores all skills via the unified scorer and
returns issues per dimension gated by difficulty level. fix() applies
dimension-specific improvements (instruction, product, UI, wiring) with
git revert on build failure or score regression.

Dimension fixers live in fixers/ subpackage — one module per dimension.

Difficulty levels:
  d0: Scan only — report tier distribution, worst skills, user journey gaps
  d1: Fix instruction — rewrite descriptions, expand bodies, add examples
  d2: Fix instruction + product — create dirs, generate seeds, scaffold actions
  d3: Fix instruction + product + UI — promote page states, add page contributions
  d4: Fix all dimensions including wiring — fix toolName refs, remove fs bypasses
"""
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
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.config.paths import get_project_root, get_project_brain_skills_dir
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
)

if __package__ in {None, ""}:
    # Allow direct script execution while avoiding cross-skill namespace collisions
    _scripts_dir = str(Path(__file__).resolve().parent)
    if _scripts_dir not in sys.path:
        sys.path.append(_scripts_dir)

    from fixers import (  # noqa: E402
        fix_instruction,
        fix_product,
        fix_ui,
        fix_wiring,
        generate_seed_evals,
        git_commit,
        git_revert,
        is_blacklisted,
        llm_fix,
        read_skill_context,
        record_revert,
        verify_build,
    )
else:
    from .fixers import (  # noqa: E402
        fix_instruction,
        fix_product,
        fix_ui,
        fix_wiring,
        generate_seed_evals,
        git_commit,
        git_revert,
        is_blacklisted,
        llm_fix,
        read_skill_context,
        record_revert,
        verify_build,
    )

name = "auto-skill-quality"

DIFFICULTY_SPEC = {
    0: "Scan only — report tier distribution, worst skills, user journey gaps",
    1: "Fix instruction — rewrite descriptions, expand bodies, add examples",
    2: "Fix instruction + product — create dirs, generate seeds, scaffold actions",
    3: "Fix instruction + product + UI — promote page states, add page contributions",
    4: "Fix all dimensions including wiring — fix toolName refs, remove fs bypasses",
}


def _get_scorer():
    """Import scorer lazily to avoid circular imports."""
    from src.lib.skill_scorer import score_all_skills
    return score_all_skills


def _check_resolvable_issues() -> list[dict]:
    """Run the ADR-741 catalog audit and emit findings as maintenance issues.

    Report-only in v1: every finding surfaces as `kind="maintenance"` so the
    auto-loop reports drift without flipping red. Phase 2 (next release) will
    promote orphans + collisions to `actionable`.
    """
    try:
        from . import check_resolvable as _cr  # type: ignore[import-not-found]
    except ImportError:
        try:
            import check_resolvable as _cr  # type: ignore[import-not-found]
        except ImportError as exc:
            return [make_issue(
                category="skill-coverage",
                detail=f"check-resolvable module unavailable: {exc}",
                kind="maintenance",
                root_cause_type="scanner_bug",
                fixability="manual",
            )]

    try:
        report = _cr.run_audit()
    except Exception as exc:  # noqa: BLE001 — report-only step
        return [make_issue(
            category="skill-coverage",
            detail=f"check-resolvable failed: {exc}",
            kind="maintenance",
            root_cause_type="scanner_bug",
            fixability="manual",
        )]

    counts = report["summary"]["findings"]
    if not any(
        counts.get(bucket, 0)
        for bucket in (
            "unrouted_intents",
            "routing_collisions",
            "orphaned_skills",
            "stale_capability_entries",
            "retired_aliases",
        )
    ):
        return []

    summary_msg = (
        f"check-resolvable: "
        f"{counts['unrouted_intents']} unrouted, "
        f"{counts['routing_collisions']} collisions, "
        f"{counts['orphaned_skills']} orphans, "
        f"{counts['stale_capability_entries']} stale, "
        f"{counts.get('retired_aliases', 0)} retired aliases"
    )
    return [make_issue(
        category="skill-coverage",
        detail=summary_msg,
        kind="maintenance",
        root_cause_type="repo_bug",
        fixability="manual",
    )]


# ── Scan ─────────────────────────────────────────────────────────────────


def scan(ctx: OpsContext) -> ScanResult:
    """Score all skills and return issues for non-A skills."""
    score_all = _get_scorer()

    try:
        scored = score_all()
    except Exception as e:
        return ScanResult(
            issues=[make_issue(
                category="skill-quality",
                detail=f"Scorer failed: {e}",
                kind="scanner-defect",
                root_cause_type="scanner_bug",
                fixability="manual",
            )],
            summary=f"Scorer error: {e}",
            severity="error",
            health="broken",
        )

    skills = scored["skills"]
    below_a = [s for s in skills if s["tier"] != "A"]
    below_a.sort(key=lambda s: s["score"])

    # --upgrade N: force d3+ difficulty and target the N worst skills (ADR-446)
    upgrade_n = ctx.config.get("upgrade_n")
    if upgrade_n:
        try:
            upgrade_n = int(upgrade_n)
        except (TypeError, ValueError):
            upgrade_n = None
    if upgrade_n and upgrade_n > 0:
        max_skills = upgrade_n
    else:
        max_skills = ctx.config.get("max_skills_per_cycle", 5)
    targets = below_a[:max_skills]

    # Write rank.json sidecar for each scored skill (skip unchanged)
    from src.lib.generated_artifacts import write_stable_json
    skills_dir = get_project_brain_skills_dir(get_project_root())
    for skill_result in scored["skills"]:
        skill_dir = skills_dir / skill_result["name"]
        if not skill_dir.is_dir():
            continue  # Don't create dirs for skills that don't exist on disk
        skill_evals_dir = skill_dir / "evals"
        skill_evals_dir.mkdir(exist_ok=True)
        rank_data = {
            "tier": skill_result["tier"],
            "score": skill_result["score"],
            "rubric": skill_result.get("rubric", "domain-low"),
            "structural": {
                "score": skill_result["score"],
                "dimensions": skill_result["dimensions"],
            },
            "behavioral": skill_result.get("behavioral"),
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }
        write_stable_json(skill_evals_dir / "rank.json", rank_data, volatile_keys=["computed_at"])

    issues: list[dict] = []
    for skill in targets:
        dims = skill["dimensions"]
        skill_name = skill["name"]
        base_path = f"project-brain/capabilities/skills/{skill_name}"

        # Instruction issues (all difficulties report, d1+ actionable)
        if dims["instruction"]["score"] < 75:
            sig = dims["instruction"]["signals"]
            issues.append(make_issue(
                category="skill-quality",
                detail=(
                    f'{skill_name}: instruction {dims["instruction"]["score"]}/100 — '
                    f'{sig["desc_words"]}w desc, {sig["body_lines"]}L body, '
                    f'{sig["sections"]} sections'
                ),
                path=f"{base_path}/SKILL.md",
                kind="actionable" if ctx.difficulty >= 1 else "maintenance",
                root_cause_type="repo_bug",
                fixability="auto" if ctx.difficulty >= 1 else "manual",
                dimension="instruction",
                skill_name=skill_name,
                score=dims["instruction"]["score"],
                signals=sig,
            ))

        # Product issues (d2+)
        if ctx.difficulty >= 2 and dims["product"]["score"] < 75:
            sig = dims["product"]["signals"]
            missing = [k.replace("has_", "").replace("_", " ")
                       for k, v in sig.items() if not v]
            issues.append(make_issue(
                category="skill-quality",
                detail=(
                    f'{skill_name}: product {dims["product"]["score"]}/100 — '
                    f'missing: {", ".join(missing) or "none"}'
                ),
                path=f"{base_path}/",
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="auto",
                dimension="product",
                skill_name=skill_name,
                score=dims["product"]["score"],
                signals=sig,
            ))

        # UI issues (d3+)
        if ctx.difficulty >= 3 and dims["ui"]["score"] < 75:
            sig = dims["ui"]["signals"]
            issues.append(make_issue(
                category="skill-quality",
                detail=(
                    f'{skill_name}: ui {dims["ui"]["score"]}/100 — '
                    f'{sig["page_count"]} pages, {sig["mature_pages"]} mature'
                ),
                path=f"{base_path}/SKILL.md",
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="auto",
                dimension="ui",
                skill_name=skill_name,
                score=dims["ui"]["score"],
                signals=sig,
            ))

        # Wiring issues (d4)
        if ctx.difficulty >= 4 and dims["wiring"]["score"] < 75:
            sig = dims["wiring"]["signals"]
            problems = [k.replace("has_", "").replace("no_", "missing ")
                        for k, v in sig.items() if not v]
            issues.append(make_issue(
                category="skill-quality",
                detail=(
                    f'{skill_name}: wiring {dims["wiring"]["score"]}/100 — '
                    f'{", ".join(problems) or "none"}'
                ),
                path=f"{base_path}/",
                kind="actionable",
                root_cause_type="repo_bug",
                fixability="auto",
                dimension="wiring",
                skill_name=skill_name,
                score=dims["wiring"]["score"],
                signals=sig,
            ))

    # Evolution gap when all skills at A
    if not below_a:
        issues.append(evolution_gap(
            "All skills at tier A (>=75). Tier A threshold could be raised to 85 "
            "to target remaining quality gaps in UI maturity and wiring integrity. "
            "Next: update DEFAULT_THRESHOLDS in skill_scorer.py and weight config.",
            category="skill-quality",
        ))

    # check-resolvable audit step (ADR-741): catalog-wide coverage report.
    # Report-only in v1 — findings emit as maintenance issues, never blocking.
    issues.extend(_check_resolvable_issues())

    total = len(skills)
    return ScanResult(
        issues=issues,
        summary=f"{len(below_a)}/{total} skills below tier A, targeting {len(targets)} this cycle",
        severity="warning" if below_a else "info",
        health="degraded" if len(below_a) > total * 0.5 else "verified",
        items_scanned=total,
    )


# ── Fix Entrypoint ───────────────────────────────────────────────────────


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Fix issues across dimensions with git safety net.

    At d3+, if file-level fixes don't improve a skill's score (plateau),
    escalates to llm_fix() and signals the engine via an llm_escalation action
    (ADR-446).
    """
    if ctx.dry_run:
        return FixResult(success=True, summary=f"Dry run: {len(issues)} issues")

    score_all = _get_scorer()
    root = ctx.project_root
    all_actions: list[dict] = []
    all_changes: list[str] = []

    # Group issues by skill
    by_skill: dict[str, list[dict]] = {}
    for issue in issues:
        sname = issue.get("skill_name", "")
        if sname:
            by_skill.setdefault(sname, []).append(issue)

    for skill_name, skill_issues in by_skill.items():
        skill_dir = get_project_brain_skills_dir(root) / skill_name
        if not skill_dir.exists():
            continue

        # Revert blacklist gate: skip skills that were recently reverted
        if is_blacklisted(root, skill_name):
            all_actions.append({
                "skill": skill_name, "skipped": True,
                "reason": "blacklisted (recently reverted)",
            })
            continue

        # Score before
        try:
            before = score_all(skill_name=skill_name)
            before_score = before["skills"][0]["score"] if before["skills"] else 0
            before_tier = before["skills"][0]["tier"] if before["skills"] else "F"
        except Exception:
            before_score = 0
            before_tier = "F"

        # Read context once per skill
        ctx_info = read_skill_context(skill_name, skill_dir)
        changes: list[str] = []
        touched_dims: set[str] = set()

        # Apply fixes per dimension
        for issue in skill_issues:
            dim = issue.get("dimension", "")
            signals = issue.get("signals", {})

            if dim == "instruction":
                dim_changes = fix_instruction(skill_name, skill_dir, signals, ctx_info)
            elif dim == "product":
                dim_changes = fix_product(skill_name, skill_dir, signals, ctx_info)
            elif dim == "ui":
                dim_changes = fix_ui(skill_name, skill_dir, signals, ctx_info)
            elif dim == "wiring":
                dim_changes = fix_wiring(skill_name, skill_dir, signals, ctx_info)
            else:
                dim_changes = []

            if dim_changes:
                touched_dims.add(dim)
                changes.extend(dim_changes)

        # After product fixes, generate seed evals if missing (d2+)
        if ctx.difficulty >= 2:
            evals_dir = skill_dir / "evals"
            if not (evals_dir / "evals.json").exists():
                fm_current = ctx_info.get("fm", {})
                seed = generate_seed_evals(skill_dir, fm_current)
                if seed["evals"]:
                    evals_dir.mkdir(exist_ok=True)
                    (evals_dir / "evals.json").write_text(json.dumps(seed, indent=2))
                    all_changes.append(f"{skill_name}: generated {len(seed['evals'])} seed evals")
                    changes.append(f"generated {len(seed['evals'])} seed evals")
                    # Evals are text-only — mark product so verify_build skips pnpm
                    touched_dims.add("product")

        if not changes:
            # No file-level fixes possible — check for LLM escalation at d3+
            if ctx.difficulty >= 3 and before_tier != "A":
                llm_prompt = llm_fix(ctx, skill_issues)
                if llm_prompt:
                    all_actions.append({
                        "kind": "llm_escalation",
                        "skill": skill_name,
                        "prompt": llm_prompt,
                        "reason": f"file fixes plateaued at d{ctx.difficulty}, score={before_score}",
                    })
            continue

        # Commit — stage only this skill's directory to avoid sweeping
        # unrelated working-tree changes (which git revert would destroy).
        commit_msg = f"auto(skill-quality): improve {skill_name} [{', '.join(changes[:3])}]"
        if not git_commit(root, commit_msg, paths=[str(skill_dir)]):
            continue

        # Build verify — pass touched dimensions so text-only fixes skip the full build
        build_ok = verify_build(root, dimensions=touched_dims) if ctx.config.get("build_verify", True) else True

        # Re-score (clear cache to get fresh results)
        try:
            import src.lib.skill_scorer as _scorer_mod
            _scorer_mod._cache.clear()
            after = score_all(skill_name=skill_name)
            after_score = after["skills"][0]["score"] if after["skills"] else 0
            after_tier = after["skills"][0]["tier"] if after["skills"] else "F"
        except Exception:
            after_score = before_score
            after_tier = before_tier

        # Revert if build failed or score regressed
        revert = False
        reason = ""
        if not build_ok:
            revert = True
            reason = "build failure"
        elif ctx.config.get("revert_on_regression", True) and after_score < before_score:
            revert = True
            reason = f"score regression {before_score}->{after_score}"

        if revert:
            git_revert(root)
            record_revert(root, skill_name, reason)
            all_actions.append({
                "skill": skill_name, "reverted": True, "reason": reason,
                "before": before_score, "after": after_score,
            })
        else:
            all_actions.append({
                "skill": skill_name, "reverted": False,
                "before": before_score, "after": after_score,
                "changes": changes,
            })
            all_changes.extend(changes)

            # Post-fix plateau check: score improved but still below A at d3+
            # Escalate to LLM for the remaining gap (ADR-446)
            if ctx.difficulty >= 3 and after_tier != "A":
                remaining = [
                    i for i in skill_issues
                    if i.get("score", 100) < 75
                ]
                if remaining:
                    llm_prompt = llm_fix(ctx, remaining)
                    if llm_prompt:
                        all_actions.append({
                            "kind": "llm_escalation",
                            "skill": skill_name,
                            "prompt": llm_prompt,
                            "reason": (
                                f"file fixes applied ({', '.join(changes[:2])}), "
                                f"score {before_score}->{after_score} still below A"
                            ),
                        })

    succeeded = sum(1 for a in all_actions if not a.get("reverted") and a.get("kind") != "llm_escalation")
    total_file_fixes = sum(1 for a in all_actions if a.get("kind") != "llm_escalation")
    llm_escalations = sum(1 for a in all_actions if a.get("kind") == "llm_escalation")

    summary_parts = []
    if total_file_fixes:
        summary_parts.append(f"Fixed {succeeded}/{total_file_fixes} skills")
    else:
        summary_parts.append("No skills needed file fixes")
    if llm_escalations:
        summary_parts.append(f"{llm_escalations} LLM escalation(s) queued")

    return FixResult(
        success=succeeded > 0 or total_file_fixes == 0,
        actions=all_actions,
        changes=all_changes,
        summary=", ".join(summary_parts),
        fix_type="code-fix",
    )
