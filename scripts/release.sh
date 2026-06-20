#!/bin/bash
#
# Release script: push current code to augur-os/augur-os with clean history
#
# Usage:
#   ./scripts/release.sh [--dry-run]
#
# What it does:
#   1. Adds augur-os remote if not present
#   2. Reads release scope from config/system/release_scope.yaml
#   3. Builds a docs-only temp public tree or prepares the mvp release workspace
#   4. Creates a single release commit on top of augur-os history
#   5. Pushes a public release branch
#   6. Opens a pull request against augur-os/main
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

AUGUR_OS_REMOTE="https://github.com/augur-os/augur-os.git"
REMOTE_NAME="augur-os"
DRY_RUN=false
RELEASE_SCOPE_CONFIG="${AUGUR_RELEASE_SCOPE_CONFIG:-config/system/release_scope.yaml}"

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
    shift
done

if [ "$DRY_RUN" = true ]; then
    echo "=== DRY RUN - no push will happen ==="
fi

# Colors
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

step() { echo -e "\n${BOLD}${CYAN}▶ $1${NC}"; }
ok() { echo -e "${GREEN}✓ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }

read_release_scope() {
    python3 - "$RELEASE_SCOPE_CONFIG" <<'PY'
import sys
from pathlib import Path
from scripts.build_public_release_tree import load_release_scope

print(load_release_scope(Path(sys.argv[1])))
PY
}

setup_remote() {
    step "Setting up augur-os remote"

    if ! git remote | grep -q "^${REMOTE_NAME}$"; then
        git remote add "$REMOTE_NAME" "$AUGUR_OS_REMOTE"
        ok "Added remote: $REMOTE_NAME -> $AUGUR_OS_REMOTE"
    else
        ok "Remote $REMOTE_NAME already exists"
    fi

    git fetch "$REMOTE_NAME" +refs/heads/main:refs/remotes/"$REMOTE_NAME"/main 2>/dev/null
    ok "Fetched augur-os state"
}

determine_next_version() {
    step "Determining next version"

    LATEST_TAG=$(
        git ls-remote --tags "$REMOTE_NAME" 'refs/tags/v[0-9]*' 2>/dev/null \
            | awk '{print $2}' \
            | sed 's|refs/tags/||; s|\^{}||' \
            | sort -uV \
            | tail -1
    )

    if [ -z "$LATEST_TAG" ]; then
        NEXT_VERSION="v1.1.0"
        echo "  No previous tags found. Starting at $NEXT_VERSION"
    else
        echo "  Latest tag: $LATEST_TAG"
        MAJOR=$(echo "$LATEST_TAG" | sed 's/v//' | cut -d. -f1)
        MINOR=$(echo "$LATEST_TAG" | sed 's/v//' | cut -d. -f2)
        NEXT_MINOR=$((MINOR + 1))
        NEXT_VERSION="v${MAJOR}.${NEXT_MINOR}.0"
    fi

    ok "Next version: $NEXT_VERSION"
}

release_scope=$(read_release_scope)
case "$release_scope" in
    docs_only|mvp|full) ;;
    *)
        echo "Unsupported release scope: $release_scope" >&2
        exit 1
        ;;
esac

echo "Release scope: $release_scope"

setup_remote
determine_next_version
RELEASE_BRANCH="release/$NEXT_VERSION"

cleanup_mvp_workspace() {
    if [ -n "${MVP_WORKTREE_DIR:-}" ] && [ -d "$MVP_WORKTREE_DIR" ]; then
        git worktree remove --force "$MVP_WORKTREE_DIR" 2>/dev/null || rm -rf "$MVP_WORKTREE_DIR"
    fi
    if [ -n "${RELEASE_VAULT_DIR:-}" ] && [ -d "$RELEASE_VAULT_DIR" ]; then
        rm -rf "$RELEASE_VAULT_DIR"
    fi
    if [ -n "${RELEASE_DOCUMENTS_DIR:-}" ] && [ -d "$RELEASE_DOCUMENTS_DIR" ]; then
        rm -rf "$RELEASE_DOCUMENTS_DIR"
    fi
}

