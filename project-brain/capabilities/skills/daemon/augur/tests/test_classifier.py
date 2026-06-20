"""Auto-generated importability test for classifier."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_classifier_importable():
    """Verify that classifier can be imported without errors."""
    import importlib
    mod = importlib.import_module("self_heal.classifier")
    assert mod is not None


def test_mcp_runtime_python_missing_is_high_severity_shell_fix():
    """Missing generated MCP Python runtime should be an immediate deterministic repair."""
    from types import SimpleNamespace

    from self_heal.classifier import match_shell_action, pre_classify

    entry = SimpleNamespace(
        message="mcp_runtime:project_python_missing -- No such file or directory: .venv/bin/python3",
        stack_trace=None,
        file="runtime-prereq:mcp-python",
    )

    hint = pre_classify(entry)
    shell_action = match_shell_action(entry)

    assert hint is not None
    assert hint["severity"] == "high"
    assert hint["category"] == "infrastructure"
    assert shell_action is not None
    assert shell_action[0] == ["uv", "sync"]
