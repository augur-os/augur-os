import subprocess

import scripts.ci.fresh_env_verify as h


def test_returns_2_when_server_never_ready(monkeypatch):
    monkeypatch.setattr(h, "_probe_once", lambda url: False)
    rc = h.run(base_url="http://localhost:3000", attempts=3, delay=0, playwright=lambda: 0)
    assert rc == 2  # server-not-ready


def test_returns_playwright_code_when_server_ready(monkeypatch):
    monkeypatch.setattr(h, "_probe_once", lambda url: True)
    assert h.run(base_url="http://localhost:3000", attempts=1, delay=0, playwright=lambda: 0) == 0
    assert h.run(base_url="http://localhost:3000", attempts=1, delay=0, playwright=lambda: 1) == 1  # playwright failed


def test_default_playwright_runner_invokes_spec(monkeypatch):
    calls = {}

    def fake_run(cmd, cwd=None, **kw):
        calls["cmd"] = cmd
        calls["cwd"] = cwd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(h.subprocess, "run", fake_run)
    code = h._run_playwright()
    assert code == 0
    cmd = calls["cmd"]
    assert "playwright" in " ".join(cmd)
    # CI-only config (no webServer) must be passed so Playwright does not manage
    # the server lifecycle and collide with the workflow's backgrounded server.
    assert "--config" in cmd
    assert "playwright.fresh-env.config.ts" in cmd
    # Playwright matches the positional `test <arg>` as a REGEX against the
    # resolved ABSOLUTE path: a "../../"-prefixed value matches 0 tests. The arg
    # must be the bare filename (a form Playwright actually resolves), not a
    # path-prefixed substring.
    assert "fresh-env-browse.spec.ts" in cmd
    assert not any(arg.startswith("../") for arg in cmd)
