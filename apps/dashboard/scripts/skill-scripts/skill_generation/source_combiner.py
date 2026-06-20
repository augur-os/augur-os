#!/usr/bin/env python3
"""
Source Combiner

Combines multiple input sources into unified context for skill generation.
Enhanced with intelligent conflict resolution and merging.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Priority order: Notion > Folder > Git > Prompt > Zip
PRIORITY = {
    'notion': 5,
    'folder': 4,
    'git': 3,
    'prompt': 2,
    'zip': 1,
}


def resolve_conflict(field: str, values: Dict[str, Any]) -> Any:
    """Resolve conflicts for a specific field using priority."""
    if not values:
        return None

    # Sort by priority
    sorted_items = sorted(values.items(), key=lambda x: PRIORITY.get(x[0], 0), reverse=True)

    # Return highest priority non-None value
    for source_type, value in sorted_items:
        if value is not None and value != '':
            return value

    return None


def merge_lists(lists: Dict[str, List]) -> List:
    """Merge multiple lists, removing duplicates."""
    merged = []
    seen = set()

    # Add items in priority order
    sorted_sources = sorted(lists.items(), key=lambda x: PRIORITY.get(x[0], 0), reverse=True)

    for source_type, items in sorted_sources:
        if not isinstance(items, list):
            continue
        for item in items:
            # Use string representation for deduplication
            item_str = str(item).lower().strip()
            if item_str and item_str not in seen:
                merged.append(item)
                seen.add(item_str)

    return merged


def _extract_notion_source(source: Dict[str, Any], collectors: Dict[str, Dict]) -> None:
    """Extract data from a Notion source."""
    preview = source.get('preview', {})
    if 'requirements' in preview:
        collectors['requirements']['notion'] = preview['requirements']
    if 'content' in preview:
        collectors['content']['notion'] = preview.get('content', [])
    if 'title' in preview:
        collectors['names']['notion'] = preview['title']
    if 'domain' in preview:
        collectors['domains']['notion'] = preview['domain']


def _extract_folder_source(source: Dict[str, Any], collectors: Dict[str, Dict]) -> None:
    """Extract data from a folder source."""
    preview = source.get('preview', {})
    if 'file_list' in preview:
        collectors['content']['folder'] = preview['file_list']
    # Infer domain from folder name
    folder_path = source.get('value', '')
    if folder_path:
        folder_name = Path(folder_path).name.lower()
        domain_keywords = {
            'health': 'medical',
            'medical': 'medical',
            'finance': 'finance',
            'legal': 'legal',
            'tech': 'technology',
            'code': 'technology',
        }
        for keyword, domain in domain_keywords.items():
            if keyword in folder_name:
                collectors['domains']['folder'] = domain
                break


def _extract_git_source(source: Dict[str, Any], collectors: Dict[str, Dict]) -> None:
    """Extract data from a Git source."""
    preview = source.get('preview', {})
    if 'structure' in preview and preview['structure']:
        collectors['structures']['git'] = preview['structure']
    if 'is_skill' in preview and preview['is_skill']:
        url = source.get('value', '')
        if url:
            parts = url.split('/')
            if len(parts) >= 5:
                repo_name = parts[-1].replace('.git', '')
                collectors['names']['git'] = repo_name


def _extract_prompt_source(source: Dict[str, Any], collectors: Dict[str, Dict]) -> None:
    """Extract data from a prompt source."""
    preview = source.get('preview', {})
    if 'requirements' in preview:
        collectors['requirements']['prompt'] = preview['requirements']
    if 'domain' in preview and preview['domain']:
        collectors['domains']['prompt'] = preview['domain']
    if 'patterns' in preview:
        collectors['patterns']['prompt'] = preview['patterns']
    if 'capabilities' in preview:
        collectors['capabilities']['prompt'] = preview['capabilities']
    collectors['descriptions']['prompt'] = source.get('value', '')[:200]


def _extract_zip_source(source: Dict[str, Any], collectors: Dict[str, Dict]) -> None:
    """Extract data from a zip source."""
    preview = source.get('preview', {})
    if 'file_list' in preview:
        collectors['content']['zip'] = preview['file_list']
    if 'is_skill' in preview and preview['is_skill']:
        zip_path = source.get('value', '')
        if zip_path:
            collectors['names']['zip'] = Path(zip_path).stem


SOURCE_EXTRACTORS = {
    'notion': _extract_notion_source,
    'folder': _extract_folder_source,
    'git': _extract_git_source,
    'prompt': _extract_prompt_source,
    'zip': _extract_zip_source,
}


def combine_sources(sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Combine multiple sources into unified context with intelligent merging."""
    sorted_sources = sorted(sources, key=lambda s: PRIORITY.get(s.get('type', ''), 0), reverse=True)

    # Collectors for each data type
    collectors = {
        'domains': {},
        'patterns': {},
        'requirements': {},
        'content': {},
        'structures': {},
        'names': {},
        'descriptions': {},
        'capabilities': {},
    }

    # Extract from each source using type-specific extractors
    for source in sorted_sources:
        source_type = source.get('type')
        extractor = SOURCE_EXTRACTORS.get(source_type)
        if extractor:
            extractor(source, collectors)

    # Build context by resolving conflicts and merging lists
    context = {
        'requirements': merge_lists(collectors['requirements']),
        'content': merge_lists(collectors['content']),
        'structure': resolve_conflict('structure', collectors['structures']),
        'metadata': {},
        'domain': resolve_conflict('domain', collectors['domains']),
        'patterns': merge_lists(collectors['patterns']),
        'capabilities': merge_lists(collectors['capabilities']),
        'description': resolve_conflict('description', collectors['descriptions']),
        'name': resolve_conflict('name', collectors['names']),
    }

    suggested = generate_suggestion(context, sources)

    return {
        'combined': True,
        'context': context,
        'suggested': suggested,
        'sources_used': len(sources),
        'conflicts_resolved': {
            'domain': len(collectors['domains']) > 1,
            'name': len(collectors['names']) > 1,
            'description': len(collectors['descriptions']) > 1,
        },
    }


