#!/bin/sh
# Commit-time guard for ADR-779: global identity mutations must go through
# src.config.runtime_identity.

set -e

STAGED=$(git diff --cached --name-only --diff-filter=ACMR \
    | grep -E '\.(py|sh|ps1|mjs|md|yml|yaml)$' \
    | grep -vE '^\.githooks/global-identity-staged-scan\.sh$' || true)
[ -z "$STAGED" ] && exit 0

DIFF=$(git diff --cached -U0 --diff-filter=ACMR -- $STAGED 2>/dev/null || true)
[ -z "$DIFF" ] && exit 0

ADDED=$(echo "$DIFF" | grep -E '^\+' | grep -vE '^\+\+\+' | sed 's/^+//' || true)
[ -z "$ADDED" ] && exit 0

FAIL=0

if echo "$ADDED" | grep -E 'AUGUR_SYNC_ALLOW_WORKTREE_GLOBAL' >/dev/null 2>&1; then
    echo "ADR-779 violation: do not add AUGUR_SYNC_ALLOW_WORKTREE_GLOBAL." >&2
    FAIL=1
fi

if echo "$ADDED" | grep -E 'uv pip install .*(-e|--editable).*(augur-wt-|\.worktrees)' >/dev/null 2>&1; then
    echo "ADR-779 violation: staged editable install targets a worktree path." >&2
    FAIL=1
fi

if echo "$ADDED" | grep -E 'pip install .*(-e|--editable).*(augur-wt-|\.worktrees)' >/dev/null 2>&1; then
    echo "ADR-779 violation: staged editable install targets a worktree path." >&2
    FAIL=1
fi

if [ "$FAIL" -eq 1 ]; then
    echo "Use src.config.runtime_identity.GlobalMutationGuard and authority-root repair instead." >&2
    exit 1
fi
