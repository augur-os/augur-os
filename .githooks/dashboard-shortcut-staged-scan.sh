#!/bin/sh
# Cross-agent commit-time backstop for CLAUDE.md rule 29: refuse to commit
# scripts or markdown that introduce dev-server shortcuts which bypass
# /dev-build (manual `kill <pid>`, `pkill`, `pnpm dev`, `npm run dev`,
# `next dev`, `next-server`, `rm -rf .next`).
#
# Fires from .githooks/pre-commit which is triggered by git for every
# committer regardless of which AI client (Claude, Codex, Gemini, OpenCode,
# Copilot, human) staged the change. This is the parity peer that closes
# the gap raised by routine-platform's agent_config_parity.py for
# clients without a PreToolUse-equivalent hook surface.
#
# Pattern source-of-truth: scripts/hooks/dashboard-shortcut-patterns.sh
# (the same file the Claude PreToolUse blocker sources). Keep this in
# lock-step — adding a regex there means it lights up here automatically.

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
PATTERNS="$REPO_ROOT/scripts/hooks/dashboard-shortcut-patterns.sh"

if [ ! -f "$PATTERNS" ]; then
    # Older clones may not have this file yet — fail open with a notice.
    echo "[dashboard-shortcut-staged-scan] patterns file missing — skipping rule 29 staged scan." >&2
    exit 0
fi

# shellcheck source=../scripts/hooks/dashboard-shortcut-patterns.sh
. "$PATTERNS"

# Only scan source-like files where a forbidden invocation would actually run
# or be copy-pasted by a future agent. Skip lockfiles, generated docs, and
# binaries (the pre-commit hook already guards binaries elsewhere).
SCAN_EXTS='\.(sh|bash|zsh|py|ts|tsx|js|jsx|mjs|cjs|md|mdx|yaml|yml|toml|json|jsonc|tf|mk|Makefile)$'

# Files we deliberately exempt:
#   - the patterns/blocker scripts themselves (they encode the regex)
#   - the cross-platform hook runner (it encodes the same blocker regex for Windows)
#   - the parity scanner (it lists keywords as data)
#   - the agent rules doc (rule 29 quotes the forbidden commands)
#   - the debugging topic doc (the dev-server recovery runbook quotes the
#     forbidden commands so the next agent can self-recover; same rationale)
#   - llms-full.txt (generated aggregate of the agent-topics docs above)
#   - generated agent instruction surfaces (CLAUDE.md / GEMINI.md / AGENTS.md /
#     copilot-instructions.md / .codex/skills/dev-merge/SKILL.md etc.) which
#     re-state rule 29 verbatim
#   - superpowers specs/plans under docs/superpowers/ — these are design and
#     implementation-plan documents that describe user-facing commands (incl.
#     install / first-run instructions) as documentation, not invocations.
#     Same rationale as docs/agent-topics/agent-rules.md.
#   - project-brain/knowledge/ — compiled wiki/memory/notes markdown. This is the
#     project brain's knowledge tree (documentation that often *describes* rule-29
#     commands like "never run pnpm dev manually"), never executable dev-server
#     code. The recurrence router (spec 2026-06-13) writes project knowledge here.
EXEMPT_REGEX='^(scripts/hooks/dashboard-shortcut-(blocker|patterns)\.sh|scripts/hooks/run-hook\.mjs|\.githooks/dashboard-shortcut-staged-scan\.sh|project-brain/capabilities/skills/routine-platform/scripts/agent_config_parity\.py|project-brain/capabilities/skills/routine-platform/augur/tests/test_agent_config_parity\.py|docs/agent-topics/agent-rules\.md|docs/agent-topics/DEBUGGING\.md|llms-full\.txt|docs/superpowers/(specs|plans)/|project-brain/decisions/adrs/archive/|project-brain/knowledge/|CLAUDE\.md|CODEX\.md|AGENTS\.md|GEMINI\.md|\.gemini/GEMINI\.md|\.opencode/AGENTS\.md|\.github/copilot-instructions\.md|\.github/instructions/)'

STAGED=$(git diff --cached --name-only --diff-filter=ACMR | grep -E "$SCAN_EXTS" | grep -vE "$EXEMPT_REGEX" || true)

[ -z "$STAGED" ] && exit 0

FAIL=0
HITS=""

# We want to inspect only NEWLY introduced lines (lines added by this commit),
# not pre-existing legitimate references. Use `git diff --cached -U0` and
# match lines beginning with `+` (but skip the `+++` file header).
DIFF=$(git diff --cached -U0 --diff-filter=ACMR -- $STAGED 2>/dev/null || true)
[ -z "$DIFF" ] && exit 0

ADDED=$(echo "$DIFF" | grep -E '^\+' | grep -vE '^\+\+\+' | sed 's/^+//' || true)
[ -z "$ADDED" ] && exit 0

check_pattern() {
    label="$1"
    regex="$2"
    matched=$(echo "$ADDED" | grep -E "$regex" || true)
    if [ -n "$matched" ]; then
        HITS="${HITS}
[$label]
${matched}
"
        FAIL=1
    fi
}

# Forbidden invocations introduced by this commit:
# rm -rf .next       → DSB_PATTERN_RM_NEXT
# pnpm dev / npm run dev / next dev → DSB_PATTERN_DEV_INVOKE
# next-server / next dev / next start direct → DSB_PATTERN_NEXT_BIN
# kill/pkill against the dashboard dev server (next.dev/next-server/node :3000) → DSB_PATTERN_KILL_NAMED
# (Bare `kill <pid>` is intentionally NOT blocked — rule 29 governs the
#  dashboard dev server, not arbitrary background processes.)
check_pattern "rm -rf .next"            "$DSB_PATTERN_RM_NEXT"
check_pattern "pnpm dev / npm run dev / next dev" "$DSB_PATTERN_DEV_INVOKE"
check_pattern "next-server / next dev / next start" "$DSB_PATTERN_NEXT_BIN"
check_pattern "kill/pkill next.dev/next-server/node:3000" "$DSB_PATTERN_KILL_NAMED"

if [ "$FAIL" -eq 1 ]; then
    cat >&2 <<EOF
[dashboard-shortcut-staged-scan] FAIL: this commit introduces dev-server
shortcuts that bypass /dev-build's safety contract (rule 29).

Forbidden additions:
$HITS
Use /dev-build to rebuild and /dev-debug to diagnose. If a script genuinely
needs one of these invocations (CI, build pipeline, system orchestrator),
add the file path to the EXEMPT_REGEX in
.githooks/dashboard-shortcut-staged-scan.sh with a comment explaining why,
or stage with --no-verify after confirming with the user.
EOF
    exit 1
fi

exit 0
