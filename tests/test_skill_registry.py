"""Lightweight contract tests for skill_registry."""

from __future__ import annotations

import ast
import sys
from dataclasses import fields
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_skill_registry_importable():
    """Verify that skill_registry can be imported without errors."""
    import src.mcp.augur_shared.interfaces.skill_registry

    assert src.mcp.augur_shared.interfaces.skill_registry is not None


def test_fallback_skill_record_declares_canonical_field_names():
    """The standalone fallback SkillRecord should mirror canonical field names."""
    from src.plugins.skill_discovery import SkillRecord as CanonicalSkillRecord

    registry_path = PROJECT_ROOT / "src" / "mcp" / "augur_shared" / "interfaces" / "skill_registry.py"
    module = ast.parse(registry_path.read_text(encoding="utf-8"))

    fallback_class: ast.ClassDef | None = None
    for node in ast.walk(module):
        if isinstance(node, ast.ClassDef) and node.name == "SkillRecord":
            fallback_class = node
            break

    assert fallback_class is not None
    fallback_fields = {
        stmt.target.id
        for stmt in fallback_class.body
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
    }
    assert fallback_fields
    canonical_fields = {field.name for field in fields(CanonicalSkillRecord)}
    assert canonical_fields <= fallback_fields


def test_fallback_skill_record_uses_container_defaults() -> None:
    """Mutable fallback collections should use default_factory semantics."""
    registry_path = PROJECT_ROOT / "src" / "mcp" / "augur_shared" / "interfaces" / "skill_registry.py"
    module = ast.parse(registry_path.read_text(encoding="utf-8"))

    fallback_class: ast.ClassDef | None = None
    for node in ast.walk(module):
        if isinstance(node, ast.ClassDef) and node.name == "SkillRecord":
            fallback_class = node
            break

    assert fallback_class is not None
    field_defaults = {
        stmt.target.id: stmt.value
        for stmt in fallback_class.body
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None
    }

    factory_fields = {
        "loop_config": "dict",
        "dependencies": "dict",
        "mcp_tools": "list",
        "dashboard_pages": "list",
        "commands": "list",
        "config": "dict",
        "upstream": "dict",
        "client_sources": "tuple",
        "file_intake": "dict",
    }
    literal_tuple_fields = {"tags", "triggers", "capabilities", "aliases"}

    for name, factory in factory_fields.items():
        value = field_defaults.get(name)
        assert isinstance(value, ast.Call), name
        assert isinstance(value.func, ast.Name) and value.func.id == "field", name
        default_factory = next(
            (keyword.value for keyword in value.keywords if keyword.arg == "default_factory"),
            None,
        )
        assert isinstance(default_factory, ast.Name) and default_factory.id == factory, name

    for name in literal_tuple_fields:
        value = field_defaults.get(name)
        assert isinstance(value, ast.Tuple), name
        assert value.elts == [], name
