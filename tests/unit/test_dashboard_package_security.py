import json
from pathlib import Path


def test_dashboard_brace_expansion_override_is_patched() -> None:
    package_json = Path("apps/dashboard/package.json")
    data = json.loads(package_json.read_text(encoding="utf-8"))

    overrides = data["pnpm"]["overrides"]

    assert overrides["minimatch@3.1.5>brace-expansion"] == "1.1.13"
