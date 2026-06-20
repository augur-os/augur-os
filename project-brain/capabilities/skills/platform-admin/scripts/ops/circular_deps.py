"""auto-circular-deps: Detect circular import dependencies in TypeScript and Python code.

Builds a dependency graph from import statements and detects cycles using DFS.
Difficulty gates:
  - d0: TypeScript in apps/dashboard/lib/ and apps/dashboard/hooks/
  - d1: all TypeScript under apps/dashboard/
  - d2+: also Python under src/ and skills/
"""
from __future__ import annotations


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
import re
from pathlib import Path

from src.config.paths import get_project_brain_skills_dir
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    make_issue,
    report_only_fix,
)

name = "auto-circular-deps"

DIFFICULTY_SPEC = {
    0: "Core shared modules — dashboard lib/ and hooks/ only",
    1: "All TypeScript under apps/dashboard/",
    2: "Also Python under src/ and skills/",
    3: "Same as d2 (full coverage)",
    4: "Same as d2 (full coverage)",
}

# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------

# TypeScript: import ... from './foo' or from '../bar/baz'
_TS_IMPORT_RE = re.compile(
    r"""(?:import|export)\s+.*?\s+from\s+['"]([^'"]+)['"]"""
)
# TypeScript: import('...')  dynamic imports
_TS_DYNAMIC_IMPORT_RE = re.compile(r"""import\s*\(\s*['"]([^'"]+)['"]\s*\)""")

# Python: import foo.bar / from foo.bar import baz
_PY_IMPORT_RE = re.compile(
    r"""^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))""", re.MULTILINE
)


def _resolve_ts_import(
    source_file: Path, import_path: str, ts_files_by_stem: dict[str, Path]
) -> Path | None:
    """Resolve a relative TypeScript import to an actual file path."""
    if not import_path.startswith("."):
        return None  # Skip node_modules / absolute imports

    source_dir = source_file.parent
    resolved = (source_dir / import_path).resolve()

    # Try exact match, then with extensions
    for candidate in [resolved, resolved.with_suffix(".ts"), resolved.with_suffix(".tsx")]:
        if candidate.is_file():
            return candidate

    # Try index files
    for index_name in ["index.ts", "index.tsx"]:
        index_candidate = resolved / index_name
        if index_candidate.is_file():
            return index_candidate

    return None


def _collect_ts_files(directories: list[Path]) -> list[Path]:
    """Collect all .ts/.tsx files from given directories."""
    files: list[Path] = []
    for d in directories:
        if not d.is_dir():
            continue
        for ext in ("*.ts", "*.tsx"):
            files.extend(d.rglob(ext))
    # Exclude node_modules, .next, test files
    return [
        f for f in files
        if "node_modules" not in f.parts
        and ".next" not in f.parts
        and "__tests__" not in f.parts
        and not f.name.endswith(".test.ts")
        and not f.name.endswith(".test.tsx")
        and not f.name.endswith(".spec.ts")
        and not f.name.endswith(".spec.tsx")
        and not f.name.endswith(".d.ts")
    ]


def _collect_py_files(directories: list[Path]) -> list[Path]:
    """Collect all .py files from given directories."""
    files: list[Path] = []
    for d in directories:
        if not d.is_dir():
            continue
        files.extend(d.rglob("*.py"))
    return [
        f for f in files
        if "__pycache__" not in f.parts
        and ".venv" not in f.parts
        and "node_modules" not in f.parts
    ]


def _build_ts_graph(
    ts_files: list[Path],
) -> dict[str, set[str]]:
    """Build adjacency list from TypeScript import statements."""
    graph: dict[str, set[str]] = {}
    ts_files_by_stem: dict[str, Path] = {}
    for f in ts_files:
        ts_files_by_stem[str(f.resolve())] = f

    ts_file_set = {str(f.resolve()) for f in ts_files}

    for source_file in ts_files:
        source_key = str(source_file.resolve())
        if source_key not in graph:
            graph[source_key] = set()

        try:
            content = source_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        # Find all import paths
        import_paths: list[str] = _TS_IMPORT_RE.findall(content)
        import_paths.extend(_TS_DYNAMIC_IMPORT_RE.findall(content))

        for imp in import_paths:
            resolved = _resolve_ts_import(source_file, imp, ts_files_by_stem)
            if resolved is None:
                continue
            resolved_key = str(resolved.resolve())
            if resolved_key in ts_file_set and resolved_key != source_key:
                graph[source_key].add(resolved_key)

    return graph


