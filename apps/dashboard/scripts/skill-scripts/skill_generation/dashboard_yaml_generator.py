"""
Dashboard YAML Generator

Generates dashboard.yaml configuration files for skills based on patterns and pillars.
This enables config-driven UI rendering via HubRenderer, supporting both monorepo
and starter template scenarios.

Part of ADR-012: Community Package Extraction
"""

from typing import Any
import yaml


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Icon mapping based on layer and patterns
LAYER_ICONS = {
    'vertical': 'Sparkles',
    'horizontal': 'Layers',
    'factory': 'Factory',
}

PATTERN_ICONS = {
    'inbox': 'Inbox',
    'database': 'Database',
    'dashboard': 'LayoutDashboard',
    'scheduler': 'Clock',
    'rag': 'Search',
    'api': 'Globe',
    'scoring': 'BarChart3',
}

# Color themes for different contexts
COLORS = ['blue', 'green', 'amber', 'purple', 'rose', 'cyan', 'orange', 'indigo']


def generate_dashboard_yaml(
    skill_name: str,
    skill_title: str,
    layer: str,
    patterns: list[str],
    pillars: dict[str, Any] | None = None,
    domain: str | None = None,
    description: str | None = None,
) -> str:
    """
    Generate dashboard.yaml content from skill configuration.

    Args:
        skill_name: Skill slug (kebab-case)
        skill_title: Display title
        layer: Layer (factory, horizontal, vertical)
        patterns: List of patterns (inbox, database, dashboard, scheduler, rag)
        pillars: Optional Five Pillar mapping (capture, analyze, execute, recall, grow)
        domain: Optional domain name for entity inference
        description: Optional description/subtitle

    Returns:
        YAML string for dashboard.yaml
    """
    patterns = patterns or ['database']
    pillars = pillars or {}

    # Build hub definition
    hub = _build_hub(skill_name, skill_title, layer, description)

    # Build tabs based on patterns
    tabs = _build_tabs(skill_name, skill_title, patterns, pillars, domain)

    # Build modals based on pillars
    modals = _build_modals(skill_name, pillars, patterns, domain)

    # Build action buttons
    actions = _build_actions(skill_name, modals)

    # Assemble config
    config: dict[str, Any] = {
        'version': '1.0',
        'hub': hub,
        'tabs': tabs,
    }

    if modals:
        config['modals'] = modals

    if actions:
        config['actions'] = actions

    # Custom YAML representer for clean output
    yaml.add_representer(str, _str_representer)

    return yaml.dump(
        config,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )


def _str_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    """Use literal style for multiline strings, plain style otherwise."""
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


def _build_hub(
    skill_name: str,
    skill_title: str,
    layer: str,
    description: str | None,
) -> dict[str, Any]:
    """Build hub definition."""
    icon = LAYER_ICONS.get(layer, 'Sparkles')

    # Map layer to color theme
    color_map = {
        'vertical': ('violet', 'purple'),
        'horizontal': ('blue', 'cyan'),
        'factory': ('amber', 'orange'),
    }
    icon_bg, icon_color = color_map.get(layer, ('violet', 'purple'))

    return {
        'id': skill_name,
        'title': skill_title,
        'subtitle': description or f'Manage your {skill_title.lower()}',
        'icon': icon,
        'iconBg': f'{icon_bg}-500/20',
        'iconColor': f'{icon_color}-400',
    }


def _build_tabs(
    skill_name: str,
    skill_title: str,
    patterns: list[str],
    pillars: dict[str, Any],
    domain: str | None,
) -> list[dict[str, Any]]:
    """Build tab definitions based on patterns."""
    tabs = []

    # Always add Overview tab first
    overview_sections = _build_overview_sections(skill_name, patterns, pillars)
    tabs.append(
        {
            'id': 'overview',
            'label': 'Overview',
            'icon': 'LayoutDashboard',
            'default': True,
            'sections': overview_sections,
        }
    )

    # Pattern-specific tabs
    if 'inbox' in patterns:
        tabs.append(_build_inbox_tab(skill_name))

    if 'database' in patterns:
        tabs.append(_build_database_tab(skill_name, domain))

    if 'scheduler' in patterns:
        tabs.append(_build_scheduler_tab(skill_name))

    if 'rag' in patterns:
        tabs.append(_build_rag_tab(skill_name))

    return tabs


