"""auto-coverage-check: Analyze test coverage and identify untested code.
Extracted from /test-coverage (ADR-200).

Scan: cross-references Python source modules against test files to find
modules with no corresponding test file.
Fix: generates minimal importability test stubs for untested modules.
Stub generation scales with difficulty:
  d0: report only — no stubs generated
  d1: up to 10 stubs per cycle (highest-priority modules)
  d2: up to 25 stubs per cycle
  d3+: unlimited — stubs for all stubbable modules
Remaining modules get a coverage gap report.

Note: TypeScript build health is handled by auto-build-health (hardening loop).
"""
from __future__ import annotations


import ast
import importlib.util as _augur_importlib_util
import sys as _augur_sys
from pathlib import Path as _AugurPath

_augur_bootstrap_start = _AugurPath(__file__).resolve()
for _augur_bootstrap_parent in (_augur_bootstrap_start.parent, *_augur_bootstrap_start.parents):
    _augur_bootstrap_path = _augur_bootstrap_parent / "daemon" / "scripts" / "bootstrap_paths.py"
    if _augur_bootstrap_path.is_file():
        break
else:
    raise RuntimeError(f"Unable to locate shared skill bootstrap from {_augur_bootstrap_start}")

_augur_bootstrap_spec = _augur_importlib_util.spec_from_file_location(
    "_augur_shared_bootstrap_paths", _augur_bootstrap_path
)
if _augur_bootstrap_spec is None or _augur_bootstrap_spec.loader is None:
    raise RuntimeError(f"Unable to load shared skill bootstrap from {_augur_bootstrap_path}")
_augur_bootstrap_module = _augur_importlib_util.module_from_spec(_augur_bootstrap_spec)
_augur_sys.modules[_augur_bootstrap_spec.name] = _augur_bootstrap_module
_augur_bootstrap_spec.loader.exec_module(_augur_bootstrap_module)
_augur_bootstrap_module.ensure_project_paths(__file__)
import subprocess
from pathlib import Path

from src.config.paths import get_all_client_skill_dirs
from src.lib.ops_protocol import FixResult, OpsContext, ScanResult, check_intentional_skip


name = "auto-coverage-check"


