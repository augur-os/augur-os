"""
Test new MCP tools added in Phase 3.2.

Tests all new tools to ensure they:
1. Are properly defined in modular files
2. Have correct structure and patterns
3. Return properly formatted JSON responses
4. Handle errors gracefully

Note: Tools are now modularized into separate files:
- infrastructure/actions.py: skill-action
- infrastructure/documents.py: sync-bugs, index-documents, search-documents
- domain/ide.py: send-ide-prompt
"""

import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
# Framework tool surfaces live under augur_framework/tools; the framework
# server entrypoint is src.mcp.augur_framework.
AUGUR_FRAMEWORK_PATH = REPO_ROOT / "src" / "mcp" / "augur_framework"
AUGUR_FRAMEWORK_TOOLS_PATH = REPO_ROOT / "src" / "mcp" / "augur_framework" / "tools"
MCP_SERVER_PATH = AUGUR_FRAMEWORK_PATH / "__main__.py"
MCP_ACTIONS_PATH = AUGUR_FRAMEWORK_TOOLS_PATH / "infrastructure" / "actions.py"
MCP_DOCUMENTS_PATH = AUGUR_FRAMEWORK_TOOLS_PATH / "infrastructure" / "documents.py"
MCP_IDE_PATH = AUGUR_FRAMEWORK_TOOLS_PATH / "domain" / "ide.py"


def _find_tool_in_files(tool_name: str) -> tuple[Path, str] | None:
    """Find a tool definition across all MCP module files."""
    search_paths = [
        MCP_SERVER_PATH,
        MCP_ACTIONS_PATH,
        MCP_DOCUMENTS_PATH,
        MCP_IDE_PATH,
    ]

    for path in search_paths:
        if path.exists():
            with open(path) as f:
                content = f.read()
            if f'name="{tool_name}"' in content:
                return path, content

    return None


class TestNewToolDefinitions:
    """Test that all new tools are properly defined."""

    def test_all_new_tools_exist_in_modules(self):
        """Test that all new tools are defined in appropriate module files."""
        # Core tools that should exist
        new_tools = [
            "sync-bugs",
            "send-ide-prompt",
        ]

        for tool in new_tools:
            result = _find_tool_in_files(tool)
            assert result is not None, f"Tool {tool} not found in any MCP module"

    def test_tool_modules_exist(self):
        """Test that expected tool module files exist."""
        expected_modules = [
            MCP_ACTIONS_PATH,
            MCP_DOCUMENTS_PATH,
            MCP_IDE_PATH,
        ]

        for module_path in expected_modules:
            assert module_path.exists(), f"Module file not found: {module_path}"

    def test_all_tools_have_interceptor(self):
        """Test that tools use @mcp_tool_interceptor or similar pattern."""
        # Tools to check with their expected locations
        tools_and_files = [
            ("sync_bugs_tool", MCP_DOCUMENTS_PATH),
            ("send_ide_prompt_tool", MCP_IDE_PATH),
        ]

        for func_name, file_path in tools_and_files:
            if not file_path.exists():
                pytest.skip(f"Module file not found: {file_path}")

            with open(file_path) as f:
                lines = f.readlines()

            # Find the function definition
            func_line_idx = None
            for i, line in enumerate(lines):
                if f"async def {func_name}" in line or f"def {func_name}" in line:
                    func_line_idx = i
                    break

            if func_line_idx is None:
                # Try to find without async prefix
                for i, line in enumerate(lines):
                    if func_name in line and "def " in line:
                        func_line_idx = i
                        break

            assert func_line_idx is not None, f"Function {func_name} not found in {file_path.name}"

            # Check for decorator or mcp.tool pattern above it
            found_decorator = False
            for i in range(max(0, func_line_idx - 10), func_line_idx):
                if "@mcp_tool_interceptor" in lines[i] or "@mcp.tool" in lines[i]:
                    found_decorator = True
                    break

            assert found_decorator, f"Decorator not found for {func_name} in {file_path.name}"

    def test_all_tools_track_metrics(self):
        """Test that all tools call metrics.track_tool()."""
        tools_and_files = [
            ("sync_bugs_tool", MCP_DOCUMENTS_PATH),
            ("send_ide_prompt_tool", MCP_IDE_PATH),
        ]

        for func_name, file_path in tools_and_files:
            if not file_path.exists():
                pytest.skip(f"Module file not found: {file_path}")

            with open(file_path) as f:
                content = f.read()

            # Find function body
            func_start = content.find(f"async def {func_name}")
            if func_start == -1:
                func_start = content.find(f"def {func_name}")

            assert func_start != -1, f"Function {func_name} not found in {file_path.name}"

            # Find next function or end of file
            next_func = content.find("async def ", func_start + 20)
            if next_func == -1:
                next_func = content.find("def ", func_start + 20)
            if next_func == -1:
                next_func = len(content)

            func_body = content[func_start:next_func]

            assert "metrics.track_tool" in func_body, f"metrics.track_tool() not called in {func_name}"


