"""run reporting: a no-op fix run is surfaced as scanned-only, not silent."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
_MOD = _REPO / "project-brain" / "capabilities" / "skills" / "daemon" / "scripts" / "mcp" / "__init__.py"


def _load():
    scripts = _MOD.parent.parent
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("daemon_mcp_run_status", _MOD)
    m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m); return m


def test_no_op_run_is_flagged_scanned_only():
    m = _load()
    payload = {"success": True, "counts": {"findings": 85, "mechanical_applied": 0, "dispatched": 0, "deferred": 85, "enqueued": 31}}
    out = m._annotate_run_status(payload)
    assert out["status"] == "scanned-only"
    assert out["summary"] == {"findings": 85, "applied": 0, "dispatched": 0, "deferred": 85, "escalated": 31}
    assert "no live fix-capable" in out["message"]
    assert "--catalog-loop" in out["message"]


def test_run_that_applied_is_not_flagged():
    m = _load()
    payload = {"success": True, "counts": {"findings": 5, "mechanical_applied": 3, "dispatched": 0, "deferred": 2, "enqueued": 0}}
    out = m._annotate_run_status(payload)
    assert out.get("status") != "scanned-only"
    assert out["summary"]["applied"] == 3