if [ "$release_scope" = "docs_only" ] || [ "$release_scope" = "full" ]; then
    PUBLIC_TREE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/augur-release-tree.XXXXXX")
    trap 'rm -rf "$PUBLIC_TREE_DIR"' EXIT

    step "Building ${release_scope} public tree"
    python3 scripts/build_public_release_tree.py \
        --config "$RELEASE_SCOPE_CONFIG" \
        --source-root "$PROJECT_ROOT" \
        --output-root "$PUBLIC_TREE_DIR"

    step "Guarding public release tree"
    AUGUR_RELEASE_SCOPE_CONFIG="$RELEASE_SCOPE_CONFIG" python3 scripts/guard_public_release_tree.py --root "$PUBLIC_TREE_DIR" --source-root "$PROJECT_ROOT"
    ok "Public release guard passed"

    step "Preparing isolated public release repo"
    git -C "$PUBLIC_TREE_DIR" init -q
    git -C "$PUBLIC_TREE_DIR" config user.name "Augur Release Bot"
    git -C "$PUBLIC_TREE_DIR" config user.email "release@augur.run"
    git -C "$PUBLIC_TREE_DIR" remote add "$REMOTE_NAME" "$AUGUR_OS_REMOTE"
    git -C "$PUBLIC_TREE_DIR" fetch "$REMOTE_NAME" --tags

    PARENT=$(git -C "$PUBLIC_TREE_DIR" rev-parse "$REMOTE_NAME/main")
    git -C "$PUBLIC_TREE_DIR" add -A
    TREE=$(git -C "$PUBLIC_TREE_DIR" write-tree)
    COMMIT_MSG="Release ${NEXT_VERSION} - ${release_scope} public tree"
    SQUASH_COMMIT=$(git -C "$PUBLIC_TREE_DIR" commit-tree "$TREE" -p "$PARENT" -m "$COMMIT_MSG")

    ok "Created ${release_scope} release commit: ${SQUASH_COMMIT:0:8}"
    ok "Prepared release branch: $RELEASE_BRANCH"

    if [ "$DRY_RUN" = true ]; then
        echo ""
        echo -e "${BOLD}${YELLOW}=== DRY RUN COMPLETE ===${NC}"
        echo "  Would push commit ${SQUASH_COMMIT:0:8} to $REMOTE_NAME/$RELEASE_BRANCH"
        echo "  Would open a pull request against $REMOTE_NAME/main"
        echo "  Release scope: $release_scope"
        echo ""
        echo "  To execute for real: ./scripts/release.sh"
    else
        step "Pushing ${release_scope} release branch"
        git -C "$PUBLIC_TREE_DIR" push "$REMOTE_NAME" "$SQUASH_COMMIT:refs/heads/$RELEASE_BRANCH"
        ok "Pushed to $REMOTE_NAME/$RELEASE_BRANCH"

        step "Opening public release pull request"
        gh pr create \
            --repo augur-os/augur-os \
            --base main \
            --head "$RELEASE_BRANCH" \
            --title "Release $NEXT_VERSION" \
            --body "Generated ${release_scope} public release from the private Augur source tree."
        ok "Opened pull request for $RELEASE_BRANCH"

        echo ""
        echo -e "${BOLD}${GREEN}=== RELEASE PR READY ===${NC}"
        echo "  Version: $NEXT_VERSION"
        echo "  Commit:  ${SQUASH_COMMIT:0:8}"
        echo "  Branch:  $RELEASE_BRANCH"
        echo "  Remote:  $AUGUR_OS_REMOTE"
        echo "  Scope:   $release_scope"
        echo ""
        echo "  Review:  https://github.com/augur-os/augur-os/pulls"
    fi

    exit 0
fi

RELEASE_TARGET="mvp"
MVP_WORKTREE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/augur-mvp-release.XXXXXX")
rm -rf "$MVP_WORKTREE_DIR"
trap cleanup_mvp_workspace EXIT

step "Creating isolated MVP release workspace"

git worktree add --detach "$MVP_WORKTREE_DIR" HEAD >/dev/null
ok "Prepared release workspace: $MVP_WORKTREE_DIR"
RELEASE_VAULT_DIR=$(mktemp -d "${TMPDIR:-/tmp}/augur-release-vault.XXXXXX")
RELEASE_DOCUMENTS_DIR=$(mktemp -d "${TMPDIR:-/tmp}/augur-release-documents.XXXXXX")

step "Sanitizing private paths for open source"

cat > "$MVP_WORKTREE_DIR/project.yaml" << 'YAML'
name: Augur
port: 3000

paths:
  vault: ~/Vault/Augur
  documents: ~/Documents/Augur
YAML
ok "Sanitized project.yaml"

