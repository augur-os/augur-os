"""Route and page template generators for the comprehensive dashboard generator.

Generates TypeScript source code for API routes, service layers, dashboard pages,
and layout components.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import warnings

from .component_templates import entity_to_component_name


def generate_service_layer(
    skill_name: str,
    skill_title: str,
    data_folder: Optional[str],
    domain: Optional[str],
    entities: Optional[List[str]] = None,
) -> str:
    """Generate TypeScript service layer."""

    # Use default entities if none provided based on domain/patterns, or fallbacks
    if not entities:
        entities = ['items', 'categories']

    # Determine data folder path
    skill_const_name = skill_name.upper().replace('-', '_')
    if data_folder:
        data_dir_const = f"const {skill_const_name}_DATA_DIR = '{data_folder}';"
        data_dir_import = ""
    else:
        # Use default path construction
        data_dir_const = f"""const {skill_const_name}_DATA_DIR = path.join(
  process.env.AUGUR_ROOT || path.join(os.homedir(), 'Projects', 'augur'),
  '{skill_name}'
);"""
        data_dir_import = "import os from 'os';"

    entity_interfaces = []
    crud_functions = []
    data_properties = []

    for entity in entities:
        entity_singular = entity.rstrip('s') if entity.endswith('s') else entity
        capitalized = entity_to_component_name(entity_singular)
        capitalized_plural = entity_to_component_name(entity)

        # Interface
        entity_interfaces.append(f"""export interface {capitalized} {{
  id: string;
  name: string;
  date: string;
  notes?: string;
  createdAt?: string;
  updatedAt?: string;
}}""")

        data_properties.append(f"  {entity}: {capitalized}[];")

        # CRUD Functions

        # Get All
        crud_functions.append(f"""
export async function get{capitalized_plural}(): Promise<{capitalized}[]> {{
  const data = await getSkillData();
  return data.{entity};
}}
""")

        # Get One
        crud_functions.append(f"""
export async function get{capitalized}(id: string): Promise<{capitalized} | null> {{
  const data = await getSkillData();
  return data.{entity}.find(item => item.id === id) || null;
}}
""")

        # Create
        crud_functions.append(f"""
export async function create{capitalized}(item: Omit<{capitalized}, 'id'>): Promise<{capitalized}> {{
  const data = await getSkillData();
  const newItem: {capitalized} = {{
    ...item,
    id: Date.now().toString(),
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }};
  data.{entity}.unshift(newItem);
  await saveSkillData(data);
  return newItem;
}}
""")

        # Delete
        crud_functions.append(f"""