def _build_overview_sections(
    skill_name: str,
    patterns: list[str],
    pillars: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build overview tab sections."""
    sections: list[dict[str, Any]] = []

    # Metrics grid with KPIs based on patterns
    metrics = []
    color_idx = 0

    if 'inbox' in patterns:
        metrics.append(
            {
                'id': 'inbox_count',
                'label': 'Inbox Items',
                'source': f'mcp://augur/{skill_name.replace("-", "_")}_get_inbox',
                'transform': 'data.length',
                'icon': 'Inbox',
                'color': COLORS[color_idx % len(COLORS)],
            }
        )
        color_idx += 1

    if 'database' in patterns:
        metrics.append(
            {
                'id': 'total_items',
                'label': 'Total Items',
                'source': f'mcp://augur/{skill_name.replace("-", "_")}_list',
                'transform': 'data.length',
                'icon': 'Database',
                'color': COLORS[color_idx % len(COLORS)],
            }
        )
        color_idx += 1

    if 'scheduler' in patterns:
        metrics.append(
            {
                'id': 'scheduled_tasks',
                'label': 'Scheduled',
                'source': f'mcp://augur/{skill_name.replace("-", "_")}_get_schedule',
                'transform': 'data.length',
                'icon': 'Clock',
                'color': COLORS[color_idx % len(COLORS)],
            }
        )
        color_idx += 1

    if 'rag' in patterns:
        metrics.append(
            {
                'id': 'indexed_docs',
                'label': 'Documents',
                'source': f'mcp://augur/{skill_name.replace("-", "_")}_rag_stats',
                'transform': 'data.document_count || 0',
                'icon': 'FileText',
                'color': COLORS[color_idx % len(COLORS)],
            }
        )
        color_idx += 1

    # Ensure at least one metric
    if not metrics:
        metrics.append(
            {
                'id': 'status',
                'label': 'Status',
                'source': 'static:{"value": "Active"}',
                'transform': 'data.value',
                'icon': 'CheckCircle',
                'color': 'green',
            }
        )

    sections.append(
        {
            'type': 'metrics-grid',
            'columns': min(4, len(metrics)),
            'metrics': metrics,
        }
    )

    # Add recent items table if database pattern
    if 'database' in patterns:
        sections.append(
            {
                'type': 'data-table',
                'title': 'Recent Items',
                'source': f'mcp://augur/{skill_name.replace("-", "_")}_list',
                'emptyMessage': 'No items yet',
                'columns': [
                    {'field': 'name', 'label': 'Name', 'sortable': True},
                    {'field': 'created_at', 'label': 'Created', 'type': 'relative-time', 'sortable': True},
                    {'field': 'status', 'label': 'Status', 'type': 'status'},
                ],
                'actions': [
                    {'type': 'view', 'icon': 'Eye'},
                    {
                        'type': 'delete',
                        'icon': 'Trash2',
                        'tool': f'mcp://augur/{skill_name.replace("-", "_")}_delete',
                        'confirmMessage': 'Delete this item?',
                    },
                ],
            }
        )

    # Add timeline if scheduler pattern
    if 'scheduler' in patterns:
        sections.append(
            {
                'type': 'timeline',
                'title': 'Upcoming',
                'source': f'mcp://augur/{skill_name.replace("-", "_")}_get_schedule',
                'dateField': 'scheduled_at',
                'titleField': 'name',
                'descriptionField': 'description',
                'emptyMessage': 'Nothing scheduled',
            }
        )

    return sections


def _build_inbox_tab(skill_name: str) -> dict[str, Any]:
    """Build inbox tab."""
    tool_prefix = skill_name.replace('-', '_')
    return {
        'id': 'inbox',
        'label': 'Inbox',
        'icon': 'Inbox',
        'sections': [
            {
                'type': 'data-table',
                'title': 'Inbox Items',
                'source': f'mcp://augur/{tool_prefix}_get_inbox',
                'emptyMessage': 'Inbox is empty',
                'columns': [
                    {'field': 'title', 'label': 'Title', 'sortable': True},
                    {'field': 'source', 'label': 'Source'},
                    {'field': 'received_at', 'label': 'Received', 'type': 'relative-time', 'sortable': True},
                    {'field': 'status', 'label': 'Status', 'type': 'status'},
                ],
                'actions': [
                    {
                        'type': 'custom',
                        'label': 'Process',
                        'icon': 'Play',
                        'tool': f'mcp://augur/{tool_prefix}_process',
                    },
                    {
                        'type': 'delete',
                        'icon': 'Trash2',
                        'tool': f'mcp://augur/{tool_prefix}_archive',
                        'confirmMessage': 'Archive this item?',
                    },
                ],
            },
        ],
    }


def _build_database_tab(skill_name: str, domain: str | None) -> dict[str, Any]:
    """Build database/items tab."""
    tool_prefix = skill_name.replace('-', '_')
    entity_name = domain or 'Items'

    return {
        'id': 'items',
        'label': entity_name,
        'icon': 'Database',
        'sections': [
            {
                'type': 'data-table',
                'title': f'All {entity_name}',
                'source': f'mcp://augur/{tool_prefix}_list',
                'emptyMessage': f'No {entity_name.lower()} found',
                'pageSize': 20,
                'columns': [
                    {'field': 'name', 'label': 'Name', 'sortable': True},
                    {'field': 'description', 'label': 'Description'},
                    {'field': 'created_at', 'label': 'Created', 'type': 'date', 'sortable': True},
                    {'field': 'updated_at', 'label': 'Updated', 'type': 'relative-time', 'sortable': True},
                ],
                'actions': [
                    {'type': 'edit', 'icon': 'Edit', 'modal': f'edit-{skill_name}'},
                    {
                        'type': 'delete',
                        'icon': 'Trash2',
                        'tool': f'mcp://augur/{tool_prefix}_delete',
                        'confirmMessage': f'Delete this {entity_name.lower()[:-1] if entity_name.endswith("s") else entity_name.lower()}?',
                    },
                ],
            },
        ],
    }


def _build_scheduler_tab(skill_name: str) -> dict[str, Any]:
    """Build scheduler tab."""
    tool_prefix = skill_name.replace('-', '_')
    return {
        'id': 'schedule',
        'label': 'Schedule',
        'icon': 'Calendar',
        'sections': [
            {
                'type': 'timeline',
                'title': 'Scheduled Tasks',
                'source': f'mcp://augur/{tool_prefix}_get_schedule',
                'dateField': 'scheduled_at',
                'titleField': 'name',
                'descriptionField': 'description',
                'typeField': 'type',
                'emptyMessage': 'No scheduled tasks',
            },
        ],
    }


def _build_rag_tab(skill_name: str) -> dict[str, Any]:
    """Build RAG/search tab."""
    tool_prefix = skill_name.replace('-', '_')
    return {
        'id': 'search',
        'label': 'Search',
        'icon': 'Search',
        'sections': [
            {
                'type': 'form',
                'title': 'Search Documents',
                'action': f'mcp://augur/{tool_prefix}_rag_search',
                'fields': [
                    {
                        'name': 'query',
                        'label': 'Search Query',
                        'type': 'text',
                        'required': True,
                        'placeholder': 'Enter search terms...',
                    },
                    {'name': 'limit', 'label': 'Results Limit', 'type': 'number', 'defaultValue': 10},
                ],
                'submitLabel': 'Search',
            },
            {
                'type': 'data-table',
                'title': 'Indexed Documents',
                'source': f'mcp://augur/{tool_prefix}_rag_list',
                'emptyMessage': 'No documents indexed',
                'columns': [
                    {'field': 'filename', 'label': 'File', 'sortable': True},
                    {'field': 'chunk_count', 'label': 'Chunks', 'type': 'number'},
                    {'field': 'indexed_at', 'label': 'Indexed', 'type': 'relative-time', 'sortable': True},
                ],
            },
        ],
    }


def _build_modals(
    skill_name: str,
    pillars: dict[str, Any],
    patterns: list[str],
    domain: str | None,
) -> dict[str, Any]:
    """Build modal definitions based on pillars and patterns."""
    modals: dict[str, Any] = {}
    tool_prefix = skill_name.replace('-', '_')
    entity_name = domain or 'Item'

    # If we have capture pillar, build modals from its tools
    if 'capture' in pillars:
        for tool in pillars.get('capture', []):
            tool_name = tool.get('name', '').replace('_', '-')
            if tool_name:
                modals[f'add-{tool_name}'] = {
                    'title': f'Add {tool_name.replace("-", " ").title()}',
                    'description': tool.get('description', ''),
                    'submitTool': f'mcp://augur/{tool.get("name", "")}',
                    'submitLabel': 'Add',
                    'fields': _infer_fields_from_tool(tool),
                }
    else:
        # Default add modal for database pattern
        if 'database' in patterns:
            modals[f'add-{skill_name}'] = {
                'title': f'Add {entity_name}',
                'description': f'Create a new {entity_name.lower()}',
                'submitTool': f'mcp://augur/{tool_prefix}_create',
                'submitLabel': f'Add {entity_name}',
                'fields': [
                    {
                        'name': 'name',
                        'label': 'Name',
                        'type': 'text',
                        'required': True,
                        'placeholder': f'Enter {entity_name.lower()} name',
                    },
                    {
                        'name': 'description',
                        'label': 'Description',
                        'type': 'textarea',
                        'placeholder': 'Optional description...',
                    },
                ],
            }

            # Edit modal
            modals[f'edit-{skill_name}'] = {
                'title': f'Edit {entity_name}',
                'description': f'Update {entity_name.lower()} details',
                'submitTool': f'mcp://augur/{tool_prefix}_update',
                'submitLabel': 'Save Changes',
                'fields': [
                    {'name': 'name', 'label': 'Name', 'type': 'text', 'required': True},
                    {'name': 'description', 'label': 'Description', 'type': 'textarea'},
                ],
            }

    return modals


def _build_actions(skill_name: str, modals: dict[str, Any]) -> list[dict[str, Any]]:
    """Build action button definitions."""
    actions = []

    # Add primary action button for the first "add" modal
    for modal_id in modals:
        if modal_id.startswith('add-'):
            actions.append(
                {
                    'id': modal_id,
                    'label': modals[modal_id].get('title', 'Add'),
                    'icon': 'Plus',
                    'type': 'modal',
                    'modal': modal_id,
                    'variant': 'default',
                }
            )
            break  # Only add one primary action

    return actions


def _infer_fields_from_tool(tool: dict[str, Any]) -> list[dict[str, Any]]:
    """Infer form fields from tool schema."""
    fields = []

    # If tool has input schema, use it
    input_schema = tool.get('input_schema', {})
    properties = input_schema.get('properties', {})
    required = input_schema.get('required', [])

    for field_name, field_def in properties.items():
        field_type = field_def.get('type', 'string')

        # Map JSON schema types to form field types
        type_map = {
            'string': 'text',
            'integer': 'number',
            'number': 'number',
            'boolean': 'checkbox',
            'array': 'multiselect',
        }

        form_type = type_map.get(field_type, 'text')

        # Check for enum (select)
        if 'enum' in field_def:
            form_type = 'select'

        field: dict[str, Any] = {
            'name': field_name,
            'label': field_name.replace('_', ' ').title(),
            'type': form_type,
        }

        if field_name in required:
            field['required'] = True

        if 'description' in field_def:
            field['placeholder'] = field_def['description']

        if 'enum' in field_def:
            field['options'] = [{'value': v, 'label': v.replace('_', ' ').title()} for v in field_def['enum']]

        if 'default' in field_def:
            field['defaultValue'] = field_def['default']

        fields.append(field)

    # Default fields if no schema
    if not fields:
        fields = [
            {'name': 'name', 'label': 'Name', 'type': 'text', 'required': True},
            {'name': 'value', 'label': 'Value', 'type': 'text'},
        ]

    return fields


# CLI entrypoint for testing
if __name__ == '__main__':
    import sys

    # Example usage
    if len(sys.argv) > 1:
        skill_name = sys.argv[1]
        patterns = sys.argv[2].split(',') if len(sys.argv) > 2 else ['database']
        layer = sys.argv[3] if len(sys.argv) > 3 else 'vertical'
    else:
        skill_name = 'expense-tracker'
        patterns = ['inbox', 'database']
        layer = 'vertical'

    yaml_content = generate_dashboard_yaml(
        skill_name=skill_name,
        skill_title=skill_name.replace('-', ' ').title(),
        layer=layer,
        patterns=patterns,
        description=f'Manage your {skill_name.replace("-", " ")}',
    )

    _out(yaml_content)
