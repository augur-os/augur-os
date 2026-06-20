"""Auto-generated importability test for repo_hygiene."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_repo_hygiene_importable():
    """Verify that repo_hygiene can be imported without errors."""
    import src.lib.repo_hygiene

    assert src.lib.repo_hygiene is not None


def test_repo_local_playwright_logs_are_not_canonical():
    """Playwright MCP console logs are disposable collateral, not repo layout."""
    from src.lib.repo_hygiene import is_allowed_root_item

    assert is_allowed_root_item(".playwright-mcp") is False


def test_shared_vault_is_canonical_repo_root():
    """Tracked shared skill sources must never be treated as root pollution."""
    from src.lib.repo_hygiene import is_allowed_root_item

    assert is_allowed_root_item("shared-vault") is True


def test_run_heal_helper_is_not_kept_at_repo_root():
    """Ad hoc heal helpers belong under scripts/, not repo root."""
    assert not (PROJECT_ROOT / "run_heal.py").exists()
    assert (PROJECT_ROOT / "scripts" / "run_heal.py").exists()
