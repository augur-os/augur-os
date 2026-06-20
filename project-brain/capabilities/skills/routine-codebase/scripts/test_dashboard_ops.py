"""auto-test-dashboard: Jest dashboard test runner with hub scoping."""
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
import os
import shutil
import subprocess
from pathlib import Path

from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, write_report

name = "auto-test-dashboard"


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


def _jest_base_cmd(dashboard_dir: Path) -> list[str]:
    bin_dir = dashboard_dir / "node_modules" / ".bin"
    local_candidates = (
        [bin_dir / "jest.cmd", bin_dir / "jest"] if os.name == "nt" else [bin_dir / "jest"]
    )
    for local_jest in local_candidates:
        if local_jest.is_file():
            return [str(local_jest.resolve())]
    package_json = dashboard_dir / "package.json"
    if package_json.is_file():
        return [*_pnpm_cmd(), "test", "--"]
    return [*_pnpm_cmd(), "exec", "jest"]


def _ensure_generated_item_actions(
    dashboard_dir: Path,
    timeout: int,
) -> subprocess.CompletedProcess:
    env = {**os.environ, "CI": "1"}
    build_scripts = subprocess.run(
        ["node", "scripts/build-scripts.mjs"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=str(dashboard_dir),
        env=env,
    )
    if build_scripts.returncode != 0:
        return build_scripts
    return subprocess.run(
        ["node", "scripts/dist/generate-item-actions.mjs"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=str(dashboard_dir),
        env=env,
    )


def _run_jest(
    dashboard_dir,
    hub: str | None,
    timeout: int,
    test_paths: list[str] | None = None,
) -> subprocess.CompletedProcess:
    generated = _ensure_generated_item_actions(dashboard_dir, timeout)
    if generated.returncode != 0:
        return generated

    jest_cmd = _jest_base_cmd(dashboard_dir)
    cmd = [*jest_cmd, "--silent", "--no-coverage"]
    if hub:
        cmd += ["--testPathPatterns", hub]
    elif test_paths:
        cmd += ["--runTestsByPath", *test_paths]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=str(dashboard_dir),
        env={**os.environ, "CI": "1"},
    )


def _clear_jest_cache(dashboard_dir: Path, timeout: int) -> subprocess.CompletedProcess:
    cmd = [*_jest_base_cmd(dashboard_dir), "--clearCache"]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=str(dashboard_dir),
        env={**os.environ, "CI": "1"},
    )


def _summarize_jest_failure(stderr: str, stdout: str = "") -> dict:
    output = "\n".join(part for part in (stdout, stderr) if part).strip()
    lowered = output.lower()
    category = "test-failure"
    if any(
        marker in lowered
        for marker in (
            'command "jest" not found',
            "jest: command not found",
            "cannot find module 'jest'",
            'cannot find package "jest"',
            "node_modules missing",
            "did you mean to install",
            "err_pnpm_recursive_exec_first_fail",
            "cannot find package ",
        )
    ):
        category = "runner-missing"
    elif any(
        marker in lowered
        for marker in (
            "haste module naming collision",
            "jest-haste-map",
            "cache",
            "worker encountered",
            "a jest worker process",
        )
    ):
        category = "cache-corruption"
    return {
        "error": output[:2000] or "Jest failed with no captured output",
        "category": category,
    }


def _normalize_test_paths(
    project_root: Path,
    dashboard_dir: Path,
    test_paths: list[str],
) -> list[str]:
    normalized: list[str] = []
    for raw_path in test_paths:
        raw = Path(raw_path)
        candidates = []
        if raw.is_absolute():
            candidates.append(raw.resolve())
        else:
            candidates.append((project_root / raw).resolve())
            candidates.append((dashboard_dir / raw).resolve())

        resolved = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
        normalized.append(Path(os.path.relpath(str(resolved), dashboard_dir)).as_posix())
    return normalized


def scan(ctx: OpsContext) -> ScanResult:
    dashboard_dir = ctx.project_root / "apps" / "dashboard"
    if not dashboard_dir.exists():
        return ScanResult(issues=[], summary="No dashboard directory", severity="info")

    hub = ctx.config.get("hub")
    timeout = ctx.config.get("jest_timeout", 300)
    smoke_test_paths = ctx.config.get(
        "smoke_test_paths",
        ["tests/dashboard/api/agents-available.test.ts"],
    )
    normalized_smoke_paths = _normalize_test_paths(ctx.project_root, dashboard_dir, smoke_test_paths)

    try:
        result = _run_jest(
            dashboard_dir,
            hub,
            timeout,
            test_paths=None if hub else normalized_smoke_paths,
        )
    except subprocess.TimeoutExpired:
        return ScanResult(
            issues=[{"error": "Jest timed out", "timeout": timeout}],
            summary=f"Jest timed out after {timeout}s",
            severity="error",
        )
    except OSError as exc:
        return ScanResult(
            issues=[{
                "error": str(exc),
                "category": "runner-missing",
                "kind": "environment",
                "hub": hub,
                "test_paths": normalized_smoke_paths if not hub else [],
            }],
            summary=f"Jest runner unavailable: {exc}",
            severity="error",
        )

    if result.returncode == 0:
        return ScanResult(issues=[], summary=f"Jest passed: {result.stdout.strip()[-80:]}", severity="info")

    failure = _summarize_jest_failure((result.stderr or "")[-2000:], (result.stdout or "")[-2000:])

    return ScanResult(
        issues=[
            {
                "error": failure["error"],
                "category": failure["category"],
                "exit_code": result.returncode,
                "hub": hub,
                "test_paths": normalized_smoke_paths if not hub else [],
            }
        ],
        summary=f"Jest failed (exit {result.returncode})",
        severity="error",
    )


