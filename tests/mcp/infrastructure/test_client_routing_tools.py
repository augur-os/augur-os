"""Tests for client routing MCP tools."""

import json
import pytest
from src.mcp.augur_framework.tools.infrastructure.local_backends import (
    resolve_client_impl,
    set_client_override_impl,
    list_available_clients_impl,
    ResolveClientInput,
    SetClientOverrideInput,
)


class TestResolveClientTool:
    @pytest.mark.asyncio
    async def test_returns_resolved_client(self):
        result = await resolve_client_impl(ResolveClientInput(action_id="test-action"))
        data = json.loads(result)
        assert "client_id" in data
        assert "source" in data


class TestSetClientOverrideTool:
    @pytest.mark.asyncio
    async def test_set_override(self):
        params = SetClientOverrideInput(action_id="test-action", client_id="codex")
        result = await set_client_override_impl(params)
        data = json.loads(result)
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_clear_override(self):
        params = SetClientOverrideInput(action_id="test-action", clear=True)
        result = await set_client_override_impl(params)
        data = json.loads(result)
        assert "success" in data

    @pytest.mark.asyncio
    async def test_set_requires_client_id(self):
        params = SetClientOverrideInput(action_id="test-action")
        result = await set_client_override_impl(params)
        data = json.loads(result)
        assert data["success"] is False
        assert "client_id required" in data["error"]


class TestListAvailableClientsTool:
    @pytest.mark.asyncio
    async def test_returns_clients_list(self):
        result = await list_available_clients_impl()
        data = json.loads(result)
        assert "clients" in data
        assert isinstance(data["clients"], list)

    @pytest.mark.asyncio
    async def test_always_includes_ollama(self):
        result = await list_available_clients_impl()
        data = json.loads(result)
        client_ids = [c["client_id"] for c in data["clients"]]
        assert "ollama" in client_ids

    @pytest.mark.asyncio
    async def test_count_matches_list(self):
        result = await list_available_clients_impl()
        data = json.loads(result)
        assert data["count"] == len(data["clients"])