def _commit_files(project_root: Path, message: str, paths: list[str]) -> str | None:
    """Stage specific paths and commit. Returns short commit hash or None."""
    for p in paths:
        subprocess.run(["git", "add", p], capture_output=True, cwd=str(project_root))
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        capture_output=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        return None
    result = subprocess.run(
        ["git", "commit", "-m", message],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    if result.returncode == 0:
        rev = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        return rev.stdout.strip() if rev.returncode == 0 else None
    return None

_SKIP_DIRS = {
    "node_modules",
    ".next",
    "__pycache__",
    "runtime",
    ".venv",
    ".git",
    "fixtures",
    "tests",
}
_SKIP_BUNDLES = {"claude-plugins"}  # exported mirrors — skip to avoid double-counting


def _find_source_modules(project_root: Path, difficulty: int) -> list[Path]:
    """Find Python source modules (not tests, not __init__)."""
    modules: list[Path] = []
    search_dirs: list[Path] = [project_root / "src"]
    if difficulty >= 1:
        search_dirs.extend(get_all_client_skill_dirs(project_root))

    for src_dir in search_dirs:
        if not src_dir.is_dir():
            continue
        for py_file in src_dir.rglob("*.py"):
            if any(skip in py_file.parts for skip in _SKIP_DIRS):
                continue
            # Skip mirror bundles (e.g. claude-plugins) to avoid double-counting
            if any(skip in py_file.parts for skip in _SKIP_BUNDLES):
                continue
            if py_file.name.startswith("test_") or py_file.name.endswith("_test.py"):
                continue
            if py_file.name in ("__init__.py", "__main__.py"):
                continue
            modules.append(py_file)

    return modules


def _collect_test_stems(test_dir: Path, test_stems: set[str]) -> None:
    """Collect test file stems from a single directory tree."""
    if not test_dir.is_dir():
        return
    for test_file in test_dir.rglob("test_*.py"):
        stem = test_file.stem.removeprefix("test_")
        test_stems.add(stem)
    for test_file in test_dir.rglob("*_test.py"):
        stem = test_file.stem.removesuffix("_test")
        test_stems.add(stem)


def _collect_test_paths(test_dir: Path, test_paths: set[Path]) -> None:
    """Collect Python test files from a single directory tree."""
    if not test_dir.is_dir():
        return
    for test_file in test_dir.rglob("test_*.py"):
        test_paths.add(test_file)
    for test_file in test_dir.rglob("*_test.py"):
        test_paths.add(test_file)


def _find_test_files(project_root: Path) -> set[str]:
    """Collect all test file stems for matching.

    Searches both the project-root ``tests/`` directory and managed skill-local
    test directories at ``{skill-root}/*/augur/tests/``.
    """
    test_stems: set[str] = set()

    # Project-root tests
    _collect_test_stems(project_root / "tests", test_stems)

    # Skill-local tests (skip mirror bundles)
    for skills_dir in get_all_client_skill_dirs(project_root):
        for skill_tests in skills_dir.glob("*/augur/tests"):
            if any(skip in skill_tests.parts for skip in _SKIP_BUNDLES):
                continue
            _collect_test_stems(skill_tests, test_stems)

    return test_stems


def _find_test_paths(project_root: Path) -> set[Path]:
    """Collect all managed Python test files for import-reference matching."""
    test_paths: set[Path] = set()
    _collect_test_paths(project_root / "tests", test_paths)

    for skills_dir in get_all_client_skill_dirs(project_root):
        for skill_tests in skills_dir.glob("*/augur/tests"):
            if any(skip in skill_tests.parts for skip in _SKIP_BUNDLES):
                continue
            _collect_test_paths(skill_tests, test_paths)

    return test_paths


def _dotted_prefixes(value: str) -> set[str]:
    """Return every dotted-path prefix of a module-like string.

    A ``mock.patch`` / ``monkeypatch.setattr`` target points *into* a module
    (e.g. ``"src.lib.knowledge._iterative.time.sleep"``). The owning module is
    some prefix of that path, but the test cannot say where the module ends and
    the attribute begins. Emitting every segment-prefix lets the exact-match in
    :func:`scan` credit only the real source module whose import target appears
    among them; bogus prefixes (``src``, ``src.lib``) collide with no real file.

    Returns an empty set when ``value`` is not a dotted identifier path.
    """
    parts = value.split(".")
    if len(parts) < 2 or not all(part.isidentifier() for part in parts):
        return set()
    return {".".join(parts[: i + 1]) for i in range(len(parts))}


def _import_refs_from_test(test_file: Path) -> set[str]:
    """Return dotted module references a test file imports or exercises.

    Covers ``import`` / ``from ... import`` statements, ``importlib.import_module``
    calls, and string targets passed to ``mock.patch`` / ``patch`` /
    ``monkeypatch.setattr`` — tests routinely cover a module solely by patching
    into it (``patch("src.lib.knowledge._iterative.time.sleep")``) without ever
    importing it at module scope.
    """
    try:
        tree = ast.parse(test_file.read_text(encoding="utf-8"), filename=str(test_file))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()

    refs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            refs.update(alias.name for alias in node.names)
            continue

        if isinstance(node, ast.ImportFrom) and node.module:
            refs.add(node.module)
            refs.update(
                f"{node.module}.{alias.name}"
                for alias in node.names
                if alias.name != "*"
            )
            continue

        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_import_module = (
            isinstance(func, ast.Attribute)
            and func.attr == "import_module"
            and isinstance(func.value, ast.Name)
            and func.value.id == "importlib"
        )
        if is_import_module and node.args and isinstance(node.args[0], ast.Constant):
            value = node.args[0].value
            if isinstance(value, str):
                refs.add(value)
            continue

        # mock.patch("a.b.c") / patch("a.b.c") / monkeypatch.setattr("a.b.c", ...)
        func_name = (
            func.attr if isinstance(func, ast.Attribute)
            else func.id if isinstance(func, ast.Name)
            else None
        )
        if func_name in {"patch", "setattr"} and node.args and isinstance(node.args[0], ast.Constant):
            value = node.args[0].value
            if isinstance(value, str):
                refs.update(_dotted_prefixes(value))

    return refs


def _find_test_import_refs(project_root: Path) -> set[str]:
    """Collect exact module references imported from managed tests."""
    refs: set[str] = set()
    for test_file in _find_test_paths(project_root):
        refs.update(_import_refs_from_test(test_file))
    return refs


def _module_import_targets(project_root: Path, module: Path) -> set[str]:
    """Return import paths that identify a source module."""
    try:
        rel_path = module.relative_to(project_root)
    except ValueError:
        return set()

    parts = list(rel_path.with_suffix("").parts)
    if not parts:
        return set()

    if parts[0] == "src":
        return {".".join(parts)}

    if "skills" in parts:
        idx = parts.index("skills")
        if idx + 2 <= len(parts):
            candidate = ["skills", parts[idx + 1], *parts[idx + 2 :]]
            if all(part.isidentifier() for part in candidate):
                return {".".join(candidate)}

    return set()


def scan(ctx: OpsContext) -> ScanResult:
    source_modules = _find_source_modules(ctx.project_root, ctx.difficulty)
    test_stems = _find_test_files(ctx.project_root)
    test_import_refs = _find_test_import_refs(ctx.project_root)

    untested: list[dict] = []
    for mod in source_modules:
        # Skip files outside the project root (e.g. external plugin caches)
        try:
            rel_path = str(mod.relative_to(ctx.project_root))
        except ValueError:
            continue
        # ADR-269: skip files with INTENTIONAL_SKIP markers
        if check_intentional_skip(mod):
            continue
        mod_stem = mod.stem
        module_import_targets = _module_import_targets(ctx.project_root, mod)
        if mod_stem not in test_stems and not (module_import_targets & test_import_refs):
            untested.append({
                "action": "untested-module",
                "file": rel_path,
                "module": mod_stem,
            })

    if not untested:
        return ScanResult(
            issues=[],
            summary=f"All {len(source_modules)} source modules have test coverage",
            severity="info",
            items_scanned=len(source_modules),
        )

    return ScanResult(
        issues=untested,
        summary=f"{len(untested)}/{len(source_modules)} modules without tests",
        severity="warning",
        items_scanned=len(source_modules),
    )


def _max_stubs_for_difficulty(difficulty: int) -> int | None:
    """Return the stub cap for a given difficulty level.

    Returns an int cap, or None for unlimited.
    d0 is handled by the fix() early return — this is only called at d1+.
    """
    if difficulty <= 0:
        return 0
    if difficulty == 1:
        return 10
    if difficulty == 2:
        return 25
    # d3+: unlimited
    return None


def _resolve_test_path(project_root: Path, source_rel: str) -> Path | None:
    """Determine the test file path for a source module.

    For skill modules ({skill-root}/{name}/...), tests go in
    {skill-root}/{name}/augur/tests/test_{stem}.py.
    For src/ modules, tests go in tests/test_{stem}.py.
    Returns None if the path pattern is unrecognised.
    """
    parts = Path(source_rel).parts
    stem = Path(source_rel).stem

    # Skill module: {skill-root}/{name}/...
    if "skills" in parts:
        idx = list(parts).index("skills")
        if idx + 1 < len(parts):
            # Reconstruct: {client_dir}/skills/{skill_name}/augur/tests/
            prefix_parts = parts[: idx]  # e.g. ('.claude',)
            skill_name = parts[idx + 1]
            test_dir = project_root.joinpath(*prefix_parts, "skills", skill_name, "augur", "tests")
            return test_dir / f"test_{stem}.py"

    # src/ module
    if parts and parts[0] == "src":
        return project_root / "tests" / f"test_{stem}.py"

    return None


def _build_import_path(source_rel: str) -> str | None:
    """Build a Python import path from a relative source file path.

    Returns a dotted module path suitable for ``importlib.import_module``,
    or None if the path cannot be converted to an import.
    """
    parts = Path(source_rel).parts
    stem = Path(source_rel).stem

    # src/config/paths.py -> src.config.paths
    if parts and parts[0] == "src":
        module_parts = list(parts[:-1]) + [stem]
        return ".".join(module_parts)

    # Skill scripts are not on sys.path by default — use importlib with
    # a sys.path insert in the stub, so return just the stem for comment.
    return None


def _generate_test_stub(module_name: str, source_rel: str) -> str:
    """Generate a minimal importability test stub."""
    import_path = _build_import_path(source_rel)
    parts = Path(source_rel).parts

    lines = [
        f'"""Auto-generated importability test for {module_name}."""',
        "from __future__ import annotations",
        "",
        "import sys",
        "from pathlib import Path",
        "",
    ]

    # For skill modules, add sys.path setup
    if "skills" in parts:
        idx = list(parts).index("skills")
        prefix_parts = list(parts[:idx])
        project_root_parent_count = 4 + len(prefix_parts)
        skill_name = parts[idx + 1] if idx + 1 < len(parts) else "unknown"
        script_idx = list(parts).index("scripts") if "scripts" in parts else -1
        nested_script_package = list(parts[script_idx + 1 : -1]) if script_idx >= 0 else []

        if nested_script_package:
            module_parts = ["skills", skill_name, "scripts", *nested_script_package, module_name]
            if not prefix_parts and all(part.isidentifier() for part in module_parts):
                import_target = ".".join(module_parts)
                lines.extend([
                    "import importlib",
                    "",
                    f"PROJECT_ROOT = Path(__file__).resolve().parents[{project_root_parent_count}]",
                    "if str(PROJECT_ROOT) not in sys.path:",
                    "    sys.path.insert(0, str(PROJECT_ROOT))",
                    "",
                    'MCP_SRC = PROJECT_ROOT / "src" / "mcp"',
                    "if str(MCP_SRC) not in sys.path:",
                    "    sys.path.insert(0, str(MCP_SRC))",
                    "",
                    "",
                    f"def test_{module_name}_importable():",
                    f'    """Verify that {module_name} can be imported without errors."""',
                    f'    mod = importlib.import_module("{import_target}")',
                    "    assert mod is not None",
                    "",
                ])
                return "\n".join(lines)

            package_name = "_".join([skill_name.replace("-", "_"), *nested_script_package, "testpkg"])
            package_dir_parts = [*prefix_parts, "skills", skill_name, "scripts", *nested_script_package]
            package_dir_expr = (
                "PROJECT_ROOT"
                + "".join(f' / "{part}"' for part in package_dir_parts)
            )
            lines.extend([
                "import importlib",
                "import importlib.util",
                "",
                f"PROJECT_ROOT = Path(__file__).resolve().parents[{project_root_parent_count}]",
                "if str(PROJECT_ROOT) not in sys.path:",
                "    sys.path.insert(0, str(PROJECT_ROOT))",
                "",
                'MCP_SRC = PROJECT_ROOT / "src" / "mcp"',
                "if str(MCP_SRC) not in sys.path:",
                "    sys.path.insert(0, str(MCP_SRC))",
                "",
                "",
                f"def test_{module_name}_importable():",
                f'    """Verify that {module_name} can be imported without errors."""',
                f'    package_name = "{package_name}"',
                f"    package_dir = {package_dir_expr}",
                "",
                "    if package_name not in sys.modules:",
                "        spec = importlib.util.spec_from_file_location(",
                "            package_name,",
                '            package_dir / "__init__.py",',
                "            submodule_search_locations=[str(package_dir)],",
                "        )",
                "        assert spec is not None and spec.loader is not None",
                "        module = importlib.util.module_from_spec(spec)",
                "        sys.modules[package_name] = module",
                "        spec.loader.exec_module(module)",
                "",
                f'    mod = importlib.import_module(f"{{package_name}}.{module_name}")',
                "    assert mod is not None",
                "",
            ])
            return "\n".join(lines)

        # Detect whether module lives in augur/lib/ vs scripts/
        # source_rel examples:
        #   {skill-root}/{name}/scripts/foo.py  -> parents[2] / "scripts"
        #   {skill-root}/{name}/augur/lib/foo.py -> parents[1] / "lib"
        in_augur_lib = "augur" in parts and "lib" in parts
        if in_augur_lib:
            # tests at {skill-root}/{name}/augur/tests/ — module at augur/lib/
            path_label = "LIB_DIR"
            path_expr = 'Path(__file__).resolve().parents[1] / "lib"'
        else:
            # tests at {skill-root}/{name}/augur/tests/ — module at scripts/
            path_label = "SCRIPTS_DIR"
            path_expr = 'Path(__file__).resolve().parents[2] / "scripts"'
        # tests are at {skill-root}/{name}/augur/tests/
        lines.extend([
            f"PROJECT_ROOT = Path(__file__).resolve().parents[{project_root_parent_count}]",
            "if str(PROJECT_ROOT) not in sys.path:",
            "    sys.path.insert(0, str(PROJECT_ROOT))",
            "",
            f"{path_label} = {path_expr}",
            f"if str({path_label}) not in sys.path:",
            f"    sys.path.insert(0, str({path_label}))",
            "",
            "",
            f"def test_{module_name}_importable():",
            f'    """Verify that {module_name} can be imported without errors."""',
            "    import importlib",
            f'    mod = importlib.import_module("{module_name}")',
            "    assert mod is not None",
            "",
        ])
    else:
        # src/ module — direct import
        lines.extend([
            "PROJECT_ROOT = Path(__file__).resolve().parents[2]",
            "if str(PROJECT_ROOT) not in sys.path:",
            "    sys.path.insert(0, str(PROJECT_ROOT))",
            "",
            "",
            f"def test_{module_name}_importable():",
            f'    """Verify that {module_name} can be imported without errors."""',
        ])
        if import_path:
            lines.append(f"    import {import_path}")
            lines.append(f"    assert {import_path} is not None")
        else:
            lines.append("    import importlib")
            lines.append(f'    mod = importlib.import_module("{module_name}")')
            lines.append("    assert mod is not None")
        lines.append("")

    return "\n".join(lines)


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    if not issues:
        return FixResult(success=True, summary="No coverage gaps to fix")

    # d0: report only — no stub generation
    if ctx.difficulty < 1:
        return FixResult(
            success=True,
            changes=[],
            summary=f"Report only (d0): {len(issues)} untested module(s) detected",
            fix_type="report",
        )

    # Partition: stubbable vs report-only
    stubbable: list[dict] = []
    report_only: list[dict] = []

    for iss in issues:
        source_rel = iss.get("file", "")
        module_name = iss.get("module", "")
        if not source_rel or not module_name:
            report_only.append(iss)
            continue

        # Skip private/internal modules (leading underscore) — harder to stub
        if module_name.startswith("_"):
            report_only.append(iss)
            continue

        # Skip conftest files — they are test infrastructure, not modules
        if module_name == "conftest":
            report_only.append(iss)
            continue

        test_path = _resolve_test_path(ctx.project_root, source_rel)
        if test_path is None:
            report_only.append(iss)
            continue

        # Skip if test file already exists (shouldn't happen given scan, but be safe)
        if test_path.exists():
            report_only.append(iss)
            continue

        stubbable.append(iss)

    # Cap stubs based on difficulty level
    max_stubs = _max_stubs_for_difficulty(ctx.difficulty)
    if max_stubs is not None:
        to_stub = stubbable[:max_stubs]
        deferred = stubbable[max_stubs:]
        report_only.extend(deferred)
    else:
        to_stub = stubbable

    if ctx.dry_run:
        stub_files = []
        for iss in to_stub:
            tp = _resolve_test_path(ctx.project_root, iss["file"])
            stub_files.append(str(tp.relative_to(ctx.project_root)) if tp else iss["file"])
        return FixResult(
            success=True,
            summary=(
                f"Dry run: would create {len(to_stub)} test stubs, "
                f"{len(report_only)} remaining as report-only"
            ),
            changes=stub_files,
        )

    # Generate test stubs
    created: list[str] = []
    for iss in to_stub:
        test_path = _resolve_test_path(ctx.project_root, iss["file"])
        if test_path is None:
            continue
        test_path.parent.mkdir(parents=True, exist_ok=True)
        content = _generate_test_stub(iss["module"], iss["file"])
        test_path.write_text(content, encoding="utf-8")
        created.append(str(test_path.relative_to(ctx.project_root)))

    # Write coverage gap report for remaining issues
    if report_only:
        report_dir = ctx.project_root / "docs" / "generated"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_file = report_dir / "coverage-gaps-report.md"

        lines = [
            "# Test Coverage Gaps Report",
            "",
            f"## {len(report_only)} Untested Python Modules (report-only)",
            "",
            "| Module | File |",
            "|--------|------|",
        ]
        for iss in sorted(report_only, key=lambda x: x.get("file", "")):
            lines.append(f"| `{iss.get('module', '?')}` | `{iss.get('file', '?')}` |")
        lines.append("")
        report_file.write_text("\n".join(lines), encoding="utf-8")

    # ADR-417: Commit generated test stubs so they persist across cycles
    sha = None
    if created:
        commit_paths = created[:]
        if report_only:
            report_rel = str(report_file.relative_to(ctx.project_root))
            commit_paths.append(report_rel)
        sha = _commit_files(
            ctx.project_root,
            f"test(adaptive): add {len(created)} importability test stub(s)",
            commit_paths,
        )

    # ADR-417: Set fix_type explicitly based on whether code was generated
    fix_type = "code-fix" if created else "report"

    summary = (
        f"Created {len(created)} test stubs; "
        f"{len(report_only)} modules in coverage gap report"
    )
    if sha:
        summary += f" (commit {sha})"

    actions = []
    if sha:
        actions.append({"commit": sha})

    return FixResult(
        success=True,
        actions=actions,
        changes=created,
        summary=summary,
        fix_type=fix_type,
    )
