"""auto-security-audit: Scan all skills for security vulnerabilities.

5-stage offline pipeline:
  S1: Prompt injection detection
  S2: Secret scanning
  S3: Static code analysis
  S4: Integrity & trust
  S5: Permissions & policy
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
import logging
import shutil
from datetime import datetime
from pathlib import Path

from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
)
from src.lib.skill_paths import get_own_data_dir
from src.plugins.skill_discovery import discover_all_skills

try:
    from . import s1_prompt_injection, s2_secret_scanning, s3_static_analysis
    from . import s4_integrity, s5_permissions, tank_integration
except ImportError:
    import sys as _sys

    _scripts_dir = str(Path(__file__).resolve().parent)
    if _scripts_dir not in _sys.path:
        _sys.path.insert(0, _scripts_dir)
    import s1_prompt_injection, s2_secret_scanning, s3_static_analysis
    import s4_integrity, s5_permissions, tank_integration

name = "auto-security-audit"

DIFFICULTY_SPEC = {
    0: "Surface — report all findings",
    1: "Quarantine — flag critical/high skills",
    2: "Block — disable MCP registration, move scripts to _quarantine/",
    3: "Auto-remove — remove blocked external skills",
    4: "Expert — evolution gaps for Sigstore/SPDX",
}

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def _is_reportable_finding(finding: dict) -> bool:
    """Return whether a scanner finding should affect loop health."""
    severity = str(finding.get("severity") or "").lower()
    return severity not in {"info", "informational"}


def _external_skill(issue: dict) -> bool:
    """Return whether an issue belongs to an external installed skill."""
    return (
        int(issue.get("tier") or 0) >= 1
        and not bool(issue.get("canonical", True))
    )


def _score(findings: list[dict]) -> float:
    """Compute security score 0-10 from findings."""
    if not findings:
        return 10.0
    deduction = 0.0
    for f in findings:
        sev = SEVERITY_ORDER.get(f.get("severity", "info"), 0)
        deduction += sev * 0.5
    # Cap deduction so a single skill with many findings doesn't dominate
    deduction = min(deduction, 10.0)
    return max(0.0, 10.0 - deduction)


def _state(score: float, has_critical: bool) -> str:
    """Determine security state from score and critical findings.

    Policy: Only block on CRITICAL findings. High/medium volume
    gets quarantined, not blocked, to avoid volume-based false blocks.
    """
    if has_critical:
        return "blocked"
    if score < 5.0:
        return "quarantined"
    if score < 7.5:
        return "quarantined"
    return "approved"


def scan(ctx: OpsContext) -> ScanResult:
    """Scan all skills for security vulnerabilities."""
    skills = discover_all_skills()
    if not skills:
        return ScanResult(
            issues=[],
            summary="No skills discovered",
            severity="info",
            health="verified",
        )

    issues: list[dict] = []
    skills_scanned = 0

    for skill_record in skills:
        skill_name = skill_record.name
        skill_dir = Path(skill_record.path)
        if not skill_dir.exists():
            continue

        # Augur-managed skills (tier=0) need Augur frontmatter; external (tier>=1) don't
        is_augur_managed = skill_record.tier == 0

        findings = []
        findings.extend(s1_prompt_injection.scan_skill(skill_dir))
        findings.extend(s2_secret_scanning.scan_skill(skill_dir))
        findings.extend(s3_static_analysis.scan_skill(skill_dir))
        findings.extend(s4_integrity.scan_skill(skill_dir, is_augur_managed=is_augur_managed))
        findings.extend(s5_permissions.scan_skill(skill_dir, is_augur_managed=is_augur_managed))
        findings.extend(tank_integration.scan_skill_with_tank(skill_dir))

        reportable_findings = [f for f in findings if _is_reportable_finding(f)]
        score = _score(reportable_findings)
        has_critical = any(f.get("severity") == "critical" for f in reportable_findings)
        state = _state(score, has_critical)

        skills_scanned += 1

        if reportable_findings:
            issues.append(make_issue(
                category="security-audit",
                detail=f"{skill_name}: {len(reportable_findings)} finding(s), score={score:.1f}, state={state}",
                path=str(skill_dir),
                kind="actionable" if state in ("quarantined", "blocked") else "maintenance",
                severity="error" if state == "blocked" else ("warning" if state == "quarantined" else "info"),
                root_cause_type="policy_violation" if state == "blocked" else "code_defect",
                fixability="auto" if state in ("quarantined", "blocked") else "manual",
                skill_name=skill_name,
                score=score,
                state=state,
                findings=reportable_findings,
                tier=skill_record.tier,
                canonical=skill_record.canonical,
                source_root=getattr(skill_record, "source_root", ""),
                ownership=getattr(skill_record, "ownership", ""),
            ))

    # d4 evolution gap
    if ctx.difficulty >= 4 and not any(i.get("state") == "blocked" for i in issues):
        issues.append(evolution_gap(
            "Consider adding: offline Sigstore verification (cosign), SPDX license normalization, "
            "GitHub branch protection checks (when network available).",
            category="security-audit",
        ))

    severity = "error" if any(i.get("state") == "blocked" for i in issues) else (
        "warning" if issues else "info"
    )
    health = "broken" if severity == "error" else ("degraded" if issues else "verified")

    summary = f"Scanned {skills_scanned} skills, {len(issues)} with findings"
    if not issues:
        summary = f"Scanned {skills_scanned} skills — all clean"

    return ScanResult(
        issues=issues,
        summary=summary,
        severity=severity,
        health=health,
        items_scanned=skills_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Apply security fixes based on difficulty."""
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: {len(issues)} security issue(s)",
        )

    if not issues:
        return FixResult(success=True, summary="No issues to fix")

    if ctx.difficulty < 1:
        return FixResult(
            success=True,
            actions=[{"action": "report", "description": "d0 — report only"}],
            summary=f"No fixes at d0; {len(issues)} issue(s) reported",
            fix_type="report",
        )

    actions: list[dict] = []
    changes: list[str] = []

    # Load or create security-state.yaml in the vault-backed skill data dir.
    state_file = get_own_data_dir(__file__) / "security-state.yaml"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_data = {"version": "1.0", "last_scan": "", "skills": {}}
    if state_file.exists():
        try:
            import yaml as _yaml
            state_data = _yaml.safe_load(state_file.read_text(encoding="utf-8")) or state_data
        except Exception:
            pass

    for issue in issues:
        skill_name = issue.get("skill_name", "")
        state = issue.get("state", "approved")
        score = issue.get("score", 10.0)
        tier = issue.get("tier", 0)
        canonical = issue.get("canonical", True)

        # d1+: quarantine
        if ctx.difficulty >= 1 and state in ("quarantined", "blocked"):
            state_data["skills"][skill_name] = {
                "state": state,
                "score": score,
                "last_findings_hash": "",
            }
            actions.append({"action": "quarantine", "skill": skill_name, "state": state})
            changes.append(f"Quarantined {skill_name} ({state}, score={score:.1f})")

        # d2+: block
        if ctx.difficulty >= 2 and state == "blocked":
            skill_dir = Path(issue.get("path", ""))
            if skill_dir.exists():
                blocked_marker = skill_dir / ".augur-blocked"
                blocked_marker.write_text(f"Blocked by auto-security-audit at d{ctx.difficulty}\n")
                actions.append({"action": "block", "skill": skill_name})
                changes.append(f"Blocked {skill_name} (.augur-blocked marker)")

                # Move scripts to _quarantine/ for external installs only.
                scripts_dir = skill_dir / "scripts"
                if _external_skill(issue) and scripts_dir.exists():
                    quarantine_dir = skill_dir / "_quarantine"
                    quarantine_dir.mkdir(exist_ok=True)
                    for script in scripts_dir.iterdir():
                        if script.is_file():
                            try:
                                shutil.move(str(script), str(quarantine_dir / script.name))
                                changes.append(f"Moved {script.name} to _quarantine/")
                            except OSError:
                                pass

        # d3+: auto-remove external skills only
        if ctx.difficulty >= 3 and state == "blocked" and tier >= 1 and not canonical:
            skill_dir = Path(issue.get("path", ""))
            if skill_dir.exists() and not canonical:
                try:
                    shutil.rmtree(str(skill_dir))
                    actions.append({"action": "remove", "skill": skill_name})
                    changes.append(f"Removed blocked external skill {skill_name}")
                except OSError as e:
                    logger.warning("Failed to remove %s: %s", skill_dir, e)

    # Write state file
    if changes:
        state_data["last_scan"] = datetime.now().isoformat()
        import yaml as _yaml
        state_file.write_text(_yaml.safe_dump(state_data, default_flow_style=False), encoding="utf-8")
        actions.append({"action": "write_state", "file": str(state_file)})

    success = True
    summary = f"Applied {len(actions)} action(s), {len(changes)} change(s)" if changes else "No actionable fixes"
    return FixResult(
        success=success,
        actions=actions,
        changes=changes,
        summary=summary,
        fix_type="code-fix" if changes else "report",
    )