def _build_py_graph(
    py_files: list[Path], project_root: Path
) -> dict[str, set[str]]:
    """Build adjacency list from Python import statements."""
    graph: dict[str, set[str]] = {}

    # Build a mapping from module dotted path to file path
    module_to_file: dict[str, str] = {}
    for f in py_files:
        try:
            rel = f.resolve().relative_to(project_root.resolve())
        except ValueError:
            continue
        # Convert path to module: src/lib/foo.py -> src.lib.foo
        parts = list(rel.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1].removesuffix(".py")
        module_path = ".".join(parts)
        module_to_file[module_path] = str(f.resolve())

    py_file_set = {str(f.resolve()) for f in py_files}

    for source_file in py_files:
        source_key = str(source_file.resolve())
        if source_key not in graph:
            graph[source_key] = set()

        try:
            content = source_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        for match in _PY_IMPORT_RE.finditer(content):
            from_module = match.group(1)
            import_module = match.group(2)
            module_name = from_module or import_module
            if not module_name:
                continue

            # Try to resolve the module to a file
            # Check progressively shorter prefixes
            parts = module_name.split(".")
            for i in range(len(parts), 0, -1):
                candidate = ".".join(parts[:i])
                if candidate in module_to_file:
                    resolved_key = module_to_file[candidate]
                    if resolved_key in py_file_set and resolved_key != source_key:
                        graph[source_key].add(resolved_key)
                    break

    return graph


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------

def _find_cycles(graph: dict[str, set[str]], max_cycles: int = 50) -> list[list[str]]:
    """Find all cycles in a directed graph using DFS. Returns list of cycle paths."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {node: WHITE for node in graph}
    path: list[str] = []
    cycles: list[list[str]] = []

    def dfs(node: str) -> None:
        if len(cycles) >= max_cycles:
            return
        color[node] = GRAY
        path.append(node)

        for neighbor in sorted(graph.get(node, set())):
            if len(cycles) >= max_cycles:
                return
            if neighbor not in color:
                color[neighbor] = WHITE
            if color[neighbor] == GRAY:
                # Found a cycle: extract it from path
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)
            elif color[neighbor] == WHITE:
                dfs(neighbor)

        path.pop()
        color[node] = BLACK

    for node in sorted(graph):
        if color[node] == WHITE:
            dfs(node)
        if len(cycles) >= max_cycles:
            break

    return cycles


def _shorten_path(full_path: str, project_root: Path) -> str:
    """Convert absolute path to relative for display."""
    try:
        return str(Path(full_path).relative_to(project_root.resolve()))
    except ValueError:
        return full_path


# ---------------------------------------------------------------------------
# Scan / Fix
# ---------------------------------------------------------------------------

def scan(ctx: OpsContext) -> ScanResult:
    """Detect circular import dependencies."""
    root = ctx.project_root
    issues: list[dict] = []
    items_scanned = 0

    # --- TypeScript ---
    if ctx.difficulty < 1:
        ts_dirs = [
            root / "apps" / "dashboard" / "lib",
            root / "apps" / "dashboard" / "hooks",
        ]
    else:
        ts_dirs = [root / "apps" / "dashboard"]

    ts_files = _collect_ts_files(ts_dirs)
    items_scanned += len(ts_files)

    if ts_files:
        ts_graph = _build_ts_graph(ts_files)
        ts_cycles = _find_cycles(ts_graph)

        for cycle in ts_cycles:
            short_cycle = [_shorten_path(p, root) for p in cycle]
            cycle_str = " -> ".join(short_cycle)
            issues.append(
                make_issue(
                    category="circular-deps",
                    detail=f"TypeScript cycle: {cycle_str}",
                    path=short_cycle[0],
                    kind="actionable",
                    root_cause_type="repo_bug",
                    fixability="manual",
                    language="typescript",
                    cycle=short_cycle,
                )
            )

    # --- Python (difficulty >= 2) ---
    if ctx.difficulty >= 2:
        py_dirs = [
            root / "src",
            get_project_brain_skills_dir(root),
        ]
        py_files = _collect_py_files(py_dirs)
        items_scanned += len(py_files)

        if py_files:
            py_graph = _build_py_graph(py_files, root)
            py_cycles = _find_cycles(py_graph)

            for cycle in py_cycles:
                short_cycle = [_shorten_path(p, root) for p in cycle]
                cycle_str = " -> ".join(short_cycle)
                issues.append(
                    make_issue(
                        category="circular-deps",
                        detail=f"Python cycle: {cycle_str}",
                        path=short_cycle[0],
                        kind="actionable",
                        root_cause_type="repo_bug",
                        fixability="manual",
                        language="python",
                        cycle=short_cycle,
                    )
                )

    if not issues:
        return ScanResult(
            issues=[],
            summary=f"No circular dependencies found ({items_scanned} files scanned)",
            severity="info",
            items_scanned=items_scanned,
        )

    ts_count = sum(1 for i in issues if i.get("language") == "typescript")
    py_count = sum(1 for i in issues if i.get("language") == "python")
    parts = []
    if ts_count:
        parts.append(f"{ts_count} TypeScript")
    if py_count:
        parts.append(f"{py_count} Python")

    return ScanResult(
        issues=issues,
        summary=f"Found {len(issues)} circular dependency cycle(s): {', '.join(parts)}",
        severity="warning",
        items_scanned=items_scanned,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Report circular dependencies (manual fix required)."""
    return report_only_fix(ctx, "circular_deps.json", issues, noun="cycle")
