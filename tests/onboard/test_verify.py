from pathlib import Path

from src.lib.onboard.result import OnboardContext
from src.lib.onboard.verify import VerifyProbes, verify


def _probes(dashboard=True, mcp=True, query="real answer"):
    return VerifyProbes(
        dashboard_interactive=lambda ctx: dashboard,
        mcp_connected=lambda ctx: mcp,
        sample_query=lambda ctx: query,
    )


def test_verify_ok_when_all_pass(tmp_path: Path):
    r = verify(OnboardContext(repo_root=tmp_path), probes=_probes())
    assert r.status == "ok"


def test_verify_fail_when_dashboard_down(tmp_path: Path):
    r = verify(OnboardContext(repo_root=tmp_path), probes=_probes(dashboard=False))
    assert r.status == "fail"
    assert "dashboard" in r.message.lower()


def test_verify_fail_when_query_empty(tmp_path: Path):
    r = verify(OnboardContext(repo_root=tmp_path), probes=_probes(query=""))
    assert r.status == "fail"
    assert "query" in r.message.lower()
