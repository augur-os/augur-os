---
x-augur-export-command: false
---
# /dev-merge

Commit, merge into the target branch, push, and clean up worktrees/branches.
In `full` mode, this is a smart inspected no-loss merge: it should classify dirty
state before merge, preserve local-only artifacts safely, merge all repo-relevant
changes, include the configured vault repository, verify the remote results, and
finish without leftover worktrees, side branches, or emergency stash state.

## Modes

- `fast` (default): git operations only
- `full`: smart inspected no-loss merge. Inspect dirty state, separate repo work
  from local-only/generated artifacts, preserve what should stay local, merge and
  push everything that belongs in the code repo and configured vault repo, verify
  both remote tips, then remove temporary branches/worktrees/stashes so the repos
  end clean
- `all`: fast-merge multiple worktrees, then run heavy steps once
- `sync`: safe sync the main checkout with `origin/main` when the local branch is
  ahead of or diverged from `origin/main`; preserve dirty work, rebase local-only
  commits onto `origin/main`, push with no force push, verify `main == origin/main`,
  and restore local dirt before returning
- `--push`: explicit multi-repo sync path, equivalent to the vault coverage that
  `full` mode already performs

## Demo Proof Flags

Optional flags:

- `--com` / `--compound-wiki`: require a wiki compounding proof before merge.
- `--skillify` / `--skilify`: require a skillification proof before merge.

Example:

```bash
/dev-merge full --com --skillify
```

These flags are pre-merge proof gates. They do not change the target branch,
merge strategy, push behavior, vault coverage, purge behavior, or cleanup rules.
When present, run the helper with `<requested proof flags>` replaced by only the
aliases the user supplied:

```bash
python3 project-brain/capabilities/skills/platform-admin/scripts/dev_merge_demo_proof.py \
  <requested proof flags>
```

### Compound Review Preflight

When `/dev-merge full --com --skillify` is being used for the project
compounding demo, run the helper with `--compound-review` as a pre-merge review
step. The helper still collects deterministic `--com`/`--skillify` evidence
before attaching the proposal review. The native AI client supplies the proposal
JSON; the helper validates the proposal, renders it, and writes runtime
artifacts. It does not write wiki, skill, or ADR files.

Use this handoff:

```bash
python3 project-brain/capabilities/skills/platform-admin/scripts/dev_merge_demo_proof.py \
  --com --skillify --compound-review
```

If the helper reports that no proposal was supplied, read the evidence artifact
path from the output, reason over that evidence in the current AI client, write a
proposal JSON under the runtime directory, and rerun:

```bash
python3 project-brain/capabilities/skills/platform-admin/scripts/dev_merge_demo_proof.py \
  --com --skillify --compound-review \
  --review-proposal-json <runtime-proposal-json>
```

The proposal JSON must include:

```json
{
  "status": "proposed",
  "durable_lesson": "Client skill projection is a contract boundary.",
  "evidence": [
    "Codex skipped 10 projected skills because frontmatter was missing.",
    "Parser-facing tests cover YAML-safe command skill metadata."
  ],
  "target_type": "existing_skill",
  "target_artifact": "project-brain/capabilities/skills/ai/references/client-projection.md",
  "next_action": "Strengthen client projection guidance with a parser-gate rule.",
  "confidence": "high",
  "why_not": [
    "No new skill is needed because sync_agents owns this path."
  ]
}
```

The compound review may block the merge when the proposal is missing, malformed,
generic, or not evidence-backed. Passing compound review is not proof that wiki
or skill artifacts changed. The requested `--com` and `--skillify` proof gates
remain deterministic; final output renders the compound review before the proof
summaries, and the merge remains blocked unless compound review and requested
proof gates pass.

For example, `/dev-merge full --skillify` runs the helper with only
`--skillify`; `/dev-merge full --com --skillify` runs both. If the helper prints
`Result: blocked before merge`, stop before merge/push and report the proof
summary. If the helper prints `Result: proof passed; continuing /dev-merge full`,
continue the normal `/dev-merge full` contract unchanged.

For `--com`, proof is live `wiki-status` readiness plus the configured vault git
change set, not only current-session proof. When durable `wiki/` files changed,
non-passable `wiki-status` verdicts block before merge/push, including queued
compile backlog, stale/low-coverage/current-low-coverage results,
structure/compiler errors, or other demo-readiness failures. If no durable
`wiki/` files changed, a queued compile backlog is reported as a verified no-op
summary and normal merge continues. Verified-noop wiki proof must name real
page/query evidence and a current freshness timestamp; aggregate counts alone
are weak proof and block. A blocked proof exits non-zero; helper automation uses
exit 2 for blocked proof.

