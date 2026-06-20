---
title: XA Main or Worktree Launch — Design
type: spec
status: draft
created: 2026-05-10
authors:
  - gsannikov
related:
  - scripts/install.sh
  - scripts/ai-launch.sh
  - scripts/worktree-launch.sh
  - tests/scripts/test_ai_launch.py
governance:
  next_step: ADR-617 already adopted (Accepted); proceed to /adr implement via the linked plan.
tags:
  - shell
  - launchers
  - worktrees
  - codex
  - claude
---

# XA Main or Worktree Launch — Design

A repo-owned shell entrypoint (`scripts/xa-launch.sh`) that replaces the
`xa()` shell function currently appended to the user's `~/.zshrc` by
`scripts/install.sh`. Every invocation prompts the user to choose between
launching their AI client (Codex by default, Claude via a sibling
entrypoint) in **main** or **new worktree** mode and refuses ambiguous
input.

The goal is to push the "did you mean to start me on dirty main, or in a
fresh worktree?" question to the front of every session — a habit that
prevents accidental work on a half-synced trunk and that every long-form
session in this repo benefits from.

## Context

### Current state (April–May 2026)

- `scripts/install.sh` lines 247-256 append three one-line shell
  functions to the user's rc file:

  ```bash
  ca() { claude --dangerously-skip-permissions "$@"; }
  xa() { codex --dangerously-bypass-approvals-and-sandbox "$@"; }
  ga() { gemini --yolo "$@"; }
  ```

  Those functions launch the AI client immediately, in whatever
  directory the user is in, against whatever branch is currently checked
  out. There is no main-vs-worktree prompt and no auto-sync.

- `scripts/ai-launch.sh` already implements the heavy lifting: it parses
  `[--dry-run] -- <client> [flags...]`, prompts `1) main / 2) new
  worktree`, validates the answer, runs `sync_main_checkout` (auto-stash,
  ff-only merge, restore stash), and either `exec`s the client at the
  repo root or hands off to `scripts/worktree-launch.sh create -- ...`.
  Tests in `tests/scripts/test_ai_launch.py` already exercise dirty-tree
  preservation, branch-switching, and "ahead of origin" rejection.

- `scripts/worktree-launch.sh` owns worktree naming
  (`derive_worktree_dir` → `<parent>/augur-<wt_name>`), branch
  creation, port registration, MCP config generation, Codex thread
  state repair, and `exec`-ing the client inside the new worktree with
  `AUGUR_ROOT/AUGUR_CORE/AUGUR_REPO` env vars set.

- The capability that ADR-617 promises — "prompt every run for `main`
  or `new worktree`" — is therefore **already inside `ai-launch.sh`**.
  What is missing is the user-facing **per-client** entrypoint that
  binds that capability to a single keystroke: `xa` for Codex, `ca` for
  Claude (if we keep it consistent).

### Constraints

1. **Do not modify the user's `~/.zshrc` from the agent side.** The
   installer is the only thing that ever writes to the rc file, and
   only at install time. The new entrypoint must be invokable by name
   from the user's shell after `install.sh` runs.

2. **Backward compatibility for one release.** Users with the existing
   `xa()` function should not have it silently broken. The installer
   should rewrite the function body to delegate to `xa-launch.sh`
   (or replace the function with a thin alias) — but a stale `xa()` in
   `~/.zshrc` that still hardcodes `codex --dangerously-bypass-...`
   must keep working until the user re-runs the installer.

3. **Do not require `ai-launch.sh` to know about Codex specifically.**
   `ai-launch.sh` is generic and should stay that way. The
   client-specific defaults (Codex flags vs Claude flags vs Gemini
   flags) belong in the per-client wrapper.

4. **TDD only.** Every change in `xa-launch.sh` ships with a black-box
   test under `tests/scripts/` that runs the script in `--dry-run` /
   `AI_NO_EXEC=1` mode against a fixture repo, exactly like
   `test_ai_launch.py` does today.

## Decision

Add a per-client launcher script at `scripts/xa-launch.sh` whose entire
job is to:

1. Resolve `$REPO_ROOT` from the script's own location (so it works
   regardless of the user's `cwd`).
2. Resolve `$AI_LAUNCH` to `$REPO_ROOT/scripts/ai-launch.sh`
   (overridable via `XA_AI_LAUNCH=` for tests).
3. Build the Codex command line: `codex
   --dangerously-bypass-approvals-and-sandbox` plus any user-supplied
   trailing args.
4. `exec`-into `ai-launch.sh -- codex
   --dangerously-bypass-approvals-and-sandbox [user_args...]`.

The entire script is ~15 lines of bash; all the meaningful logic
(prompt, sync, dirty-tree handling, worktree creation, port allocation,
MCP-config generation, Codex thread-state repair) is reused unchanged
from `ai-launch.sh` and `worktree-launch.sh`.

