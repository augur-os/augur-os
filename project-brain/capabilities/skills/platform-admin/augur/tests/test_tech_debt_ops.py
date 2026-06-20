"""Tests for tech_debt_ops scanner — focus on long-function detection contract."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "ops"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load_module():
    import importlib

    return importlib.import_module("tech_debt_ops")


def test_tech_debt_ops_importable():
    """Verify that tech_debt_ops can be imported without errors."""
    mod = _load_module()
    assert mod is not None


def test_count_function_lines_stops_at_sibling_method(tmp_path):
    """Nested method should NOT bleed into the next sibling method's body.

    Regression: previously `_count_function_lines` used `line.rstrip()` for the
    prefix check, so `    def next_method(...)` did not match `startswith("def ")`
    and the counter ran to end-of-class, inflating function lengths by hundreds
    of lines.
    """
    mod = _load_module()
    src = (
        "class Sample:\n"
        "    def first(self):\n"
        "        x = 1\n"
        "        return x\n"
        "\n"
        "    def second(self):\n"
        "        return 2\n"
    )
    lines = src.splitlines()
    # `first` is at index 1 (0-indexed), with 4-space indent.
    count = mod._count_function_lines(lines, 1, "    ", "py")
    # Body: def line + 2 statements + 1 blank = 4. Must NOT continue into
    # `def second`. Anything > 4 means the sibling break check is broken.
    assert count <= 4, f"expected <=4, got {count} (sibling-method break failed)"


def test_count_function_lines_handles_decorated_sibling(tmp_path):
    """A decorator at the same indent ends the current function."""
    mod = _load_module()
    src = (
        "class Sample:\n"
        "    def first(self):\n"
        "        return 1\n"
        "\n"
        "    @staticmethod\n"
        "    def second():\n"
        "        return 2\n"
    )
    lines = src.splitlines()
    count = mod._count_function_lines(lines, 1, "    ", "py")
    # Should stop at the @staticmethod decorator at indent 4.
    assert count <= 3, f"expected <=3, got {count} (decorator break failed)"


def test_count_function_lines_truly_long_function():
    """A genuinely long function should still be detected as long."""
    mod = _load_module()
    body = "        x = 1\n" * 100
    src = (
        "class Sample:\n"
        "    def big(self):\n"
        f"{body}"
    )
    lines = src.splitlines()
    count = mod._count_function_lines(lines, 1, "    ", "py")
    assert count > mod.LONG_FUNC_THRESHOLD


def test_find_long_functions_does_not_double_count(tmp_path):
    """Real bug repro: a small class of small methods must report 0 long funcs."""
    mod = _load_module()
    src = "class Sample:\n"
    for i in range(20):
        src += f"    def method_{i}(self):\n"
        src += "        return None\n\n"

    fp = tmp_path / "sample.py"
    fp.write_text(src)
    hits = mod._find_long_functions(fp, tmp_path)
    assert hits == [], f"expected 0 long functions, got {len(hits)}: {hits}"
