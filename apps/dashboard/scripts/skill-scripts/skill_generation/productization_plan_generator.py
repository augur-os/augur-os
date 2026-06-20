#!/usr/bin/env python3
"""
Productization Plan Generator

Generates a maturation task list for newly created dashboards.
Tasks are dynamic based on selected patterns, layer, and domain.
"""

import os
from shutil import which
from subprocess import TimeoutExpired, run as subprocess_run  # nosec B404
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


def _resolve_command(command: str) -> str:
    """Resolve executable path for safer subprocess invocation."""
    resolved = which(command)
    return resolved or command


def _run_command(args: list[str], cwd: Path, timeout: int, env: dict[str, str]) -> tuple[int, str, str]:
    """Run subprocess command in a controlled, non-shell mode."""
    result = subprocess_run(  # nosec B603
        args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return result.returncode, result.stdout, result.stderr


# Add project root to path for imports
try:
    from src.config.paths import get_project_root
    sys.path.insert(0, str(get_project_root()))
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))  # fallback

from src.config.paths import get_project_root  # noqa: E402

# =============================================================================
# Task Definitions
# =============================================================================

# Core tasks that apply to all dashboards
CORE_TASKS = [
    {
        'id': 'verify_build',
        'name': 'Verify Build',
        'description': 'Ensure dashboard builds without TypeScript or compilation errors',
        'phase': 'mvp',
        'refactor_template_id': 'productization_verify_build',
    },
    {
        'id': 'verify_loads',
        'name': 'Verify Dashboard Loads',
        'description': 'Confirm dashboard renders in browser without runtime errors',
        'phase': 'mvp',
        'refactor_template_id': 'productization_verify_build',
    },
    {
        'id': 'verify_layout',
        'name': 'Layout Alignment',
        'description': 'Verify layout follows design standards (/sense reference)',
        'phase': 'polish',
        'refactor_template_id': 'productization_fix_layout',
    },
    {
        'id': 'verify_colors',
        'name': 'Color Scheme',
        'description': 'Ensure color scheme follows design system tokens',
        'phase': 'polish',
        'refactor_template_id': 'productization_fix_colors',
    },
    {
        'id': 'verify_typography',
        'name': 'Typography Hierarchy',
        'description': 'Check text styling follows design hierarchy (H1/H2, sections)',
        'phase': 'polish',
        'refactor_template_id': 'productization_fix_layout',
    },
    {
        'id': 'add_business_logic',
        'name': 'Implement Core Business Logic',
        'description': 'Add domain-specific functionality and data processing',
        'phase': 'production',
        'refactor_template_id': 'productization_implement_feature',
    },
]

# Pattern-specific tasks
PATTERN_TASKS = {
    'inbox': [
        {
            'id': 'implement_inbox_integration',
            'name': 'Inbox Integration',
            'description': 'Connect to Apple Notes inbox for data capture',
            'phase': 'production',
            'refactor_template_id': 'productization_implement_inbox',
        },
        {
            'id': 'configure_inbox_sources',
            'name': 'Configure Inbox Sources',
            'description': 'Set up inbox folder paths and parsing rules',
            'phase': 'production',
            'refactor_template_id': 'productization_implement_inbox',
        },
    ],
    'database': [
        {
            'id': 'implement_crud_operations',
            'name': 'CRUD Operations',
            'description': 'Implement create, read, update, delete for data entities',
            'phase': 'production',
            'refactor_template_id': 'productization_implement_crud',
        },
        {
            'id': 'add_data_validation',
            'name': 'Data Validation',
            'description': 'Add input validation and error handling for data operations',
            'phase': 'production',
            'refactor_template_id': 'productization_implement_crud',
        },
    ],
    'rag': [
        {
            'id': 'implement_search',
            'name': 'RAG Search',
            'description': 'Implement semantic search using indexed documents',
            'phase': 'production',
            'refactor_template_id': 'productization_implement_rag',
        },
        {
            'id': 'configure_rag_project',
            'name': 'Configure RAG Project',
            'description': 'Set up RAG project settings and indexing parameters',
            'phase': 'production',
            'refactor_template_id': 'productization_implement_rag',
        },
    ],
    'api': [
        {
            'id': 'implement_api_endpoints',
            'name': 'API Endpoints',
            'description': 'Create REST API routes for external integrations',
            'phase': 'production',
            'refactor_template_id': 'productization_implement_feature',
        },
        {
            'id': 'add_error_handling',
            'name': 'API Error Handling',
            'description': 'Add proper error responses and logging for API routes',
            'phase': 'production',
            'refactor_template_id': 'productization_implement_feature',
        },
    ],
    'scheduler': [
        {
            'id': 'implement_schedules',
            'name': 'Scheduled Tasks',
            'description': 'Implement automated task scheduling',
            'phase': 'production',
            'refactor_template_id': 'productization_implement_feature',
        },
        {
            'id': 'configure_triggers',
            'name': 'Configure Triggers',
            'description': 'Set up cron expressions and event triggers',
            'phase': 'production',
            'refactor_template_id': 'productization_implement_feature',
        },
    ],
}

