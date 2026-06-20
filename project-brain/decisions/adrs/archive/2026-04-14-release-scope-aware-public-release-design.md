# Release-Scope-Aware Public Release Design

## Goal

Make `/release` the single publish entrypoint for `augur` -> `augur-os` releases, while allowing the published surface to change automatically based on the current release phase.

Current required behavior:

- release scope is `docs_only`
- `/release` publishes only the approved public documentation surface
- no per-run mode flag is required
- `docs/user-guide.md` must be cleaned up so it is safe to include in the docs-only surface

Future required behavior:

- when the project phase changes to `mvp`, the release path should automatically publish the broader MVP surface without redesigning the command

## Current Problem

The existing release flow already treats `augur` as the private source repo and `augur-os` as the public target:

- command surface: `skills/platform-admin/commands/release.md`
- engine: `scripts/release.sh`

But the current implementation is still a coarse full-tree publish flow:

- it sanitizes a few private config paths
- it squashes the current tree onto `augur-os/main`
- it does not define a public docs allowlist
- it does not encode a release-scope state
- it does not know that the current phase is `docs_only`

As a result, public docs sync is currently manual and `docs/user-guide.md` remains too stale to include in the public mirror.

## Decision

Introduce a canonical release-scope state in `augur`, and make `/release` scope-aware.

### Canonical Release Scope

Add one repo-owned machine-readable state file:

```text
config/system/release_scope.yaml
```

Initial contents:

```yaml
scope: docs_only
```

Later, when the project phase changes:

```yaml
scope: mvp
```

`/release` must read this state and choose the publish surface automatically.

## Scope Modes

### `docs_only`

This is the active mode now.

Publish only the curated public docs surface:

- `README.md`
- `ROADMAP.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `CHANGELOG.md`
- `LICENSE`
- `docs/getting-started.md`
- `docs/developer-guide.md`
- `docs/user-guide.md`
- `docs/creating-skills.md`
- `docs/architecture-overview.md`
- `docs/architecture-mcp-gateway.md`
- `docs/guides/installation-windows.md`

Explicitly exclude:

- `docs/superpowers/`
- `docs/agent-topics/`
- generated IDE instruction docs
- specs, plans, session artifacts
- code, tests, scripts, config, workflows, and any broader repo content outside the allowlist

### `mvp`

`mvp` is the next planned scope, but not the active scope in this design.

When scope later becomes `mvp`, `/release` should still use the same entrypoint and state file, but switch to an MVP publish surface builder instead of the docs-only builder.

## Publish Model

The release flow should become:

1. Read canonical release scope from repo state
2. Print detected release scope in preflight output
3. Run existing safety scan
4. Build a temporary publish tree for the current scope
5. Release that publish tree to `augur-os`
6. Report the detected scope and what was published

For `docs_only`, the temporary publish tree should contain only the allowlisted public docs surface.

The public repo should be overwritten only for the published files in that tree, not for the full private repo.

## Release Integration

### Command Surface

Update `skills/platform-admin/commands/release.md` so it documents:

- release scope is automatic
- current scope is read from repo state
- `docs_only` publishes the curated documentation surface
- future `mvp` support will use the same entrypoint

The command should stop describing release as a permanently full-tree public sync.

### Release Engine

Update `scripts/release.sh` so it no longer assumes a single fixed publication shape.

Required changes:

- read `config/system/release_scope.yaml`
- branch on scope
- call a publish-tree builder for the current scope
- release the built tree rather than blindly squashing the working tree

Recommended structure:

- keep `scripts/release.sh` as orchestrator
- add one helper script responsible for building the docs-only publish tree

Suggested helper:

```text
scripts/build_public_release_tree.py
```

Responsibilities:

- create a temporary output directory
- copy only the allowlisted files for `docs_only`
- preserve relative structure
- fail if an allowlisted source file is missing
- optionally emit a short manifest of published files

This keeps policy out of the shell script and makes the public surface explicit and testable.

## `docs/user-guide.md` Cleanup

The current canonical `docs/user-guide.md` is not safe for public mirroring because it still contains stale assumptions such as:

- `augur-data` paths
- older skill catalog content
- macOS-only scheduler assumptions

This task must update `docs/user-guide.md` so it matches the current external docs story and is safe to include in the `docs_only` allowlist.

The rewrite should:

- reflect current soft-launch status
- avoid stale hardcoded data-path language
- avoid macOS-only scheduler framing as if it were universal
- stay aligned with the same platform story used in the top-level docs

## Non-Goals

This task does not:

- implement the `mvp` publish surface
- define the full public code release boundary
- replace the broader release/tagging/version flow
- publish internal docs, plans, or specs

## Risks

### Hidden Docs Drift

If docs-only mirroring includes stale files outside the allowlist, `augur-os` will become contradictory again.

Mitigation:

- use an explicit allowlist
- fail closed on missing files
- keep the mirrored set intentionally narrow

### Scope Ambiguity

If release scope is inferred from roadmap text or tags, releases will become brittle.

Mitigation:

- use one explicit machine-readable scope file

### Shell Policy Drift

If the allowlist lives only inside `release.sh`, it will become hard to reason about and easy to break.

Mitigation:

- move the publish-surface logic into a dedicated builder script

## Success Criteria

This design is complete when:

- `/release` automatically detects `docs_only`
- the release engine publishes the curated docs surface without manual repo syncing
- `docs/user-guide.md` is safe to include in that docs surface
- `augur-os` can be refreshed from `augur` without editorial cleanup each time
- switching to `mvp` later requires changing repo state, not redesigning the command