def fix(ctx: OpsContext, issues: list[dict]):
    if ctx.dry_run:
        return FixResult(
            success=True,
            summary=f"Dry run: would investigate {len(issues)} Jest failure(s)",
        )

    if not issues:
        return FixResult(success=True, summary="No Jest failures to fix", fix_type="report")

    dashboard_dir = ctx.project_root / "apps" / "dashboard"
    if not dashboard_dir.exists():
        report = write_report(
            ctx,
            "test-dashboard-latest.json",
            {
                "issues": issues,
                "fixed_count": 0,
                "by_category": {"unknown": len(issues)},
            },
        )
        return FixResult(
            success=True,
            actions=[{"report": str(report), "remaining_count": len(issues)}],
            summary=f"{len(issues)} issue(s) need manual fix (see report)",
            fix_type="report",
        )

    timeout = int(ctx.config.get("jest_timeout", 300))
    install_timeout = int(ctx.config.get("install_timeout", 240))
    actions: list[dict] = []
    changes: list[str] = []
    remaining: list[dict] = []

    for issue in issues:
        category = issue.get("category", "test-failure")
        issue_error = str(issue.get("error", ""))
        if "cannot find package " in issue_error.lower():
            category = "runner-missing"
        hub = issue.get("hub")
        test_paths = issue.get("test_paths") or None

        if category == "runner-missing":
            try:
                install = subprocess.run(
                    [*_pnpm_cmd(), "install", "--frozen-lockfile"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=install_timeout,
                    cwd=str(dashboard_dir),
                )
                if install.returncode != 0:
                    subprocess.run(
                        [*_pnpm_cmd(), "install"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=install_timeout,
                        cwd=str(dashboard_dir),
                    )
                verify = _run_jest(dashboard_dir, hub, timeout, test_paths=test_paths)
            except subprocess.TimeoutExpired:
                remaining.append({
                    **issue,
                    "fix_attempted": "pnpm install + jest rerun",
                    "result": "timed out",
                })
                continue
            except OSError as exc:
                remaining.append({
                    **issue,
                    "fix_attempted": "pnpm install + jest rerun",
                    "result": f"runner unavailable: {exc}",
                })
                continue

            if verify.returncode == 0:
                actions.append({"fixed": "runner-missing", "method": "pnpm install + jest rerun"})
                changes.append("apps/dashboard/node_modules/")
                continue

            follow_up = _summarize_jest_failure((verify.stderr or "")[-2000:], (verify.stdout or "")[-2000:])
            issue = {
                **issue,
                "error": follow_up["error"],
                "category": follow_up["category"],
                "fix_attempted": "pnpm install + jest rerun",
                "result": f"Jest still failing ({follow_up['category']})",
            }
            category = follow_up["category"]

        if category in {"cache-corruption", "test-failure"}:
            try:
                _clear_jest_cache(dashboard_dir, timeout)
                verify = _run_jest(dashboard_dir, hub, timeout, test_paths=test_paths)
            except subprocess.TimeoutExpired:
                remaining.append({
                    **issue,
                    "fix_attempted": "jest cache clear + rerun",
                    "result": "timed out",
                })
                continue
            except OSError as exc:
                remaining.append({
                    **issue,
                    "fix_attempted": "jest cache clear + rerun",
                    "result": f"runner unavailable: {exc}",
                })
                continue

            if verify.returncode == 0:
                actions.append({"fixed": category, "method": "jest cache clear + rerun"})
                continue

            follow_up = _summarize_jest_failure((verify.stderr or "")[-2000:], (verify.stdout or "")[-2000:])
            remaining.append({
                **issue,
                "error": follow_up["error"],
                "category": follow_up["category"],
                "fix_attempted": "jest cache clear + rerun",
                "result": f"Jest still failing ({follow_up['category']})",
            })
            continue

        remaining.append({
            **issue,
            "fix_instruction": "Review the Jest failure output and fix the underlying test or runtime issue.",
        })

    if remaining:
        by_category: dict[str, int] = {}
        for issue in remaining:
            key = issue.get("category", "unknown")
            by_category[key] = by_category.get(key, 0) + 1
        report = write_report(
            ctx,
            "test-dashboard-latest.json",
            {
                "issues": remaining,
                "fixed_count": len([a for a in actions if "fixed" in a]),
                "by_category": by_category,
            },
        )
        actions.append({"report": str(report), "remaining_count": len(remaining)})

    fixed_count = len([a for a in actions if "fixed" in a])
    parts = []
    if fixed_count:
        parts.append(f"auto-fixed {fixed_count} Jest failure(s)")
    if remaining:
        parts.append(f"{len(remaining)} issue(s) need manual fix (see report)")

    return FixResult(
        success=True,
        actions=actions,
        changes=changes,
        summary="; ".join(parts) if parts else "No fixable Jest failures",
        fix_type="code-fix" if fixed_count else "report",
    )