# Layer-specific tasks
LAYER_TASKS = {
    'factory': [
        {
            'id': 'implement_mcp_tools',
            'name': 'MCP Tool Integration',
            'description': 'Register and implement MCP tools for agent capabilities',
            'phase': 'production',
            'refactor_template_id': 'productization_implement_feature',
        },
    ],
    'horizontal': [
        {
            'id': 'implement_cross_cutting',
            'name': 'Cross-Cutting Integration',
            'description': 'Ensure service works across all vertical dashboards',
            'phase': 'production',
            'refactor_template_id': 'productization_implement_feature',
        },
    ],
    'vertical': [
        {
            'id': 'domain_customization',
            'name': 'Domain Customization',
            'description': 'Add domain-specific widgets and data visualizations',
            'phase': 'polish',
            'refactor_template_id': 'productization_implement_feature',
        },
    ],
}


def get_dashboard_url(layer: str, slug: str) -> str:
    """Get the dashboard URL based on layer."""
    if layer == 'vertical':
        return f'/lifestyle/{slug}'
    elif layer == 'horizontal':
        return f'/hands/{slug}'
    else:  # factory
        return f'/agents/{slug}'


def generate_tasks(
    skill_slug: str,
    skill_title: str,
    layer: str,
    patterns: list[str],
    rag_project_id: str | None = None,
    domain: str | None = None,
) -> list[dict[str, Any]]:
    """Generate task list based on patterns and layer."""
    tasks = []
    dashboard_url = get_dashboard_url(layer, skill_slug)

    # Add core tasks with context
    for task_def in CORE_TASKS:
        task = {
            **task_def,
            'status': 'pending',
            'approved_at': None,
            'context': {
                'skill_slug': skill_slug,
                'skill_title': skill_title,
                'dashboard_path': dashboard_url,
                'layer': layer,
            },
        }
        tasks.append(task)

    # Add pattern-specific tasks
    for pattern in patterns:
        if pattern in PATTERN_TASKS:
            for task_def in PATTERN_TASKS[pattern]:
                task = {
                    **task_def,
                    'status': 'pending',
                    'approved_at': None,
                    'context': {
                        'skill_slug': skill_slug,
                        'skill_title': skill_title,
                        'dashboard_path': dashboard_url,
                        'pattern': pattern,
                        'layer': layer,
                    },
                }
                # Add RAG project ID if applicable
                if pattern == 'rag' and rag_project_id:
                    task['context']['rag_project_id'] = rag_project_id
                tasks.append(task)

    # Add layer-specific tasks
    if layer in LAYER_TASKS:
        for task_def in LAYER_TASKS[layer]:
            task = {
                **task_def,
                'status': 'pending',
                'approved_at': None,
                'context': {
                    'skill_slug': skill_slug,
                    'skill_title': skill_title,
                    'dashboard_path': dashboard_url,
                    'layer': layer,
                },
            }
            tasks.append(task)

    # Add domain context if available
    if domain:
        for task in tasks:
            task['context']['domain'] = domain

    return tasks


