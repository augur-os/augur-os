"""Auto-generated importability test for memory_consolidation."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_memory_consolidation_importable():
    """Verify that memory_consolidation can be imported without errors."""
    mod = importlib.import_module("skills.daemon.scripts.ops.memory_consolidation")
    assert mod is not None


def test_find_memory_dir_uses_central_claude_path_helper(monkeypatch, tmp_path):
    mod = importlib.import_module("skills.daemon.scripts.ops.memory_consolidation")
    memory_dir = tmp_path / "home" / ".claude" / "projects" / "C--Users-tester-Projects-Augur" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")

    calls = []

    def fake_native_dir(project_root):
        calls.append(project_root)
        return memory_dir

    monkeypatch.setattr(mod, "get_claude_native_memory_dir", fake_native_dir)

    result = mod._find_memory_dir(Path(r"C:\Users\tester\Projects\Augur"))

    assert result == memory_dir
    assert calls == [Path(r"C:\Users\tester\Projects\Augur")]


def test_find_memory_dir_uses_linked_client_memory_plan(monkeypatch, tmp_path):
    mod = importlib.import_module("skills.daemon.scripts.ops.memory_consolidation")
    memory_dir = tmp_path / "cursor" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")

    def fake_plan(*, project_root):
        return {
            "sources": {},
            "outputs": [
                {
                    "client": "cursor",
                    "kind": "linked_index",
                    "dir": memory_dir,
                }
            ],
        }

    monkeypatch.setattr(mod, "resolve_default_client_memory_plan", fake_plan, raising=False)
    monkeypatch.setattr(mod, "get_claude_native_memory_dir", lambda project_root: None)

    result = mod._find_memory_dir(Path(r"C:\Users\tester\Projects\Augur"))

    assert result == memory_dir
