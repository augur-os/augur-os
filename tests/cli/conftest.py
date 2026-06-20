"""Pytest fixtures for CLI tests."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"

# Remove src dir from path if present (it shadows standard 'logging')
sys.path = [p for p in sys.path if Path(p).resolve() != SRC_DIR]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
