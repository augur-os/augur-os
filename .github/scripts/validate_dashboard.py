#!/usr/bin/env python3
"""
Dashboard Validation Script

Validates that all API routes have corresponding service functions,
and that all imports are correct. Run this after any dashboard changes.
"""

import sys
import re
from pathlib import Path
from typing import List, Dict, Set, Tuple


def find_service_file(skill_name: str, dashboard_dir: Path) -> Path:
    """Find the service file for a skill."""
    return dashboard_dir / 'lib' / 'services' / f'{skill_name}.ts'


def find_api_routes(skill_name: str, dashboard_dir: Path) -> List[Path]:
    """Find all API route files for a skill."""
    api_dir = dashboard_dir / 'app' / 'api' / skill_name
    if not api_dir.exists():
        return []

    routes = []
    for route_file in api_dir.rglob('route.ts'):
        routes.append(route_file)
    return routes


def extract_imports_by_service(file_path: Path) -> Dict[str, Set[str]]:
    """Extract all imports grouped by service file name."""
    if not file_path.exists():
        return {}

    content = file_path.read_text(encoding='utf-8')
    service_imports = {}

    # Match: import { func1, func2 } from '@/lib/services/service-name'
    # Group 1: identifiers, Group 2: service name
    pattern = r"import\s+(?:type\s+)?\{([^}]+)\}\s+from\s+['\"]@/lib/services/([^'\"]+)['\"]"
    matches = re.findall(pattern, content)
    for identifiers_str, service_name in matches:
        if service_name not in service_imports:
            service_imports[service_name] = set()
        
        items = [item.strip() for item in identifiers_str.split(',')]
        for item in items:
            if item.startswith('type '):
                item = item[5:].strip()
            if item:
                service_imports[service_name].add(item)

    return service_imports


def extract_exports(file_path: Path) -> Set[str]:
    """Extract all exported functions and types from a TypeScript file."""
    if not file_path.exists():
        return set()

    content = file_path.read_text(encoding='utf-8')
    exports = set()

    # Match: export async function funcName
    pattern = r"export\s+(?:async\s+)?function\s+(\w+)"
    matches = re.findall(pattern, content)
    exports.update(matches)

    # Match: export const funcName = ...
    pattern = r"export\s+const\s+(\w+)\s*="
    matches = re.findall(pattern, content)
    exports.update(matches)

    # Match: export interface InterfaceName
    pattern = r"export\s+interface\s+(\w+)"
    matches = re.findall(pattern, content)
    exports.update(matches)

    # Match: export type TypeName
    pattern = r"export\s+type\s+(\w+)"
    matches = re.findall(pattern, content)
    exports.update(matches)

    return exports


def validate_skill(skill_name: str, dashboard_dir: Path) -> Tuple[bool, List[str]]:
    """
    Validate a skill's dashboard files.
    """
    errors = []

    # Find API routes
    api_routes = find_api_routes(skill_name, dashboard_dir)
    if not api_routes:
        return True, []

    # Cache for service exports to avoid re-parsing
    service_exports_cache = {}

    # Check each API route
    for route_file in api_routes:
        imports_by_service = extract_imports_by_service(route_file)

        for service_name, imports in imports_by_service.items():
            # Only validate if the service name belongs to this skill (fuzzy match)
            if skill_name == 'rag' and service_name == 'rag-projects':
                 pass # Allow specifically for rag
            elif not service_name.startswith(skill_name) and not service_name.replace('-', '_').startswith(skill_name):
                continue

            if service_name not in service_exports_cache:
                service_file = dashboard_dir / 'lib' / 'services' / f'{service_name}.ts'
                if not service_file.exists():
                    errors.append(f"Imported service file not found: {service_file} (in {route_file.relative_to(dashboard_dir)})")
                    continue
                service_exports_cache[service_name] = extract_exports(service_file)

            exports = service_exports_cache[service_name]
            for import_name in imports:
                if import_name not in exports:
                    errors.append(
                        f"Missing export '{import_name}' in {service_name}.ts "
                        f"(imported by {route_file.relative_to(dashboard_dir)})"
                    )

    return len(errors) == 0, errors


def validate_all_skills(dashboard_dir: Path) -> Tuple[bool, Dict[str, List[str]]]:
    """
    Validate all skills in the dashboard.

    Returns:
        (all_valid, {skill_name: [errors]})
    """
    api_dir = dashboard_dir / 'app' / 'api'
    if not api_dir.exists():
        return True, {}

    results = {}
    all_valid = True

    # Find all skills (directories in api/)
    for skill_dir in api_dir.iterdir():
        if skill_dir.is_dir():
            skill_name = skill_dir.name
            is_valid, errors = validate_skill(skill_name, dashboard_dir)
            if errors:
                results[skill_name] = errors
                all_valid = False

    return all_valid, results


def _resolve_dashboard_dir() -> Path:
    """Resolve dashboard directory. Emits heal event if not found (ADR-084)."""
    project_root = Path(__file__).resolve().parent.parent.parent
    dashboard_dir = project_root / 'apps' / 'dashboard'
    if not dashboard_dir.exists():
        try:
            from src.logging.self_heal_event import emit_heal_event

            emit_heal_event(
                source="validate_dashboard",
                category="path_missing",
                severity="high",
                message=f"Dashboard directory not found: {dashboard_dir}",
                context={"project_root": str(project_root)},
            )
        except ImportError:
            pass
        raise FileNotFoundError(f"Dashboard directory not found: {dashboard_dir}")
    return dashboard_dir


def main():
    """Main entry point."""
    dashboard_dir = _resolve_dashboard_dir()

    if len(sys.argv) > 1:
        skill_name = sys.argv[1]
        is_valid, errors = validate_skill(skill_name, dashboard_dir)

        if is_valid:
            print(f"✅ {skill_name}: All validations passed")
            return 0
        else:
            print(f"❌ {skill_name}: Validation failed")
            for error in errors:
                print(f"   - {error}")
            return 1
    else:
        # Validate all skills
        all_valid, results = validate_all_skills(dashboard_dir)

        if all_valid:
            print("✅ All skills: All validations passed")
            return 0
        else:
            print("❌ Validation failures found:")
            for skill_name, errors in results.items():
                print(f"\n{skill_name}:")
                for error in errors:
                    print(f"   - {error}")
            return 1


if __name__ == '__main__':
    sys.exit(main())
