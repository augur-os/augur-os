from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
ARCHITECTURE = (ROOT / "docs" / "architecture-overview.md").read_text(encoding="utf-8")


def test_readme_positions_augur_os_as_harness_not_wrapper() -> None:
    assert "Augur OS is the open-source local second-brain harness" in README
    assert "AI clients are the reasoning engines" in README
    assert "Augur is not an LLM wrapper" in README
    assert "does not require an Augur API key" in README
    assert "Claude, Codex, Gemini, Cursor, and Ollama" in README


def test_architecture_names_local_mcp_as_the_harness_boundary() -> None:
    assert "AI clients are the reasoning engines" in ARCHITECTURE
    assert "Augur is the local harness" in ARCHITECTURE
    assert "local MCP" in ARCHITECTURE
    assert "not an LLM wrapper" in ARCHITECTURE
