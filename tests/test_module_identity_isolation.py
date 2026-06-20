from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_MCP = (PROJECT_ROOT / "src" / "mcp").resolve()


def test_root_test_process_does_not_put_repo_src_mcp_on_sys_path() -> None:
    resolved_entries = [(entry, Path(os.path.realpath(os.path.abspath(os.fspath(entry or "."))))) for entry in sys.path]
    resolved_sys_path = {resolved for _, resolved in resolved_entries}

    assert SRC_MCP not in resolved_sys_path, (
        "Root tests must not put repo src/mcp directly on sys.path; repo tests "
        "should import MCP modules through canonical src.mcp.* paths.\n"
        + "\n".join(f"{entry!r} -> {resolved}" for entry, resolved in resolved_entries)
    )