Run wiki proof before skillify proof when both flags are present. The proof must
print the wiki compounding summary and skillify summary before merge/push, using
real repo/vault data. A generated client export is not skillification proof
unless the canonical skill source under `project-brain/capabilities/skills/`
also changed. Skillify proof must also name the durable skill behavior, block
deletion-only skill diffs, and include routing/quality evidence. Routing proof
comes from a matching skill manifest root or a `skill:<name>` capability policy
entry; `primary_skill` ownership metadata on another capability is not routing
proof by itself. For code-bearing skill changes such as scripts, MCP wrappers,
or dashboard surfaces, the helper runs the affected skill's `augur/tests/`
through the existing `auto-test-pytest` operation and blocks on missing/failing
quality verification.

The helper bootstraps Augur path helpers and resolves the configured
vault/runtime paths automatically; normal `/dev-merge full --com --skillify`
callers do not pass `--vault-root` or `--runtime-dir`.

## Contract

- acquire the merge lock before starting
- never commit conflict markers
- inspect current dirty state before mutating branches
- create a reversible safety path until the merge result is verified remotely
- merge all repo-relevant changes that should land, not just the currently staged subset
- `full` mode includes the configured vault repository from `config/system/vault.yaml`
- inspect, commit and push vault changes when the vault repo is present and dirty
- verify both remote tips after code and vault pushes
- safe sync mode must never force push; if rebase, push, verification, or stash
  restoration fails, stop with the exact git error and leave the user with a
  recoverable state
- preserve local-only artifacts without publishing machine-specific caches, personal skills, or generated installs by mistake
- preserve dirty target-branch state before merge if needed
- regenerate/sync generated surfaces after merge when required
- when the merged set adds or changes any `project-brain/decisions/adrs/ADR-*.md` (new ADR or status flip), run the **ADR Index Sync** below before the final push so `adrs-index.json` and `docs/generated/adr-index.md` never land stale
- classify leftover branch commits into `already_in_main`, `clean_salvage`, and `stale_or_conflicting` when a leftover worktree branch cannot be merged as one unit
- merge or cherry-pick every `clean_salvage` commit and prove equivalent `already_in_main` work is present in the target before cleanup
- auto-discard the leftover branch/worktree after all merge-worthy repo work is verified in the target branch, and report exactly which stale/conflicting commits were discarded
- escalate instead of leaving leftovers behind only when equivalence or salvage cannot be proven safely
- before deleting an Augur worktree, repair Codex thread state so saved sessions no longer point at the removed checkout
- before removing any worktree, run the shared live-process guard — `python project-brain/capabilities/skills/platform-admin/scripts/worktree_guard.py --active-processes <worktree-path>` (exit 3 = a live owner was found) — and never use a bare `git worktree remove`/`rm -rf` that skips it; if `codex`, `claude`, `gemini`, or Cowork still owns the path, report the cwd/branch/PID and defer deletion instead of crashing the session
- after a successful verified merge, remove the originating worktree and delete the originating branch only when no live AI/client process is using that path
- remove temporary merge branches, worktrees, and stash/backup state after a successful verified `full` merge so there are no leftovers

## Purge Mode

`--purge` is a stalled-leftover cleanup mode.

It may remove a leftover branch/worktree only when:

- no merge-worthy commits remain to be salvaged into `main`
- all remaining dirty paths are technical leftovers from an explicit allowlist

It must skip purge when:

- `clean_salvage` commits still exist
- meaningful repo changes remain
- any dirty path is ambiguous

Examples:

- `/dev-merge --purge`
- `/dev-merge full --purge`
- `/dev-merge all --purge`

Purge reporting must classify leftovers as:

- purged
- skipped: merge-worthy commits remain
- skipped: meaningful repo changes remain
- skipped: ambiguous leftovers

## Mixed Leftovers

When `full` mode encounters a leftover branch/worktree that contains a mix of old
WIP and merge-worthy fixes, it must not stop at "branch still exists".

Required sequence:

1. Create an isolated merge worktree from the target branch.
2. Classify leftover branch commits into `already_in_main`, `clean_salvage`, and
   `stale_or_conflicting`.
3. Merge or cherry-pick every `clean_salvage` commit, and verify that
   `already_in_main` commits are truly equivalent in the target branch.
4. If all repo-relevant work is now present in the target branch, auto-discard
   the leftover branch/worktree and report the discarded `stale_or_conflicting`
   commits explicitly.
