---
status: Proposed
date: 2026-06-22
deciders:
  - Gur
related:
  - ADR-195
  - ADR-449
  - ADR-474
  - ADR-464
  - ADR-101
hub: null
tags:
  - vault
  - concurrency
  - merge-lock
  - cross-client
  - inbox-triage
superseded_by: null
spec_file: null
plan_file: null
---

# ADR-816: Cross-machine vault write coordination

## Decision summary

Adopt a **remote advisory lease** (an extension of the ADR-195 dev-merge lock onto
the vault git remote) as the durable fix for concurrent vault writers across
machines/clients, while keeping the already-shipped machine-local lock +
push-rebase-retry as the cheap first line of defense. **Proposed — needs Gur's
ratification of the writer-topology tradeoff before implementation.**

## Context

The augur-vault DATA repo (ADR-449/ADR-474) is written by **many uncoordinated
actors**, and Augur is cross-client and multi-machine by design (rule 38; the user
mirrors Augur across a Mac + Windows laptop, plus cloud-run scheduled routines):

- `/dev merge full` (the canonical commit/merge/push path)
- the machine's auto-commit / dashboard-sync cron
- manual `/keep` captures
- the scheduled **inbox-triage** routine (runs in whichever client/machine the
  schedule fires on — often the cloud, not the Mac)

The ADR-195 **dev-merge concurrency lock** (`<state>/locks/dev-merge.lock`)
already serializes writers — but its lock file lives in the **machine-local shared
state dir** (`get_state_dir()`, worktree-shared but not machine-shared). It
therefore coordinates writers **on one machine only**. Two machines/clients
mutating the vault concurrently have no mutual exclusion and will diverge.

### Concrete incident (this proposal's trigger)

On 2026-06-22, the cloud inbox-triage routine pushed `602cbc1`
("chore(inbox-triage): daily auto-file 2 cards into domains") to `origin/main`
while the Mac sat on 5 unpushed local auto-commits touching the **same** files
(`_augur/knowledge/memory/index.yaml`, `_augur/system/pins.yaml`, and two
`inbox/` cards). The result was a diverged vault (6 ahead / 1 behind) that
required a hand-run `/dev merge full` no-loss merge to reconcile. This is the
recurring "shared-checkout collision" pattern already noted in memory. The
machine-local lock could not have prevented it because the two writers were on
different machines.

### What is already mitigated (do not re-solve)

The inbox-triage routine was hardened in the same session to:
1. acquire the **machine-local** ADR-195 lock (`--tool inbox-triage`) around its
   pull→file→commit→push critical section — coordinating it with same-machine
   `/dev merge` runs;
2. `git pull --rebase` with an abort-and-report guard (never commit on a broken
   merge);
3. commit by **exact pathspec** (the moved cards), never `git add -A`;
4. retry once on a non-fast-forward push (re-pull-rebase, then stop cleanly).

(3) and (4) make most cross-machine collisions *cheap* (the loser rebases and
retries), but nothing makes them *impossible*. The gap this ADR closes is
**cross-machine mutual exclusion**.

## Decision

Extend the merge-lock model to a **remote advisory lease** that every vault
writer acquires before its pull→commit→push critical section, regardless of which
machine or client it runs on.

Shape (to be detailed in a spec before implementation):

- A dedicated, tiny lock object on the vault remote — e.g. a `refs/locks/vault`
  ref (or a single-file `vault-lock` orphan branch) holding `{tool, owner, host,
  pid, acquired_at, heartbeat_at}` as JSON.
- **Acquire** = atomically create/advance the lock ref via `git push` with a
  compare-and-swap (`--force-with-lease`-style expected-old-value). A push that
  loses the CAS means another writer holds the lease → wait/retry or skip.
- **Heartbeat + TTL**: long-running holders refresh `heartbeat_at`; a lease idle
  past the TTL (mirror the ADR-195 30-minute stale window) is breakable by the
  next acquirer, so a dead client never deadlocks the vault.
