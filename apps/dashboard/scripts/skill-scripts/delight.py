#!/usr/bin/env python3
"""
Delight Generator
Creates a short list of delight ideas for UI improvements.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from typing import Any

from src.lib.skill_paths import get_peer_data_dir


import sys


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _load_context(raw: str | None) -> dict[str, Any]:
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
    env = os.environ.get("CHAIN_CONTEXT")
    if env:
        try:
            return json.loads(env)
        except json.JSONDecodeError:
            return {}
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate delight ideas")
    parser.add_argument("--context", help="Optional JSON context", default=None)
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    context = _load_context(args.context)
    ideas = [
        "Add subtle ambient gradient",
        "Introduce staggered load animation",
        "Highlight key actions with microcopy",
    ]

    result = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "ideas": ideas,
        "context_present": bool(context),
    }

    data_dir = get_peer_data_dir(__file__, "frontend")
    output_path = data_dir / "delight" / f"delight_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["report_path"] = str(output_path)

    if args.json:
        _out(json.dumps(result, indent=2))
    else:
        _out("Delight ideas")
        for idea in ideas:
            _out(f"- {idea}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