cat > "$MVP_WORKTREE_DIR/config/system/vault.yaml" << 'YAML'
vault:
  path: ~/Vault/Augur
  git:
    auto_commit: true
    auto_push: false
    remote: origin
    branch: main
  remote: ""
YAML
ok "Sanitized config/system/vault.yaml"

step "Pruning skills for ${RELEASE_TARGET}"

(cd "$MVP_WORKTREE_DIR" && AUGUR_ROOT="$MVP_WORKTREE_DIR" AUGUR_VAULT="$RELEASE_VAULT_DIR" AUGUR_DOCUMENTS="$RELEASE_DOCUMENTS_DIR" python3 scripts/prepare_release_workspace.py --release-target "$RELEASE_TARGET")
(cd "$MVP_WORKTREE_DIR" && AUGUR_ROOT="$MVP_WORKTREE_DIR" AUGUR_VAULT="$RELEASE_VAULT_DIR" AUGUR_DOCUMENTS="$RELEASE_DOCUMENTS_DIR" python3 scripts/generate-skill-manifest.py)
(cd "$MVP_WORKTREE_DIR" && AUGUR_ROOT="$MVP_WORKTREE_DIR" AUGUR_VAULT="$RELEASE_VAULT_DIR" AUGUR_DOCUMENTS="$RELEASE_DOCUMENTS_DIR" python3 scripts/generate-launch-skill-inventory.py)
(cd "$MVP_WORKTREE_DIR" && AUGUR_ROOT="$MVP_WORKTREE_DIR" AUGUR_VAULT="$RELEASE_VAULT_DIR" AUGUR_DOCUMENTS="$RELEASE_DOCUMENTS_DIR" python3 scripts/generate-skill-release-matrix.py)
ok "Regenerated release artifacts for ${RELEASE_TARGET}"

step "Guarding MVP release workspace"
python3 scripts/guard_public_release_tree.py --root "$MVP_WORKTREE_DIR"
ok "Public release guard passed"

step "Freezing release branch tree"

git -C "$MVP_WORKTREE_DIR" add -A
ok "Release branch tree staged for ${RELEASE_TARGET}"

step "Squashing onto augur-os/main"

TREE=$(git -C "$MVP_WORKTREE_DIR" write-tree)
PARENT=$(git rev-parse "$REMOTE_NAME/main")

COMMIT_MSG="Release ${NEXT_VERSION} - staged Augur OS release

Features:
- Staged skill release pruning via x-augur-release
- Full-system onboarding flow for supported agent platforms
- Generated release matrix and release-aware manifests
- Dependency-closed release workspace preparation
- Dashboard mount/build gated to enabled skills only"

SQUASH_COMMIT=$(git commit-tree "$TREE" -p "$PARENT" -m "$COMMIT_MSG")
ok "Created squash commit: ${SQUASH_COMMIT:0:8}"

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo -e "${BOLD}${YELLOW}=== DRY RUN COMPLETE ===${NC}"
    echo "  Would push commit ${SQUASH_COMMIT:0:8} to $REMOTE_NAME/$RELEASE_BRANCH"
    echo "  Would open a pull request against $REMOTE_NAME/main"
    echo "  Release scope: $release_scope"
    echo ""
    echo "  To execute for real: ./scripts/release.sh"
else
    step "Pushing release branch to augur-os/augur-os"

    git push "$REMOTE_NAME" "$SQUASH_COMMIT:refs/heads/$RELEASE_BRANCH"
    ok "Pushed to $REMOTE_NAME/$RELEASE_BRANCH"

    step "Opening public release pull request"
    gh pr create \
        --repo augur-os/augur-os \
        --base main \
        --head "$RELEASE_BRANCH" \
        --title "Release $NEXT_VERSION" \
        --body "Generated staged public release from the private Augur source tree."
    ok "Opened pull request for $RELEASE_BRANCH"

    echo ""
    echo -e "${BOLD}${GREEN}=== RELEASE PR READY ===${NC}"
    echo "  Version: $NEXT_VERSION"
    echo "  Commit:  ${SQUASH_COMMIT:0:8}"
    echo "  Branch:  $RELEASE_BRANCH"
    echo "  Remote:  $AUGUR_OS_REMOTE"
    echo "  Scope:   $release_scope"
    echo ""
    echo "  Review:  https://github.com/augur-os/augur-os/pulls"

    cleanup_mvp_workspace
fi
