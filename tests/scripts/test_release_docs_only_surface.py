from pathlib import Path

from src.config.paths import get_skill_root


def test_release_script_uses_release_scope_and_docs_only_tree():
    text = Path("scripts/release.sh").read_text(encoding="utf-8")

    assert "config/system/release_scope.yaml" in text
    assert "scripts/build_public_release_tree.py" in text
    assert "scripts/prepare_release_workspace.py" in text
    assert "read_release_scope" in text
    assert "docs_only" in text
    assert "mvp" in text
    assert "scripts/guard_public_release_tree.py" in text
    assert text.index("scripts/build_public_release_tree.py") < text.index("scripts/guard_public_release_tree.py")
    assert "git fetch \"$REMOTE_NAME\" --tags" not in text
    assert "git worktree add --detach" in text
    assert "git tag -d" not in text
    assert "git tag -a" not in text
    assert "To execute for real: ./scripts/release.sh --dry-run" not in text


def test_release_script_uses_public_pr_instead_of_direct_main_push():
    text = Path("scripts/release.sh").read_text(encoding="utf-8")

    assert "RELEASE_BRANCH=\"release/$NEXT_VERSION\"" in text
    assert "gh pr create" in text
    assert "$SQUASH_COMMIT:refs/heads/$RELEASE_BRANCH" in text
    assert "$SQUASH_COMMIT:refs/heads/main" not in text
    assert "git -C \"$PUBLIC_TREE_DIR\" push \"$REMOTE_NAME\" \"$NEXT_VERSION\"" not in text


def test_release_command_docs_describe_scope_aware_publish():
    text = (get_skill_root("platform-admin") / "commands/release.md").read_text(encoding="utf-8")

    assert "release scope" in text
    assert "config/system/release_scope.yaml" in text
    assert "docs_only" in text
    assert "mvp" in text
    assert "To execute for real: ./scripts/release.sh --dry-run" not in text
    assert "scripts/build_public_release_tree.py" in text
    assert "scripts/guard_public_release_tree.py" in text
    assert "scripts/prepare_release_workspace.py" in text
    assert "--release-target" not in text
    assert "release branch" in text
    assert "pull request" in text


def test_ci_tests_run_public_release_guard():
    text = Path(".github/workflows/ci-tests.yml").read_text(encoding="utf-8")

    assert "public-release-guard:" in text
    assert "scripts/build_public_release_tree.py" in text
    assert "scripts/guard_public_release_tree.py" in text
