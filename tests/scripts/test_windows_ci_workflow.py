from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/ci-cross-platform.yml")


def test_cross_platform_windows_checks_are_pr_reachable() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "pull_request:" in text
    assert "scripts/windows-one-click-bootstrap.ps1" in text
    assert "project-brain/capabilities/skills/daemon/**" in text
    assert "project-brain/capabilities/skills/onboard/**" in text
    assert "src/config/**" in text
    assert "src/lib/**" in text
    assert "apps/dashboard/app/api/cli/**" in text
    assert "apps/dashboard/lib/paths.ts" in text
    assert "Verify Windows one-click bootstrap contract" in text
    assert "Verify Windows one-click orchestrator unit tests" in text
    assert "Verify Windows dashboard path handling" in text


def test_cross_platform_windows_steps_use_activated_pytest() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "skills/observe/augur/tests/test_daemon_status_runtime.py" not in text
    assert "uv run" not in text
