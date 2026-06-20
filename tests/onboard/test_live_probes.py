import json
from pathlib import Path

import src.lib.onboard.live_probes as lp
from src.lib.onboard.result import OnboardContext


class _FakeResp:
    def __init__(self, status=200, body=b""):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _ctx(tmp_path: Path) -> OnboardContext:
    return OnboardContext(repo_root=tmp_path)


# --- _dashboard_interactive -------------------------------------------------


def test_dashboard_interactive_true_on_200_with_next_marker(monkeypatch, tmp_path: Path):
    body = b'<html><body><div id="__next"></div></body></html>'
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeResp(200, body))
    assert lp._dashboard_interactive(_ctx(tmp_path)) is True


def test_dashboard_interactive_false_without_marker(monkeypatch, tmp_path: Path):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeResp(200, b"<html></html>"))
    assert lp._dashboard_interactive(_ctx(tmp_path)) is False


def test_dashboard_interactive_false_on_exception(monkeypatch, tmp_path: Path):
    def boom(*a, **k):
        raise OSError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    assert lp._dashboard_interactive(_ctx(tmp_path)) is False


# --- _mcp_connected ---------------------------------------------------------


def test_mcp_connected_posts_health_tool(monkeypatch, tmp_path: Path):
    seen = {}

    def fake_open(req, *a, **k):
        seen["url"] = req.full_url
        seen["data"] = json.loads(req.data.decode())
        return _FakeResp(200, b"{}")

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    assert lp._mcp_connected(_ctx(tmp_path)) is True
    assert seen["url"].endswith("/api/mcp/tool")
    assert seen["data"]["tool"] == "health"


def test_mcp_connected_false_on_exception(monkeypatch, tmp_path: Path):
    def boom(*a, **k):
        raise OSError("down")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    assert lp._mcp_connected(_ctx(tmp_path)) is False


# --- _sample_query ----------------------------------------------------------


def test_sample_query_posts_capabilities_tool_and_returns_body(monkeypatch, tmp_path: Path):
    seen = {}

    def fake_open(req, *a, **k):
        seen["data"] = json.loads(req.data.decode())
        return _FakeResp(200, b'{"capabilities": ["x"]}')

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    out = lp._sample_query(_ctx(tmp_path))
    assert seen["data"]["tool"] == "augur-list-capabilities"
    assert "capabilities" in out


def test_sample_query_empty_on_exception(monkeypatch, tmp_path: Path):
    def boom(*a, **k):
        raise OSError("down")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    assert lp._sample_query(_ctx(tmp_path)) == ""


# --- live_probes wiring -----------------------------------------------------


def test_live_probes_wires_all_three(tmp_path: Path):
    probes = lp.live_probes(_ctx(tmp_path))
    assert probes.dashboard_interactive is lp._dashboard_interactive
    assert probes.mcp_connected is lp._mcp_connected
    assert probes.sample_query is lp._sample_query
