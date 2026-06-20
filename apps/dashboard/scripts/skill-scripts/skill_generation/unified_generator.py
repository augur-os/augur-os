#!/usr/bin/env python3
"""
Unified Skill Generator

Orchestrates all generation services to create a complete skill from any input source.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Add project root to path
try:
    from src.config.paths import get_project_root
    sys.path.insert(0, str(get_project_root()))
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))  # fallback

from . import (  # noqa: E402
    generate_structure,
    generate_skill_md,
    generate_scripts,
    generate_tests,
    generate_mcp_server,
    validate_skill,
    create_config,
    check_skill_exists,
)

# Note: generate_dashboard import removed - now using dashboard_yaml_generator directly


def normalize_input(config: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize input from any source to common format."""
    source = config.get('source', 'form')
    normalized: dict[str, Any] = {
        'source': source,
    }

    if source == 'create':
        normalized.update(
            {
                'slug': config.get('name', ''),
                'title': config.get('name', '').replace('-', ' ').title(),
                'description': config.get('description', ''),
                'patterns': config.get('patterns', []),
                'layer': config.get('layer', 'vertical'),
            }
        )
    elif source == 'import':
        skill = config.get('skill', {})
        normalized.update(
            {
                'slug': skill.get('slug', ''),
                'title': skill.get('title', ''),
                'imported_content': skill.get('content'),
                'layer': skill.get('layer', 'vertical'),
            }
        )
    elif source == 'documents':
        skill = config.get('skill', {})
        normalized.update(
            {
                'slug': config.get('slug') or skill.get('slug', ''),
                'title': config.get('title') or skill.get('title', ''),
                'domain': config.get('domain', ''),
                'description': config.get('description') or skill.get('description', ''),
                'pillars': config.get('pillars', {}),
                'use_cases': config.get('use_cases', []),
                'rag_project_id': config.get('rag_project_id'),
                'layer': config.get('layer') or skill.get('layer', 'vertical'),
            }
        )
    elif source == 'unified':
        # Multi-source input - combine from combined_context
        combined_context = config.get('combined_context', {})
        suggested = combined_context.get('suggested', {})
        context = combined_context.get('context', {})

        # Validate slug - reject placeholder names
        raw_slug = config.get('slug') or config.get('name') or suggested.get('name')
        if not raw_slug or raw_slug == 'new-skill':
            return {
                'success': False,
                'error': 'Skill name is required. Cannot use placeholder "new-skill".',
                'generated': {},
            }

        normalized.update(
            {
                'slug': raw_slug,
                'title': (config.get('name') or suggested.get('name') or raw_slug).replace('-', ' ').title(),
                'description': config.get('description')
                or suggested.get('description', 'Combined from multiple sources'),
                'patterns': config.get('patterns') or suggested.get('patterns', ['inbox', 'database']),
                'layer': config.get('layer') or suggested.get('layer', 'vertical'),
                'domain': suggested.get('domain') or context.get('domain'),
                'pillars': config.get('pillars', {}),
                'use_cases': context.get('requirements', []),
                'rag_project_id': config.get('rag_project_id'),
                'multi_source': True,
                'sources': config.get('sources', []),
            }
        )

    return normalized


