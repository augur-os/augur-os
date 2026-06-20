"""
Tests for distribution platform plugin structure (ADR-437).

Verifies that Obsidian and VS Code plugins have correct file structure
and required fields in their manifest files.

Run with: pytest tests/scripts/test_platform_plugins.py -v
"""

import json


from src.config.paths import get_project_root

PROJECT_ROOT = get_project_root()
PLATFORM_PLUGINS = PROJECT_ROOT / "plugins"


class TestObsidianPlugin:
    """Verify Obsidian community plugin structure."""

    def test_manifest_exists(self):
        manifest = PLATFORM_PLUGINS / "obsidian" / "manifest.json"
        assert manifest.exists(), "Obsidian manifest.json missing"

    def test_manifest_valid_json(self):
        manifest = PLATFORM_PLUGINS / "obsidian" / "manifest.json"
        data = json.loads(manifest.read_text())
        assert "id" in data
        assert "name" in data
        assert "version" in data
        assert "minAppVersion" in data

    def test_manifest_id_is_augur(self):
        manifest = PLATFORM_PLUGINS / "obsidian" / "manifest.json"
        data = json.loads(manifest.read_text())
        assert data["id"] == "augur"

    def test_source_exists(self):
        source = PLATFORM_PLUGINS / "obsidian" / "src" / "main.ts"
        assert source.exists(), "Obsidian main.ts missing"

    def test_source_has_five_capabilities(self):
        source = PLATFORM_PLUGINS / "obsidian" / "src" / "main.ts"
        content = source.read_text()
        # Check for the 5 required capabilities
        assert "detect()" in content, "Missing Capability 1: Detect"
        assert "installAugur" in content, "Missing Capability 2: Install"
        assert "configure()" in content, "Missing Capability 3: Configure"
        assert "showStatus()" in content, "Missing Capability 4: Status"
        assert "getDashboardUrl()" in content, "Missing Capability 5: Link"

    def test_styles_exist(self):
        styles = PLATFORM_PLUGINS / "obsidian" / "styles.css"
        assert styles.exists(), "Obsidian styles.css missing"

    def test_tsconfig_exists(self):
        tsconfig = PLATFORM_PLUGINS / "obsidian" / "tsconfig.json"
        assert tsconfig.exists(), "Obsidian tsconfig.json missing"


class TestVSCodeExtension:
    """Verify VS Code extension structure."""

    def test_package_json_exists(self):
        pkg = PLATFORM_PLUGINS / "vscode" / "package.json"
        assert pkg.exists(), "VS Code package.json missing"

    def test_package_json_valid(self):
        pkg = PLATFORM_PLUGINS / "vscode" / "package.json"
        data = json.loads(pkg.read_text())
        assert data["name"] == "augur"
        assert "engines" in data
        assert "vscode" in data["engines"]

    def test_package_has_commands(self):
        pkg = PLATFORM_PLUGINS / "vscode" / "package.json"
        data = json.loads(pkg.read_text())
        commands = data.get("contributes", {}).get("commands", [])
        command_ids = [c["command"] for c in commands]
        assert "augur.status" in command_ids
        assert "augur.install" in command_ids
        assert "augur.openDashboard" in command_ids

    def test_extension_source_exists(self):
        source = PLATFORM_PLUGINS / "vscode" / "src" / "extension.ts"
        assert source.exists(), "VS Code extension.ts missing"

    def test_extension_has_five_capabilities(self):
        source = PLATFORM_PLUGINS / "vscode" / "src" / "extension.ts"
        content = source.read_text()
        assert "detect()" in content, "Missing Capability 1: Detect"
        assert "augur.install" in content, "Missing Capability 2: Install"
        assert "augur.sync" in content, "Missing Capability 3: Configure (via sync)"
        assert "augur.status" in content, "Missing Capability 4: Status"
        assert "augur.openDashboard" in content, "Missing Capability 5: Link"

    def test_tsconfig_exists(self):
        tsconfig = PLATFORM_PLUGINS / "vscode" / "tsconfig.json"
        assert tsconfig.exists(), "VS Code tsconfig.json missing"


class TestSharedHealth:
    """Verify shared health check library."""

    def test_health_library_exists(self):
        health = PLATFORM_PLUGINS / "lib" / "health.ts"
        assert health.exists(), "Shared health.ts missing"

    def test_health_exports_functions(self):
        health = PLATFORM_PLUGINS / "lib" / "health.ts"
        content = health.read_text()
        assert "detectInstalled" in content
        assert "checkMcpHealth" in content
        assert "checkDashboardHealth" in content
        assert "fullHealthCheck" in content
        assert "readLastSync" in content

    def test_readme_exists(self):
        readme = PLATFORM_PLUGINS / "README.md"
        assert readme.exists(), "Platform plugins README missing"
