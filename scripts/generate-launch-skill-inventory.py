#!/usr/bin/env python3
"""Generate docs/generated/launch-skill-inventory.json from skill discovery."""

from __future__ import annotations

import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from src.lib.generated_artifacts import write_stable_json
from src.lib.launch_skill_inventory import build_launch_skill_inventory
from src.plugins.skill_discovery import discover_all_skills


def main() -> None:
    inventory = build_launch_skill_inventory(discover_all_skills(tiers=(0,)), root)
    out_path = root / "docs" / "generated" / "launch-skill-inventory.json"
    write_stable_json(out_path, inventory, volatile_keys=["generated_at"])
    print(f"Generated {out_path}: {inventory['count']} skills")


if __name__ == "__main__":
    main()
