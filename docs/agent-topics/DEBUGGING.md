<!--
⚠️  AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
Source: docs/agent-topics/DEBUGGING.md
Generator: project-brain/capabilities/skills/ai/scripts/sync_agents/__init__.py
-->
# Debugging

> **When to load**: Load this doc when debugging errors, investigating failures, or verifying fixes in the browser.

## Debugging Efficiency -- Full-Stack Vision (ADR-052)

### Principle: See Before You Fix
The agent must observe failures before attempting fixes. Never fix blind.

### Build Gate (Rule #24)
**Before investigating dashboard issues**, run `/dev-build`. If the build is broken, fix it FIRST — a broken build means zero customer value from any other work. Build errors are never "pre-existing" or "unrelated" — they are always the current highest-priority problem.

### Visibility Stack
1. **Build errors** -> `/dev-build` (CHECK FIRST for dashboard issues)
2. **Runtime errors** -> the active browser verification tool's console logs
3. **UI issues** -> the active browser verification tool's screenshots and DOM inspection
4. **API errors** -> Background MCP server logs
5. **Test failures** -> pytest/vitest output with full tracebacks

### Verification Screenshot Location
Save browser-proof/verification screenshots under `get_logs_dir()/browser-verification/`
(`~/Library/Logs/Augur/browser-verification/` on macOS) — NEVER in the repo tree. The
repo .gitignore blanket-hides binaries (`*.png`, `*.pdf`, `*.wav`), so screenshots dropped
in the repo never show in git status and accumulate silently; the `auto-repo-pollution`
loop deletes session artifacts it finds in the working tree.

### Background Dev Servers
- When modifying dashboard code: use `/dev-build` to rebuild or recover the dashboard server; do not start or restart it manually.
- When modifying MCP tools: use the owning MCP/dev workflow to start or verify the server; do not kill active AI/client-owned processes.
- Read background task output BEFORE reporting success to user
- If build errors appear in background task, fix them before proceeding

### Browser Verification (Dashboard Development)
- After any dashboard UI change, verify in a real browser through the active browser integration
- Check: component renders, no console errors, responsive layout intact
- If browser tooling is unavailable, note "NOT VERIFIED IN BROWSER" in the handoff and commit message
- If the user names a localhost port, confirm that exact port is listening before using any other server. A different worktree/server can be useful for comparison, but it does not verify the user's reported target.
- For data pages, "renders" means useful data is visible and actionable. Headings, empty shells, stale cards, or permanent loading states are not a pass.
- Detect blocking overlays and modals before closeout. A page with useful data hidden behind setup migration, auth, or fatal-error UI is still blocked.
- Cross-check duplicate status surfaces. If Setup, Browse, Brain pages, and Insights report different facts about the same source, treat it as a live bug and debug the producer/consumer mismatch before declaring success.
- **Turbopack caveat**: After mount-plugins adds new route directories, use `/dev-build` to recover the dashboard server so Turbopack compiles the new routes. Existing routes work but new ones return 404 until recovery.
- **Nested API route caveat**: During Turbopack HMR, nested App Router API handlers can briefly return `404`/`405` even when the route exists on disk. For MCP context routes, mark the handler `dynamic = "force-dynamic"` and make the client retry once before treating it as a real failure.
- **Build ownership caveat**: Treat `apps/dashboard/.next` as single-owner state. If `mount-plugins --watch` or daemon recovery can outlive the dashboard server, they may delete `.next` during a build and cause random manifest ENOENTs. Use `/dev-debug` to identify stale owners and guard cache clears on active dev/build state before chasing route-specific fixes.

### Documentation Fetching Priority
1. Check if dependency has llms.txt -> fetch and navigate to relevant docs
2. If no llms.txt -> check if MCP server exists with doc tools
3. If neither -> use web search as last resort
4. NEVER guess at API patterns for dependencies updated after training cutoff

### Autonomous Verification Checklist
Before reporting a task as complete:
- [ ] Background task shows clean build (no errors/warnings)
- [ ] If UI change: verified in browser through the active browser integration (no console errors, no blocking overlays, useful domain data visible where expected)
- [ ] If API change: tested endpoint returns expected response
- [ ] If config change: restart relevant services and confirm they start cleanly
- [ ] If dashboard status/data changed: checked related surfaces for contradictions and reported any remaining empty/error/stale states

### Context Window Hygiene
- Prefer llms.txt over MCP servers for documentation
- Compact the conversation when context exceeds 60% (not 75% -- we have heavy tool definitions)
- Start new session for unrelated tasks rather than accumulating context

## Dashboard Dev-Server Recovery (self-recover — never hand off, rule 36)

