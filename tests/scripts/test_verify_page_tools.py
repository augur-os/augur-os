from __future__ import annotations

import importlib.util
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_verify_page_tools_module():
    script_path = PROJECT_ROOT / "scripts" / "verify-page-tools.py"
    spec = importlib.util.spec_from_file_location("verify_page_tools", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verify_page_tools_launches_canonical_split_servers_only():
    module = _load_verify_page_tools_module()

    entries = module._load_probe_server_entries(PROJECT_ROOT)
    launches = {entry.id: module._build_server_launch(PROJECT_ROOT, entry) for entry in entries}
    rendered = json.dumps(launches, sort_keys=True)

    assert "augur-core" in launches
    assert "augur-framework" in launches
    assert launches["augur-core"]["args"] == ["-m", "augur_core"]
    assert launches["augur-framework"]["args"] == ["-m", "augur_framework"]
    assert "augur_mcp" not in rendered
    assert "--no-lock" not in rendered
