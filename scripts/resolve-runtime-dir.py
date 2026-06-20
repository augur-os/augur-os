#!/usr/bin/env python3
"""Print the canonical Augur state/runtime directory."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_runtime_dir() -> Path:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        from src.config.paths import get_runtime_dir

        return Path(get_runtime_dir())
    except Exception:
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "Augur" / "state"
        return Path(os.environ.get("XDG_STATE_HOME", "~/.local/state")).expanduser() / "augur"


if __name__ == "__main__":
    print(resolve_runtime_dir())
