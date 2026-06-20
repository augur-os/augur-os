---
title: Worktree Dashboard Validation Isolation - Design
type: spec
status: draft
created: 2026-05-13
authors:
  - gsannikov
related:
  - docs/agent-topics/ARCHITECTURE.md
  - docs/agent-topics/DEBUGGING.md
  - docs/agent-topics/WORKFLOWS.md
  - scripts/worktree_registry.py
  - scripts/worktree_preflight.py
  - src/scripts/agent_launch.py
  - apps/dashboard/scripts/start-dev.mjs
  - apps/dashboard/scripts/build-lock.mjs
  - shared-vault/skills/daemon/scripts/dashboard_lifecycle.py
  - shared-vault/skills/daemon/scripts/ops/self_heal.py
governance:
  next_step: User review, then ADR for the instance-scoped lifecycle contract before implementation planning.
tags:
  - dashboard
  - worktrees
  - validation
  - self-heal
  - mcp
  - windows
---

# Worktree Dashboard Validation Isolation - Design

Augur already supports parallel development through git worktrees, dedicated
dashboard ports, dedicated MCP ports, and `.augur-worktree.yaml` markers.
However, dashboard lifecycle, healing, browser verification, and visible
surface behavior still contain global assumptions. That lets a worktree
validation run interfere with the main checkout dashboard, move the visible
browser, or trigger false-positive healing/update prompts that block automatic
verification.

This design makes every dashboard runtime an explicit instance. Main remains
the production/control-plane instance. Worktrees become isolated validation
instances that can be fully tested without mutating the user's visible main
dashboard session.

## 1. Problem

The user often develops in Augur worktrees and expects every worktree to receive
full validation before merge. The current behavior is unreliable because parts
of the runtime still behave as if there is only one dashboard:

1. **Lifecycle state is global.** `dashboard_lifecycle.py` stores one dashboard
   state/gate path, so a worktree crash or build can contaminate main lifecycle
   reporting.
2. **Build and heal operations are not consistently instance-scoped.**
   Worktree launch already resolves `PORT` and `MCP_PORT`, but lifecycle locks,
   build recovery, monitor state, and heal decisions can still read or write the
   global dashboard state.
3. **Visible surfaces can be hijacked.** Dashboard health hooks and repair paths
   may navigate the visible browser or send IDE/update prompts while the agent
   is trying to run automated worktree verification.
4. **False positives block automation.** A validation run may fail because main
   dashboard state changed, a heal prompt stole focus, or a visible browser tab
   jumped, not because the worktree code is broken.

The root failure is not a missing port. It is a missing instance boundary.

## 2. Goals

1. **Full worktree validation.** Every worktree can run build, MCP, dashboard,
   browser, and merge-gate verification before it is merged.
2. **Main dashboard stability.** Worktree validation never navigates, heals, or
   marks unhealthy the main checkout dashboard unless explicitly targeting main.
3. **Strict invisible defaults.** Worktree validation uses headless or isolated
   browser automation by default, with no visible browser jumps and no IDE
   update prompts.
4. **Instance-scoped lifecycle.** Dashboard state, gates, locks, logs, and
   artifacts are keyed by dashboard instance, not by "the dashboard" globally.
5. **Clear failure evidence.** Failed worktree validation reports the target
   URL, dashboard port, MCP port, lifecycle state, console errors, screenshot,
   and git branch.
6. **Opt-in interactive debug.** A developer may explicitly open a visible
   worktree browser/window for debugging, but that must be a separate surface
   from main.

## 3. Non-goals

- Do not remove main dashboard self-heal. Main remains the production-like
  control-plane dashboard and may still use user-visible recovery when the user
  asks for it.
- Do not require worktree validation to reuse port 3000.
- Do not allow automatic worktree validation to reuse the current visible
  browser tab.
- Do not rewrite all daemon/adaptive-loop behavior in one pass. This design
  introduces a contract and migration path.
- Do not build a full multi-worktree dashboard management UI in the first
  implementation. The data model should make that possible later.

## 4. Decision Summary

Introduce an **Augur Dashboard Instance** contract.

Every dashboard-affecting operation must resolve an instance before it can read
or mutate lifecycle state, build locks, browser state, MCP bridge state, or
self-heal policy.

```text
main checkout      -> instance_id = main
git worktree       -> instance_id = worktree:<name>
unknown checkout   -> instance_id = isolated:<hash> until registered
```

Default behavior:

| Context | Dashboard | MCP | Heal policy | Browser policy | IDE/update policy |
|---|---:|---:|---|---|---|
| main | 3000 | 8080 | enabled | visible allowed | allowed when user-triggered |
| worktree | 3001-3010 | 8081-8090 | validation only | headless/isolated only | disabled |
| worktree interactive | 3001-3010 | 8081-8090 | target-only repair | separate visible surface | disabled by default |

Core invariant:

> A validation run may only mutate the instance it targets.

This means:

- Main checkout can heal main.
- Worktree checkout can validate its own worktree.
- Worktree validation cannot navigate the main visible browser.
- Worktree validation cannot send IDE/update prompts.
- Worktree validation cannot mark main dashboard crashed.
- Main self-heal cannot kill or repair a live worktree server.

## 5. Current Building Blocks

The repo already has most identity primitives:

- `scripts/worktree_registry.py` allocates dashboard ports `3001-3010` and MCP
  ports offset by `5080`, producing MCP ports `8081-8090`.
- `src/scripts/agent_launch.py` writes `.env.local` and `.augur-worktree.yaml`
  when creating a worktree.
- `scripts/worktree_preflight.py` reads `.augur-worktree.yaml`, resolves
  dashboard/MCP ports, resolves the main repo, and returns launch metadata.
- `apps/dashboard/scripts/start-dev.mjs` already consumes preflight output and
  uses the worktree dashboard port when `preflight.worktree` is true.
- `docs/agent-topics/ARCHITECTURE.md` and `docs/agent-topics/DEBUGGING.md`
  already describe worktree port isolation and daemon worktree detection.

The missing pieces are instance-scoped lifecycle, scoped build/heal behavior,
and visible-surface policy enforcement.

## 6. Instance Model

Create a small shared resolver that all dashboard lifecycle/build/heal/browser
paths can use.

```text
AugurInstance:
  instance_id: string
  kind: main | worktree | isolated
  name: string
  project_root: path
  main_repo: path
  branch: string
  dashboard_port: number
  mcp_port: number
  runtime_scope: path
  browser_mode: visible_allowed | headless_only | isolated_visible
  heal_policy: enabled | validation_only | disabled
  visibility_policy: visible_allowed | no_visible_mutation
```

Resolution order:

1. Read explicit CLI/env target when present, for example
   `AUGUR_INSTANCE_ID` or `--instance`.
2. Read `.augur-worktree.yaml` from the current project root.
3. Read `worktree_registry.yaml`.
4. Compare current git worktree root with the main checkout root.
5. Fall back to `main` only when the checkout is the main repo and port is
   `3000`; otherwise use `isolated:<hash>`.

The resolver should live in a Python module that can be called from Node scripts
through JSON output, matching the existing `worktree_preflight.py` pattern.

## 7. Runtime Layout

Use the existing runtime directory from `src.config.paths.get_runtime_dir()`.
Do not store runtime state in the repo.

```text
<runtime>/daemon/dashboard/
  main/
    state.json
    events.jsonl
    gate.lock
  worktrees/
    <name>/
      state.json
      events.jsonl
      gate.lock
  isolated/
    <hash>/
      state.json
      events.jsonl
      gate.lock

<runtime>/locks/dashboard/
  main/
    build.lock
  worktrees/
    <name>/
      build.lock

<runtime>/browser-verification/
  main/
  worktrees/<name>/
```

The current global files may remain temporarily as compatibility mirrors, but
new writes must go to the scoped path once an instance is resolved.

## 8. Lifecycle Contract

`dashboard_lifecycle.py` should become instance-aware while keeping existing
commands usable.

Current style:

```text
python dashboard_lifecycle.py state
python dashboard_lifecycle.py request-action --actor X --action Y --reason Z
```

New style:

```text
python dashboard_lifecycle.py state --instance main
python dashboard_lifecycle.py state --project-root C:\path\to\worktree
python dashboard_lifecycle.py request-action --instance worktree:adr-123 ...
```

Compatibility rule:

- If no target is provided and cwd is main, target `main`.
- If no target is provided and cwd is a registered worktree, target that
  worktree.
- If no target is provided and cwd cannot be resolved, fail closed for mutating
  actions and print a resolution error.

State fields should include:

```json
{
  "instance_id": "worktree:adr-123",
  "kind": "worktree",
  "project_root": "C:\\Users\\intel\\Projects\\Augur\\.worktrees\\adr-123",  // audit-ignore: illustrative Windows path in archived ADR
  "branch": "adr-123",
  "dashboard_port": 3004,
  "mcp_port": 8084,
  "state": "healthy",
  "owner": "dev-build",
  "last_check_at": "2026-05-13T10:00:00Z",
  "last_browser_artifact": "...",
  "last_error": null
}
```

## 9. Heal Policy

Self-heal should split diagnosis from repair.

