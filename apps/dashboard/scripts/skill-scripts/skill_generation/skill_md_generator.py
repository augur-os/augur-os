"""
SKILL.md Generator Service

Generates SKILL.md files from various input sources:
- Form data (name, description, patterns)
- Imported SKILL.md (parses and normalizes)
- RAG analysis results (domain, pillars, use cases)
"""

import re
import yaml
from datetime import datetime
from typing import Any, Optional, Dict


def get_emoji(name: str) -> str:
    """Get appropriate emoji based on skill name."""
    emoji_map = {
        'tracker': '📊',
        'capture': '💡',
        'automation': '⚙️',
        'list': '📚',
        'memos': '🎙️',
        'notes': '📝',
        'calendar': '📅',
        'finance': '💰',
        'health': '❤️',
        'doctor': '👨‍⚕️',
        'medical': '🏥',
        'legal': '⚖️',
        'research': '🔬',
        'default': '🔧',
    }

    name_lower = name.lower()
    for key, emoji in emoji_map.items():
        if key in name_lower:
            return emoji
    return emoji_map['default']


def parse_skill_md(content: str) -> tuple[Optional[dict], str]:
    """
    Parse SKILL.md content to extract frontmatter and body.

    Args:
        content: SKILL.md content

    Returns:
        Tuple of (frontmatter_dict, body_content)
    """
    if not content.startswith("---"):
        return None, content

    match = re.match(r"^---\n(.*?)\n---\n?(.*)", content, re.DOTALL)
    if not match:
        return None, content

    try:
        frontmatter = yaml.safe_load(match.group(1))
        body = match.group(2)
        return frontmatter or {}, body
    except yaml.YAMLError:
        return None, content


def generate_from_form_data(name: str, description: str, patterns: list[str], layer: str = 'vertical') -> str:
    """
    Generate SKILL.md from form data.

    Args:
        name: Skill name (kebab-case)
        description: Skill description
        patterns: List of patterns (inbox, database, scoring, etc.)
        layer: Layer (factory, horizontal, vertical)

    Returns:
        SKILL.md content
    """
    emoji = get_emoji(name)
    display_name = name.replace('-', ' ').title()

    frontmatter = {
        'name': name,
        'description': description or f'{display_name} skill with {", ".join(patterns)} patterns.',
        'layer': layer,
        'patterns': patterns,
    }

    frontmatter_yaml = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).strip()

    content = f"""---
{frontmatter_yaml}
---

# {emoji} {display_name}

{description or f'A Claude skill for {display_name.lower()}.'}

## 🌟 Key Capabilities
"""

    # Add capabilities based on patterns
    cap_num = 1
    if 'inbox' in patterns:
        content += f"{cap_num}. **Apple Notes Inbox**: Add items to \"{emoji} {display_name} Inbox\" note\n"
        cap_num += 1
    if 'database' in patterns:
        content += f"{cap_num}. **YAML Database**: Persistent storage with stats tracking\n"
        cap_num += 1
    if 'scoring' in patterns:
        content += f"{cap_num}. **Scoring System**: Multi-dimensional scoring with tiers\n"
        cap_num += 1

    # Storage configuration
    content += f"""
## ⚙️ Storage Configuration

**User Data Location**: Configured in `src/lib/config/paths.py`
Default: `~/Projects/augur/{name}/`

```
{name}/
├── {name}.yaml           # Main database
├── config.yaml           # Local config overrides
└── output/               # Generated outputs
```

## 🚀 Commands

| Command | Action |
|---------|--------|
| `process {name.replace('-', ' ')}` | Process items from inbox |
| `show {name.replace('-', ' ')}` | Display current items |
| `search: [query]` | Find by keyword |
"""

    # Add inbox workflow if applicable
    if 'inbox' in patterns:
        content += f"""
## 📋 Workflow: Apple Notes Inbox

### Step 1: Read Inbox

```python
def process_inbox():
    note_content = get_note_content("{emoji} {display_name} Inbox")
    # Parse pending section
    # Process items
    # Update processed section
```

### Step 2: Process Items

For each item in inbox:
1. Validate/parse input
2. {'Score and classify' if 'scoring' in patterns else 'Process content'}
3. Save to database
4. Update Apple Note

### Step 3: Update Apple Note

Move processed items to Processed section with timestamp.
"""

    # Footer
    content += f"""
---

**Version**: 1.0.0
**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}
**Patterns**: {', '.join(patterns)}
"""

    return content