export async function delete{capitalized}(id: string): Promise<void> {{
  const data = await getSkillData();
  data.{entity} = data.{entity}.filter((i) => i.id !== id);
  await saveSkillData(data);
}}
""")

    interfaces_block = '\n\n'.join(entity_interfaces)
    crud_block = '\n'.join(crud_functions)

    data_interface = f"""export interface SkillData {{
{chr(10).join(data_properties)}
  lastUpdated?: string;
}}"""

    # Initial data construction
    initial_data_props = '\n        '.join([f"{e}: []," for e in entities])

    return f'''import fs from 'fs/promises';
import path from 'path';
import yaml from 'yaml';
{data_dir_import}

{data_dir_const}
const DATA_FILE = path.join({skill_const_name}_DATA_DIR, '{skill_name}.yaml');

{interfaces_block}

{data_interface}

async function ensureDataFile(): Promise<void> {{
  try {{
    await fs.mkdir({skill_const_name}_DATA_DIR, {{ recursive: true }});
    try {{
      await fs.access(DATA_FILE);
    }} catch {{
      const initialData: SkillData = {{
        {initial_data_props}
        lastUpdated: new Date().toISOString(),
      }};
      await fs.writeFile(DATA_FILE, yaml.stringify(initialData), 'utf8');
    }}
  }} catch (error) {{
    console.error('Failed to ensure data file:', error);
    throw error;
  }}
}}

// Internal helper to get all data
async function getSkillData(): Promise<SkillData> {{
  try {{
    await ensureDataFile();
    const content = await fs.readFile(DATA_FILE, 'utf8');
    const data = yaml.parse(content) as SkillData;
    return {{
      {initial_data_props}
      ...data,
    }};
  }} catch (error) {{
    console.error('Failed to read {skill_name} data:', error);
    return {{
      {initial_data_props}
    }};
  }}
}}

async function saveSkillData(data: SkillData): Promise<void> {{
  try {{
    await ensureDataFile();
    const dataToSave = {{
      ...data,
      lastUpdated: new Date().toISOString(),
    }};
    await fs.writeFile(DATA_FILE, yaml.stringify(dataToSave), 'utf8');
  }} catch (error) {{
    console.error('Failed to save {skill_name} data:', error);
    throw error;
  }}
}}

{crud_block}
'''


def generate_data_api_route(skill_name: str) -> str:
    """Generate main data API route using MCP-first pattern (ADR-266)."""
    return f'''import {{ createAPIRoute }} from '@/lib/mcp/createAPIRoute';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export const GET = createAPIRoute({{
  toolName: '{skill_name}-get-data',
  extractParams: async () => ({{}}),
}});
'''


def generate_entity_api_route(skill_name: str, entity: str) -> str:
    """Generate API route for an entity."""
    entity_singular = entity.rstrip('s') if entity.endswith('s') else entity
    capitalized_singular = entity_to_component_name(entity_singular)

    create_func = f'add{capitalized_singular}'
    delete_func = f'delete{capitalized_singular}'
    get_func = f'get{entity_to_component_name(entity)}'

    return f'''import {{ createAPIRoute }} from '@/lib/mcp/createAPIRoute';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export const GET = createAPIRoute({{
  toolName: '{skill_name}-get-{entity}',
  extractParams: async () => ({{}}),
}});

export const POST = createAPIRoute({{
  toolName: '{skill_name}-create-{entity_singular}',
  extractParams: async (req) => {{
    const body = await req.json();
    return body;
  }},
}});

export const DELETE = createAPIRoute({{
  toolName: '{skill_name}-delete-{entity_singular}',
  extractParams: async (req) => {{
    const {{ searchParams }} = new URL(req.url);
    const id = searchParams.get('id');
    return {{ id }};
  }},
}});
'''


def generate_rag_search_route(skill_name: str, rag_project_id: str) -> str:
    """Generate RAG search API route using MCP-first pattern (ADR-266)."""
    return f'''import {{ createAPIRoute }} from '@/lib/mcp/createAPIRoute';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export const POST = createAPIRoute({{
  toolName: 'rag-search',
  extractParams: async (req) => {{
    const {{ query }} = await req.json();
    return {{ project_id: '{rag_project_id}', query }};
  }},
}});
'''


def generate_enhanced_dashboard_page(
    skill_name: str,
    skill_title: str,
    layer: str,
    patterns: List[str],
    entities: List[str],
    rag_project_id: Optional[str],
) -> str:
    """Generate enhanced dashboard page with EditableMasonryGrid."""
    component_name = skill_title.replace(' ', '').replace('-', '')

    # Generate imports
    imports = [
        'import DashboardWidget from \'@/features/components/DashboardWidget\';',
        'import DisabledSkillPage from \'@/components/DisabledSkillPage\';',
        'import { readDisabledSkills } from \'@/lib/server/skillsState\';',
        'import EditableMasonryGrid from \'@/features/components/EditableMasonryGrid\';',
    ]

    # Generate component imports
    component_imports = []
    widget_blocks = []
    widget_items = []

    if 'rag' in patterns and rag_project_id:
        search_component = skill_title.replace(' ', '') + 'SearchPanel'
        component_imports.append(f"import {search_component} from './{search_component}';")
        widget_blocks.append("    'search': { width: 'full' },")
        widget_items.append(
            f'''      <DashboardWidget key="search" title="Knowledge Search" icon={{Search}} fillHeight={{false}}>
        <{search_component} />
      </DashboardWidget>'''
        )

    for entity in entities:
        component_name_entity = entity_to_component_name(entity)
        component_imports.append(f"import {component_name_entity}Panel from './{component_name_entity}Panel';")
        widget_blocks.append(f"    '{entity}': {{ width: 'half' }},")
        widget_items.append(
            f'''      <DashboardWidget key="{entity}" title="{component_name_entity}" icon={{Package}} fillHeight={{false}}>
        <{component_name_entity}Panel />
      </DashboardWidget>'''
        )

    # Add icon imports
    icon_imports = ['Search', 'Package']
    if 'rag' in patterns:
        icon_imports.append('Search')
    imports.append(f"import {{ {', '.join(set(icon_imports))} }} from 'lucide-react';")

    all_imports = '\n'.join(imports + component_imports)

    return f'''{all_imports}

export default async function {component_name}Page() {{
  const disabled = await readDisabledSkills();
  if (disabled.has('{skill_name}')) {{
    return <DisabledSkillPage skill="{skill_name}" title="{skill_title}" />;
  }}

  return (
    <EditableMasonryGrid
      className="dashboard-grid"
      storageKey="{skill_name}"
      defaultBlocks={{
{chr(10).join(widget_blocks)}
      }}
    >
{chr(10).join(widget_items)}
    </EditableMasonryGrid>
  );
}}
'''


def generate_layout(skill_name: str, skill_title: str, layer: str) -> str:
    """Generate layout component with DEV-mode conditional productization tab."""
    parent_route = 'lifestyle' if layer == 'vertical' else 'hands'
    component_name = skill_title.replace(' ', '').replace('-', '')
    base_path = f'/{parent_route}/{skill_name}'

    return f''''use client';

import UnifiedHubTabs from '@/components/UnifiedHubTabs';
import {{ useModeStore }} from '@/lib/stores/modeStore';
import {{ LayoutDashboard }} from 'lucide-react';

// Tabs configuration
const baseTabs = [
  {{ id: 'overview', label: 'Overview', icon: 'LayoutDashboard', href: '{base_path}' }},
];

// Productization Plan tab (DEV mode only)
const PRODUCTIZATION_TAB = {{
  id: 'productization-plan',
  label: 'Productization Plan',
  icon: 'Sparkles',
  href: '{base_path}/productization-plan',
}};

export default function {component_name}Layout({{
  children,
}}: {{
  children: React.ReactNode;
}}) {{
  const {{ mode }} = useModeStore();
  const isDev = mode === 'development';

  // Add productization tab in DEV mode
  const visibleTabs = isDev ? [...baseTabs, PRODUCTIZATION_TAB] : baseTabs;

  return (
    <div className="space-y-6">
      <header className="page-header">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-[var(--accent-secondary)]/20 flex items-center justify-center">
            <LayoutDashboard className="w-6 h-6 text-[var(--accent-secondary)]" />
          </div>
          <div>
            <h1 className="page-title">{skill_title}</h1>
            <p className="page-subtitle mt-1">{layer.capitalize()} layer dashboard</p>
          </div>
        </div>
      </header>

      <UnifiedHubTabs tabs={{visibleTabs}} />

      <div>{{children}}</div>
    </div>
  );
}}
'''


def update_parent_layout(layout_path: Path, skill_name: str, skill_title: str) -> None:
    """Update parent layout to include skill tab."""
    try:
        content = layout_path.read_text(encoding='utf-8')
        # Simple approach: check if tab already exists
        if skill_name not in content:
            # Find tabs array and add new tab
            # This is a simplified implementation
            # In production, would use AST parsing
            return
    except Exception as e:
        warnings.warn(
            f"Unable to update parent layout {layout_path}: {e}",
            RuntimeWarning,
            stacklevel=2,
        )


def generate_productization_plan_page(
    app_dir: Path,
    skill_name: str,
    skill_title: str,
) -> bool:
    """Generate the productization-plan subpage for a dashboard.

    Args:
        app_dir: The dashboard app directory (e.g., app/lifestyle/my-skill)
        skill_name: Skill name (kebab-case)
        skill_title: Skill display title

    Returns:
        True if page was generated successfully
    """
    try:
        import sys

        def _out(*args: object, **kwargs: object) -> None:
            sep = kwargs.get("sep", " ")
            end = kwargs.get("end", "\n")
            file = kwargs.get("file", sys.stdout)
            file.write(sep.join(str(arg) for arg in args) + str(end))

        # Create productization-plan directory
        plan_dir = app_dir / 'productization-plan'
        plan_dir.mkdir(parents=True, exist_ok=True)

        # Generate page.tsx
        page_content = f'''import ProductizationPlanView from '@/components/ProductizationPlanView';

export default function ProductizationPlanPage() {{
  return (
    <ProductizationPlanView
      skillSlug="{skill_name}"
      skillTitle="{skill_title}"
    />
  );
}}
'''
        page_path = plan_dir / 'page.tsx'
        page_path.write_text(page_content, encoding='utf-8')

        return True
    except Exception as e:
        import sys
        sys.stdout.write(f"Failed to generate productization plan page: {e}\n")
        return False