def save_plan(plan: dict[str, Any]) -> tuple[bool, str | None, str | None]:
    """Save productization plan to YAML file."""
    try:
        user_data_base = get_project_root()
        plans_dir = Path(user_data_base) / 'operations' / 'productization-plans'
        plans_dir.mkdir(parents=True, exist_ok=True)

        plan_path = plans_dir / f"{plan['skill_slug']}.yaml"

        with open(plan_path, 'w', encoding='utf-8') as f:
            yaml.dump(plan, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        return True, None, str(plan_path)
    except Exception as e:
        return False, str(e), None


def load_plan(skill_slug: str) -> dict[str, Any] | None:
    """Load productization plan from YAML file."""
    try:
        user_data_base = get_project_root()
        plan_path = Path(user_data_base) / 'operations' / 'productization-plans' / f'{skill_slug}.yaml'

        if not plan_path.exists():
            return None

        with open(plan_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def update_task_status(skill_slug: str, task_id: str, status: str, approved: bool = False) -> tuple[bool, str | None]:
    """Update a task's status in the plan."""
    try:
        plan = load_plan(skill_slug)
        if not plan:
            return False, f'Plan not found for skill: {skill_slug}'

        # Find and update the task
        task_found = False
        for task in plan.get('tasks', []):
            if task['id'] == task_id:
                task['status'] = status
                if approved:
                    task['approved_at'] = datetime.now(timezone.utc).isoformat()
                elif status == 'pending':
                    task['approved_at'] = None
                task_found = True
                break

        if not task_found:
            return False, f'Task not found: {task_id}'

        # Update plan status based on tasks
        all_completed = all(t['status'] == 'completed' for t in plan['tasks'])
        any_in_progress = any(t['status'] == 'in_progress' for t in plan['tasks'])

        if all_completed:
            plan['status'] = 'completed'
        elif any_in_progress:
            plan['status'] = 'in_progress'
        else:
            plan['status'] = 'pending'

        plan['updated_at'] = datetime.now(timezone.utc).isoformat()

        success, error, _ = save_plan(plan)
        return success, error
    except Exception as e:
        return False, str(e)


def generate_productization_plan(
    skill_slug: str,
    skill_title: str,
    layer: str,
    patterns: list[str],
    rag_project_id: str | None = None,
    domain: str | None = None,
) -> dict[str, Any]:
    """Generate and save a productization plan for a new skill."""
    try:
        now = datetime.now(timezone.utc).isoformat()

        # Generate tasks
        tasks = generate_tasks(
            skill_slug=skill_slug,
            skill_title=skill_title,
            layer=layer,
            patterns=patterns,
            rag_project_id=rag_project_id,
            domain=domain,
        )

        # Create plan structure
        plan = {
            'skill_slug': skill_slug,
            'skill_title': skill_title,
            'layer': layer,
            'patterns': patterns,
            'created_at': now,
            'updated_at': now,
            'status': 'pending',
            'visibility_mode': 'dev_only',  # Default: visible in DEV mode only
            'tasks': tasks,
        }

        if rag_project_id:
            plan['rag_project_id'] = rag_project_id
        if domain:
            plan['domain'] = domain

        # Save plan
        success, error, plan_path = save_plan(plan)

        if not success:
            return {
                'success': False,
                'error': error,
            }

        return {
            'success': True,
            'plan_path': plan_path,
            'task_count': len(tasks),
            'phases': {
                'mvp': len([t for t in tasks if t['phase'] == 'mvp']),
                'polish': len([t for t in tasks if t['phase'] == 'polish']),
                'production': len([t for t in tasks if t['phase'] == 'production']),
            },
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
        }


def run_auto_validation(
    skill_slug: str,
    dashboard_path: str,
    skill_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Run automatic validation checks and update task statuses.

    This runs:
    1. Build check (npm run build)
    2. Basic file existence checks
    """
    results = {
        'build_check': {'success': False, 'message': ''},
        'file_check': {'success': False, 'message': ''},
    }

    # Get project root
    try:
        from src.config.paths import get_project_root
        project_root = get_project_root()
    except ImportError:
        project_root = Path(__file__).parent.parent.parent.parent  # fallback
    dashboard_dir = project_root / 'apps' / 'dashboard'

    # 1. Build check - just verify TypeScript compilation
    try:
        # Run a quick type check instead of full build
        npm_cmd = _resolve_command('npm')
        return_code, stdout, stderr = _run_command(
            [npm_cmd, 'run', 'build'],
            dashboard_dir,
            timeout=120,
            env={**os.environ, 'NEXT_TELEMETRY_DISABLED': '1'},
        )

        if return_code == 0:
            results['build_check'] = {
                'success': True,
                'message': 'Build completed successfully',
            }
            # Auto-approve verify_build task
            update_task_status(skill_slug, 'verify_build', 'completed', approved=True)
        else:
            # Extract relevant error
            error_output = stderr or stdout
            results['build_check'] = {
                'success': False,
                'message': f'Build failed: {error_output[:500]}',
            }
    except TimeoutExpired:
        results['build_check'] = {
            'success': False,
            'message': 'Build timed out after 2 minutes',
        }
    except Exception as e:
        results['build_check'] = {
            'success': False,
            'message': f'Build check error: {e}',
        }

    # 2. File existence check
    try:
        # Determine expected page path based on dashboard URL
        if dashboard_path.startswith('/lifestyle/'):
            page_dir = dashboard_dir / 'app' / 'lifestyle' / skill_slug
        elif dashboard_path.startswith('/hands/'):
            page_dir = dashboard_dir / 'app' / 'hands' / skill_slug
        elif dashboard_path.startswith('/agents/'):
            page_dir = dashboard_dir / 'app' / 'agents' / skill_slug
        else:
            page_dir = dashboard_dir / 'app' / skill_slug

        page_tsx = page_dir / 'page.tsx'

        if page_tsx.exists():
            results['file_check'] = {
                'success': True,
                'message': f'Page file exists at {page_tsx}',
            }
        else:
            results['file_check'] = {
                'success': False,
                'message': f'Page file not found at {page_tsx}',
            }
    except Exception as e:
        results['file_check'] = {
            'success': False,
            'message': f'File check error: {e}',
        }

    return {
        'success': all(r['success'] for r in results.values()),
        'results': results,
    }


def set_visibility_mode(skill_slug: str, mode: str) -> tuple[bool, str | None]:
    """Set the visibility mode for a productization plan."""
    if mode not in ('dev_only', 'always'):
        return False, f"Invalid mode: {mode}. Must be 'dev_only' or 'always'"

    try:
        plan = load_plan(skill_slug)
        if not plan:
            return False, f'Plan not found for skill: {skill_slug}'

        plan['visibility_mode'] = mode
        plan['updated_at'] = datetime.now(timezone.utc).isoformat()

        success, error, _ = save_plan(plan)
        return success, error
    except Exception as e:
        return False, str(e)


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == '__main__':
    import json

    if len(sys.argv) < 2:
        _out(json.dumps({'success': False, 'error': 'Command required: generate, load, update, validate'}))
        sys.exit(1)

    command = sys.argv[1]

    if command == 'generate':
        if len(sys.argv) < 5:
            _out(json.dumps({'success': False, 'error': 'Usage: generate <slug> <title> <layer> [patterns...]'}))
            sys.exit(1)

        slug = sys.argv[2]
        title = sys.argv[3]
        layer = sys.argv[4]
        patterns = sys.argv[5:] if len(sys.argv) > 5 else []

        result = generate_productization_plan(
            skill_slug=slug,
            skill_title=title,
            layer=layer,
            patterns=patterns,
        )
        _out(json.dumps(result, indent=2))

    elif command == 'load':
        if len(sys.argv) < 3:
            _out(json.dumps({'success': False, 'error': 'Usage: load <slug>'}))
            sys.exit(1)

        slug = sys.argv[2]
        plan = load_plan(slug)
        if plan:
            _out(json.dumps({'success': True, 'plan': plan}, indent=2, default=str))
        else:
            _out(json.dumps({'success': False, 'error': f'Plan not found: {slug}'}))

    elif command == 'update':
        if len(sys.argv) < 5:
            _out(json.dumps({'success': False, 'error': 'Usage: update <slug> <task_id> <status>'}))
            sys.exit(1)

        slug = sys.argv[2]
        task_id = sys.argv[3]
        status = sys.argv[4]
        approved = status == 'completed'

        success, error = update_task_status(slug, task_id, status, approved)
        _out(json.dumps({'success': success, 'error': error}))

    elif command == 'validate':
        if len(sys.argv) < 4:
            _out(json.dumps({'success': False, 'error': 'Usage: validate <slug> <dashboard_path>'}))
            sys.exit(1)

        slug = sys.argv[2]
        dashboard_path = sys.argv[3]

        result = run_auto_validation(slug, dashboard_path)
        _out(json.dumps(result, indent=2))

    else:
        _out(json.dumps({'success': False, 'error': f'Unknown command: {command}'}))
        sys.exit(1)
