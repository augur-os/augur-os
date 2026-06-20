---
name: release
description: Release current private repo state to the public augur-os/augur-os repo. Builds the guarded public tree, pushes a release branch, opens a pull request, and follows the active release scope.
x-augur-export-command: false
---

# /release - Publish to augur-os/augur-os

Sync the current private repo state to the public `augur-os/augur-os` GitHub repo with clean history. The release scope is automatic and is read from `config/system/release_scope.yaml`.

## Usage

```
/release [--dry-run] [--help]
```

## Options

| Flag | Description |
|------|-------------|
| `--help` | Show usage and stop |
| `--dry-run` | Run all checks, build the release commit, and report the release branch and pull request actions without pushing |

## Current Scope

- `config/system/release_scope.yaml` is the source of truth for release behavior.
- Current value: `scope: docs_only`.
- `docs_only` builds a temp public architecture-doc tree with `scripts/build_public_release_tree.py` and does not mutate the main working tree.
- `scripts/guard_public_release_tree.py` must pass before anything is pushed to `augur-os/augur-os`.
- `.githooks/pre-push` runs `scripts/guard_public_push.py` so manual pushes to `augur-os/augur-os` are blocked unless the exact pushed commit tree matches the public allowlist.
- `mvp` is retained as an internal staging concept, but the public release guard rejects full worktree surfaces such as `src/`, `apps/`, `project-brain/` (which now includes ADRs at `project-brain/decisions/adrs/`), and `docs/security/`.

## Relationship To Staged Porting

`/release` publishes the currently prepared public surface.
It does not pull future-release payloads out of the `porting` branch automatically.
Use `/stage-release` to prepare the payload and `/port-release` to adapt it into `main`, then run `/release`.

## Execution Steps

### 1. Pre-flight checks

- [ ] Verify repo has no uncommitted changes (`git status --porcelain` must be empty)
- [ ] If not clean, ask user: commit now or abort?

### 2. Safety scan (skip if `--skip-safety`)

Scan for private data that must not reach the public repo:

```bash
# Personal/client identifiers configured for the private checkout - must return zero hits
: "${AUGUR_PRIVATE_MARKER_REGEX:?Set a private marker regex for this checkout before release}"
grep -r -E "$AUGUR_PRIVATE_MARKER_REGEX" . \
  --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=docs/superpowers \
  --exclude-dir=.venv --exclude-dir=__pycache__ -l
```

```bash
# Hardcoded user paths - must return zero hits outside exclusions
grep -r "/Users/$(id -un)\|$(id -un)" . \
  --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=docs/superpowers \
  --exclude-dir=.venv --exclude-dir=__pycache__ --exclude-dir='.claude' \
  --exclude='*.pyc' --exclude='release.md' -l
```

If any hits found: STOP, report them, and ask user how to proceed. Do NOT continue until resolved.

### 3. Run release script

```bash
./scripts/release.sh [--dry-run]
```

The script reads `config/system/release_scope.yaml` and chooses the path automatically:

- `docs_only` builds a temp public tree with `scripts/build_public_release_tree.py`, commits that tree in an isolated temp repo, and pushes that tree without touching the main checkout.
- The generated tree is then checked by `scripts/guard_public_release_tree.py`; any forbidden path, binary/archive file, ADR/security packet, or private marker stops the release.
- `mvp` builds an isolated release worktree, sanitizes the repo, runs `scripts/prepare_release_workspace.py`, and then hits the same public release guard before it can publish.
- A real release pushes `release/<version>` to `augur-os/augur-os` and opens a pull request against public `main`. It does not push directly to public `main`.

GitHub.com public source repositories do not support repository push rulesets. Keep `augur-os/augur-os` `main` protected by pull request, deletion, and history-rewrite rules. A true remote content hook requires a private/internal repository with push rules or GitHub Enterprise Server pre-receive hooks.

If `--dry-run`, stop here and report what would be pushed.

### 4. Review and merge the release pull request

This is the required human gate for the public repo. Review the generated release branch diff in `augur-os/augur-os`, then merge the pull request after confirming it contains only architecture files.

After the pull request is merged, create and push the release tag from the public repo's merged commit:

```bash
VERSION=vX.Y.Z
git fetch augur-os main
MERGED_COMMIT=$(git rev-parse augur-os/main)
git tag -a "$VERSION" "$MERGED_COMMIT" -m "Release $VERSION"
git push augur-os "$VERSION"
gh release create "$VERSION" \
  --repo augur-os/augur-os \
  --title "$VERSION" \
  --generate-notes
```

If the release page already exists, verify it instead of recreating it:

```bash
gh release view "$VERSION" --repo augur-os/augur-os
```

### 5. Verify release state

Check that the tag exists and the target repo reflects the merged release:

```bash
gh api repos/augur-os/augur-os/tags --jq '.[0].name'
gh release view "$VERSION" --repo augur-os/augur-os
```

### 6. Report

Print summary:

```
Release complete:
  Version:      {VERSION}
  Repo:         https://github.com/augur-os/augur-os
  PR:           https://github.com/augur-os/augur-os/pulls
  Release:      https://github.com/augur-os/augur-os/releases/tag/{VERSION}
  Install:      paste project-brain/capabilities/skills/onboard/install.md into any supported AI agent
```

## Architecture

| Component | Location |
|-----------|----------|
| Release engine | `scripts/release.sh` |
| Release scope config | `config/system/release_scope.yaml` |
| Docs-only tree builder | `scripts/build_public_release_tree.py` |
| Public tree guard | `scripts/guard_public_release_tree.py` |
| Public push guard | `scripts/guard_public_push.py` |
| Release pruning | `scripts/prepare_release_workspace.py` |
| Release matrix | `docs/generated/skill-release-matrix.json` |
| Install prompt | `project-brain/capabilities/skills/onboard/install.md` |
| Private repo (source) | current private checkout |
| Public repo (target) | `augur-os/augur-os` |
