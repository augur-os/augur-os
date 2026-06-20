from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


EXPECTED_IGNORED_SYNC_OUTPUTS: set[str] = {
    "CLAUDE.md",
    "CODEX.md",
    "AGENTS.md",
    ".claude/mcp.json",
    ".claude/agents",
    ".claude/commands",
    ".clinerules/augur-rules.md",
    ".cursorrules",
    ".cursor/agents",
    ".cursor/mcp.json",
    ".cursor/memory",
    ".windsurfrules",
    ".windsurf/rules",
    ".windsurf/skills",
    ".windsurf/mcp.json",
    ".github/instructions",
    ".github/copilot",
    ".github/copilot-memory.md",
    ".opencode/AGENTS.md",
    ".opencode/skills",
    ".antigravity",
    ".codex/config.toml",
    ".codex/agents",
    ".codex/plugins/cache/augur-local",
    ".codex/prompts",
    ".codex/skills",
    "plugins/augur",
    ".agents/plugins/marketplace.json",
    "build/cowork",
    "build/codex",
    "build/gemini",
}


@pytest.fixture
def repo_local_sync_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUGUR_SYNC_PROJECT_ROOT", str(PROJECT_ROOT))
    monkeypatch.setenv("AUGUR_SYNC_REPO_LOCAL_ONLY", "1")


def _get_repo_local_adapters():
    for module_name in list(sys.modules):
        if module_name == "skills.ai.scripts.sync_agents" or module_name.startswith(
            "skills.ai.scripts.sync_agents."
        ):
            sys.modules.pop(module_name)

    from skills.ai.scripts.sync_agents.engine import _get_all_adapters

    return _get_all_adapters()


def _repo_local_managed_paths() -> set[str]:
    """Return repo-local adapter outputs relative to the project root."""
    managed_paths: set[str] = set()
    for adapter in _get_repo_local_adapters():
        for raw_path in adapter.get_managed_files():
            path = Path(raw_path)
            if path.is_absolute():
                try:
                    path = path.resolve().relative_to(PROJECT_ROOT)
                except ValueError:
                    continue
            managed_paths.add(str(path).rstrip("/"))
    return managed_paths


def _is_git_ignored(path: str) -> bool:
    return (
        subprocess.run(
            ["git", "check-ignore", "-q", "--", path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        == 0
    )


def test_repo_local_sync_outputs_are_gitignored(repo_local_sync_env: None) -> None:
    repo_local_managed_paths = _repo_local_managed_paths()

    assert EXPECTED_IGNORED_SYNC_OUTPUTS <= repo_local_managed_paths
    missing = sorted(path for path in EXPECTED_IGNORED_SYNC_OUTPUTS if not _is_git_ignored(path))

    assert not missing, f"Expected git to ignore repo-local sync outputs: {missing}"

    assert not _is_git_ignored(".cursor/rules/augur.mdc")
    assert _is_git_ignored(".cursor/rules/other-generated-rule.md")


def test_import_does_not_mutate_sync_root_environment() -> None:
    # Load this test module by file path so the test works regardless of where
    # the file lives in the repo (originally tests/scripts/, now
    # project-brain/capabilities/skills/ai/augur/tests/ per ADR-762). Using importlib's
    # spec_from_file_location avoids the brittle dotted-module-path lookup
    # that broke on the move.
    self_path = str(Path(__file__).resolve())
    script = f"""
import importlib.util
import os
os.environ.pop("AUGUR_SYNC_PROJECT_ROOT", None)
os.environ.pop("AUGUR_SYNC_REPO_LOCAL_ONLY", None)
spec = importlib.util.spec_from_file_location("_sync_output_policy_under_test", {self_path!r})
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(os.environ.get("AUGUR_SYNC_PROJECT_ROOT"))
print(os.environ.get("AUGUR_SYNC_REPO_LOCAL_ONLY"))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.splitlines() == ["None", "None"]
