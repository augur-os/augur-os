"""auto-test-build: Dashboard build verification with auto-fix.

Difficulty escalation:
  d0: Surface — verify dashboard directory exists
  d1: Fix stale cache + module-resolution via cache clear / pnpm install
  d2: Delegate type-error and syntax-error to headless Claude CLI
  d3+: Same as d2 with extended timeouts and error parsing
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
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from src.lib.llm_retry import resolve_cli as _find_cli
from src.lib.ops_protocol import OpsContext, ScanResult, FixResult, write_report

logger = logging.getLogger(__name__)

name = "auto-test-build"

DIFFICULTY_SPEC = {
    0: "Surface check — verify dashboard directory exists",
    1: "Content check — run lifecycle-locked dashboard build",
    2: "Deep check — run lifecycle-locked dashboard build with extended timeout",
    3: "Exhaustive — run lifecycle-locked dashboard build and parse error categories",
    4: "Expert — full build with type-checking and bundle analysis",
}
EXPANSION_TARGETS = [
    {
        "category": "auto-test-dashboard",
        "difficulty": 2,
        "min_clean_streak": 2,
        "reason": "build remains clean, so expand into mounted dashboard runtime checks",
    },
    {
        "category": "auto-test-pages",
        "difficulty": 2,
        "min_clean_streak": 3,
        "reason": "build and dashboard smoke stay clean, so widen into page-route coverage",
    },
]


def _dashboard_dir(project_root: Path) -> Path:
    return project_root / "apps" / "dashboard"


def _command(name: str) -> str | None:
    candidates = [f"{name}.cmd", name] if os.name == "nt" else [name]
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _pnpm_cmd() -> list[str]:
    pnpm = _command("pnpm")
    if pnpm:
        return [pnpm]
    corepack = _command("corepack")
    if corepack:
        return [corepack, "pnpm"]
    return ["pnpm"]


def _run_build(dashboard_dir, timeout: int = 300) -> subprocess.CompletedProcess:
    cmd = (
        [*_pnpm_cmd(), "run", "build:safe"]
        if os.name == "nt"
        else ["./scripts/build.sh"]
    )
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(dashboard_dir),
    )


def _run_typecheck(dashboard_dir, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["npx", "tsc", "--noEmit"],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(dashboard_dir),
    )


_LIFECYCLE_GATE_RE = "lifecycle gate denied"


def _summarize_build_failure(stderr: str, stdout: str = "") -> dict:
    output = "\n".join(part for part in (stderr, stdout) if part).strip()
    lowered = output.lower()
    category = "unknown"
    if _LIFECYCLE_GATE_RE in lowered:
        category = "lifecycle-gate"
    elif any(s in lowered for s in (
        "cannot find module",
        "cannot find package",
        "module not found",
        "can't resolve",
        "err_module_not_found",
        "node_modules missing",
        "did you mean to install",
        "local package.json exists, but node_modules missing",
    )):
        category = "module-resolution"
    elif any(s in lowered for s in (
        "turbopackinternalerror", "corrupted",
        "unable to open static sorted file",
        "failed to restore task data",
        "enoent", "prerender-manifest", "app-paths-manifest", "build-manifest",
    )):
        category = "stale-cache"
    elif "type error" in lowered or "typescript error" in lowered:
        category = "type-error"
    elif "syntax error" in lowered or "unexpected token" in lowered:
        category = "syntax-error"
    elif "invalid" in lowered and "config" in lowered:
        category = "config-error"
    return {
        "error": output[:2000],
        "category": category,
    }


def scan(ctx: OpsContext) -> ScanResult:
    dashboard_dir = _dashboard_dir(ctx.project_root)
    if not dashboard_dir.exists():
        return ScanResult(issues=[], summary="No dashboard directory", severity="info")

    # Build verification is critical when explicitly configured at d1+, but keep
    # the d0 surface pass reachable when no minimum is enforced.
    effective_difficulty = max(ctx.difficulty, int(ctx.config.get("min_difficulty", 0)))

    # d0 surface check only if min_difficulty isn't enforced
    if effective_difficulty < 1:
        return ScanResult(
            issues=[], summary="Dashboard directory exists (d0 surface only)",
            severity="info", health="verified",
        )

    timeout = int(ctx.config.get("build_timeout", 300))
    if effective_difficulty >= 2:
        timeout = max(timeout, int(ctx.config.get("deep_build_timeout", 600)))
    try:
        result = _run_build(dashboard_dir, timeout=timeout)
    except subprocess.TimeoutExpired:
        return ScanResult(
            issues=[{"error": "Build timed out", "timeout": timeout}],
            summary=f"Build timed out after {timeout}s",
            severity="error",
        )

    # Lifecycle gate denial is an environment issue, not a build error.
    # The dashboard_lifecycle gate blocks concurrent builds — retry later.
    combined_output = (result.stderr or "") + (result.stdout or "")
    if result.returncode != 0 and _LIFECYCLE_GATE_RE in combined_output.lower():
        return ScanResult(
            issues=[],
            summary="Build skipped: lifecycle gate denied (dashboard busy)",
            severity="info",
            health="environment",
        )

    if result.returncode == 0:
        if effective_difficulty >= 4:
            typecheck_timeout = int(ctx.config.get("typecheck_timeout", 240))
            try:
                typecheck = _run_typecheck(dashboard_dir, timeout=typecheck_timeout)
            except subprocess.TimeoutExpired:
                return ScanResult(
                    issues=[{"error": "Type-check timed out", "timeout": typecheck_timeout, "category": "typecheck-timeout"}],
                    summary=f"Build succeeded but type-check timed out after {typecheck_timeout}s",
                    severity="error",
                )
            if typecheck.returncode != 0:
                failure = _summarize_build_failure(typecheck.stderr, typecheck.stdout)
                failure["phase"] = "typecheck"
                failure["exit_code"] = typecheck.returncode
                return ScanResult(
                    issues=[failure],
                    summary=f"Build succeeded but type-check failed ({failure['category']})",
                    severity="error",
                )
        return ScanResult(issues=[], summary="Build succeeded", severity="info")

    failure = _summarize_build_failure(result.stderr, result.stdout)
    failure["exit_code"] = result.returncode
    return ScanResult(
        issues=[failure],
        summary=(
            f"Build failed ({failure['category']}, exit {result.returncode})"
            if effective_difficulty >= 3
            else f"Build failed (exit {result.returncode})"
        ),
        severity="error",
    )


def _clear_next_cache(dashboard_dir: Path) -> bool:
    """Remove .next/cache and .next/dev to fix stale/corrupted build artifacts."""
    cleared = False
    for subdir in ("cache", "dev"):
        target = dashboard_dir / ".next" / subdir
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            cleared = True
    return cleared


def _extract_error_files(error_output: str) -> list[str]:
    """Extract file paths from TypeScript/Next.js build error output.

    Looks for patterns like:
      ./app/foo/page.tsx:12:5
      Type error: ... in apps/dashboard/features/components/Foo.tsx
      Error: ... at /absolute/path/to/file.tsx (line:col)
    """
    patterns = [
        # Next.js build error format: ./relative/path.tsx:line:col
        re.compile(r"\./([^\s:]+\.(?:tsx?|jsx?))(?=:\d+)"),
        # TypeScript error with path
        re.compile(r"((?:skills|apps)/[^\s:]+\.(?:tsx?|jsx?))"),
    ]
    files: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in pattern.finditer(error_output):
            # Use capturing group if present, otherwise full match
            fpath = (match.group(1) if match.lastindex else match.group(0)).lstrip("./")
            if fpath not in seen:
                seen.add(fpath)
                files.append(fpath)
    return files


def _build_fix_prompt(file_paths: list[str], error_output: str, category: str) -> str:
    """Build a prompt for headless Claude CLI to fix build errors."""
    file_list = "\n".join(f"  - {f}" for f in file_paths[:5])
    error_excerpt = error_output[:1500]
    return (
        f"Fix a dashboard build {category} with the smallest safe change.\n"
        f"Affected files:\n{file_list}\n\n"
        f"Build error output:\n```\n{error_excerpt}\n```\n\n"
        "Rules:\n"
        "- Only modify the listed files.\n"
        "- Do not add @ts-ignore, eslint-disable, or any error suppression.\n"
        "- Do not remove data sources or features to silence errors.\n"
        "- Fix the actual type/syntax issue in the source.\n"
        "- Preserve existing behavior except the specific fix.\n"
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Attempt to fix build failures based on error category.

    Difficulty escalation:
    - d0: report only -- summarize build errors without attempting fixes
    - d1+: auto-fix stale-cache (clear .next/cache + rebuild) and
            module-resolution (pnpm install + rebuild)
    - d2+: delegate type-error and syntax-error to headless Claude CLI
            for AI-assisted source fixes
    """
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: {len(issues)} build error(s) to investigate",
        )

    if not issues:
        return FixResult(success=True, summary="No build errors to fix", fix_type="report")

    # Build fixes use the same effective difficulty as scan — stale-cache
    # and module-resolution are safe ops (cache clear, pnpm install) that
    # should always be attempted when a build failure is detected.
    effective_difficulty = max(ctx.difficulty, int(ctx.config.get("min_difficulty", 0)))

    dashboard_dir = _dashboard_dir(ctx.project_root)
    changes: list[str] = []
    actions: list[dict] = []
    remaining: list[dict] = []

    install_timeout = 120 if effective_difficulty < 2 else 240
    build_timeout = 300 if effective_difficulty < 2 else 600

    for issue in issues:
        category = issue.get("category", "unknown")

        # --- Stale cache: clear .next/cache and .next/dev, then rebuild ---
        if category == "stale-cache":
            cleared = _clear_next_cache(dashboard_dir)
            if not cleared:
                remaining.append({**issue, "fix_attempted": "cache clear", "result": "no cache dirs found"})
                continue

            try:
                verify = _run_build(dashboard_dir, timeout=build_timeout)
            except subprocess.TimeoutExpired:
                remaining.append({**issue, "fix_attempted": "cache clear + rebuild", "result": "rebuild timed out"})
                continue

            if verify.returncode == 0:
                actions.append({"fixed": "stale-cache", "method": "clear .next/cache + rebuild"})
                changes.append("apps/dashboard/.next/")
            else:
                # Cache clear wasn't enough — also try pnpm install
                try:
                    subprocess.run(
                        ["pnpm", "install"],
                        capture_output=True, text=True, timeout=install_timeout,
                        cwd=str(dashboard_dir),
                    )
                    verify2 = _run_build(dashboard_dir, timeout=build_timeout)
                except subprocess.TimeoutExpired:
                    remaining.append({**issue, "fix_attempted": "cache clear + pnpm install", "result": "timed out"})
                    continue

                if verify2.returncode == 0:
                    actions.append({"fixed": "stale-cache", "method": "clear .next/cache + pnpm install + rebuild"})
                    changes.append("apps/dashboard/.next/")
                else:
                    remaining.append({
                        **issue,
                        "fix_attempted": "cache clear + pnpm install",
                        "result": "build still fails after cache clear",
                    })
            continue

        # --- Module resolution: pnpm install ---
        if category == "module-resolution":
            try:
                install = subprocess.run(
                    ["pnpm", "install", "--frozen-lockfile"],
                    capture_output=True, text=True, timeout=install_timeout,
                    cwd=str(dashboard_dir),
                )
                if install.returncode != 0:
                    subprocess.run(
                        ["pnpm", "install"],
                        capture_output=True, text=True, timeout=install_timeout,
                        cwd=str(dashboard_dir),
                    )
            except subprocess.TimeoutExpired:
                remaining.append({**issue, "fix_attempted": "pnpm install", "result": "install timed out"})
                continue

            try:
                verify = _run_build(dashboard_dir, timeout=build_timeout)
            except subprocess.TimeoutExpired:
                remaining.append({**issue, "fix_attempted": "pnpm install", "result": "build timed out"})
                continue

            if verify.returncode == 0:
                actions.append({"fixed": "module-resolution", "method": "pnpm install"})
                changes.append("apps/dashboard/")
            else:
                remaining.append({
                    **issue,
                    "fix_attempted": "pnpm install",
                    "result": "build still fails",
                    "fix_instruction": (
                        "pnpm install did not resolve the missing module. "
                        "Check if the package is listed in package.json, "
                        "or if the import path is correct."
                    ),
                })
            continue

        if category == "lifecycle-gate":
            actions.append({"skipped": "lifecycle-gate", "reason": "transient"})
            continue

        # --- Type errors and syntax errors: delegate to headless CLI at d2+ ---
        if category in ("type-error", "syntax-error") and effective_difficulty >= 2:
            error_output = issue.get("error", "")
            error_files = _extract_error_files(error_output)
            if not error_files:
                remaining.append({
                    **issue,
                    "fix_instruction": (
                        f"Could not extract file paths from {category} output. "
                        "Run the build manually and fix the reported errors."
                    ),
                })
                continue

            try:
                cli_path = _find_cli()
            except RuntimeError:
                cli_path = None

            if not cli_path:
                remaining.append({
                    **issue,
                    "fix_instruction": (
                        f"Headless CLI not available to auto-fix {category}. "
                        f"Affected files: {', '.join(error_files[:5])}"
                    ),
                })
                continue

            prompt = _build_fix_prompt(error_files, error_output, category)
            allowed_tools = "Read,Edit,Write,Grep,Glob"
            max_turns = str(ctx.config.get("max_turns", 8))
            fix_timeout = ctx.config.get("fix_timeout", 180)

            try:
                cli_result = subprocess.run(
                    [
                        cli_path,
                        "--print",
                        "--max-turns", max_turns,
                        "--allowedTools", allowed_tools,
                        "-p", prompt,
                    ],
                    capture_output=True, text=True, timeout=fix_timeout,
                    cwd=str(ctx.project_root),
                )
            except subprocess.TimeoutExpired:
                remaining.append({
                    **issue,
                    "fix_attempted": f"CLI delegation ({category})",
                    "result": f"CLI timed out after {fix_timeout}s",
                })
                continue

            if cli_result.returncode != 0:
                remaining.append({
                    **issue,
                    "fix_attempted": f"CLI delegation ({category})",
                    "result": f"CLI exited with code {cli_result.returncode}",
                })
                continue

            # Verify the fix by rebuilding
            try:
                verify = _run_build(dashboard_dir, timeout=build_timeout)
            except subprocess.TimeoutExpired:
                remaining.append({**issue, "fix_attempted": f"CLI fix ({category})", "result": "verify build timed out"})
                continue

            if verify.returncode == 0:
                actions.append({"fixed": category, "method": "CLI delegation", "files": error_files[:5]})
                changes.extend(error_files[:5])
            else:
                remaining.append({
                    **issue,
                    "fix_attempted": f"CLI delegation ({category})",
                    "result": "build still fails after CLI fix",
                    "files_attempted": error_files[:5],
                })
            continue

        # --- Remaining: enrich with fix instructions ---
        enriched = dict(issue)
        if category == "type-error":
            enriched["fix_instruction"] = (
                "TypeScript type error in the build. "
                "Run `pnpm --filter dashboard exec tsc --noEmit` to see full error output. "
                "Fix the type error in the source file. (Raise difficulty to d2+ for AI-assisted fix.)"
            )
        elif category == "syntax-error":
            enriched["fix_instruction"] = (
                "Syntax error in the build. Check recent changes for "
                "unclosed brackets, missing semicolons, or invalid JSX. "
                "(Raise difficulty to d2+ for AI-assisted fix.)"
            )
        elif category == "config-error":
            enriched["fix_instruction"] = (
                "Build configuration error. Check next.config.js, "
                "tsconfig.json, and tailwind.config.ts for issues."
            )
        else:
            enriched["fix_instruction"] = (
                f"Build failed with category '{category}'. "
                f"Review the error output and fix the root cause."
            )
        remaining.append(enriched)

    # Write report for remaining issues
    if remaining:
        report_data = {
            "issues": remaining,
            "fixed_count": len([a for a in actions if "fixed" in a]),
            "by_category": {},
        }
        for r in remaining:
            cat = r.get("category", "unknown")
            report_data["by_category"][cat] = report_data["by_category"].get(cat, 0) + 1
        report_path = write_report(ctx, "test-build-latest.json", report_data)
        actions.append({"report": str(report_path), "remaining_count": len(remaining)})

    fixed_count = len([a for a in actions if "fixed" in a])
    parts = []
    if fixed_count:
        parts.append(f"auto-fixed {fixed_count} build error(s)")
    if remaining:
        parts.append(f"{len(remaining)} issue(s) need manual fix (see report)")
    summary = "; ".join(parts) if parts else "No fixable build errors"

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary=summary,
        fix_type="code-fix" if changes else "report",
    )