def generate_skill(config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate complete skill using src/lib services."""
    normalized = normalize_input(config)

    slug = normalized['slug']
    layer = normalized.get('layer', 'vertical')
    source = normalized['source']

    # Initialize issue tracking
    errors = []
    warnings = []

    display_name = normalized.get('title', slug.replace('-', ' ').title())

    # Step 0: RAG Integration (Unified Source)
    # Check for folder sources and run indexing/analysis if found
    rag_project_id = normalized.get('rag_project_id')
    folder_sources = [s for s in normalized.get('sources', []) if s.get('type') == 'folder']

    if folder_sources:
        _out(f"Found {len(folder_sources)} folder sources. Initializing RAG...")

        # Determine paths
        try:
            from src.config.paths import get_project_root as _get_root
            repo_root = _get_root()
        except ImportError:
            repo_root = Path(__file__).parent.parent.parent.parent  # fallback
        plugins_dir = repo_root / 'plugins'

        # Add plugins to path for imports
        if str(plugins_dir) not in sys.path:
            sys.path.insert(0, str(plugins_dir))

        # Generate RAG project ID if not provided
        if not rag_project_id:
            import uuid

            rag_project_id = f"gen-{uuid.uuid4().hex[:8]}"
            normalized['rag_project_id'] = rag_project_id
            _out(f"Generated RAG Project ID: {rag_project_id}")

        # Determine data directory (standardize this logic)
        import os

        data_root = os.environ.get('AUGUR_ROOT') or str(Path.home() / 'Projects' / 'augur')

        user_data_dir = str(Path(data_root) / 'local-rag' / 'projects' / rag_project_id)

        try:
            # Initialize Indexer
            # Now that plugins is in path, we can import horizontal
            try:
                from horizontal.memory.local_rag.services.index_service import DocumentIndexer
            except ImportError:
                # Fallback if path insertion didn't work as expected
                from plugins.horizontal.memory.local_rag.services.index_service import DocumentIndexer

            indexer = DocumentIndexer(user_data_dir=user_data_dir)

            # Index each folder
            for source in folder_sources:
                path_str = source.get('path') or source.get('content')
                if path_str:
                    folder_path = Path(path_str)
                    if folder_path.exists():
                        _out(f"Indexing folder: {folder_path}")
                        stats = indexer.index_directory(folder_path, force=False)
                        _out(f"Indexing complete: {stats['files_processed']} files")
                    else:
                        warnings.append(f"Folder source path not found: {folder_path}")

            # Analyze Content
            _out("Analyzing RAG content...")
            from ..analyze_rag_content import analyze_content

            analysis = analyze_content(rag_project_id)

            # Merge Analysis Results
            _out("Merging analysis results...")

            # 1. Enhance Description
            if not normalized.get('description') or normalized.get('description') == 'Combined from multiple sources':
                normalized['description'] = analysis.get('suggested_skill', {}).get('description') or analysis.get(
                    'summary'
                )

            # 2. Enhance Patterns
            analyzed_patterns = analysis.get('suggested_skill', {}).get('patterns', [])
            current_patterns = normalized.get('patterns', [])
            if analyzed_patterns:
                # Add unique new patterns
                for p in analyzed_patterns:
                    if p not in current_patterns:
                        current_patterns.append(p)
                normalized['patterns'] = current_patterns

            # 3. Enhance Pillars
            analyzed_pillars = analysis.get('five_pillar_mapping', {})
            if analyzed_pillars:
                normalized['pillars'] = analyzed_pillars

            # 4. Enhance Metadata/Domain
            if not normalized.get('domain'):
                normalized['domain'] = analysis.get('domain', {}).get('primary')

            # 5. Store analysis results for epic generation
            normalized['_rag_analysis'] = analysis
            normalized['_business_opportunities'] = analysis.get('business_opportunities', {})
            normalized['_action_plan'] = analysis.get('action_plan', {})

            _out("RAG integration complete.")

        except ImportError as e:
            warnings.append(f"RAG integration skipped (dependency missing): {e}")
        except Exception as e:
            warnings.append(f"RAG integration failed: {e}")
            import traceback

            traceback.print_exc()

    # Validate skill name (rejects 'new-skill', test-*, etc.)
    from ..structure_generator import validate_skill_name

    is_valid, error = validate_skill_name(slug)
    if not is_valid:
        return {
            'success': False,
            'errors': [error or 'Invalid skill name'],
        }

    # Additional validation: ensure we have a real name, not placeholder
    if slug == 'new-skill' or slug.startswith('test-') or slug.endswith('-test'):
        return {
            'success': False,
            'errors': [f"Skill name '{slug}' is not allowed. Please provide a real skill name."],
        }

    # Check if skill exists
    exists, existing_path = check_skill_exists(slug, layer)
    if exists:
        return {
            'success': False,
            'errors': [f"Skill '{slug}' already exists at {existing_path}"],
        }

    # Step 0.5: Generate Epic in Backlog (if RAG analysis available)
    # This happens BEFORE skill generation so user can review and adapt
    epic_path = None
    if normalized.get('_rag_analysis') and (source == 'documents' or source == 'unified'):
        _out("Generating epic in backlog for review...")
        try:
            from .epic_generator import generate_epic

            epic_success, epic_error, epic_path = generate_epic(
                skill_name=slug,
                skill_title=display_name,
                layer=layer,
                analysis=normalized.get('_rag_analysis', {}),
                action_plan=normalized.get('_action_plan', {}),
                business_opportunities=normalized.get('_business_opportunities', {}),
                pillars=normalized.get('pillars', {}),
                domain=normalized.get('domain'),
            )
            if epic_success:
                _out(f"✅ Epic generated at: {epic_path}")
                warnings.append(f"Epic generated for review: {epic_path}")
            else:
                warnings.append(f"Epic generation skipped: {epic_error}")
        except Exception as e:
            warnings.append(f"Epic generation failed: {e}")
            import traceback

            traceback.print_exc()

    # Step 1: Generate structure
    success, skill_dir, error = generate_structure(slug, layer)
    if not success:
        return {
            'success': False,
            'errors': [error or 'Failed to create skill structure'],
        }

    generated = {
        'structure': True,
        'skill_md': False,
        'scripts': False,
        'tests': False,
        'mcp': False,
        'dashboard': False,
    }

    # Step 2: Generate SKILL.md
    try:
        skill_md_config: dict[str, Any] = {
            'source': source,
            'name': slug,
        }

        if source == 'create':
            skill_md_config.update(
                {
                    'description': normalized.get('description', ''),
                    'patterns': normalized.get('patterns', []),
                    'layer': layer,
                }
            )
        elif source == 'import':
            skill_md_config.update(
                {
                    'content': normalized.get('imported_content', ''),
                    'target_name': slug,
                }
            )
        elif source == 'documents':
            skill_md_config.update(
                {
                    'domain': normalized.get('domain', ''),
                    'description': normalized.get('description', ''),
                    'pillars': normalized.get('pillars', {}),
                    'use_cases': normalized.get('use_cases', []),
                    'rag_project_id': normalized.get('rag_project_id'),
                }
            )
        elif source == 'unified':
            skill_md_config.update(
                {
                    'description': normalized.get('description', ''),
                    'patterns': normalized.get('patterns', []),
                    'layer': layer,
                    'domain': normalized.get('domain', ''),
                    'use_cases': normalized.get('use_cases', []),
                    'pillars': normalized.get('pillars', {}),  # Added pillars support
                }
            )

        skill_md_content = generate_skill_md(skill_md_config)
        skill_md_path = skill_dir / 'skill-package' / 'SKILL.md'
        skill_md_path.write_text(skill_md_content, encoding='utf-8')
        generated['skill_md'] = True

        # Validate SKILL.md was created successfully
        if not skill_md_path.exists():
            raise FileNotFoundError(f"SKILL.md was not created at {skill_md_path}")
    except Exception as e:
        errors.append(f"Failed to generate SKILL.md: {e}")
        # If SKILL.md generation fails, the skill is incomplete - clean up
        import shutil

        try:
            if skill_dir.exists():
                shutil.rmtree(skill_dir)
                warnings.append("Removed incomplete skill directory due to SKILL.md generation failure")
        except Exception:
            pass
        return {'success': False, 'errors': errors, 'warnings': warnings, 'generated': generated}

    # Step 3: Generate tests
    try:
        success, error = generate_tests(skill_dir, slug)
        if success:
            generated['tests'] = True
        else:
            warnings.append(f"Test generation: {error}")
    except Exception as e:
        warnings.append(f"Test generation failed: {e}")

    # Step 4: Generate scripts (if patterns provided)
    if (source == 'create' or source == 'unified') and normalized.get('patterns'):
        try:
            success, error = generate_scripts(
                skill_dir, slug, normalized.get('patterns', []), normalized.get('use_cases')
            )
            if success:
                generated['scripts'] = True
        except Exception as e:
            warnings.append(f"Script generation failed: {e}")

    # Step 5: Generate MCP server (if pillars provided or unified source with RAG)
    if (source == 'documents' and normalized.get('pillars')) or (
        source == 'unified' and normalized.get('rag_project_id')
    ):
        try:
            success, error = generate_mcp_server(
                skill_dir,
                slug,
                normalized.get('pillars', {}),
                normalized.get('rag_project_id'),
                normalized.get('domain'),
            )
            if success:
                generated['mcp'] = True
        except Exception as e:
            warnings.append(f"MCP generation failed: {e}")

    # Step 6: Generate dashboard.yaml (config-driven UI)
    # This replaces the old comprehensive_dashboard_generator approach.
    # Skills now use dashboard.yaml which HubRenderer interprets at runtime.
    try:
        from .dashboard_yaml_generator import generate_dashboard_yaml

        patterns = normalized.get('patterns', [])
        dashboard_yaml_content = generate_dashboard_yaml(
            skill_name=slug,
            skill_title=display_name,
            layer=layer,
            patterns=patterns,
            pillars=normalized.get('pillars'),
            domain=normalized.get('domain'),
            description=normalized.get('description'),
        )

        # Write dashboard.yaml to skill directory root
        dashboard_yaml_path = skill_dir / 'dashboard.yaml'
        dashboard_yaml_path.write_text(dashboard_yaml_content, encoding='utf-8')
        generated['dashboard_yaml'] = True
        generated['dashboard'] = True  # Keep for backwards compat

        _out(f"✅ Generated dashboard.yaml at {dashboard_yaml_path}")

    except Exception as e:
        warnings.append(f"Dashboard YAML generation failed: {e}")
        import traceback

        traceback.print_exc()

    # Step 7: Create configuration
    try:
        success, error = create_config(
            skill_dir, slug, layer, normalized.get('rag_project_id'), normalized.get('metadata')
        )
        if not success:
            warnings.append(f"Config creation: {error}")
    except Exception as e:
        warnings.append(f"Config creation failed: {e}")

    # Step 8: Validate generated skill
    validation_result = validate_skill(skill_dir, normalized if source in ['documents', 'unified'] else None)
    if validation_result['validation_status'] == 'failed':
        errors.extend(validation_result['errors'])
    warnings.extend(validation_result.get('warnings', []))

    # Determine dashboard URL based on layer (needed for productization plan)
    if layer == 'vertical':
        dashboard_url = f'/lifestyle/{slug}'
    elif layer == 'horizontal':
        dashboard_url = f'/hands/{slug}'
    else:  # factory
        dashboard_url = f'/agents/{slug}'

    # Step 9: Generate productization plan
    productization_plan_path = None
    try:
        from .productization_plan_generator import generate_productization_plan, run_auto_validation

        plan_result = generate_productization_plan(
            skill_slug=slug,
            skill_title=display_name,
            layer=layer,
            patterns=normalized.get('patterns', []),
            rag_project_id=normalized.get('rag_project_id'),
            domain=normalized.get('domain'),
        )

        if plan_result.get('success'):
            generated['productization_plan'] = True
            productization_plan_path = plan_result.get('plan_path')
            _out(f"✅ Productization plan generated: {plan_result.get('task_count')} tasks")

            # Step 10: Run automatic validation (pre-populate task statuses)
            validation_result = run_auto_validation(
                skill_slug=slug,
                dashboard_path=dashboard_url,
                skill_dir=skill_dir,
            )
            if validation_result.get('success'):
                _out("✅ Auto-validation passed - build check succeeded")
            else:
                _out("⚠️  Auto-validation found issues (tasks marked as pending)")
        else:
            warnings.append(f"Productization plan generation: {plan_result.get('error')}")
    except Exception as e:
        warnings.append(f"Productization plan generation failed: {e}")

    # Determine dashboard URL based on layer
    if layer == 'vertical':
        dashboard_url = f'/lifestyle/{slug}'
    elif layer == 'horizontal':
        dashboard_url = f'/hands/{slug}'
    else:  # factory
        dashboard_url = f'/agents/{slug}'

    # Generate Cursor command
    cursor_command = f'@augur skill_analyze skill_path="plugins/{layer}/{slug}"'

    # Build next steps
    next_steps = []

    # Add epic review step if epic was generated
    if epic_path:
        next_steps.append(f"📋 Review epic at: {epic_path}")
        next_steps.append("   - Review features and priorities")
        next_steps.append("   - Adjust user stories as needed")
        next_steps.append("   - Approve to proceed with generation")

    # Add productization plan step if generated
    if productization_plan_path:
        next_steps.append(f"📋 Complete productization plan at {dashboard_url}/productization-plan")
        next_steps.append("   - Review and approve each task")
        next_steps.append("   - Use Refactor button for AI-assisted improvements")

    next_steps.extend(
        [
            f"View skill at plugins/{layer}/{slug}",
            f"View dashboard at {dashboard_url}",
            'Customize SKILL.md',
            'Add domain-specific logic',
        ]
    )

    # Build response
    response: dict[str, Any] = {
        'success': len(errors) == 0,
        'skill': {
            'slug': slug,
            'title': display_name,
            'layer': layer,
            'path': str(skill_dir.relative_to(repo_root)),
        },
        'generated': generated,
        'dashboard_url': dashboard_url,
        'cursor_command': cursor_command,
        'epic_path': str(epic_path) if epic_path else None,
        'productization_plan_path': productization_plan_path,
        'productization_plan_url': f'{dashboard_url}/productization-plan' if productization_plan_path else None,
        'next_steps': next_steps,
    }

    if errors:
        response['errors'] = errors
    if warnings:
        response['warnings'] = warnings

    return response


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        _out(
            json.dumps(
                {
                    'success': False,
                    'errors': ['Config file path required'],
                }
            )
        )
        sys.exit(1)

    config_path = Path(sys.argv[1])

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except Exception as e:
        _out(
            json.dumps(
                {
                    'success': False,
                    'errors': [f'Failed to read config: {e}'],
                }
            )
        )
        sys.exit(1)

    result = generate_skill(config)
    _out(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
