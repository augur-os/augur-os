from __future__ import annotations

import html
from collections.abc import Callable
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

from mcp.server.auth.provider import ProviderTokenVerifier
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic.networks import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response

from .oauth_provider import AugurOAuthProvider

_oauth_consent_route_registered = False


def register_oauth_consent_route(
    mcp: FastMCP,
    get_provider: Callable[[], AugurOAuthProvider | None],
) -> None:
    global _oauth_consent_route_registered
    if _oauth_consent_route_registered:
        return
    _oauth_consent_route_registered = True

    @mcp.custom_route("/oauth/consent", methods=["GET", "POST"], include_in_schema=False)
    async def oauth_consent(request: Request) -> Response:
        oauth_provider = get_provider()
        if oauth_provider is None:
            return PlainTextResponse("OAuth is not configured on this server.", status_code=404)

        request_id = request.query_params.get("request_id")
        if not request_id:
            return PlainTextResponse("Missing request_id.", status_code=400)

        pending = oauth_provider.get_pending(request_id)
        if pending is None:
            return PlainTextResponse("Authorization request not found (expired or already handled).", status_code=400)

        client = await oauth_provider.get_client(pending.client_id)
        client_name = getattr(client, "client_name", None) if client else None

        if request.method == "GET":
            scopes = pending.scopes or []
            scopes_display = ", ".join(scopes) if scopes else "(none)"

            title = "Authorize Augur MCP"
            html_body = f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{html.escape(title)}</title>
    <style>
      body {{ font-family: -apple-system, system-ui, sans-serif; padding: 24px; max-width: 720px; margin: 0 auto; }}
      .card {{ border: 1px solid #ddd; border-radius: 12px; padding: 16px; }}
      .row {{ margin: 8px 0; }}
      code {{ background: #f6f6f6; padding: 2px 6px; border-radius: 6px; }}
      button {{ padding: 10px 14px; border-radius: 10px; border: 1px solid #ccc; cursor: pointer; }}
      button.primary {{ background: #111; color: #fff; border-color: #111; }}
      button.danger {{ background: #fff; color: #111; }}
      .buttons {{ display: flex; gap: 10px; margin-top: 16px; }}
    </style>
  </head>
  <body>
    <h1>{html.escape(title)}</h1>
    <div class="card">
      <div class="row"><strong>Client</strong>: {html.escape(client_name or '(unknown)')}</div>
      <div class="row"><strong>Client ID</strong>: <code>{html.escape(pending.client_id)}</code></div>
      <div class="row"><strong>Redirect URI</strong>: <code>{html.escape(pending.redirect_uri)}</code></div>
      <div class="row"><strong>Scopes</strong>: <code>{html.escape(scopes_display)}</code></div>
      <form method="post">
        <input type="hidden" name="request_id" value="{html.escape(request_id)}" />
        <div class="buttons">
          <button class="primary" type="submit" name="decision" value="approve">Authorize</button>
          <button class="danger" type="submit" name="decision" value="deny">Deny</button>
        </div>
      </form>
    </div>
    <p style="margin-top: 16px; color: #555;">
      Only authorize clients you trust. This MCP server can execute actions on your machine.
    </p>
  </body>
</html>"""
            return HTMLResponse(html_body, headers={"Cache-Control": "no-store"})

        form = await request.form()
        decision = str(form.get("decision") or "")
        posted_request_id = str(form.get("request_id") or request_id)
        if posted_request_id != request_id:
            return PlainTextResponse("Mismatched request_id.", status_code=400)

        if decision == "approve":
            redirect_url = oauth_provider.approve(request_id)
        else:
            redirect_url = oauth_provider.deny(request_id)

        if not redirect_url:
            return PlainTextResponse(
                "Authorization request not found (expired or already handled).",
                status_code=400,
            )

        return RedirectResponse(url=redirect_url, status_code=302, headers={"Cache-Control": "no-store"})


def configure_transport_security_for_public_url(mcp: FastMCP, public_url: str) -> None:
    """
    FastMCP auto-enables DNS rebinding protection for localhost. When exposing the
    server via a tunnel (ngrok/cloudflared) the Host header will be the public
    domain, so we need to allow that host explicitly.
    """
    parsed = urlparse(public_url)
    if not parsed.hostname:
        return

    security = mcp.settings.transport_security
    if security is None:
        return
    if not security.enable_dns_rebinding_protection:
        return

    _add_allowed_host(security, parsed.hostname, parsed.port)
    _add_allowed_origin(security, parsed.scheme, parsed.hostname, parsed.port)


def enable_oauth(
    mcp: FastMCP,
    *,
    storage_dir: Path,
    issuer_url: str,
    resource_url: str,
    auto_approve: bool,
) -> AugurOAuthProvider:
    auth_settings = AuthSettings(
        issuer_url=cast(AnyHttpUrl, issuer_url),
        resource_server_url=cast(AnyHttpUrl, resource_url),
        client_registration_options=ClientRegistrationOptions(enabled=True),
    )

    oauth_provider = AugurOAuthProvider(
        storage_dir=storage_dir,
        issuer_url=issuer_url,
        consent_url="/oauth/consent",
        auto_approve=auto_approve,
    )

    mcp.settings.auth = auth_settings
    mcp._auth_server_provider = oauth_provider
    mcp._token_verifier = ProviderTokenVerifier(oauth_provider)

    configure_transport_security_for_public_url(mcp, issuer_url)
    return oauth_provider


def _add_allowed_host(security: TransportSecuritySettings, host: str, port: int | None) -> None:
    allowed_hosts = set(security.allowed_hosts or [])
    allowed_hosts.add(host)
    allowed_hosts.add(f"{host}:*")
    if port is not None:
        allowed_hosts.add(f"{host}:{port}")
    security.allowed_hosts = sorted(allowed_hosts)


def _add_allowed_origin(security: TransportSecuritySettings, scheme: str, host: str, port: int | None) -> None:
    allowed_origins = set(security.allowed_origins or [])
    allowed_origins.add(f"{scheme}://{host}")
    allowed_origins.add(f"{scheme}://{host}:*")
    if port is not None:
        allowed_origins.add(f"{scheme}://{host}:{port}")
    security.allowed_origins = sorted(allowed_origins)
