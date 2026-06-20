import sys
from pathlib import Path

import pytest

# Make src/scripts/ importable for dashboard modules that do bare imports like
# `from workflow_runner import RunState, Stage` (e.g. apps/dashboard/scripts/skill-scripts/
# import_stages/*.py, import_workflow.py). In production runtime these resolve via a
# bootstrap that adds src/scripts/ to sys.path; under pytest we have to add it here.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SRC_SCRIPTS = _PROJECT_ROOT / "src" / "scripts"
if _SRC_SCRIPTS.is_dir() and str(_SRC_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SRC_SCRIPTS))


@pytest.fixture
def client():
    """Provide an httpx AsyncClient for API route tests.

    These tests require a running dashboard API server. Skip when unavailable.
    """
    pytest.skip("API route tests require a running dashboard server")
