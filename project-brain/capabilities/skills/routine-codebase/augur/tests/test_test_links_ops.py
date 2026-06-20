"""Tests for auto-test-links scan/fix protocol."""
from __future__ import annotations

import importlib.util
import json
import os
import socketserver
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch

from src.lib.ops_protocol import OpsContext, ScanResult, FixResult

_MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "test_links_ops.py"
_SPEC = importlib.util.spec_from_file_location("test_links_under_test", _MODULE_PATH)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


def _ctx(tmp_path: Path, **kw) -> OpsContext:
    return OpsContext(project_root=tmp_path, **kw)


def test_module_name() -> None:
    assert mod.name == "auto-test-links"


def test_scan_missing_script(tmp_path: Path) -> None:
    """scan reports broken when the scanner script is missing."""
    with patch.object(mod, "_get_script_path", return_value=tmp_path / "nonexistent.mjs"):
        result = mod.scan(_ctx(tmp_path))
    assert isinstance(result, ScanResult)
    assert result.health == "broken"
    assert len(result.issues) == 1


def test_scan_dashboard_not_reachable(tmp_path: Path) -> None:
    """scan reports degraded when dashboard is not running."""
    script = tmp_path / "script.mjs"
    script.write_text("// placeholder")
    with patch.object(mod, "_get_script_path", return_value=script):
        with patch("urllib.request.urlopen", side_effect=ConnectionError("refused")), patch.object(mod.time, "sleep"):
            result = mod.scan(_ctx(tmp_path))
    assert result.health == "degraded"


def test_scan_uses_stable_api_probe_when_root_is_cold(tmp_path: Path) -> None:
    """A transient root-page failure should not classify the dashboard as down."""
    script = tmp_path / "script.mjs"
    script.write_text("// placeholder")
    clean_report = {
        "summary": {
            "pages_scanned": 2,
            "unique_links": 3,
            "pages_unreachable": 0,
            "unique_broken": 0,
            "broken_pct": 0,
        },
        "unreachable_pages": [],
        "unique_broken_links": [],
    }

    def fake_open(url, timeout=5):
        if url.endswith("/api/settings/layout/pulse?mode=quick"):
            return object()
        raise ConnectionError("root unavailable")

    with patch.object(mod, "_get_script_path", return_value=script):
        with patch("urllib.request.urlopen", side_effect=fake_open):
            with patch.object(mod, "_run_scanner", return_value=clean_report):
                result = mod.scan(_ctx(tmp_path))

    assert result.health == "verified"


def test_dashboard_reachability_waits_through_compile_window() -> None:
    calls = {"count": 0}

    def fake_open(url, timeout=5):
        calls["count"] += 1
        if calls["count"] < 9:
            raise ConnectionError("still compiling")
        return object()

    with patch("urllib.request.urlopen", side_effect=fake_open), patch.object(mod.time, "sleep"):
        assert mod._is_dashboard_reachable("http://localhost:3000") is True


def test_dashboard_reachability_is_bounded_when_dashboard_is_down() -> None:
    calls = []

    def fake_open(url, timeout=5):
        calls.append((url, timeout))
        raise ConnectionError("refused")

    with patch("urllib.request.urlopen", side_effect=fake_open), patch.object(mod.time, "sleep") as sleep:
        assert mod._is_dashboard_reachable("http://localhost:3000") is False

    assert len(calls) == 12
    assert {timeout for _, timeout in calls} == {mod.DASHBOARD_PROBE_TIMEOUT_SECONDS}
    assert sleep.call_count == 2


def test_scan_clears_stale_report_when_clean(tmp_path: Path) -> None:
    """scan clears stale leaf reports after a clean run."""
    script = tmp_path / "script.mjs"
    script.write_text("// placeholder")
    clean_report = {
        "summary": {
            "pages_scanned": 2,
            "unique_links": 3,
            "pages_unreachable": 0,
            "unique_broken": 0,
            "broken_pct": 0,
        },
        "unreachable_pages": [],
        "unique_broken_links": [],
    }
    with patch.object(mod, "_get_script_path", return_value=script):
        with patch("urllib.request.urlopen", return_value=object()):
            with patch.object(mod, "_run_scanner", return_value=clean_report):
                with patch.object(mod, "clear_report") as clear_report:
                    result = mod.scan(_ctx(tmp_path))
    assert result.health == "verified"
    clear_report.assert_called_once_with("test-links-latest.json")


class _FallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/alpha":
            body = b'<html><body><a href="/beta">beta</a></body></html>'
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/beta":
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_HEAD(self) -> None:  # noqa: N802
        if self.path == "/beta":
            time.sleep(0.2)
            self.send_response(200)
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()


def test_fix_returns_report(tmp_path: Path) -> None:
    result = mod.fix(_ctx(tmp_path), [{"detail": "broken link", "path": "/missing"}])
    assert isinstance(result, FixResult)
    assert result.success is True
    assert result.fix_type == "report"


def test_has_difficulty_spec() -> None:
    assert hasattr(mod, "DIFFICULTY_SPEC")
    assert isinstance(mod.DIFFICULTY_SPEC, dict)


def test_collect_auto_page_routes_uses_shared_vault_skills(tmp_path: Path) -> None:
    skill_dir = tmp_path / "project-brain" / "capabilities" / "skills" / "notes"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: notes\n"
        "x-augur-hub: workspace\n"
        "x-augur-config:\n"
        "  contributions:\n"
        "    pages:\n"
        "      - id: capture\n"
        "        page_type: auto\n"
        "---\n",
        encoding="utf-8",
    )

    routes = mod._collect_auto_page_routes(tmp_path)

    assert "/workspace/notes/capture" in routes


def test_node_scanner_default_root_resolves_repo_checkout() -> None:
    """The Node scanner lives under project-brain but must discover the repo root."""
    script = Path(__file__).resolve().parents[2] / "scripts" / "check_links.mjs"
    expected_root = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
    result = subprocess.run(
        ["node", str(script), "--print-project-root"],
        check=True,
        capture_output=True,
        text=True,
        env={k: v for k, v in os.environ.items() if k != "AUTO_TEST_LINKS_PROJECT_ROOT"},
    )

    assert Path(result.stdout.strip()) == expected_root


def test_node_scanner_falls_back_to_get_after_head_timeout(tmp_path: Path) -> None:
    """The Node scanner should not flag a valid route broken just because HEAD timed out."""
    app_dir = tmp_path / "apps" / "dashboard" / "app" / "alpha"
    app_dir.mkdir(parents=True)
    (app_dir / "page.tsx").write_text("export default function Page() { return null; }")

    with socketserver.TCPServer(("127.0.0.1", 0), _FallbackHandler) as httpd:
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            script = Path(__file__).resolve().parents[2] / "scripts" / "check_links.mjs"
            result = subprocess.run(
                ["node", str(script), "--json"],
                check=True,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "AUTO_TEST_LINKS_PROJECT_ROOT": str(tmp_path),
                    "BASE_URL": f"http://127.0.0.1:{port}",
                    "REQUEST_TIMEOUT": "50",
                    "LINK_BATCH_SIZE": "1",
                },
            )
        finally:
            httpd.shutdown()
            thread.join(timeout=1)

    report = json.loads(result.stdout)
    assert report["summary"]["pages_scanned"] == 1
    assert report["summary"]["unique_broken"] == 0
