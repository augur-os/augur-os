---
x-augur-export-command: false
---
# Goal Catalog-Loop (inline-session)

You are driving a routines **goal** to convergence. You are the orchestrator and
the Task invoker — Augur runs no LLM here. Catalog goals: `harden`, `clean`,
`harden-and-clean`.

## Contract

1. Confirm you are in an AI-client session with a Task/Agent subagent tool. If not,
   stop and tell the user to run this in-session.
2. **Create the worktree:** run `aug a-loops goal-worktree <goal-id> --stamp <utc-stamp>`.
   Read `worktree_path`, `branch`, and the ordered `loops`. ALL work happens in
   `worktree_path`, never the main checkout. Do not merge — you end at branch + report.
3. **Drain the backlog first** (the original motivation): run
   `aug a-loops goal-drain-backlog --loops <comma-loops>`. It returns `entries`
   (each `{id, finding}`, actionable) plus `stale` (entries whose absolute `path`
   does not exist in THIS checkout — each `{id, finding, reason}`).
   For each actionable finding, spawn a fix subagent (step 4's pattern) in
   `worktree_path`. After a finding is RESOLVED, run
   `aug a-loops goal-consume-finding --entry-id <id>` so it is cleared and never
   re-surfaces. If you CANNOT resolve one, leave it (it stays queued) — do not
   consume it. For each `stale` entry, do NOT try to fix it AND do NOT consume it:
   the path is just absent from this checkout, which can mean a removed worktree
   OR a path that is still valid in another worktree/context — consuming it could
   discard a legitimately-actionable finding. Leave stale entries queued; their
   TTL reaps the genuinely-dead ones automatically.
   Drained entries are not auto-removed; only `goal-consume-finding` clears them.
4. **Per loop, in the returned order** (test/build before hygiene), iterate:
   a. `aug a-loops goal-scan-loop --loop <loop> --worktree <path> --budget-used <n>
      --max-iterations <N>`. It auto-applies mechanical fixes and returns
      `buckets` (semantic — each with `prompt`, `subagent_type`, `allowed_tools`),
      `maintenance` (deterministic items — maintenance fixes (reindex/rebuild) AND
      missing/stale generated artifacts (regenerated via the owning command's `fix()`);
      each with `auto_command`, `primary_file`, `finding_count`, `findings`; NO
      prompt/subagent), `residual_fingerprint`,
      `budget_remaining`, and `verify_command`.
      **Save the returned `residual_fingerprint` before re-running goal-scan-loop** —
      you must pass it as `--prev-fingerprint` to `goal-loop-status` in step (d).
   b. For each semantic bucket, **spawn your own subagent** (your Task/Agent tool) using
      that bucket's `prompt`, `subagent_type`, and `allowed_tools`. The subagent edits
      files under `worktree_path` to fix the finding.
   b2. For each `maintenance` item, do **NOT** spawn a subagent — it is a deterministic
      command action (e.g. `reindex-*`, project-index rebuild, or regenerating a
      missing/stale generated artifact such as the block registry). Run
      `aug a-loops goal-run-maintenance --loop <loop> --worktree <path>
      --auto-command <item.auto_command> --findings-json '<item.findings JSON>'`.
      It invokes the owning command's `fix()` directly (deterministic, no
      subagent) and reports `success`, `applied`, `changed_files`, and
      `fix_summary`. Many maintenance fixes (reindex/rebuild) write runtime state
      with no tracked-file change (`changed_files: []`) — that is success, not a
      no-op. If `changed_files` is non-empty, proceed to step (c) to verify/commit
      those; otherwise record the outcome in your report and move on.
   c. After each bucket's subagent returns, run `aug a-loops goal-record-bucket
      --worktree <path> --loop <loop> --auto-command <auto_command>
      --verify-command "<verify_command from step a>"`. Pass the `verify_command`
      returned by `goal-scan-loop` — this is the REAL project check from
      `config/system/adaptive_loops.yaml` `engine.verify_command` (e.g. a
      type-check), not a hardcoded empty string. NOTE: `goal-scan-loop` returns
      this verify command ONLY for code loops (testing, code-quality, ui-quality,
      page-health) — the project type-check meaningfully validates those changes.
      For hygiene loops (skill-standards, vault hygiene, …) it returns `""` because
      the type-check does not validate those changes; those checkpoints are recorded
      honestly without that check. If it was empty, omit the flag or pass `""`.
      It commits a checkpoint ONLY if verify passes; on red — INCLUDING a failure
      unrelated to this bucket (e.g. a pre-existing type error elsewhere in the
      project) — nothing is committed. Do NOT silently retry forever: report the
      verify failure honestly and escalate the finding (treat the residual as
      `stalled`/`exhausted` in step d) rather than looping. When no verify command
      was provided, it still commits for progress but reports
      `verified: false, unverified: true`.
   d. Re-run `goal-scan-loop`; pass the previously saved and current
      `residual_fingerprint` to `aug a-loops goal-loop-status --prev-fingerprint
      '<json>' --current-fingerprint '<json>' --iterations <i> --loop-cap <cap>
      --budget-remaining <r>`. Act on `verdict`:
      - `converged` → this loop is done; go to the next loop.
      - `stalled` or `exhausted` → escalate the residual findings with
        `aug a-loops goal-escalate --findings-json '<json>'`, then go to the next loop.
      - `continue` → repeat from (a) with the incremented iteration and budget.
5. **Report honestly** (never overstate): for each loop the verdict
   (converged / stalled / exhausted), the counts of mechanical fixes, subagent
   fixes, escalations, and backlog entries consumed, plus the `branch` name and any
   residual. Distinguish **verified checkpoints** (a real verify command ran and
   passed, `verified: true`) from **unverified checkpoints** (`unverified: true`,
   meaning no verify command was available — do NOT call these "verified"). Never say
   "all clean" if a loop stalled or exhausted. Tell the user to review and merge via
   `/dev-merge` — do NOT merge yourself.