`/dev-build` and the self-heal daemon (`dashboard_monitor`) own the normal lifecycle. But running the build steps **manually/piecemeal** — e.g. `cleanup_processes.py` then `npm run build:safe` — collides with the daemon and can leave `:3000` down in a crash loop. When that happens it is YOURS to fix; do not ask the user to restart it or run commands.

**Symptoms**
- `curl localhost:3000` returns `000` (connection refused) for minutes.
- `dashboard.stdout.log` loops `predev → start-dev.mjs → predev …`, never reaching `✓ Ready`.
- Lifecycle gate stuck `starting`/`stopping`; `build:safe` returns `{"decision":"denied", ...}`.

**Diagnose (read-only — all allowed)**
- Gate state: `python3 project-brain/capabilities/skills/daemon/scripts/dashboard_lifecycle.py state`
- Server logs: `tail "$HOME/Library/Logs/Augur/dashboard.stdout.log"` and `…/dashboard.stderr.log`
- Lifecycle events: `tail "$HOME/Library/Logs/Augur/dashboard_lifecycle.jsonl"`

**Root causes, fix in this order**
1. **Stuck gate** — state `starting`/`stopping` owned by `dashboard_monitor`/`build_lock`, so every start (the daemon's own retries AND yours) is denied. Transient states TTL-expire to `crashed` after 60s; if it keeps refreshing, reset it: write `{"state":"stopped","owner":null,"owner_since":null,"recent_crashes":[],"consecutive_healthy_polls":0}` to `<runtime_dir>/daemon/dashboard/main/state.json` (resolve `<runtime_dir>` via `src.config.paths.get_runtime_dir()`; `main` is the non-worktree instance).
2. **Stale production `.next`** — a prior `npm run build:safe` leaves `apps/dashboard/.next/BUILD_ID` (a production build) that crash-loops `next dev`. Move it aside (not `rm -rf`, which the rule-29 hook blocks): `mv apps/dashboard/.next /tmp/next-stale-$$`.

**Bring it up — sanctioned path (not hook-blocked)**
- After fixing (1) and (2), start via the wrapper: `bash apps/dashboard/scripts/start-dev.sh` (it does port-owner detection + gate coordination and is NOT blocked by the rule-29 hook). It exits silently if the gate still denies it — so the gate reset in (1) must come first. Poll `curl localhost:3000` until it serves; tail its log for `✓ Ready`.
- Reconcile to a clean daemon-managed state with `/dev-build` once `:3000` is healthy.
- Last resort only (loop confirmed, wrapper still failing, and the user has explicitly authorized overriding rule 29): run `next dev --turbopack --port 3000` directly from `apps/dashboard` to break the loop, then reconcile with `/dev-build`.

The rule-29 hook (`pnpm dev` / `next dev` / `rm -rf .next` / `kill`) protects the normal path; in recovery it is a redirection to the wrapper + gate reset above, not a wall and not a reason to hand the problem to the user (rule 36). **Verify** the recovered page loads to interactive state with real data (rules 28/31/34).

### Dev-server memory & OOM reboots (RAM-aware heap clamp)

**Symptom**: the machine runs out of memory and hard-restarts while running/debugging the dashboard. macOS records it in `~/Library/Logs/DiagnosticReports/node-*.ips` — look for `next-server`, `signal: SIGKILL`, a huge `Memory Tag 255` (V8/Chromium heap), and bug_type 309 (a jetsam memory kill).

**Root cause**: `start-dev.sh` sizes the V8 heap cap by session tier (worktree 16384 MB / focused 12288 MB / default 4096 MB). On a low-RAM host those tier values can exceed physical RAM, so Next.js's "restart the dev server at 80% of the heap limit" safety never fires before the OS itself OOMs.

**Fix in place**: `apps/dashboard/scripts/lib/heap-clamp.sh` (POSIX) and `lib/heap-clamp.mjs` (Windows launcher) clamp the selected cap to **`max(2048 MB, floor(total_RAM_MB × 0.30))`** — clamp DOWN only. On 16 GB RAM the cap becomes **4915 MB** (verified: a worktree server that would have requested 16384 MB ran at `--max-old-space-size=4915`, RSS plateaued ~1 GB, page interactive on its port). The server now *restarts* under pressure instead of rebooting the box.

**Overrides** (env vars): `AUGUR_NODE_OLD_SPACE_MB`, `AUGUR_FOCUSED_NODE_OLD_SPACE_MB`, `AUGUR_WORKTREE_NODE_OLD_SPACE_MB` set the desired per-tier cap (still clamped down to the RAM ceiling); `AUGUR_TEST_TOTAL_RAM_MB` overrides detected RAM (testing only).

**Confirm the clamp is live**: `NODE_OPTIONS` is an env var, not a CLI arg, so `ps -o command` won't show it. Read the running server's env: `ps -Eww -p <pid> -o command= | grep -oE 'max-old-space-size=[0-9]+'` (pid from `lsof -ti tcp:<port>`). Note: the deeper architectural cause — the dashboard hosting process-spawning/output-buffering at all (rule 11) — is tracked as a Phase 2 follow-up (`docs/superpowers/plans/2026-06-25-dashboard-dev-oom-fix.md`).

## Runtime Error Detection (Auto-Trigger)

**IMPORTANT**: When user reports UI issues, proactively check the browser console using the active browser integration.

### Trigger Phrases

When user says any of these, **automatically** use browser tooling to check for errors:
- "there's an error" / "see error"
- "it's broken" / "not working"
- "page crashed" / "something went wrong"
- "runtime error" / "console error"
- "hydration" / "red error"

### Auto-Check Flow

```
1. Locate the active dashboard browser tab.

2. Read console messages, filtering for errors when supported.

3. If errors found:
   -> Parse stack trace
   -> Read affected files
   -> Fix automatically
   -> Verify fix worked

4. If no errors:
   -> Take screenshot to understand visual issue
```

This removes the need for user to copy-paste errors manually.

**For systematic debugging**, use the full `/dev-debug` (6 phases including Phase 0: Establish Visibility and Phase 5: Autonomous Regression Check).

### Related Commands
- `/dev-debug` - Full 6-phase debugging with autonomous verification (ADR-052)
- `/dev-build` - Rebuild dashboard and diagnose build errors
- `/verify ui` - Full UI rebuild with runtime check

## Worktree Issues (ADR-101)

When debugging git worktree isolation problems, check these common issues:

**ADR-249 note**: if the same worktree/runtime issue keeps returning, treat it as a recurring incident, not a fresh debugging session. Normalize it to one fingerprint, aggregate recurrence, then promote one owner-path `TODO_` marker.

### 1. Port Collision

**Symptom**: Multiple worktrees trying to use same port (3000, 8080)

**Diagnosis**:
```bash
scripts/worktree_registry.py list
lsof -i :3000 -i :3001 -i :8080 -i :8081
```

**Solution**: Check registry for stale entries, unregister old worktrees:
```bash
scripts/worktree_registry.py unregister --path /path/to/old/worktree
```

### 2. Daemon Restarting Worktree Server

**Symptom**: Daemon treating worktree dev server as main repo, causing false restarts

**Diagnosis**:
```bash
cat .augur-worktree.yaml  # Should exist in worktree root
python3 -c "from skills.daemon.scripts.daemon_mode import get_repo_context; print(get_repo_context())"
```

**Solution**: Verify worktree marker exists and daemon correctly detects context:
- `.augur-worktree.yaml` marker file must exist in worktree root
- `daemon_mode.is_worktree_context()` should return `True` for worktrees
- Daemon should skip monitoring for worktree processes

### 3. MCP Tools Not Found After Merge

**Symptom**: After merging worktree to main, MCP tools fail with "file not found"

**Diagnosis**:
```bash
grep -r "augur-adr\|augur-harden" .claude/*.json config/
```

**Solution**: Regenerate client configs from source-of-truth:
```bash
PYTHONPATH=project-brain/capabilities python3 -m skills.ai.scripts.sync_agents sync all
```

This refreshes IDE/client configs after path or structure changes.

### 4. "No Available Worktree Ports"

**Symptom**: Port allocation fails with "No available worktree ports (max 10)"

**Diagnosis**:
```bash
scripts/worktree_registry.py list
git worktree list
```

**Solution**: Remove old/unused worktrees to free ports:
```bash
git worktree remove /path/to/old/worktree
scripts/worktree_registry.py unregister --path /path/to/old/worktree
```

Max 10 concurrent worktrees (ports 3001-3010, MCP 8081-8090).

### 5. Instance Lock Conflict

**Symptom**: Two MCP instances cannot run, lock contention

**Diagnosis**:
```bash
find "$(python3 scripts/resolve-runtime-dir.py --state)" -maxdepth 1 -name '*.pid' -ls
echo $MCP_PORT  # Should be set for worktree
```

**Solution**: Verify MCP_PORT environment variable and lock file naming:
- Main repo: `MCP_PORT=8080`, lock file `{state}/mcp_server.pid`
- Worktree: `MCP_PORT=8081+`, lock file `{state}/mcp_server_{port}.pid`

Each worktree must have unique MCP_PORT and corresponding lock file.
