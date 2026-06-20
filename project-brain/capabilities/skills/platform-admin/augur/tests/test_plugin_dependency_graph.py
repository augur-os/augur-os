"""Tests for plugin_dependency_graph.py — dependency parsing and cycle detection."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from plugin_dependency_graph import build_graph, detect_cycles, parse_dependencies


# ---------------------------------------------------------------------------
# parse_dependencies
# ---------------------------------------------------------------------------


class TestParseDependencies:
    def test_returns_empty_when_no_skill_md(self, tmp_path):
        deps = parse_dependencies(tmp_path)
        assert deps["plugins"] == []
        assert deps["mcp_servers"] == []

    def test_parses_frontmatter_dependencies(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: test-skill\n"
            "dependencies:\n"
            "  plugins:\n"
            "    - core/executor\n"
            "    - ai/knowledge\n"
            "  python:\n"
            "    - pyyaml\n"
            "---\n"
        )
        deps = parse_dependencies(tmp_path)
        assert deps["plugins"] == ["core/executor", "ai/knowledge"]
        assert deps["python"] == ["pyyaml"]

    def test_ignores_non_dict_dependencies(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: test\n"
            "dependencies: just-a-string\n"
            "---\n"
        )
        deps = parse_dependencies(tmp_path)
        assert deps["plugins"] == []


# ---------------------------------------------------------------------------
# detect_cycles
# ---------------------------------------------------------------------------


class TestDetectCycles:
    def test_no_cycles_in_dag(self):
        graph = {
            "a": ["b"],
            "b": ["c"],
            "c": [],
        }
        cycles = detect_cycles(graph)
        assert cycles == []

    def test_detects_simple_cycle(self):
        graph = {
            "a": ["b"],
            "b": ["a"],
        }
        cycles = detect_cycles(graph)
        assert len(cycles) >= 1
        # The cycle should contain both nodes
        flat = [node for cycle in cycles for node in cycle]
        assert "a" in flat
        assert "b" in flat

    def test_detects_longer_cycle(self):
        graph = {
            "a": ["b"],
            "b": ["c"],
            "c": ["a"],
        }
        cycles = detect_cycles(graph)
        assert len(cycles) >= 1

    def test_empty_graph(self):
        assert detect_cycles({}) == []


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------


class TestBuildGraph:
    def test_builds_from_plugin_structure(self, tmp_path):
        # Create a minimal plugin layout
        skill_dir = tmp_path / "plugins" / "core" / "skills" / "executor"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: executor\ndependencies:\n  plugins:\n    - ai/knowledge\n---\n"
        )

        graph = build_graph(tmp_path)
        assert "core/executor" in graph
        assert graph["core/executor"] == ["ai/knowledge"]
