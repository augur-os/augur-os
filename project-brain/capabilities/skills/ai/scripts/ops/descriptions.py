"""auto-descriptions: Generate missing SKILL.md descriptions using headless Claude CLI.

Extracted from KnowledgeEnrichmentLoop._generate_description (ADR-200).
Scan returns empty (fed externally by the engine); fix runs Claude CLI headlessly.
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
import subprocess
from pathlib import Path

from src.lib.llm_retry import resolve_cli as _find_cli
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult

name = "auto-descriptions"


def scan(ctx: OpsContext) -> ScanResult:
    """No scanner — description issues are fed externally by the engine.

    Returns empty so the daemon does not spontaneously generate descriptions
    without an explicit external trigger (e.g. a new skill being discovered).
    """
    return ScanResult(
        issues=[],
        summary="No scanner — issues fed externally",
        severity="info",
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Use headless Claude CLI to generate a SKILL.md description for each issue."""
    if ctx.dry_run:
        skills = [i.get("skill", i.get("path", "?")) for i in issues]
        return FixResult(
            success=True,
            summary=f"Dry run: would generate descriptions for {', '.join(skills)}",
        )

    cli_path = _find_cli()
    if not cli_path:
        return FixResult(
            success=False,
            summary="Claude CLI not found — cannot generate descriptions",
        )

    all_actions: list[dict] = []
    failed: list[str] = []

    for issue in issues:
        skill_path = issue.get("path", "")
        skill_name = issue.get("skill", Path(skill_path).name if skill_path else "unknown")

        if not skill_path:
            failed.append(f"{skill_name}(no path)")
            continue

        prompt = (
            f"Analyze the skill at {skill_path} and generate "
            "a concise SKILL.md description. Write it to the skill directory."
        )
        result = subprocess.run(
            [
                cli_path, "--print", "--max-turns", "8",
                "--allowedTools", "Read,Write,Grep,Glob",
                "-p", prompt,
            ],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(ctx.project_root),
        )
        if result.returncode != 0:
            failed.append(f"{skill_name}(CLI exit {result.returncode})")
            continue

        all_actions.append({"skill": skill_name, "generated": True})

    success = len(failed) == 0
    summary_parts = [f"Generated descriptions for {len(all_actions)} skill(s)"]
    if failed:
        summary_parts.append(f"failed: {', '.join(failed)}")

    return FixResult(
        success=success,
        actions=all_actions,
        summary="; ".join(summary_parts),
    )
