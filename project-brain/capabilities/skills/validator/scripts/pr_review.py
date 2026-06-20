#!/usr/bin/env python3
"""
PR Review Script - Validator Agent

Performs a lightweight, local PR-style review by analyzing the latest commit diff
and applying heuristic quality gates.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from subprocess import CompletedProcess, run  # nosec B404
from typing import Any


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _resolve_command(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise RuntimeError(f"Required executable not found in PATH: {name}")
    return resolved


def _find_repo_root(start: Path) -> Path:
    for parent in [start] + list(start.parents):
        if (parent / ".git").exists():
            return parent
    return start


def _run_git(args: list[str], cwd: Path) -> str:
    proc: CompletedProcess[str] = run(
        [_resolve_command("git"), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )  # nosec B603
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git command failed")
    return proc.stdout.strip()


def _resolve_commit_range(repo: Path, commit: str, base: str | None) -> tuple[str | None, str]:
    if base:
        return base, commit
    try:
        parent = _run_git(["rev-parse", f"{commit}^"], repo)
        return parent, commit
    except Exception:
        return None, commit


def _is_code_file(path: str) -> bool:
    return any(
        path.endswith(ext)
        for ext in (
            ".py",
            ".ts",
            ".tsx",
            ".js",
            ".jsx",
            ".sh",
            ".yml",
            ".yaml",
        )
    )


def _parse_added_entries(diff_text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current_file = None
    new_line = None

    for raw in diff_text.splitlines():
        line = raw.rstrip("\n")
        if line.startswith("diff --git "):
            current_file = None
            new_line = None
            continue
        if line.startswith("+++ b/"):
            current_file = line[6:]
            continue
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            if match:
                new_line = int(match.group(1))
            continue
        if line.startswith("+") and not line.startswith("+++"):
            if current_file and _is_code_file(current_file):
                entries.append(
                    {
                        "file": current_file,
                        "line": new_line,
                        "text": line[1:],
                    }
                )
            if new_line is not None:
                new_line += 1
            continue
        if line.startswith(" ") and new_line is not None:
            new_line += 1
            continue
        if line.startswith("-") and not line.startswith("---"):
            continue

    return entries


def _collect_diff(repo: Path, base: str | None, commit: str) -> dict[str, Any]:
    if base:
        diff_range = f"{base}..{commit}"
        name_only = _run_git(["diff", "--name-only", diff_range], repo)
        numstat = _run_git(["diff", "--numstat", diff_range], repo)
        diff_text = _run_git(["diff", "--unified=0", diff_range], repo)
    else:
        name_only = _run_git(["show", "--name-only", "--pretty=", commit], repo)
        numstat = _run_git(["show", "--numstat", "--pretty=", commit], repo)
        diff_text = _run_git(["show", "--unified=0", "--pretty=", commit], repo)

    files = [line for line in name_only.splitlines() if line.strip()]
    stats = []
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            stats.append({"added": parts[0], "deleted": parts[1], "file": parts[2]})

    added_entries = _parse_added_entries(diff_text)

    return {"files": files, "stats": stats, "added_entries": added_entries}


def _analyze_findings(files: list[str], added_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    patterns = [
        {
            "id": "bare-except",
            "pattern": r"^\s*except\s*:\s*$",
            "severity": "high",
            "category": "quality",
            "message": "Bare except detected (can hide unexpected errors).",
        },
        {
            "id": "except-pass",
            "pattern": r"^\s*except\b[^:]*:\s*(pass|return\s+None|\.\.\.)\s*$",
            "severity": "high",
            "category": "quality",
            "message": "Silent exception handling detected.",
        },
        {
            "id": "empty-catch",
            "pattern": r"^\s*catch\s*\([^)]*\)\s*\{\s*\}\s*$",
            "severity": "high",
            "category": "quality",
            "message": "Empty catch block detected.",
        },
        {
            "id": "ts-ignore",
            "pattern": r"@ts-ignore|@ts-expect-error",
            "severity": "high",
            "category": "quality",
            "message": "Type suppression detected; fix types instead of ignoring errors.",
        },
        {
            "id": "todo-marker",
            "pattern": r"TODO_(BUG|WORKAROUND|SECURITY|OUTDATED)",
            "severity": "medium",
            "category": "quality",
            "message": "TODO marker added; ensure it is tracked and resolved.",
        },
        {
            "id": "eslint-disable",
            "pattern": r"eslint-disable",
            "severity": "medium",
            "category": "quality",
            "message": "Lint suppression detected; fix the underlying issue instead.",
        },
        {
            "id": "shell-true",
            "pattern": r"shell=True",
            "severity": "high",
            "category": "security",
            "message": "subprocess shell=True detected; validate inputs or avoid shell.",
        },
        {
            "id": "eval-exec",
            "pattern": r"\b(eval|exec)\s*\(",
            "severity": "high",
            "category": "security",
            "message": "Dynamic code execution detected.",
        },
        {
            "id": "requests-verify-false",
            "pattern": r"verify=False",
            "severity": "high",
            "category": "security",
            "message": "TLS verification disabled; avoid verify=False in production.",
        },
        {
            "id": "yaml-load",
            "pattern": r"yaml\.load\(",
            "severity": "medium",
            "category": "security",
            "message": "yaml.load used; prefer yaml.safe_load unless a loader is required.",
        },
        {
            "id": "dangerously-set-html",
            "pattern": r"dangerouslySetInnerHTML|innerHTML\s*=",
            "severity": "medium",
            "category": "security",
            "message": "Direct HTML injection detected; ensure content is sanitized.",
        },
        {
            "id": "hardcoded-path",
            "pattern": r"/Users/[A-Za-z0-9._-]+/|C:\\\\Users\\\\",  # audit-ignore
            "severity": "medium",
            "category": "quality",
            "message": "Hardcoded absolute path detected.",
        },
        {
            "id": "debug-log",
            "pattern": r"\bconsole\.log\b|\bprint\(",
            "severity": "low",
            "category": "quality",
            "message": "Debug logging added; verify it is intentional for production code.",
        },
    ]

    for entry in added_entries:
        line = entry["text"]
        for rule in patterns:
            if re.search(rule["pattern"], line):
                findings.append(
                    {
                        "severity": rule["severity"],
                        "category": rule["category"],
                        "message": rule["message"],
                        "evidence": line.strip(),
                        "file": entry["file"],
                        "line": entry["line"],
                    }
                )

    # Testing gate: if code changed without tests
    code_files = [f for f in files if _is_code_file(f)]
    test_files = [f for f in files if any(token in f.lower() for token in ("test", "spec", "__tests__"))]
    if code_files and not test_files:
        findings.append(
            {
                "severity": "medium",
                "category": "testing",
                "message": "Code changes detected without accompanying tests.",
                "evidence": f"{len(code_files)} code files changed, 0 tests updated.",
            }
        )

    return findings


def _summarize_gates(findings: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    has_high = any(f["severity"] == "high" for f in findings)
    has_medium = any(f["severity"] == "medium" for f in findings)
    has_security_high = any(f["severity"] == "high" and f.get("category") == "security" for f in findings)
    has_security_medium = any(f["severity"] == "medium" and f.get("category") == "security" for f in findings)
    has_testing_medium = any(f["severity"] == "medium" and f.get("category") == "testing" for f in findings)

    def _status(sev: str) -> str:
        if has_high and sev == "high":
            return "FAIL"
        if has_medium and sev in {"medium", "high"}:
            return "WARN"
        return "PASS"

    return {
        "code_quality": {"status": _status("high"), "notes": "Static heuristics on diff"},
        "security": {
            "status": "FAIL" if has_security_high else ("WARN" if has_security_medium else "PASS"),
            "notes": "Static security heuristics on diff",
        },
        "performance": {"status": "PASS", "notes": "No performance heuristics applied"},
        "testing": {
            "status": "WARN" if has_testing_medium else "PASS",
            "notes": "Test coverage heuristic",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Lightweight PR review (local diff heuristics)")
    parser.add_argument("--commit", default="HEAD", help="Commit to review (default: HEAD)")
    parser.add_argument("--base", default=None, help="Base commit (default: commit parent)")
    parser.add_argument("--path", default=None, help="Repo path (default: auto-detect)")
    parser.add_argument("--json", action="store_true", help="JSON output only")
    args = parser.parse_args()

    repo_root = _find_repo_root(Path(args.path).resolve() if args.path else Path.cwd())

    try:
        base, commit = _resolve_commit_range(repo_root, args.commit, args.base)
        diff = _collect_diff(repo_root, base, commit)
    except Exception as exc:
        result = {
            "error": str(exc),
            "verdict": "BLOCK",
            "review_date": datetime.now().isoformat(),
        }
        _out(json.dumps(result, indent=2))
        return 1

    findings = _analyze_findings(diff["files"], diff["added_entries"])
    gates = _summarize_gates(findings)

    verdict = "APPROVE"
    if any(f["severity"] == "high" for f in findings):
        verdict = "REQUEST_CHANGES"

    severity_counts = {
        "high": sum(1 for f in findings if f["severity"] == "high"),
        "medium": sum(1 for f in findings if f["severity"] == "medium"),
        "low": sum(1 for f in findings if f["severity"] == "low"),
    }

    report = {
        "review_date": datetime.now().isoformat(),
        "repo": str(repo_root),
        "commit": commit,
        "base": base,
        "files_changed": diff["files"],
        "stats": diff["stats"],
        "findings": findings,
        "severity_counts": severity_counts,
        "gates": gates,
        "verdict": verdict,
        "summary": f"{len(diff['files'])} files changed, {len(findings)} findings",
    }

    _out(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
