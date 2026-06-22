from __future__ import annotations

import subprocess
from pathlib import Path

import sys as _sys
import pytest as _pytest

pytestmark = _pytest.mark.skipif(
    _sys.platform == "win32", reason="POSIX shell (.sh) script; Windows uses the .ps1 adapter"
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT_ROOT / "scripts" / "worktree-launch.sh"


def test_help_mentions_generic_create_cleanup_contract() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "create" in result.stdout
    assert "cleanup" in result.stdout
    assert "implement-adr" not in result.stdout
    assert "launch Claude Code" not in result.stdout


def test_help_mentions_passthrough_launch_mode() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "create -- codex" in result.stdout


def test_bootstrap_worktree_contract_uses_worktree_preflight_repair_json_output() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'bootstrap_worktree "$wt_dir"' in text
    assert "--profile worktree --repair" in text
    assert 'json.load(sys.stdin)["repairs_applied"]' in text
    assert (
        'env \\\n        AUGUR_ROOT="$wt_dir" \\\n        AUGUR_CORE="$wt_dir" \\\n        AUGUR_REPO="$wt_dir" \\\n        python3 "$PREFLIGHT_SCRIPT"'
        in text
    )


def test_worktree_bootstrap_regenerates_dashboard_runtime_artifacts() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'generate_dashboard_runtime_artifacts "$wt_dir"' in text
    assert text.index('bootstrap_worktree "$wt_dir"') < text.index('generate_dashboard_runtime_artifacts "$wt_dir"')
    assert "scripts/dist/rebuild-plugins.mjs" in text
    assert "--skip-registry" in text
    assert 'AUGUR_ROOT="$wt_dir"' in text


def test_passthrough_launch_prefers_worktree_local_cli_on_path() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'PATH="$WT_DIR/scripts:$WT_DIR/.venv/bin:$PATH"' in text


def test_worktreeinclude_comment_is_client_neutral() -> None:
    text = (PROJECT_ROOT / "worktreeinclude").read_text(encoding="utf-8")

    assert "Claude" not in text
    assert "AI client" in text or "agent" in text
