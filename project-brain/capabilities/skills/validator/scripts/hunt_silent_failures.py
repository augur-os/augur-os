#!/usr/bin/env python3
"""
Silent Failure Hunter - Validator Agent

Scans recent diff for patterns that swallow errors or fail silently.
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


def _collect_added_entries(repo: Path, base: str | None, commit: str) -> list[dict[str, Any]]:
    if base:
        diff_text = _run_git(["diff", "--unified=0", f"{base}..{commit}"], repo)
    else:
        diff_text = _run_git(["show", "--unified=0", "--pretty=", commit], repo)

    return _parse_added_entries(diff_text)


def _scan_silent_failures(added_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    patterns = [
        {
            "id": "bare-except",
            "pattern": r"^\s*except\s*:\s*$",
            "severity": "high",
            "message": "Bare except detected (likely to hide errors).",
        },
        {
            "id": "except-pass",
            "pattern": r"^\s*except\b[^:]*:\s*(pass|return\s+None|\.\.\.)\s*$",
            "severity": "high",
            "message": "Silent exception handling detected.",
        },
        {
            "id": "except-generic",
            "pattern": r"^\s*except\s+Exception\s*:",
            "severity": "medium",
            "message": "Generic exception catch added; ensure errors are logged or re-raised.",
        },
        {
            "id": "empty-catch",
            "pattern": r"^\s*catch\s*\([^)]*\)\s*\{\s*\}\s*$",
            "severity": "high",
            "message": "Empty catch block detected.",
        },
        {
            "id": "catch-return",
            "pattern": r"^\s*catch\s*\([^)]*\)\s*\{\s*return\s*;?\s*\}\s*$",
            "severity": "high",
            "message": "Catch block returns early without handling error.",
        },
        {
            "id": "promise-catch-empty",
            "pattern": r"\.catch\(\s*\(\)\s*=>\s*\{\s*\}\s*\)",
            "severity": "high",
            "message": "Empty promise catch handler detected.",
        },
        {
            "id": "promise-catch-null",
            "pattern": r"\.catch\(\s*\(\)\s*=>\s*(null|undefined)\s*\)",
            "severity": "medium",
            "message": "Promise catch returns null/undefined; ensure errors are handled.",
        },
        {
            "id": "optional-chain",
            "pattern": r"\?\.\w+\(",
            "severity": "low",
            "message": "Optional chaining call added; ensure failures are handled explicitly.",
        },
    ]

    for entry in added_entries:
        line = entry["text"]
        for rule in patterns:
            if re.search(rule["pattern"], line):
                findings.append(
                    {
                        "severity": rule["severity"],
                        "message": rule["message"],
                        "evidence": line.strip(),
                        "file": entry["file"],
                        "line": entry["line"],
                    }
                )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Silent failure hunter (diff heuristics)")
    parser.add_argument("--commit", default="HEAD", help="Commit to review (default: HEAD)")
    parser.add_argument("--base", default=None, help="Base commit (default: commit parent)")
    parser.add_argument("--path", default=None, help="Repo path (default: auto-detect)")
    parser.add_argument("--json", action="store_true", help="JSON output only")
    args = parser.parse_args()

    repo_root = _find_repo_root(Path(args.path).resolve() if args.path else Path.cwd())

    try:
        base, commit = _resolve_commit_range(repo_root, args.commit, args.base)
        added_entries = _collect_added_entries(repo_root, base, commit)
    except Exception as exc:
        result = {
            "error": str(exc),
            "status": "failed",
            "scan_date": datetime.now().isoformat(),
        }
        _out(json.dumps(result, indent=2))
        return 1

    findings = _scan_silent_failures(added_entries)
    has_high = any(f["severity"] == "high" for f in findings)
    status = "FAIL" if has_high else ("WARN" if findings else "PASS")

    report = {
        "scan_date": datetime.now().isoformat(),
        "repo": str(repo_root),
        "commit": commit,
        "base": base,
        "findings": findings,
        "status": status,
        "summary": f"{len(findings)} potential silent failure patterns found",
    }

    _out(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
