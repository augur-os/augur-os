from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def load_audit_paths_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "audit_paths",
        ROOT / ".github" / "scripts" / "audit_paths.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT_PATHS = load_audit_paths_module()


def test_iter_repo_files_respects_gitignore(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / ".gitignore").write_text("ignored.json\n", encoding="utf-8")
    tracked = tmp_path / "tracked.py"
    tracked.write_text("print('tracked')\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore", "tracked.py"], cwd=tmp_path, check=True)
    untracked = tmp_path / "untracked.py"
    untracked.write_text("print('untracked')\n", encoding="utf-8")
    ignored = tmp_path / "ignored.json"
    ignored.write_text('{"path": "/Users/example/local"}\n', encoding="utf-8")

    rel_paths = {path.relative_to(tmp_path).as_posix() for path in AUDIT_PATHS._iter_repo_files(tmp_path)}

    assert rel_paths == {".gitignore", "tracked.py", "untracked.py"}