### Main policy

Main remains repair-capable:

```text
heal_policy = enabled
detect = yes
collect_evidence = yes
repair = yes
visible_browser_guidance = allowed when user-triggered
ide_update_prompt = allowed when user-triggered
```

### Worktree policy

Worktrees default to validation-only:

```text
heal_policy = validation_only
detect = yes
collect_evidence = yes
repair = no by default
restart_own_instance = only with explicit repair mode
visible_browser_guidance = no
ide_update_prompt = no
touch_main_lifecycle = no
```

This keeps worktree validation honest. A failing worktree should fail with
evidence rather than silently making global repairs or moving windows.

### Explicit repair mode

Worktree repair must be explicit:

```text
/dev-debug --target current-worktree --repair
/dev-build --target current-worktree --repair
```

Even in repair mode, the operation may only touch the target worktree instance.

## 10. Browser and IDE Surface Policy

Add one shared policy gate:

```text
may_use_visible_surface(instance, action, reason) -> allow | deny
```

Default rules:

| Instance | Action | Result |
|---|---|---|
| main | user-triggered navigation | allow |
| main | user-triggered IDE prompt | allow |
| main | automated validation | deny visible mutation unless explicitly requested |
| worktree | automated validation | deny |
| worktree | self-heal | deny |
| worktree | interactive debug | allow separate visible worktree surface only |

This gate should protect:

- dashboard health hooks that navigate the browser,
- `send-ide-prompt` or equivalent IDE update paths,
- browser verification runners,
- lifecycle recovery scripts that attempt user-visible guidance,
- any future "open dashboard" action.

For worktree validation, the only allowed browser surface is:

```text
browser_mode = headless_only
profile = <runtime>/browser-profiles/worktrees/<name>
artifacts = <runtime>/browser-verification/worktrees/<name>
```

Interactive worktree debug may use:

```text
browser_mode = isolated_visible
profile = <runtime>/browser-profiles/worktrees/<name>
url = http://127.0.0.1:<dashboard_port>/...
```

It must never reuse the current main tab.

## 11. Command UX

The user-facing commands should make the target explicit in output even when
the target is inferred.

Examples:

```text
/dev-build --target current-worktree
/dev-debug --target current-worktree
/dev-merge full
```

Expected validation banner:

```text
Validating instance: worktree:adr-123
Project root: C:\Users\intel\Projects\Augur\.worktrees\adr-123
Branch: adr-123
Dashboard: http://127.0.0.1:3004
MCP: 8084
Browser: isolated headless
Main dashboard: untouched
Heal policy: validation_only
```

Main validation banner:

```text
Validating instance: main
Dashboard: http://127.0.0.1:3000
MCP: 8080
Browser: visible allowed only for user-triggered actions
Heal policy: enabled
```

## 12. Dev-Merge Integration

`/dev-merge full` should validate changed worktree surfaces before merging, but
it must not steal the main browser tab.

Merge flow:

1. Resolve source worktree instance.
2. Acquire merge lock as usual.
3. Run scoped build/validation for the source worktree.
4. Save browser artifacts under the source worktree scope.
5. Merge into main only after worktree validation passes or after the user
   explicitly accepts a known validation failure.
6. After merge, validate main as main.
7. Only main validation may use the production/control-plane visible surface.

This preserves the current requirement that dashboard work be browser-verified
while making the pre-merge worktree validation automation-safe.

## 13. Implementation Phases

### Phase 1 - Instance Resolver and Read-Only Reporting

- Add a shared instance resolver.
- Extend `worktree_preflight.py` output with `instance_id`, `instance_kind`,
  `browser_mode`, `heal_policy`, and `visibility_policy`.
- Add a small CLI command to print the resolved instance.
- No behavior change yet except clearer logs.

Verification:

- Main resolves to `main` on port `3000` / MCP `8080`.
- Registered worktree resolves to `worktree:<name>` on allocated ports.
- Missing marker or stale registry produces a clear diagnostic.

### Phase 2 - Scoped Lifecycle State and Locks

- Add instance arguments to `dashboard_lifecycle.py`.
- Store lifecycle state, events, and gates under scoped runtime paths.
- Scope dashboard build locks by instance.
- Keep temporary compatibility reads from old global state only for main.

Verification:

- Marking a worktree crashed does not change main state.
- Main `state` command still works from the main checkout.
- Worktree `state` command resolves from cwd without manual flags.

### Phase 3 - Worktree Validation Surface Isolation

- Make browser verification use a per-instance artifact directory and isolated
  browser profile.
- Add visible-surface guard to dashboard hooks and IDE/update prompt paths.
- Default worktree validation to `headless_only`.
- Add explicit interactive worktree debug mode.