We **also** add `scripts/ca-launch.sh` (Claude wrapper) and
`scripts/ga-launch.sh` (Gemini wrapper) in the same shape so the three
shell functions become symmetric:

- `xa-launch.sh` → `ai-launch.sh -- codex --dangerously-bypass-approvals-and-sandbox "$@"`
- `ca-launch.sh` → `ai-launch.sh -- claude --dangerously-skip-permissions "$@"`
- `ga-launch.sh` → `ai-launch.sh -- gemini --yolo "$@"`

Then we update `scripts/install.sh` so that the marker block written to
`~/.zshrc` defines the three functions to delegate:

```bash
# === augur CLI shortcuts (ca/xa/ga) ===
xa() { "$AUGUR_INSTALL_DIR/scripts/xa-launch.sh" "$@"; }
ca() { "$AUGUR_INSTALL_DIR/scripts/ca-launch.sh" "$@"; }
ga() { "$AUGUR_INSTALL_DIR/scripts/ga-launch.sh" "$@"; }
# === end augur CLI shortcuts ===
```

Where `AUGUR_INSTALL_DIR` is captured at install time and frozen into
the rc-file block. (We resolve the path once and embed it; we do not
require the user to set an environment variable themselves.)

### Sub-decisions

1. **Prompt UX is non-negotiable.** `ai-launch.sh` already rejects
   invalid input by re-prompting until `1` / `main` / `2` / `worktree`
   is entered. `xa-launch.sh` inherits that — no override flag is added
   to skip the prompt. (The user can still pipe `1\n` or `2\n` into
   the function for non-interactive use, which is what the existing
   tests do.)

2. **Worktree naming stays automatic.** The user is *not* prompted for
   a worktree name from `xa`. The default
   `wt-YYYYMMDD-HHMMSS` pattern from `worktree-launch.sh` keeps the
   one-keystroke flow. Users who want an explicit name should call
   `scripts/worktree-launch.sh create --name <foo> -- codex ...`
   directly, or shadow `xa` with a personal alias.

3. **Codex thread-state repair already runs.** When
   `worktree-launch.sh` removes a worktree it calls
   `repair_codex_thread_state`. When it creates one we **rely on Codex
   itself to repopulate state** in the new worktree — no
   pre-launch repair is needed. This is unchanged.

4. **Dry-run is supported.** `xa-launch.sh --dry-run` forwards to
   `ai-launch.sh --dry-run`, which prints the planned mode + command
   and exits without calling `codex`. Tests use this to assert
   behavior without launching a real client.

5. **`--help` exits without prompting.** The wrapper recognizes
   `--help` / `-h` *before* prompting the user, prints its own short
   usage (which mentions the inherited `1) main / 2) new worktree`
   prompt), and exits 0. This satisfies CLAUDE.md rule 15 (`--help`
   stops execution).

6. **Keep `ai-launch.sh` as the single source of truth for sync
   logic.** No syncing logic is duplicated into `xa-launch.sh`. If we
   ever want to harden the merge (e.g., reject if behind by >N
   commits, or require a green CI status), that change lives in
   `ai-launch.sh` and is automatically inherited by all three
   wrappers.

## Architecture

### Components

```
~/.zshrc
  └── xa() { /abs/path/scripts/xa-launch.sh "$@"; }
        │
        ▼
scripts/xa-launch.sh   (15 lines, this ADR)
        │
        │ exec scripts/ai-launch.sh -- codex --dangerously-bypass-approvals-and-sandbox "$@"
        ▼
scripts/ai-launch.sh   (existing)
        │
        ├─ prompt: 1) main / 2) new worktree
        │
        ├── main mode ─── sync_main_checkout ─── exec codex
        │
        └── worktree ──── exec scripts/worktree-launch.sh create -- codex ...
                              │
                              ├── git worktree add
                              ├── register_worktree (port allocation)
                              ├── bootstrap_worktree (preflight)
                              ├── generate_mcp_config
                              └── exec codex (cwd=new worktree)
```

### Interfaces

**Public CLI surface**

```
xa-launch.sh [--dry-run] [--help] [-- <extra-codex-flags>]
```

- No flags: prompt + sync + launch Codex with the standard
  bypass-approvals flag.
- `--dry-run`: forwards to `ai-launch.sh --dry-run`; prints planned
  mode + final command line, exits 0.
- `--help`: prints usage, exits 0.
- `-- <extras>`: anything after `--` is appended to the Codex command
  line as additional flags.

**Environment overrides (for tests)**

- `XA_AI_LAUNCH`: absolute path to a substitute `ai-launch.sh` (so
  tests can swap in a stub).
- `XA_NO_EXEC`: when `1`, `xa-launch.sh` prints the resolved command
  it *would* exec (`mode=invoke target=<path> args=<...>`) and exits 0
  without exec-ing.
- All env vars consumed by `ai-launch.sh` (`AI_PROJECT_ROOT`,
  `AI_NO_EXEC`, `AI_WORKTREE_LAUNCH`) pass through unchanged.

