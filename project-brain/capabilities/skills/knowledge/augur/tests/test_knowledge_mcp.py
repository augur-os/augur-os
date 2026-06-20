"""
Knowledge MCP Tool Contract Tests (CLI-based tools).

Tests summarize and nano-pdf CLI wrapper contracts.
Does NOT test memory or RAG tools (those have separate test coverage).

Run with: pytest skills/knowledge/tests/test_knowledge_mcp.py -v
"""

import pytest
from unittest.mock import patch

from src.mcp.augur_shared.cli_bridge import CLIBridge  # noqa: E402

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def summarize_bridge():
    """Create a mocked summarize CLIBridge."""
    bridge = CLIBridge("summarize", install_hint="brew install steipete/tap/summarize")
    with patch.object(bridge, "is_installed", return_value=True), patch.object(bridge, "run") as mock_run:
        yield bridge, mock_run


@pytest.fixture
def nanopdf_bridge():
    """Create a mocked nano-pdf CLIBridge."""
    bridge = CLIBridge("nano-pdf", install_hint="brew install nano-pdf")
    with patch.object(bridge, "is_installed", return_value=True), patch.object(bridge, "run") as mock_run:
        yield bridge, mock_run


# =============================================================================
# Contract Tests: Summarize
# =============================================================================


@pytest.mark.contract
class TestSummarizeContract:
    def test_summarize_url(self, summarize_bridge):
        bridge, mock_run = summarize_bridge
        mock_run.return_value = {
            "stdout": "Summary: Article discusses AI trends in 2026...",
            "stderr": "",
            "returncode": 0,
        }
        result = bridge.run_or_error(["https://example.com/article"], timeout=60)
        assert result
        mock_run.assert_called_with(["https://example.com/article"], timeout=60)

    def test_summarize_youtube(self, summarize_bridge):
        bridge, mock_run = summarize_bridge
        mock_run.return_value = {
            "stdout": "Video Summary: Introduction to machine learning...",
            "stderr": "",
            "returncode": 0,
        }
        result = bridge.run_or_error(["https://youtube.com/watch?v=abc123"], timeout=120)
        assert result

    def test_summarize_podcast(self, summarize_bridge):
        bridge, mock_run = summarize_bridge
        mock_run.return_value = {
            "stdout": "Podcast Summary: Discussion about tech startups...",
            "stderr": "",
            "returncode": 0,
        }
        result = bridge.run_or_error(["https://podcast.example.com/ep1"], timeout=180)
        assert result

    def test_summarize_file(self, summarize_bridge):
        bridge, mock_run = summarize_bridge
        mock_run.return_value = {
            "stdout": "File Summary: Quarterly report highlights...",
            "stderr": "",
            "returncode": 0,
        }
        result = bridge.run_or_error(["/tmp/report.pdf"], timeout=120)
        assert result

    def test_summarize_error(self, summarize_bridge):
        bridge, mock_run = summarize_bridge
        mock_run.return_value = {"stdout": "", "stderr": "Failed to fetch URL", "returncode": 1}
        result = bridge.run_or_error(["https://invalid.url"])
        assert "failed" in result.lower() or "error" in result.lower()

    def test_not_installed(self):
        bridge = CLIBridge("summarize", install_hint="brew install steipete/tap/summarize")
        with patch.object(bridge, "is_installed", return_value=False):
            result = bridge.run(["https://example.com"])
            assert "error" in result
            assert "not installed" in result["error"]


# =============================================================================
# Contract Tests: nano-pdf
# =============================================================================


@pytest.mark.contract
class TestPdfContract:
    def test_edit_pdf(self, nanopdf_bridge):
        bridge, mock_run = nanopdf_bridge
        mock_run.return_value = {
            "stdout": "PDF edited successfully. Output: /tmp/report_edited.pdf",
            "stderr": "",
            "returncode": 0,
        }
        result = bridge.run_or_error(["/tmp/report.pdf", "--instruction", "Remove page 3"], timeout=120)
        assert result
        mock_run.assert_called_with(
            ["/tmp/report.pdf", "--instruction", "Remove page 3"],
            timeout=120,
        )

    def test_edit_pdf_complex_instruction(self, nanopdf_bridge):
        bridge, mock_run = nanopdf_bridge
        mock_run.return_value = {"stdout": "PDF edited", "stderr": "", "returncode": 0}
        bridge.run_or_error(
            ["/tmp/contract.pdf", "--instruction", "Add watermark 'DRAFT' to all pages"],
            timeout=120,
        )
        # Verify instruction is passed as-is
        call_args = mock_run.call_args[0][0]
        assert "--instruction" in call_args
        assert "Add watermark" in call_args[call_args.index("--instruction") + 1]

    def test_edit_pdf_file_not_found(self, nanopdf_bridge):
        bridge, mock_run = nanopdf_bridge
        mock_run.return_value = {"stdout": "", "stderr": "File not found: /tmp/missing.pdf", "returncode": 1}
        result = bridge.run_or_error(["/tmp/missing.pdf", "--instruction", "test"])
        assert "not found" in result.lower()

    def test_not_installed(self):
        bridge = CLIBridge("nano-pdf", install_hint="brew install nano-pdf")
        with patch.object(bridge, "is_installed", return_value=False):
            result = bridge.run(["/tmp/file.pdf", "--instruction", "test"])
            assert "error" in result
            assert "not installed" in result["error"]