- **Release** = reset the lock ref to the free sentinel, owner-checked like
  ADR-195's `release`.
- The local ADR-195 lock stays as the **same-machine** layer; the remote lease is
  the **cross-machine** layer. A writer holds both for its critical section.
- Expose acquire/release through a client-neutral engine (shared Python, surfaced
  via `aug` / MCP) so every client — `/dev merge`, inbox-triage, `/keep`, the
  auto-commit cron — enters the *same* shared logic, not a per-client copy
  (rule 38).

This is **Proposed**: it carries a real product tradeoff (latency + a remote
round-trip on every vault write, and the writer-topology question below) that is
Gur's call before any code is written.

## Consequences

**Positive**
- Eliminates the cross-machine divergence class entirely — concurrent writers
  serialize instead of colliding; `/dev merge` hand-merges become rare exceptions,
  not routine.
- Generalizes the model the user already chose (the merge lock) rather than
  inventing a new mechanism.
- TTL + heartbeat means no permanent deadlock from a crashed/offline client.

**Negative**
- Every vault write pays a remote round-trip to acquire/release the lease (extra
  latency; offline writes can't acquire — see Open Questions).
- Git refs as a CAS lock are workable but fiddly; needs careful, well-tested
  acquisition to avoid races and stale-lease false positives.
- All writers must opt in; a single non-participating writer (e.g. a manual
  `git push` from a terminal) reintroduces the collision.

**Neutral**
- The machine-local ADR-195 lock and the routine's push-retry remain; this layers
  on top, it does not replace them.

## Alternatives Considered

1. **Single designated vault writer.** Only one actor (e.g. the cloud routine, or
   only the Mac) ever pushes; all others are pull-only and route writes through
   the designated writer. *Simplest and fully collision-proof*, but it breaks the
   user's real workflow of capturing on both laptops independently, and forces
   every `/keep` to funnel through one path. Rejected as the default for being too
   constraining — but it remains the lowest-complexity fallback if the remote
   lease proves too costly.

2. **Serialize all writes through one service/daemon.** Route every vault
   mutation through a single MCP/daemon endpoint that holds the local lock.
   Doesn't help cross-machine (the cloud routine runs in its own session), and
   adds an always-on dependency that fights Augur's local-first design. Rejected.

3. **Status quo (machine-local lock + push-rebase-retry only).** Accept that
   cross-machine writers occasionally diverge and are reconciled cheaply by the
   retry, with a hand-run `/dev merge full` for the rare real conflict. *Zero new
   engineering.* This is the honest "good enough" option if the collision rate is
   low in practice — the decision below is only worth its cost if divergence is
   frequent enough to annoy. Documented as the explicit no-op alternative.

## Open Questions

- **Offline writes.** A laptop capturing offline can't acquire a remote lease.
  Do offline writes queue and acquire-on-reconnect, or fall back to the
  retry-on-push path? (Likely: offline → local-only commit, acquire+push when
  back online.)
- **Latency budget.** Is a remote round-trip acceptable on every `/keep`, or
  should the lease be batched/held for a session?
- **Which writers must participate** to make the guarantee real, and how do we
  detect/flag a non-participating writer?
- **Is the collision rate high enough** to justify this over Alternative 3? Worth
  measuring divergence frequency over a few weeks first.

## References

- ADR-195 — Dev-Merge Concurrency Lock (the machine-local lock extended here)
- ADR-449 / ADR-474 — Vault Git Integration
- ADR-464 — Cross-Client Agent Sync (multi-master distribution precedent)
- ADR-101 — Worktree Isolation for Parallel Development
- `project-brain/capabilities/skills/platform-admin/scripts/merge_lock.py` — current lock implementation
- `project-brain/capabilities/skills/platform-admin/commands/dev-merge.md` — `/dev merge full` no-loss contract
- inbox-triage routine hardening (machine-local lock + pathspec commit + push-rebase-retry), same session as this ADR
