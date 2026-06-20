"""Ensure project root and AI module dirs are on sys.path for imports."""
import sys
from pathlib import Path

project_root = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
ai_skill_root = project_root / "project-brain" / "capabilities" / "skills" / "ai"

# Pin the external MCP SDK before adding the AI skill scripts directory. That
# directory contains a local ``mcp`` package for AI helpers and can otherwise
# shadow the SDK during mixed-suite pytest collection.
try:
    import mcp  # noqa: F401
    import mcp.types  # noqa: F401
except ImportError:
    pass

path_candidates = [
    project_root,
    ai_skill_root / "augur",
    ai_skill_root / "augur" / "adapters",
    ai_skill_root / "scripts",
    ai_skill_root / "scripts" / "mcp",
    ai_skill_root / "scripts" / "ops",
    ai_skill_root / "scripts" / "ops" / "agent_digest",
    ai_skill_root / "scripts" / "sync_agents",
]

for candidate in path_candidates:
    path_str = str(candidate)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _protect_repo_llms_files():
    """Guard the real repo-root llms.txt / llms-full.txt during sync_agents tests.

    Several tests patch ``sync_agents.constants.PROJECT_ROOT`` but the mode
    functions read the directly-imported ``modes.PROJECT_ROOT``; a destructive
    ``purge_mode``/``clean_mode`` call therefore operates on the real repo root
    and removes the version-controlled llms files as a side effect. Snapshot and
    restore their contents so no test corrupts tracked output.
    """
    targets = [project_root / "llms.txt", project_root / "llms-full.txt"]
    saved = {p: (p.read_bytes() if p.exists() else None) for p in targets}
    try:
        yield
    finally:
        for path, content in saved.items():
            if content is None:
                continue
            if not path.exists() or path.read_bytes() != content:
                path.write_bytes(content)
