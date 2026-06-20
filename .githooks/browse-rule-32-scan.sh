#!/bin/sh
# Cross-agent commit-time enforcement of CLAUDE.md rule 32 +
# docs/architecture-dashboard.md "Browse page taxonomy — every tab is the
# shared file-card mechanism".
#
# When apps/dashboard/app/(views)/browse/BrowseDisplayRenderer.tsx is
# staged, refuse the commit if it contains an `if (viewMode === "X")`
# guard followed by an early `return` outside the manager-surface
# allowlist. The only sanctioned exception today is `extensions-bundles`
# (interactive install/configure surface); every other tab must render
# via the standard BrowseCardShell / BrowseListRowCard grid.
#
# Escape hatch: add a `// rule-32-ok: <reason>` comment on the same line
# as the `if` to opt out (e.g. for a new sanctioned manager surface).
# That keeps the gate honest — the comment is grep-able evidence the
# author considered rule 32.
#
# Author memory: feedback_browse_rule_32_cards_only.md captures the
# 2026-05-17 incident this hook prevents.
#
# Cross-agent parity: fires for any committer (Claude, Codex, Gemini,
# Copilot, human) per feedback_cross_agent_enforcement memory.

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
RENDERER="apps/dashboard/app/(views)/browse/BrowseDisplayRenderer.tsx"

# Only run when the renderer is part of the commit.
if ! git diff --cached --name-only --diff-filter=ACMR | grep -qxF "$RENDERER"; then
    exit 0
fi

PYTHON_BIN="${PYTHON:-python3}"
for candidate in "$REPO_ROOT/.venv/bin/python3" "$REPO_ROOT/.venv/bin/python" python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done

git show ":$RENDERER" | "$PYTHON_BIN" - "$RENDERER" <<'PYEOF'
import re
import sys

path = sys.argv[1]
src = sys.stdin.read()
lines = src.split("\n")

# Allowlist: tabs that may legitimately have a custom render path because
# they are interactive manager surfaces (install/configure/rebuild),
# not discovery content. Keep this list short and document additions
# in docs/architecture-dashboard.md.
ALLOW = {"extensions-bundles"}

VIEWMODE_IF_RE = re.compile(r'\bif\b[^/]*\bviewMode\s*===\s*"([^"]+)"')
# We only flag returns that render JSX directly — that's the
# bespoke-panel pattern rule 32 forbids. Scalar / void returns inside
# helper functions (selectedForItem, handleSelect, etc) are fine.
RENDER_RETURN_RE = re.compile(r'\breturn\s*\(?\s*<')

violations = []
for i, line in enumerate(lines):
    no_comment = line.split("//")[0]
    m = VIEWMODE_IF_RE.search(no_comment)
    if not m:
        continue
    viewmode = m.group(1)
    if viewmode in ALLOW:
        continue
    # Opt-out marker on the same line
    if "rule-32-ok" in line:
        continue
    # Scan up to 8 lines ahead for a JSX-returning render statement.
    for j in range(i, min(i + 8, len(lines))):
        if RENDER_RETURN_RE.search(lines[j].split("//")[0]):
            violations.append(
                f"{path}:{i + 1}: `if (viewMode === \"{viewmode}\")` "
                f"followed by `return <...>` is a bespoke-panel pattern "
                f"that violates CLAUDE.md rule 32 "
                f"(docs/architecture-dashboard.md \"Discovery contract\"). "
                f"Either render via the shared BrowseCardShell grid, "
                f"add \"{viewmode}\" to the ALLOW set in "
                f".githooks/browse-rule-32-scan.sh after updating "
                f"docs/architecture-dashboard.md, or append "
                f"`// rule-32-ok: <reason>` to the if-line."
            )
            break

if violations:
    print("Browse rule-32 violation in staged BrowseDisplayRenderer.tsx:")
    for v in violations:
        print(f"  {v}")
    sys.exit(1)
PYEOF
