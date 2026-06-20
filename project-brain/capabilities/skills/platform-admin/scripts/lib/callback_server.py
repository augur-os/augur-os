"""
OAuth Callback Server — Temporary localhost HTTP server for OAuth callbacks.

Spins up a short-lived server on localhost to receive the OAuth callback,
extract the authorization code, and shut down. Binds to 127.0.0.1 only
for security.
"""

from __future__ import annotations

import http.server
import socket
import threading
from urllib.parse import parse_qs, urlparse

# =============================================================================
# Constants
# =============================================================================

_DEFAULT_PORT = 18492
_PORT_RANGE = range(18492, 18501)
_CALLBACK_PATH = "/callback"
_TIMEOUT_SECONDS = 300  # 5 minutes

_SUCCESS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Augur — Authentication Successful</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      background: #0a0a0f;
      color: #e2e8f0;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }
    .card {
      background: #1a1a2e;
      border: 1px solid #2d2d44;
      border-radius: 16px;
      padding: 48px;
      text-align: center;
      max-width: 420px;
    }
    .icon { font-size: 48px; margin-bottom: 16px; }
    h1 { font-size: 20px; margin-bottom: 8px; color: #8b5cf6; }
    p { font-size: 14px; color: #94a3b8; line-height: 1.6; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">&#10003;</div>
    <h1>Authentication Successful</h1>
    <p>You can close this tab and return to the terminal.</p>
  </div>
</body>
</html>"""

_ERROR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Augur — Authentication Failed</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
      background: #0a0a0f;
      color: #e2e8f0;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }
    .card {
      background: #1a1a2e;
      border: 1px solid #2d2d44;
      border-radius: 16px;
      padding: 48px;
      text-align: center;
      max-width: 420px;
    }
    .icon { font-size: 48px; margin-bottom: 16px; }
    h1 { font-size: 20px; margin-bottom: 8px; color: #ef4444; }
    p { font-size: 14px; color: #94a3b8; line-height: 1.6; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">&#10007;</div>
    <h1>Authentication Failed</h1>
    <p>{error}</p>
    <p style="margin-top: 12px;">Please close this tab and try again in the terminal.</p>
  </div>
</body>
</html>"""


# =============================================================================
# Callback Handler
# =============================================================================


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that captures the OAuth callback parameters."""

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path != _CALLBACK_PATH:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        params = parse_qs(parsed.query)

        # Check for OAuth error from provider
        error = params.get("error", [None])[0]
        if error:
            error_desc = params.get("error_description", [error])[0]
            server: OAuthCallbackServer = self.server  # type: ignore[assignment]
            server.error = error_desc
            server.received.set()

            html = _ERROR_HTML.replace("{error}", str(error_desc))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        # Extract code and state
        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]

        server = self.server  # type: ignore[assignment]
        server.code = code
        server.state = state
        server.received.set()

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(_SUCCESS_HTML.encode("utf-8"))

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default logging to keep terminal clean."""


# =============================================================================
# Callback Server
# =============================================================================


class OAuthCallbackServer(http.server.HTTPServer):
    """
    Temporary localhost HTTP server for OAuth callbacks.

    Usage:
        server = OAuthCallbackServer()
        callback_url = server.start()
        # ... open browser with auth URL ...
        code, state = server.wait_for_callback()
        server.stop()
    """

    code: str | None = None
    state: str | None = None
    error: str | None = None

    def __init__(self, port: int | None = None) -> None:
        self.received = threading.Event()
        self._thread: threading.Thread | None = None

        actual_port = port or _find_available_port()
        super().__init__(("127.0.0.1", actual_port), _CallbackHandler)

    @property
    def callback_url(self) -> str:
        """The full callback URL to pass to the OAuth provider."""
        _, port = self.server_address
        return f"http://localhost:{port}{_CALLBACK_PATH}"

    def start(self) -> str:
        """
        Start the server in a daemon thread.

        Returns the callback URL.
        """
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()
        return self.callback_url

    def wait_for_callback(self, timeout: int = _TIMEOUT_SECONDS) -> tuple[str | None, str | None]:
        """
        Block until the callback is received or timeout.

        Returns (code, state) or raises TimeoutError.
        """
        received = self.received.wait(timeout=timeout)
        if not received:
            raise TimeoutError(f"OAuth callback not received within {timeout} seconds. " "Please try again.")
        if self.error:
            raise RuntimeError(f"OAuth provider returned error: {self.error}")
        return self.code, self.state

    def stop(self) -> None:
        """Shut down the server."""
        self.shutdown()
        if self._thread:
            self._thread.join(timeout=5)


# =============================================================================
# Helpers
# =============================================================================


def _find_available_port() -> int:
    """Find an available port in the expected range."""
    for port in _PORT_RANGE:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError(
        f"No available port found in range {_PORT_RANGE.start}-{_PORT_RANGE.stop - 1}. "
        "Close other applications and try again."
    )
