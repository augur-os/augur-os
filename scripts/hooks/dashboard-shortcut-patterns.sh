# Shared regex patterns for dashboard-dev-server shortcut detection.
# Single source-of-truth used by:
#   - scripts/hooks/dashboard-shortcut-blocker.sh   (Claude PreToolUse Bash)
#   - .githooks/dashboard-shortcut-staged-scan.sh   (cross-agent commit-time)
#
# CLAUDE.md rule 29: never manually `kill` the dev server, `rm -rf .next`,
# or invoke `pnpm dev` / `next dev` / `next-server` / `npm run dev`.
# Always use /dev-build to rebuild and /dev-debug to diagnose.
#
# Keywords aligned with the parity scanner's _GATE_KEYWORDS table in
# project-brain/capabilities/skills/routine-platform/scripts/agent_config_parity.py — adding a new pattern here
# implies updating the scanner (and vice versa).
#
# This file is sourced (`. dashboard-shortcut-patterns.sh`); it must be
# side-effect-free and define only DSB_* environment variables.

# 1. rm -rf <something>.next  — never legitimate; /dev-build owns cache cleanup
#    Token: ".next"
DSB_PATTERN_RM_NEXT='rm[[:space:]]+-[a-z]*r[a-z]*f?[[:space:]].*\.next(/|$|[[:space:]])'

# 2. Direct dev-server invocations (pnpm dev / npm run dev / yarn dev / pnpm next dev / pnpm --filter X dev)
#    Tokens: "pnpm dev", "npm run dev", "next dev"
DSB_PATTERN_DEV_INVOKE='(^|[[:space:]]|&&[[:space:]]*|;[[:space:]]*|\|\|[[:space:]]*|\|[[:space:]]*)(pnpm|npm|yarn|bun|bunx|npx)([[:space:]]+--filter[[:space:]]+[^[:space:]]+)?[[:space:]]+(run[[:space:]]+)?(dev|next[[:space:]]+dev)([[:space:]]|$)'

# 3. next-server / next dev / next start direct invocation
#    Tokens: "next dev", "next-server"
DSB_PATTERN_NEXT_BIN='(^|[[:space:]]|&&[[:space:]]*|;[[:space:]]*|\|\|[[:space:]]*)(npx[[:space:]]+|bunx[[:space:]]+)?(next[[:space:]]+(dev|start)|next-server)([[:space:]]|$)'

# 4. kill / pkill against the dashboard dev server, identified by name or
#    port. We deliberately do NOT block bare `kill <pid>` — rule 29 governs
#    the dashboard dev server (next-server, port 3000), not arbitrary
#    background processes (MCP daemons, linters, etc.). Killing those by
#    PID is a normal operation and previously produced false positives that
#    blocked even read-only `grep "kill"` queries.
#    Tokens: "kill", "pkill"
DSB_PATTERN_KILL_NAMED='(p?kill).*(next\.?dev|next-server|node.*3000)'

# Canonical reason printed when any of the above match.
DSB_REASON='Blocked by rule 29: use /dev-build (rebuild) or /dev-debug (diagnose). Manual dev-server gymnastics bypass /dev-build safety (port-owner detection, codex thread state, vault sync, post-build verify).'
