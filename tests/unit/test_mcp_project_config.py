from __future__ import annotations

import json
from pathlib import Path

from src.cli_config.manifest import ServerEntry


def test_generate_project_mcp_json_writes_only_project_scoped_servers(
    tmp_path: Path,
) -> None:
    from src.lib.mcp_project_config import generate_project_mcp_json

    servers = [
        ServerEntry(
            id="augur-core",
            description="project",
            command="python",
            args=["-m", "augur_core"],
            cwd_required=True,
            env={"PYTHONPATH": "${AUGUR_ROOT}"},
            scope="project",
        ),
        ServerEntry(
            id="augur-vault",
            description="global",
            command="python",
            args=["-m", "augur_shared.bundle_server", "vault"],
            scope="global",
        ),
    ]

    target = generate_project_mcp_json(servers, tmp_path / ".mcp.json")

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert set(payload["mcpServers"]) == {"augur-core"}
    entry = payload["mcpServers"]["augur-core"]
    from src.config.paths import get_project_root

    root = str(get_project_root())
    # Fully resolved output: Copilot CLI performs no ${VAR} expansion, and
    # Claude only expands variables present in the session environment.
    assert "${AUGUR_ROOT}" not in target.read_text(encoding="utf-8")
    assert entry["args"] == ["-m", "augur_core"]
    assert entry["cwd"] == root
    assert entry["env"]["PYTHONPATH"] == root
    assert entry["env"]["AUGUR_ROOT"] == root
    assert entry["command"].endswith("python3") or entry["command"] == "python"