def generate_suggestion(context: Dict[str, Any], sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate suggested skill configuration from combined context."""
    # Extract skill name from first available source
    skill_name = context.get('name')

    if not skill_name:
        # Try to infer from sources
        for source in sources:
            source_type = source.get('type')
            if source_type == 'notion' and 'title' in source.get('preview', {}):
                skill_name = source['preview']['title'].lower().replace(' ', '-')
                # Clean up
                skill_name = ''.join(c if c.isalnum() or c == '-' else '' for c in skill_name)
                break
            elif source_type == 'git':
                url = source.get('value', '')
                if 'github.com' in url:
                    parts = url.split('/')
                    if len(parts) >= 5:
                        skill_name = parts[-1].replace('.git', '').replace('_', '-')
                        break
            elif source_type == 'zip':
                zip_path = source.get('value', '')
                if zip_path:
                    skill_name = Path(zip_path).stem.replace('_', '-')
                    break

    if not skill_name:
        skill_name = 'new-skill'

    # Determine patterns from context
    patterns = context.get('patterns', [])
    if not patterns:
        # Infer patterns from content
        if context.get('content'):
            patterns = ['inbox', 'database']
        elif context.get('structure'):
            patterns = ['database']
        else:
            patterns = ['database']

    # Ensure patterns are valid
    valid_patterns = ['inbox', 'database', 'scoring', 'rag']
    patterns = [p for p in patterns if p in valid_patterns]
    if not patterns:
        patterns = ['database']

    # Determine domain
    domain = context.get('domain') or 'general'

    # Generate description
    description = context.get('description')
    if not description:
        source_count = len(sources)
        description = f'Skill created from {source_count} source(s)'
        if domain and domain != 'general':
            description += f' in the {domain} domain'

    return {
        'name': skill_name,
        'description': description,
        'layer': 'vertical',  # Default, can be overridden
        'patterns': patterns,
        'domain': domain,
        'capabilities': context.get('capabilities', []),
    }


def main():
    if len(sys.argv) < 2:
        _out(json.dumps({'error': 'Config file path required'}), file=sys.stderr)
        sys.exit(1)

    config_path = Path(sys.argv[1])
    if not config_path.exists():
        _out(json.dumps({'error': f'Config file not found: {config_path}'}), file=sys.stderr)
        sys.exit(1)

    with open(config_path, 'r') as f:
        config = json.load(f)

    sources = config.get('sources', [])
    if not sources:
        _out(json.dumps({'error': 'No sources provided'}), file=sys.stderr)
        sys.exit(1)

    try:
        result = combine_sources(sources)

        # Override with user-provided values if present
        if 'skill_name' in config:
            result['suggested']['name'] = config['skill_name']
        if 'layer' in config:
            result['suggested']['layer'] = config['layer']

        _out(json.dumps(result))
    except Exception as e:
        _out(json.dumps({'error': str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
