#!/usr/bin/env python3
"""Map plugin dependency graph and detect circular dependencies."""


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
import sys

sys.path.insert(0, '.')

from pathlib import Path
import yaml
from src.config.paths import get_project_root


def parse_dependencies(skill_path: Path) -> dict:
    """Parse a skill's declared dependencies."""
    deps = {"plugins": [], "mcp_servers": [], "python": [], "npm": []}

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return deps

    content = skill_md.read_text()
    # Parse frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1])
                if frontmatter and "dependencies" in frontmatter:
                    fm_deps = frontmatter["dependencies"]
                    if isinstance(fm_deps, dict):
                        deps.update({k: v for k, v in fm_deps.items() if k in deps and isinstance(v, list)})
            except yaml.YAMLError:
                pass

    return deps


def build_graph(root: Path) -> dict[str, list[str]]:
    """Build dependency graph across all skills."""
    graph = {}

    for bundle in [
        "core",
        "career",
        "growth",
        "finance",
        "health",
        "productivity",
        "integrations",
        "lifestyle",
        "creative",
        "home",
        "consulting",
        "venture",
        "enterprise",
        "ai",
        "admin",
        "observe",
        "dev",
    ]:
        skills_dir = root / "plugins" / bundle / "skills"
        if not skills_dir.exists():
            continue
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            skill_name = f"{bundle}/{skill_dir.name}"
            deps = parse_dependencies(skill_dir)
            graph[skill_name] = deps.get("plugins", [])

    return graph


def detect_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    """Detect circular dependencies using DFS."""
    cycles = []
    visited = set()
    path = []

    def dfs(node):
        if node in path:
            cycle_start = path.index(node)
            cycles.append(path[cycle_start:] + [node])
            return
        if node in visited:
            return

        path.append(node)
        for dep in graph.get(node, []):
            dfs(dep)
        path.pop()
        visited.add(node)

    for node in graph:
        dfs(node)

    return cycles


def main():
    root = get_project_root()
    graph = build_graph(root)

    print("Plugin Dependency Graph")
    print("=" * 50)

    for skill, deps in sorted(graph.items()):
        if deps:
            print(f"  {skill} → {', '.join(deps)}")

    skills_with_deps = {k: v for k, v in graph.items() if v}
    if not skills_with_deps:
        print("  (no declared dependencies)")

    print(f"\nTotal skills: {len(graph)}")
    print(f"Skills with dependencies: {len(skills_with_deps)}")

    cycles = detect_cycles(graph)
    if cycles:
        print("\nCIRCULAR DEPENDENCIES DETECTED:")
        for cycle in cycles:
            print(f"  {' → '.join(cycle)}")
        sys.exit(1)
    else:
        print("\nNo circular dependencies detected")


if __name__ == "__main__":
    main()
