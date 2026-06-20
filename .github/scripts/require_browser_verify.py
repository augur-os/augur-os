#!/usr/bin/env python3
"""Require Verified-Browser: trailer when a commit touches dashboard UI/config.

CLAUDE.md rule 28: server-side smoke tests (curl + grep) miss client-side
runtime failures (chunk-load errors, hydration crashes). Any commit that
touches dashboard-rendered surfaces must declare browser verification.

Pass when:
  - No staged files match the dashboard-affecting set, OR
  - Commit message contains a `Verified-Browser:` trailer with a non-empty
    value (page list, screenshot path, "chrome-mcp", etc.), OR
  - Commit message contains a `Skip-Verify:` trailer with a reason.

Fail otherwise — print clear message pointing at /dev-build and rule 28.

Cross-agent: this runs in pre-commit which fires for any committer
(Claude, Codex, Gemini, human, CI rebase) — not Claude-specific.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Paths that imply dashboard rendering / page changes. Conservative set —
# generated registry/config drift, UI source, page YAML, hub-assembly inputs.
DASHBOARD_PATTERNS = [
    re.compile(r"^apps/dashboard/(app|components|features|lib/configs|lib/blocks|lib/tabs|lib/plugin-runtime)/"),
    re.compile(r"^apps/dashboard/app/"),
    re.compile(r"^project-brain/capabilities/skills/[^/]+/augur/pages/.*\.yaml$"),
    re.compile(r"^project-brain/capabilities/skills/[^/]+/config\.yaml$"),
    re.compile(r"^project-brain/capabilities/skills/[^/]+/SKILL\.md$"),
    re.compile(r"^project-brain/capabilities/skills/[^/]+/manifest\.yaml$"),
]

# A commit may opt out with one of these trailers. Both must carry a value.
VERIFIED_TRAILER = re.compile(r"^Verified-Browser:\s*\S", re.MULTILINE)
SKIP_TRAILER = re.compile(r"^Skip-Verify:\s*\S", re.MULTILINE)


def staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def touches_dashboard(files: list[str]) -> list[str]:
    return [
        path
        for path in files
        if any(pattern.search(path) for pattern in DASHBOARD_PATTERNS)
    ]


def commit_message() -> str:
    # pre-commit framework with stages: [commit-msg] passes the commit-msg path
    # as the first arg. Outside that hook stage, fall back to COMMIT_EDITMSG.
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if path.is_file():
            return path.read_text(encoding="utf-8")
    fallback = Path(".git/COMMIT_EDITMSG")
    if fallback.is_file():
        return fallback.read_text(encoding="utf-8")
    return ""


def main() -> int:
    files = staged_files()
    if not files:
        return 0

    affected = touches_dashboard(files)
    if not affected:
        return 0

    message = commit_message()
    if VERIFIED_TRAILER.search(message) or SKIP_TRAILER.search(message):
        return 0

    print(
        "\n[require-browser-verify] FAIL: commit touches dashboard surfaces but "
        "carries no browser-verification trailer.\n",
        file=sys.stderr,
    )
    print("Affected paths:", file=sys.stderr)
    for path in affected[:8]:
        print(f"  - {path}", file=sys.stderr)
    if len(affected) > 8:
        print(f"  ... and {len(affected) - 8} more", file=sys.stderr)
    print(
        "\nRule 28 requires interactive-browser verification for any change that "
        "triggers a dashboard rebuild. Add ONE of:\n"
        "  Verified-Browser: <pages or screenshot path or 'chrome-mcp'>\n"
        "  Skip-Verify: <reason>\n"
        "as a trailer in the commit message, or run /dev-build first and add the\n"
        "verification result.\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