Verification:

- With the main browser open on `http://127.0.0.1:3000/browse/platform-admin`,
  run failing worktree validation and confirm that URL remains unchanged.
- Confirm artifacts are written under the worktree artifact directory.
- Confirm worktree validation reports console errors and screenshot path.

### Phase 4 - Heal Policy Enforcement

- Split self-heal into detect/evidence/repair phases.
- Main may repair when allowed.
- Worktree validation collects evidence and fails unless explicit repair mode is
  requested.
- Repair mode may only restart or mutate the target instance.

Verification:

- Worktree self-heal reports `validation_only` and does not update IDE/browser.
- Main self-heal still works for the main dashboard.
- Main monitor does not kill or mark unhealthy a registered worktree server.

### Phase 5 - Dev-Merge Gate

- Teach `/dev-merge full` to validate the source worktree instance before
  merge.
- After merge, validate main instance separately.
- Report both artifact sets distinctly.

Verification:

- Worktree validation failure blocks merge with evidence.
- Successful merge includes both source worktree validation and post-merge main
  validation.
- Worktree cleanup remains subject to active AI/client ownership checks.

## 14. Acceptance Criteria

The feature is done when all of these are true:

1. A worktree dashboard failure does not navigate
   `http://127.0.0.1:3000/browse/platform-admin`.
2. A worktree validation run can fail with screenshot, console errors, target
   URL, dashboard port, MCP port, lifecycle state, branch, and cwd.
3. Main dashboard lifecycle remains healthy while a worktree instance is
   unhealthy.
4. Worktree lifecycle can be unhealthy without contaminating main lifecycle
   state.
5. Worktree validation does not send IDE/update prompts.
6. Main self-heal cannot kill or repair a registered worktree server.
7. `/dev-merge full` validates the source worktree before merge and validates
   main after merge.
8. Interactive worktree debugging is opt-in and opens a separate surface.
9. All scoped runtime files are stored under `get_runtime_dir()`, not the repo.
10. Browser-touching dashboard changes are verified in a real browser or
    screenshot-capable browser tool, with artifacts linked in the result.

## 15. Test Strategy

Unit and integration coverage:

- Instance resolver tests:
  - main checkout,
  - registered worktree,
  - stale registry entry,
  - marker present but registry missing,
  - explicit `--instance` override.
- Lifecycle tests:
  - scoped state write/read,
  - scoped gate lock,
  - global compatibility for main,
  - mutating action fails closed when instance cannot be resolved.
- Build-lock tests:
  - main and worktree can hold separate locks,
  - shared cache lock still protects truly global cache mutation.
- Heal policy tests:
  - worktree defaults to evidence-only,
  - explicit repair mode is target-scoped,
  - main retains repair behavior.
- Browser policy tests:
  - worktree validation cannot call visible navigation,
  - worktree validation cannot send IDE prompt,
  - interactive debug produces separate visible-surface intent.

Browser verification:

- Open main visible browser at
  `http://127.0.0.1:3000/browse/platform-admin`.
- Create or use a worktree with a scoped dashboard port.
- Force a detectable worktree dashboard failure.
- Run worktree validation.
- Confirm main visible URL does not change.
- Confirm worktree artifact directory contains screenshot and console evidence.
- Restore/fix worktree failure and confirm validation passes.

Merge verification:

- Run `/dev-merge full` from a worktree with dashboard changes.
- Confirm pre-merge validation targets the worktree instance.
- Confirm post-merge validation targets main.
- Confirm final report distinguishes both targets.

## 16. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Compatibility break for existing `dashboard_lifecycle.py state` callers | Default no-arg reads to resolved cwd; keep main compatibility path while migrating callers |
| Worktree registry stale entries cause wrong target | Resolver validates path existence, port match, and marker consistency before mutating |
| Too many instance paths make debugging harder | Print the resolved instance banner at the start of every build/debug/merge validation |
| Main and worktree share build cache mutation | Keep a coarse shared cache lock only around truly global cache operations |
| Browser policy is bypassed by a UI hook | Centralize `may_use_visible_surface` and add tests around navigation/IDE prompt helpers |
| Worktree repair becomes too weak | Add explicit `--repair` mode that can restart only the target instance |

## 17. Future Extension

After the lifecycle contract is stable, add a platform-admin view for active
dashboard instances:

- main/worktree instance list,
- branch, port, MCP port, health, last validation,
- artifact links,
- cleanup warnings,
- explicit actions: validate, open isolated debug window, repair target.

This should be a follow-on UI feature, not part of the initial isolation fix.