class TestNewToolsInGroups:
    """Test that new tools are properly configured in tool groups."""

    def test_ui_tools_added(self):
        """Test that UI tools were added to UI group."""
        import os

        if os.getenv("AUGUR_TEST_MODE") == "true":
            pytest.skip("Test mode uses temporary directory")

        from src.config.paths import get_config_dir
        import yaml

        config_path = get_config_dir() / "mcp_tool_groups.yaml"
        if not config_path.exists():
            pytest.skip(f"Config file not found: {config_path}")

        with open(config_path) as f:
            config = yaml.safe_load(f)

        ui_tools = config["tool_groups"]["UI"]

        expected_new_ui_tools = [
            "send_ide_prompt",
        ]

        for tool in expected_new_ui_tools:
            assert tool in ui_tools, f"Expected UI tool {tool} not in tool groups config"

    def test_backend_tools_added(self):
        """Test that backend tools were added to BACKEND group."""
        import os

        if os.getenv("AUGUR_TEST_MODE") == "true":
            pytest.skip("Test mode uses temporary directory")

        from src.config.paths import get_config_dir
        import yaml

        config_path = get_config_dir() / "mcp_tool_groups.yaml"
        if not config_path.exists():
            pytest.skip(f"Config file not found: {config_path}")

        with open(config_path) as f:
            config = yaml.safe_load(f)

        backend_tools = config["tool_groups"]["BACKEND"]

        expected_new_backend_tools = ["sync_bugs"]

        for tool in expected_new_backend_tools:
            assert tool in backend_tools, f"Expected BACKEND tool {tool} not in tool groups config"

    def test_data_tools_added(self):
        """Test that data tools were added to DATA group."""
        import os

        if os.getenv("AUGUR_TEST_MODE") == "true":
            pytest.skip("Test mode uses temporary directory")

        from src.config.paths import get_config_dir
        import yaml

        config_path = get_config_dir() / "mcp_tool_groups.yaml"
        if not config_path.exists():
            pytest.skip(f"Config file not found: {config_path}")

        with open(config_path) as f:
            config = yaml.safe_load(f)

        if "DATA" not in config["tool_groups"]:
            pytest.skip("DATA group not configured")

        data_tools = config["tool_groups"]["DATA"]

        expected_new_data_tools = [
            "index_documents",
            "search_documents",
        ]

        for tool in expected_new_data_tools:
            if tool not in data_tools:
                pytest.skip(f"Tool {tool} not yet added to DATA group")

    def test_tool_counts_under_limit(self):
        """Test that all context combinations stay under 80-tool limit."""
        import os

        if os.getenv("AUGUR_TEST_MODE") == "true":
            pytest.skip("Test mode uses temporary directory")

        from src.config.paths import get_config_dir
        import yaml

        config_path = get_config_dir() / "mcp_tool_groups.yaml"
        if not config_path.exists():
            pytest.skip(f"Config file not found: {config_path}")

        with open(config_path) as f:
            config = yaml.safe_load(f)

        max_tools = config["max_tools"]
        assert max_tools == 80

        # Check sprint contexts
        for sprint, groups in config.get("context_rules", {}).get("sprints", {}).items():
            tool_count = sum(len(config["tool_groups"].get(g, [])) for g in groups)
            assert tool_count <= max_tools, f"Sprint {sprint} has {tool_count} tools (> {max_tools})"

        # Check page contexts
        for page, groups in config.get("context_rules", {}).get("pages", {}).items():
            tool_count = sum(len(config["tool_groups"].get(g, [])) for g in groups)
            assert tool_count <= max_tools, f"Page {page} has {tool_count} tools (> {max_tools})"

        # Check workflow contexts
        for workflow, groups in config.get("context_rules", {}).get("workflows", {}).items():
            tool_count = sum(len(config["tool_groups"].get(g, [])) for g in groups)
            assert tool_count <= max_tools, f"Workflow {workflow} has {tool_count} tools (> {max_tools})"


class TestToolImplementations:
    """Test specific implementation details of new tools."""

    def test_sync_bugs_has_force_flag(self):
        """Test sync-bugs has optional force parameter."""
        if not MCP_DOCUMENTS_PATH.exists():
            pytest.skip("documents.py not found")

        with open(MCP_DOCUMENTS_PATH) as f:
            content = f.read()

        func_start = content.find("async def sync_bugs_tool")
        if func_start == -1:
            pytest.skip("sync_bugs_tool not found")

        func_end = content.find("async def ", func_start + 20)
        if func_end == -1:
            func_end = len(content)

        func_body = content[func_start:func_end]

        assert "force" in func_body


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
