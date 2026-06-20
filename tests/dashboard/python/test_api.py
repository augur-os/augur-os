"""API route tests for mcp-app-factory"""

import pytest
from httpx import AsyncClient


class TestApiRoutes:
    """Test API routes."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/api/factory/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["plugin"] == "mcp-app-factory"

    @pytest.mark.asyncio
    async def test_plugins_endpoint(self, client: AsyncClient):
        """Test plugins list endpoint."""
        response = await client.get("/api/factory/plugins")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "plugins" in data

    @pytest.mark.asyncio
    async def test_templates_list_endpoint(self, client: AsyncClient):
        """Test templates list endpoint."""
        response = await client.get("/api/factory/templates")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "templates" in data

    @pytest.mark.asyncio
    async def test_templates_content_endpoint(self, client: AsyncClient):
        """Test template content endpoint."""
        response = await client.get("/api/factory/templates?name=dashboard.yaml.template")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "content" in data

    @pytest.mark.asyncio
    async def test_audit_endpoint(self, client: AsyncClient):
        """Test audit endpoint."""
        response = await client.get("/api/factory/audit")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "summary" in data
        assert "audits" in data