**Failure modes**

| Symptom | Cause | Behavior |
|---|---|---|
| `ai-launch.sh` not found | `XA_AI_LAUNCH` typo or moved script | Print error to stderr, exit 1. |
| Invalid prompt input | User typed garbage | `ai-launch.sh` re-prompts; `xa-launch.sh` does nothing extra. |
| Local main ahead of origin/main | Unpushed commits on main | `ai-launch.sh` exits 1 with the existing message; `xa-launch.sh` propagates the exit code. |
| Worktree directory already exists | Reused name | `worktree-launch.sh` reuses it (existing behavior). |
| Codex binary missing | User didn't install Codex | `exec codex …` fails with "command not found"; user fixes their PATH. We do NOT pre-check Codex availability — that's a deliberate non-goal to keep the wrapper trivial. |

### Data flow

The wrapper is stateless. It has zero I/O of its own: it reads no
files, writes no files, does not touch the registry, does not touch
the vault. Every side effect lives in `ai-launch.sh` and
`worktree-launch.sh`, which already have ADR coverage (ADR-583 and
predecessors).

## Alternatives Considered

### A. Keep the inline `xa()` shell function, just enrich it

Rewrite the `xa()` body in `install.sh` to inline the prompt + sync
logic directly into the rc file. Rejected because:

- Long shell functions in `~/.zshrc` are hostile to debugging
  (no version control, no test coverage, no syntax highlighting in
  most users' editors).
- We already fixed this once for `ai-launch.sh`; doing it again for
  `xa()` would duplicate logic.
- Tests would need to spawn a login shell with the user's rc file to
  exercise the flow — far harder than running a checked-in script
  under pytest.

### B. Make `ai-launch.sh` itself client-aware via `--client codex|claude|gemini`

Drop per-client wrappers entirely; teach `ai-launch.sh` to look up
default flags by client name. Rejected because:

- It mixes "policy" (which flags does Codex want today?) into the
  generic launcher, requiring `ai-launch.sh` updates every time a
  client changes its flag set.
- The shell-function indirection in `~/.zshrc` would still need to
  pick a client somehow, just shifted from script name to flag.
- No win on lines of code: `ai-launch.sh` grows ~15 lines and the
  user-facing alias still needs to specify which client.

### C. Build it in Python

Move the prompt + dispatch into a Python CLI under
`src/scripts/`, invoked from a tiny shell stub. Rejected because:

- Cold-start latency for `python3 -c …` is ~150–250 ms on a typical
  Mac; bash is ~10 ms. The wrapper is on the hottest path of the
  user's day; we should not pay that tax.
- All upstream scripts already tested in bash and called from bash;
  introducing Python in the middle adds a dependency we already
  managed to avoid.

## Consequences

### Positive

- One canonical entrypoint per AI client, all three following the
  same shape (`xa`, `ca`, `ga`).
- Forced choice between `main` and `worktree` at every launch — the
  same friction level for every client and every user.
- Logic lives in version control with tests; rc file changes are
  tiny and rare.
- New users get the worktree habit "for free" the first time they
  use `xa`; experienced users keep their muscle memory.
- Future hardening (require green CI, reject if main is N commits
  behind, etc.) lands in one place (`ai-launch.sh`) and is inherited
  by all three wrappers.

### Negative

- One more script per client (3 trivial files instead of 3 trivial
  shell functions).
- Existing users with old-style rc-file functions need to re-run
  `scripts/install.sh` to pick up the delegating versions; until they
  do, their old `xa()` runs without the prompt.
- Adds 2 process forks per launch (shell function → wrapper script
  → `ai-launch.sh`). Negligible (<20 ms total).

### Neutral

- Worktree-mode launches still go through the full
  `worktree-launch.sh create` pipeline, which already includes port
  registration, preflight, and MCP-config generation. No change.
- Environment variables (`AUGUR_ROOT`, `AUGUR_CORE`, `AUGUR_REPO`)
  set by `worktree-launch.sh` for the spawned client are unchanged.
- `--dangerously-bypass-approvals-and-sandbox` and the equivalent
  Claude/Gemini "yolo" flags remain hardcoded in the wrappers; the
  trust posture matches the current `xa()` function exactly.

## References

- ADR-617 (this) — XA Main or Worktree Launch
- ADR-583 — `ai-launch.sh` introduction (worktree/main split + sync)
- `scripts/ai-launch.sh` — implements the prompt + sync logic this
  ADR delegates to.
- `scripts/worktree-launch.sh` — implements worktree creation + port
  allocation + bootstrap.
- `scripts/install.sh` — the only file that writes the `xa()`/`ca()`/`ga()`
  block into `~/.zshrc`; this ADR rewrites that block.
- `tests/scripts/test_ai_launch.py` — black-box test pattern that
  the new wrapper tests follow.
- CLAUDE.md rules 15 (`--help` stops execution) and 24 (Main checkout
  and AI-client safety).