def generate_from_rag_analysis(
    name: str,
    domain: str,
    description: str,
    pillars: dict[str, Any],
    use_cases: list[str],
    rag_project_id: Optional[str] = None,
) -> str:
    """
    Generate SKILL.md from RAG analysis results.

    Args:
        name: Skill name (kebab-case)
        domain: Knowledge domain (e.g., 'medical', 'legal', 'research')
        description: Skill description
        pillars: Five Pillar mapping with relevance scores
        use_cases: List of use cases
        rag_project_id: Optional RAG project ID

    Returns:
        SKILL.md content
    """
    emoji = get_emoji(name)
    display_name = name.replace('-', ' ').title()

    # Determine relevant pillars
    relevant_pillars = [p for p, data in pillars.items() if data.get('relevance', 0) > 0.5]

    content = f"""---
name: {name}
description: {description}
domain: {domain}
pillars: {relevant_pillars}
rag_project_id: {rag_project_id or ''}
---

# {emoji} {display_name}

{description}

## 🌟 Key Capabilities

This skill operates on the **{domain}** domain, providing intelligent interfaces for:
"""

    # Add use cases
    for i, use_case in enumerate(use_cases[:5], 1):  # Limit to 5 use cases
        content += f"{i}. {use_case}\n"

    # Five Pillar Framework
    content += """
## 🏛️ Five Pillar Framework

This skill follows the Augur Five Pillar Framework:
"""

    pillar_descriptions = {
        'capture': 'Capture new domain-specific data',
        'analyze': 'Analyze domain data and patterns',
        'execute': 'Execute domain-specific actions',
        'recall': 'Recall domain knowledge from indexed documents',
        'grow': 'Grow domain knowledge from new data',
    }

    for pillar in relevant_pillars:
        if pillar in pillar_descriptions:
            content += f"- **{pillar.title()}**: {pillar_descriptions[pillar]}\n"

    # RAG Integration
    if rag_project_id:
        content += f"""
## 🔍 RAG Integration

This skill uses a RAG project to search and analyze documents:
- Project ID: `{rag_project_id}`
- Indexed documents provide knowledge base for domain operations
- Recall pillar queries indexed documents for relevant information
"""

    # Storage configuration
    content += f"""
## ⚙️ Storage Configuration

**User Data Location**: Configured in `src/lib/config/paths.py`
Default: `~/Projects/augur/{name}/`

```
{name}/
├── {name}.yaml           # Main database
├── config.yaml           # Local config overrides
└── output/               # Generated outputs
```

## 🚀 Commands

| Command | Action |
|---------|--------|
| `search {domain} [query]` | Search indexed documents |
| `analyze {domain} [topic]` | Analyze domain patterns |
| `execute {domain} [action]` | Execute domain-specific action |
"""

    # Footer
    content += f"""
---

**Version**: 1.0.0
**Last Updated**: {datetime.now().strftime('%Y-%m-%d')}
**Domain**: {domain}
**Pillars**: {', '.join(relevant_pillars)}
"""

    return content


def normalize_imported_skill_md(content: str, target_name: str) -> str:
    """
    Normalize imported SKILL.md to match Augur conventions.

    Args:
        content: Imported SKILL.md content
        target_name: Target skill name (kebab-case)

    Returns:
        Normalized SKILL.md content
    """
    frontmatter, body = parse_skill_md(content)

    if frontmatter is None:
        # No frontmatter, create one
        frontmatter = {}

    # Update name
    frontmatter['name'] = target_name

    # Ensure description exists
    if 'description' not in frontmatter:
        # Try to extract from body
        first_line = body.split('\n')[0] if body else ''
        frontmatter['description'] = (
            first_line[:100] if first_line else f'{target_name.replace("-", " ").title()} skill'
        )

    # Reconstruct SKILL.md
    frontmatter_yaml = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False)
    normalized = f"""---
{frontmatter_yaml}---

{body}
"""

    return normalized


def generate_skill_md(config: Dict[str, Any]) -> str:
    """
    Generate SKILL.md from configuration.

    Args:
        config: Configuration dict with one of:
            - source: 'form' or 'create' -> name, description, patterns, layer
            - source: 'import' -> content (imported SKILL.md), target_name
            - source: 'rag' or 'documents' -> name, domain, description, pillars, use_cases, rag_project_id

    Returns:
        SKILL.md content
    """
    source = config.get('source', 'form')

    if source in ('form', 'create'):
        return generate_from_form_data(
            name=config['name'],
            description=config.get('description', ''),
            patterns=config.get('patterns', []),
            layer=config.get('layer', 'vertical'),
        )

    elif source == 'import':
        content = config['content']
        target_name = config['target_name']
        return normalize_imported_skill_md(content, target_name)

    elif source == 'rag' or source == 'documents':
        return generate_from_rag_analysis(
            name=config['name'],
            domain=config['domain'],
            description=config['description'],
            pillars=config.get('pillars', {}),
            use_cases=config.get('use_cases', []),
            rag_project_id=config.get('rag_project_id'),
        )

    elif source == 'unified':
        # Unified uses form data structure + potentially other info
        # For now, map to form generation as it supports patterns
        return generate_from_form_data(
            name=config['name'],
            description=config.get('description', ''),
            patterns=config.get('patterns', []),
            layer=config.get('layer', 'vertical'),
        )

    else:
        raise ValueError(f"Unknown source type: {source}")
