from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    OAuthClientInformationFull,
    OAuthToken,
    RefreshToken,
    construct_redirect_uri,
)
from pydantic import ValidationError
from pydantic.networks import AnyUrl

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PendingAuthorization:
    request_id: str
    created_at: float
    client_id: str
    redirect_uri: str
    redirect_uri_provided_explicitly: bool
    state: str | None
    scopes: list[str]
    code_challenge: str
    resource: str | None


class AugurOAuthProvider(OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]):
    """
    Minimal OAuth 2.0 Authorization Server for MCP clients.

    - Supports dynamic client registration (RFC 7591)
    - Supports authorization code grant + PKCE (RFC 7636)
    - Issues bearer access tokens and refresh tokens
    - Stores registered clients on disk (user data); tokens/codes are in-memory
    """

    def __init__(
        self,
        *,
        storage_dir: Path,
        issuer_url: str,
        consent_url: str,
        auto_approve: bool = False,
        client_store_filename: str = "mcp-oauth-clients.json",
        authorization_code_ttl_seconds: int = 10 * 60,
        access_token_ttl_seconds: int = 60 * 60,
        refresh_token_ttl_seconds: int | None = 30 * 24 * 60 * 60,
        max_pending_authorizations: int = 200,
    ) -> None:
        self._storage_dir = storage_dir
        self._issuer_url = issuer_url.rstrip("/")
        self._consent_url = self._absolute_url(consent_url)
        self._auto_approve = auto_approve

        self._client_store_path = self._storage_dir / client_store_filename

        self._authorization_code_ttl_seconds = authorization_code_ttl_seconds
        self._access_token_ttl_seconds = access_token_ttl_seconds
        self._refresh_token_ttl_seconds = refresh_token_ttl_seconds
        self._max_pending_authorizations = max_pending_authorizations

        self._clients: dict[str, OAuthClientInformationFull] = self._load_clients()
        self._pending: dict[str, PendingAuthorization] = {}
        self._authorization_codes: dict[str, AuthorizationCode] = {}
        self._refresh_tokens: dict[str, RefreshToken] = {}
        self._access_tokens: dict[str, AccessToken] = {}

    def _absolute_url(self, path_or_url: str) -> str:
        parsed = urlparse(path_or_url)
        if parsed.scheme and parsed.netloc:
            return path_or_url
        if not path_or_url.startswith("/"):
            path_or_url = "/" + path_or_url
        return f"{self._issuer_url}{path_or_url}"

    def _load_clients(self) -> dict[str, OAuthClientInformationFull]:
        try:
            raw = self._client_store_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except FileNotFoundError:
            return {}
        except Exception:
            return {}

        clients: dict[str, OAuthClientInformationFull] = {}
        if isinstance(data, dict):
            for client_id, value in data.items():
                try:
                    clients[str(client_id)] = OAuthClientInformationFull.model_validate(value)
                except (ValidationError, TypeError, ValueError) as error:
                    logger.warning("Skipping invalid OAuth client %s: %s", client_id, error)
                    continue
        return clients

    def _save_clients(self) -> None:
        try:
            self._client_store_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {client_id: info.model_dump(mode="json") for client_id, info in self._clients.items()}
            self._client_store_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        except OSError as exc:
            logger.warning("_save_clients failed (disk full or permission error): %s", exc)

    def _gc_pending(self) -> None:
        # Keep memory bounded; pending auths are short-lived and do not need persistence.
        if len(self._pending) <= self._max_pending_authorizations:
            return
        sorted_pending = sorted(self._pending.values(), key=lambda item: item.created_at)
        to_remove = max(0, len(sorted_pending) - self._max_pending_authorizations)
        for item in sorted_pending[:to_remove]:
            self._pending.pop(item.request_id, None)

    @staticmethod
    def _require_client_id(client: OAuthClientInformationFull) -> str:
        client_id = client.client_id
        if client_id is None:
            raise ValueError("client_id is required")
        return client_id

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self._clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        client_id = self._require_client_id(client_info)
        self._clients[client_id] = client_info
        self._save_clients()

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        client_id = self._require_client_id(client)
        scopes = params.scopes or []
        if self._auto_approve:
            return self._issue_authorization_code_redirect(
                client_id=client_id,
                redirect_uri=str(params.redirect_uri),
                redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
                state=params.state,
                scopes=scopes,
                code_challenge=params.code_challenge,
                resource=params.resource,
            )

        request_id = secrets.token_urlsafe(24)
        self._pending[request_id] = PendingAuthorization(
            request_id=request_id,
            created_at=time.time(),
            client_id=client_id,
            redirect_uri=str(params.redirect_uri),
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            state=params.state,
            scopes=scopes,
            code_challenge=params.code_challenge,
            resource=params.resource,
        )
        self._gc_pending()

        return construct_redirect_uri(self._consent_url, request_id=request_id)

    def get_pending(self, request_id: str) -> PendingAuthorization | None:
        return self._pending.get(request_id)

    def approve(self, request_id: str) -> str | None:
        pending = self._pending.pop(request_id, None)
        if pending is None:
            return None
        return self._issue_authorization_code_redirect(**pending.__dict__)

    def deny(self, request_id: str) -> str | None:
        pending = self._pending.pop(request_id, None)
        if pending is None:
            return None
        return construct_redirect_uri(
            pending.redirect_uri,
            error="access_denied",
            state=pending.state,
        )

    def _issue_authorization_code_redirect(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        redirect_uri_provided_explicitly: bool,
        state: str | None,
        scopes: list[str],
        code_challenge: str,
        resource: str | None,
        request_id: str | None = None,
        created_at: float | None = None,
        **_: Any,
    ) -> str:
        code = secrets.token_urlsafe(32)
        redirect_uri_url = cast(AnyUrl, redirect_uri)
        authorization_code = AuthorizationCode(
            code=code,
            scopes=scopes,
            expires_at=time.time() + self._authorization_code_ttl_seconds,
            client_id=client_id,
            code_challenge=code_challenge,
            redirect_uri=redirect_uri_url,
            redirect_uri_provided_explicitly=redirect_uri_provided_explicitly,
            resource=resource,
        )
        self._authorization_codes[code] = authorization_code
        return construct_redirect_uri(redirect_uri, code=code, state=state)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        client_id = self._require_client_id(client)
        code = self._authorization_codes.get(authorization_code)
        if code is None or code.client_id != client_id:
            return None
        return code

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        client_id = self._require_client_id(client)
        # One-time use: remove before issuing tokens.
        self._authorization_codes.pop(authorization_code.code, None)

        access_token_value = secrets.token_urlsafe(32)
        refresh_token_value = secrets.token_urlsafe(32)

        access_token = AccessToken(
            token=access_token_value,
            client_id=client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time()) + self._access_token_ttl_seconds,
            resource=authorization_code.resource,
        )
        refresh_token = RefreshToken(
            token=refresh_token_value,
            client_id=client_id,
            scopes=authorization_code.scopes,
            expires_at=(
                (int(time.time()) + self._refresh_token_ttl_seconds) if self._refresh_token_ttl_seconds else None
            ),
        )

        self._access_tokens[access_token_value] = access_token
        self._refresh_tokens[refresh_token_value] = refresh_token

        return OAuthToken(
            access_token=access_token_value,
            expires_in=self._access_token_ttl_seconds,
            refresh_token=refresh_token_value,
            scope=" ".join(authorization_code.scopes) if authorization_code.scopes else None,
        )

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        client_id = self._require_client_id(client)
        token = self._refresh_tokens.get(refresh_token)
        if token is None or token.client_id != client_id:
            return None
        return token

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        client_id = self._require_client_id(client)
        # Rotate refresh token.
        self._refresh_tokens.pop(refresh_token.token, None)

        access_token_value = secrets.token_urlsafe(32)
        refresh_token_value = secrets.token_urlsafe(32)

        access_token = AccessToken(
            token=access_token_value,
            client_id=client_id,
            scopes=scopes,
            expires_at=int(time.time()) + self._access_token_ttl_seconds,
        )
        new_refresh_token = RefreshToken(
            token=refresh_token_value,
            client_id=client_id,
            scopes=scopes,
            expires_at=(
                (int(time.time()) + self._refresh_token_ttl_seconds) if self._refresh_token_ttl_seconds else None
            ),
        )

        self._access_tokens[access_token_value] = access_token
        self._refresh_tokens[refresh_token_value] = new_refresh_token

        return OAuthToken(
            access_token=access_token_value,
            expires_in=self._access_token_ttl_seconds,
            refresh_token=refresh_token_value,
            scope=" ".join(scopes) if scopes else None,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        access = self._access_tokens.get(token)
        if access is None:
            return None
        if access.expires_at and access.expires_at < int(time.time()):
            self._access_tokens.pop(token, None)
            return None
        return access

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        # Best-effort revocation; we don't maintain strict one-to-one mapping between AT/RT.
        if isinstance(token, AccessToken):
            self._access_tokens.pop(token.token, None)
            return
        if isinstance(token, RefreshToken):
            self._refresh_tokens.pop(token.token, None)
            return
