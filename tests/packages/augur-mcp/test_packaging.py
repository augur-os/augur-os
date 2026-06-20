from __future__ import annotations

import ast
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = PROJECT_ROOT / "src" / "mcp" / "pyproject.toml"
TESTS_ROOT = PROJECT_ROOT / "tests"

CANONICAL_MCP_TEST_PREFIXES = ("augur_core", "augur_framework", "augur_shared")
LEGACY_SHIM_TEST_PREFIX = "augur_mcp"
TEST_CONTRACT_CALLS = {
    "import_module",
    "importorskip",
    "patch",
    "setattr",
    "delattr",
    "spec_from_file_location",
}


def _is_module_name(value: str, prefixes: tuple[str, ...]) -> bool:
    return any(value == prefix or value.startswith(f"{prefix}.") for prefix in prefixes)


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _repo_test_import_contract_violations(prefixes: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    for path in sorted(TESTS_ROOT.rglob("test_*.py")):
        if path == Path(__file__).resolve():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(PROJECT_ROOT)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_module_name(alias.name, prefixes):
                        violations.append(f"{relative}:{node.lineno} imports {alias.name!r}")
            elif isinstance(node, ast.ImportFrom) and node.module and _is_module_name(node.module, prefixes):
                violations.append(f"{relative}:{node.lineno} imports from {node.module!r}")
            elif isinstance(node, ast.Call) and node.args:
                call_name = _call_name(node.func).split(".")[-1]
                if call_name not in TEST_CONTRACT_CALLS:
                    continue
                target = node.args[0]
                if isinstance(target, ast.Constant) and isinstance(target.value, str):
                    value = target.value
                    if _is_module_name(value, prefixes):
                        violations.append(f"{relative}:{node.lineno} targets {value!r}")
    return violations


def test_augur_mcp_wheel_targets_current_namespaces() -> None:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))

    assert data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "augur_core",
        "augur_framework",
        "augur_shared",
    ]


def test_augur_mcp_console_scripts_target_existing_modules() -> None:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    scripts = data["project"]["scripts"]

    assert scripts["augur-mcp"] == "augur_framework.__main__:main"
    assert scripts["augur-core"] == "augur_core.__main__:main"
    assert scripts["augur-framework"] == "augur_framework.__main__:main"
    assert scripts["augur-wizard"] == "augur_framework.tools.wizard.cli:main"
    assert (
        data["project"]["entry-points"]["augur_mcp.registry"]["filesystem"]
        == "augur_shared.adapters.filesystem_registry:FilesystemSkillRegistry"
    )


def test_repo_tests_use_canonical_src_mcp_import_and_patch_targets() -> None:
    violations = _repo_test_import_contract_violations(CANONICAL_MCP_TEST_PREFIXES)

    assert not violations, (
        "Repo tests must import and patch MCP modules through src.mcp.* so one "
        "source file has one module identity:\n" + "\n".join(violations[:40])
    )


def test_repo_tests_do_not_import_or_patch_legacy_augur_mcp() -> None:
    violations = _repo_test_import_contract_violations((LEGACY_SHIM_TEST_PREFIX,))

    assert not violations, (
        "The legacy augur_mcp shim is not a supported repo-test import or patch "
        "contract; use canonical src.mcp.* targets:\n" + "\n".join(violations[:40])
    )
