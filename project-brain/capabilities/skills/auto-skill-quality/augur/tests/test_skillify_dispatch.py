import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "optimizer" / "dispatch.py"
spec = importlib.util.spec_from_file_location("dispatch", SCRIPT)
dispatch = importlib.util.module_from_spec(spec)
sys.modules["dispatch"] = dispatch
spec.loader.exec_module(dispatch)


def test_existing_skill_arg_routes_to_optimize():
    assert dispatch.resolve_mode("file-manager-augur", skill_exists_fn=lambda n: True) == "optimize"


def test_incident_summary_routes_to_create():
    assert dispatch.resolve_mode("login bug crashed the app", skill_exists_fn=lambda n: False) == "create"


def test_help_passthrough():
    assert dispatch.resolve_mode("--help", skill_exists_fn=lambda n: True) == "help"


def test_unknown_single_token_creates():
    assert dispatch.resolve_mode("nonexistent-skill", skill_exists_fn=lambda n: False) == "create"


def test_empty_creates():
    assert dispatch.resolve_mode("", skill_exists_fn=lambda n: True) == "create"