5. If equivalence or salvage cannot be proven, stop and escalate instead of
   leaving silent leftovers or guessing.

## Successful Verified Merge Cleanup

When `/dev-merge` succeeds from an active worktree, the successful verified merge
is the terminal point of that worktree lifecycle.

Required successful path:

1. determine whether the current session is running in a worktree
2. complete the merge and any required verification
3. prove the target branch contains the intended result
4. repair Codex thread state for the originating worktree path
5. run the shared live-process guard — `worktree_guard.py --active-processes <worktree-path>` — and confirm it exits 0 (no live AI/client process owns the path). This is a mandatory gate, not a self-check: a bare `git worktree remove` or `rm -rf` that skips the guard is a contract violation.
6. remove the originating worktree
7. delete the originating branch
8. report what was deleted

If verification is incomplete or salvage proof fails, stop and escalate instead
of deleting the worktree.
If the live-process guard reports an owner (exit 3) — i.e. a `codex`, `claude`,
`gemini`, or Cowork process still owns the worktree path — report the blocking
PID/command and defer deletion (steps 6–7) rather than removing the checkout
from under an active session. The session itself is the common owner: a
`/dev-merge` run launched from inside the very worktree being cleaned up must
defer its own worktree removal, not delete the ground it is standing on.

When deferring, do not stop at "report and defer" — **enqueue the worktree for
deferred auto-purge** so it is reaped automatically once every client releases
the path, with no manual follow-up session:

```bash
python3 project-brain/capabilities/skills/platform-admin/scripts/worktree_purge_queue.py \
  enqueue --path <worktree-path> --branch <branch> --target main
```

`enqueue` re-verifies the branch is fully merged into `main` and refuses
otherwise (no-loss). The `session-start` and `session-end` hooks then run
`worktree_purge_queue.py sweep`, which re-checks the no-loss preconditions
(merged + clean + zero live owners via `worktree_guard.py`) and runs the
canonical `worktree-launch.sh cleanup` the moment the path is free. A worktree
held open in a second client (e.g. Cowork) stays queued — correctly — until that
client also releases it. Inspect or drain the queue with
`worktree_purge_queue.py list`.

## Worktree Dashboard Validation Gate

When `/dev-merge full` starts from an Augur worktree, validate the source
worktree instance before merging:

1. Resolve the source instance from `.augur-worktree.yaml` and
   `worktree_registry.yaml`.
2. Run scoped dashboard/MCP/browser validation against the worktree dashboard
   port and MCP port.
3. Save screenshot, console, lifecycle, and MCP evidence under the worktree
   artifact directory.
4. Do not navigate the main browser tab and do not send IDE update prompts.
5. Block merge on validation failure unless the user explicitly accepts the
   failure with the evidence in view.
6. After merge, validate `main` separately and report a separate main artifact
   set.

## ADR Index Sync

ADRs are often written or status-flipped directly in `project-brain/decisions/adrs/ADR-*.md` during
feature work (not via `/adr`), which means the `/adr` post-write hook never ran
and the central `adrs-index.json` + the `docs/generated/adr-index.md` rollup drift
from the ADRs actually landing in the target branch. `full` mode must detect this
and resync before the final push.

Required sequence:

1. **Detect ADR changes in the merged set** — compare the target branch before and
   after the merge:
   ```bash
   git diff --name-only <target-before>..<merged-head> -- project-brain/decisions/adrs/
   ```
   If any `ADR-*.md` is added or modified (new ADR, status change, or status-notes
   edit), the index needs a resync. No ADR paths → skip this section.
2. **Run the canonical ADR post-write hook** (source of truth: `/adr` →
   "Post-Write Hook: Index and Doc Sync"):
   ```bash
   python .github/scripts/adr_upsert_live.py            # live .md -> central JSON
   python .github/scripts/generate_adr_index.py         # regenerate markdown rollup
   python src/lib/index/unified_indexer.py --category adrs   # RAG pointer index
   PYTHONPATH=project-brain/capabilities python3 -m skills.ai.scripts.sync_agents sync agents all  # ADR status table in agent instructions
   ```
3. **Commit the regenerated outputs** (`adrs-index.json`,
   `docs/generated/adr-index.md`, and any synced agent surfaces) into the merge and
   push — never leave the index stale. Re-verify the remote tip afterward.

This keeps the ADR status summary in `CLAUDE.md` and the rollup consistent with the
ADRs in the target branch.

## Runtime Owner

The merge-lock/runtime owner is `platform-admin`, including [../scripts/merge_lock.py](../scripts/merge_lock.py).
