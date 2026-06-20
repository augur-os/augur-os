"""MCP tool tests for the dashboard skill-scripts MCP package.

Originally authored for the standalone mcp-app-factory plugin; the impl
functions now live at apps/dashboard/scripts/skill-scripts/mcp/__init__.py
(merged from mcp-app-factory, frontend, and page-builder skills). The plugin's
standalone templates/ directory and plugin-spec.yaml were intentionally
removed in the merge, so the original template/spec/migrate tests were
vestigial and have been dropped.
"""

import sys
from pathlib import Path

import pytest

# This test sits at tests/dashboard/python/test_mcp.py so parents[3] is the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
MCP_DIR = PROJECT_ROOT / "apps" / "dashboard" / "scripts" / "skill-scripts" / "mcp"

sys.path.insert(0, str(PROJECT_ROOT))
# Deliberately NOT adding MCP_DIR.parent (apps/dashboard/scripts/skill-scripts/)
# to sys.path: that directory contains a `scoring/` package which would shadow
# project-brain/capabilities/skills/ai/scripts/ops/agent_digest/scoring.py for any subsequent
# test that does `from scoring import ...`. importlib.spec_from_file_location
# below doesn't need it.

# Import implementation functions from the mcp package via importlib because the
# parent directory has hyphens ("skill-scripts") and is not a Python package.
import importlib.util  # noqa: E402

_mcp_init = MCP_DIR / "__init__.py"
_spec = importlib.util.spec_from_file_location(
    "dashboard_skill_scripts_mcp",
    _mcp_init,
    submodule_search_locations=[str(MCP_DIR)],
)
_module = importlib.util.module_from_spec(_spec)
sys.modules["dashboard_skill_scripts_mcp"] = _module  # register before exec for relative imports
_spec.loader.exec_module(_module)

audit_plugin_impl = _module.audit_plugin_impl


class TestMcpTools:
    """Smoke tests for the merged dashboard skill-scripts MCP surface."""

    def test_audit_plugin_all(self, monkeypatch):
        """audit_plugin_impl() with no args audits all discovered plugins.

        The impl internally does `sys.path.insert(0, PLUGIN_ROOT / 'scripts')` then
        `from audit import ...`. PLUGIN_ROOT computes to apps/dashboard/scripts/, so
        the impl's expected import path is apps/dashboard/scripts/scripts/ which does
        not exist in the merged layout. We add apps/dashboard/scripts/skill-scripts/
        (the real location of audit.py) via monkeypatch so pytest auto-cleans it up
        after this test — without polluting sys.path globally and shadowing
        project-brain/capabilities/skills/ai/scripts/ops/agent_digest/scoring.py for downstream tests.
        """
        monkeypatch.syspath_prepend(str(MCP_DIR.parent))
        result = audit_plugin_impl()
        assert result["success"] is True
        assert "summary" in result
        assert "plugins" in result

        # discover_plugins() scans the assembled bundle at plugins/augur/skills/**
        # (gitignored build output) plus external client skill dirs (~/.codex,
        # ~/.claude, ~/.cowork). A fresh / partition-export checkout that has not
        # assembled the bundle and has no client skills installed legitimately
        # discovers zero plugins, so skip rather than hard-fail. When the bundle
        # IS assembled the audit returns real plugins and the assertion holds.
        if result["summary"]["total"] == 0:
            pytest.skip(
                "no assembled plugin bundle present in this checkout (plugins/augur/skills/** is gitignored build output)"
            )
        assert result["summary"]["total"] > 0
