#!/usr/bin/env python3
"""Run the repo-health autoloops (routine-platform + routine-vault ops) with fixes applied."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.lib.ops_protocol import OpsContext

_SKILLS_DIR = PROJECT_ROOT / "project-brain" / "capabilities" / "skills"

# ADR-756 consolidated the old loop-repo skill into routine-platform/routine-vault.
MODULES = [
    ("auto-dir-alignment", _SKILLS_DIR / "routine-platform" / "scripts" / "dir_alignment_ops.py"),
    ("auto-file-growth", _SKILLS_DIR / "routine-platform" / "scripts" / "file_growth_ops.py"),
    ("auto-git-health", _SKILLS_DIR / "routine-platform" / "scripts" / "git_health.py"),
    ("auto-repo-pollution", _SKILLS_DIR / "routine-platform" / "scripts" / "repo_pollution_ops.py"),
    ("auto-vault-hygiene", _SKILLS_DIR / "routine-vault" / "scripts" / "vault_hygiene_ops.py"),
]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def run_loop(name: str, module_path: Path, ctx: OpsContext) -> dict:
    print(f"\n{'='*60}")
    print(f"Running: {name} (difficulty={ctx.difficulty}, dry_run={ctx.dry_run})")
    print(f"{'='*60}")
    try:
        mod = _load_module(name, module_path)
        scan_result = mod.scan(ctx)
        print(f"Scan summary: {scan_result.summary}")
        print(f"Severity: {scan_result.severity}")
        print(f"Health: {scan_result.health}")
        if scan_result.issues:
            print(f"Issues found: {len(scan_result.issues)}")
            for i, issue in enumerate(scan_result.issues[:10], 1):
                detail = issue.get("detail") or issue.get("message", "")
                print(f"  {i}. {detail[:120]}")
            if len(scan_result.issues) > 10:
                print(f"  ... and {len(scan_result.issues) - 10} more")
        else:
            print("No issues found.")

        if scan_result.issues and hasattr(mod, "fix"):
            print(f"\n→ Applying fixes...")
            fix_result = mod.fix(ctx, list(scan_result.issues))
            print(f"Fix summary: {fix_result.summary}")
            print(f"Fix success: {fix_result.success}")
            if fix_result.changes:
                print(f"Changes ({len(fix_result.changes)}):")
                for c in fix_result.changes[:10]:
                    print(f"  • {c[:120]}")
                if len(fix_result.changes) > 10:
                    print(f"  ... and {len(fix_result.changes) - 10} more")
            return {
                "name": name,
                "status": "ok",
                "scan_summary": scan_result.summary,
                "fix_summary": fix_result.summary,
                "fix_success": fix_result.success,
                "severity": scan_result.severity,
                "health": scan_result.health,
                "issue_count": len(scan_result.issues),
                "changes_count": len(fix_result.changes) if fix_result.changes else 0,
            }

        return {
            "name": name,
            "status": "ok",
            "scan_summary": scan_result.summary,
            "severity": scan_result.severity,
            "health": scan_result.health,
            "issue_count": len(scan_result.issues),
        }
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"name": name, "status": "error", "error": str(e)}


def main() -> int:
    ctx = OpsContext(project_root=PROJECT_ROOT, difficulty=4, dry_run=False, verbose=True)
    results = []
    for name, module_path in MODULES:
        results.append(run_loop(name, module_path, ctx))

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in results:
        status = "✅" if r["status"] == "ok" else "❌"
        fix = f" | fixes: {r.get('fix_summary', 'N/A')}" if "fix_summary" in r else ""
        print(f"{status} {r['name']}: {r.get('scan_summary', r.get('error'))}{fix}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
