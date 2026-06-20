"""Import code generator: blueprint.yaml -> plugin files (ADR-086 Stage 3).

Input:  blueprint dict (from blueprint_generator.py)
Output: Generated plugin files written to disk:
  - SKILL.md
  - dashboard.yaml
  - dashboard/page.tsx
  - dashboard/layout.tsx
  - dashboard/loading.tsx
  - dashboard/tabs/OverviewTab.tsx
  - dashboard/tabs/<TabId>Tab.tsx  (per non-overview tab)
  - api/health/route.ts
  - api/data/route.ts  (if rendered files exist)
  - data/connections.yaml  (initial connection config)

Generated pages import ExternalDataCards + FileActions from @/components/bridge/.
"""

from __future__ import annotations

import re
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Map of tab_type -> component import patterns
TAB_TYPE_IMPORTS: dict[str, str] = {
    "table": "ExternalDataCards",
    "time-series": "ExternalDataCards",
    "folder-browser": "FileActions",
    "rendered-content": "",
    "overview": "ExternalDataCards",
}


# ---------------------------------------------------------------------------
# CodeGenerator
# ---------------------------------------------------------------------------


class ImportCodeGenerator:
    """Generate a complete plugin from a blueprint dict.

    Args:
        blueprint: Blueprint dict (matching blueprint.schema.yaml).
        project_root: Project root directory. If None, resolved from this file.
    """

    def __init__(
        self,
        blueprint: dict[str, Any],
        *,
        project_root: Path | None = None,
    ) -> None:
        self.bp = blueprint
        self.hub = blueprint["hub"]
        self.hub_id: str = self.hub["id"]
        self.hub_title: str = self.hub["title"]
        # Track 3b: `bundle` here is the plugin BUNDLE name (e.g. "lifestyle",
        # "ai", "dev"), NOT a hub id from config/system/hubs.yaml. Bundles
        # group skills for distribution; hubs are dashboard navigation
        # surfaces. The "lifestyle" default is the user-facing-personal
        # plugin bundle.
        self.bundle: str = self.hub.get("bundle", "lifestyle")
        self.icon: str = self.hub.get("icon", "LayoutDashboard")

        if project_root is None:
            # Walk up from this file to find project root
            project_root = Path(__file__).resolve()
            while project_root.name != "plugins" and project_root != project_root.parent:
                project_root = project_root.parent
            project_root = project_root.parent  # one above "plugins"
        self.project_root = project_root

    @property
    def skill_dir(self) -> Path:
        """Path to the generated skill directory."""
        return self.project_root / "plugins" / self.bundle / "skills" / self.hub_id

    @property
    def component_name(self) -> str:
        """PascalCase component name derived from hub_id."""
        return re.sub(r"(?:^|[-_])(\w)", lambda m: m.group(1).upper(), self.hub_id)

    def generate(self) -> dict[str, str]:
        """Generate all plugin files.

        Returns:
            Dict mapping relative path -> file content (for logging/testing).
            Files are also written to disk.
        """
        files: dict[str, str] = {}

        files["SKILL.md"] = self._gen_skill_md()
        files["dashboard.yaml"] = self._gen_dashboard_yaml()
        files["dashboard/page.tsx"] = self._gen_page_tsx()
        files["dashboard/layout.tsx"] = self._gen_layout_tsx()
        files["dashboard/loading.tsx"] = self._gen_loading_tsx()

        # Generate tab files
        for tab in self.bp.get("tabs", []):
            tab_id = tab["id"]
            tab_file = f"dashboard/tabs/{_pascal_case(tab_id)}Tab.tsx"
            files[tab_file] = self._gen_tab_tsx(tab)

        # API routes
        files["api/health/route.ts"] = self._gen_health_route()

        if self.bp.get("rendered_files"):
            files["api/data/route.ts"] = self._gen_data_route()

        # connections.yaml (initial draft)
        files["data/connections.yaml"] = self._gen_connections_yaml()

        # Write to disk
        self._write_files(files)

        return files

    # ------------------------------------------------------------------
    # File generators
    # ------------------------------------------------------------------

    def _gen_skill_md(self) -> str:
        """Generate SKILL.md."""
        tabs_table = ""
        for tab in self.bp.get("tabs", []):
            tabs_table += f"| `/{self.hub_id}/{tab['id']}` | {tab['label']} |\n"

        actions_table = ""
        for action in self.bp.get("actions", []):
            actions_table += (
                f"| `{action['id']}` | {action.get('dispatch', action.get('flow', 'fire'))} | {action.get('description', action['label'])} |\n"
            )

        source = self.bp.get("source", {})

        return textwrap.dedent(f"""\
            ---
            name: {self.hub_id}
            version: 1.0.0
            description: {self.hub.get('subtitle', f'{self.hub_title} dashboard')}

            triggers:
              - dashboard page load
              - manual action

            category: {self.hub.get('category', 'personal')}
            mode: all
            ---

            # {self.hub_title}

            Auto-generated by `/import` from external data at `{source.get('path', 'N/A')}`.

            ## Pages
            | Route | Tab |
            |-------|-----|
            {tabs_table}
            ## Actions
            | Action | Flow | Description |
            |--------|------|-------------|
            {actions_table}
            ## External Data Source
            - **Type**: {source.get('type', 'folder')}
            - **Path**: `{source.get('path', 'N/A')}`

            ## Storage
            `plugins/{self.bundle}/skills/{self.hub_id}/data/`
        """)

    def _gen_dashboard_yaml(self) -> str:
        """Generate dashboard.yaml."""
        lines = [
            f"# {self.hub_title} Dashboard Configuration",
            f"# Auto-generated by /import on {datetime.now().strftime('%Y-%m-%d')}",
            'version: "1.0"',
            "",
            "hub:",
            f"  id: {self.hub_id}",
            f"  title: {self.hub_title}",
            f"  subtitle: {self.hub.get('subtitle', '')}",
            f"  icon: {self.icon}",
            f"  category: {self.hub.get('category', 'personal')}",
            "",
            f"data_dir: {self.hub_id}",
            "mode: all",
            "",
            "tabs:",
        ]

        for tab in self.bp.get("tabs", []):
            lines.append(f"  - id: {tab['id']}")
            lines.append(f"    label: {tab['label']}")
            lines.append(f"    icon: {tab.get('icon', 'LayoutDashboard')}")
            if tab.get("default"):
                lines.append("    default: true")
            if tab["id"] != "overview":
                lines.append(f"    href: /{self.hub_id}/{tab['id']}")
            lines.append("")

        if self.bp.get("actions"):
            lines.append("actions:")
            for action in self.bp["actions"]:
                lines.append(f"  - id: {action['id']}")
                lines.append(f"    label: {action['label']}")
                lines.append(f"    description: {action.get('description', '')}")
                lines.append(f"    icon: {action.get('icon', 'Zap')}")
                lines.append(f"    dispatch: {action.get('dispatch', action.get('flow', 'fire'))}")
                lines.append("")

        return "\n".join(lines) + "\n"

    def _gen_page_tsx(self) -> str:
        """Generate dashboard/page.tsx with tab routing."""
        tabs = self.bp.get("tabs", [])
        imports: list[str] = []
        conditions: list[str] = []

        for tab in tabs:
            tab_comp = f"{_pascal_case(tab['id'])}Tab"
            imports.append(f"import {tab_comp} from './tabs/{tab_comp}';")

            if tab.get("default") or tab["id"] == "overview":
                conditions.append(f"      {{tab === '{tab['id']}' && <{tab_comp} />}}")
            else:
                conditions.append(f"      {{tab === '{tab['id']}' && <{tab_comp} />}}")

        imports_str = "\n".join(imports)
        conditions_str = "\n".join(conditions)

        return textwrap.dedent(f"""\
            'use client';

            import {{ useSearchParams }} from 'next/navigation';
            {imports_str}

            export default function {self.component_name}Page() {{
              const searchParams = useSearchParams();
              const tab = searchParams.get('tab') || 'overview';

              return (
                <>
            {conditions_str}
                </>
              );
            }}
        """)

    def _gen_layout_tsx(self) -> str:
        """Generate dashboard/layout.tsx."""
        return textwrap.dedent(f"""\
            import UnifiedHubTabs from '@/components/UnifiedHubTabs';
            import {{ getHubConfig }} from '@/lib/tabs/registry';
            import {{ {self.icon} }} from 'lucide-react';

            const hub = getHubConfig('{self.hub_id}');

            export default function {self.component_name}Layout({{
              children,
            }}: {{
              children: React.ReactNode;
            }}) {{
              if (!hub) {{
                return (
                  <div className="space-y-6">
                    <div className="text-red-500">{self.hub_title} hub configuration not found</div>
                    {{children}}
                  </div>
                );
              }}

              return (
                <div className="space-y-6">
                  <header className="page-header">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center">
                        <{self.icon} className="w-6 h-6 text-blue-400" />
                      </div>
                      <div>
                        <h1 className="page-title from-blue-400 to-cyan-400">{{hub.title}}</h1>
                        <p className="page-subtitle mt-1">{{hub.subtitle}}</p>
                      </div>
                    </div>
                  </header>

                  <UnifiedHubTabs tabs={{hub.tabs}} />

                  <div>{{children}}</div>
                </div>
              );
            }}
        """)

    def _gen_loading_tsx(self) -> str:
        """Generate dashboard/loading.tsx."""
        return textwrap.dedent(f"""\
            'use client';

            import {{ Skeleton }} from '@/components/ui/Skeleton';
            import DashboardWidget from '@/features/components/DashboardWidget';
            import {{ {self.icon} }} from 'lucide-react';

            export default function Loading() {{
              return (
                <DashboardWidget title="{self.hub_title}" icon={{{self.icon}}} fillHeight={{false}}>
                  <div className="space-y-4 animate-in fade-in duration-300">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {{[...Array(3)].map((_, i) => (
                        <div key={{i}} className="p-4 bg-[var(--bg-card)] rounded-lg">
                          <Skeleton className="h-8 w-16 mb-2" />
                          <Skeleton className="h-4 w-24" />
                        </div>
                      ))}}
                    </div>
                    <div className="space-y-2">
                      {{[...Array(5)].map((_, i) => (
                        <div key={{i}} className="flex items-center gap-4 p-3 bg-[var(--bg-card)] rounded-lg">
                          <Skeleton className="w-5 h-5 rounded" />
                          <Skeleton className="h-4 flex-1 max-w-xs" />
                          <Skeleton className="h-4 w-16" />
                        </div>
                      ))}}
                    </div>
                  </div>
                </DashboardWidget>
              );
            }}
        """)

    def _gen_tab_tsx(self, tab: dict[str, Any]) -> str:
        """Generate a tab component file."""
        tab_type = tab.get("tab_type", "overview")

        if tab_type == "overview":
            return self._gen_overview_tab(tab)
        elif tab_type == "table":
            return self._gen_table_tab(tab)
        elif tab_type == "time-series":
            return self._gen_time_series_tab(tab)
        elif tab_type == "folder-browser":
            return self._gen_folder_browser_tab(tab)
        elif tab_type == "rendered-content":
            return self._gen_rendered_content_tab(tab)
        else:
            return self._gen_default_tab(tab)

    def _gen_overview_tab(self, tab: dict[str, Any]) -> str:
        """Generate OverviewTab with stat cards and external data."""
        stat_cards = self.bp.get("stat_cards", [])

        stat_card_jsx = ""
        if stat_cards:
            cards = []
            for sc in stat_cards[:6]:
                cards.append(textwrap.dedent(f"""\
                    <DashboardWidget title="{sc['label']}" icon={{BarChart3}} fillHeight={{false}}>
                      <div className="p-4">
                        <div className="text-3xl font-bold text-neutral-100">--</div>
                        <div className="text-sm text-neutral-500">{sc['label']}</div>
                      </div>
                    </DashboardWidget>"""))
            stat_card_jsx = "\n          ".join(cards)

        return textwrap.dedent(f"""\
            'use client';

            import DashboardWidget from '@/features/components/DashboardWidget';
            import ExternalDataCards from '@/components/bridge/ExternalDataCards';
            import {{ LayoutDashboard, BarChart3 }} from 'lucide-react';

            export default function OverviewTab() {{
              return (
                <div className="space-y-6">
                  {{/* Stat Cards */}}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {stat_card_jsx or "{ /* No stat cards detected */ }"}
                  </div>

                  {{/* External Data */}}
                  <ExternalDataCards hubId="{self.hub_id}" />
                </div>
              );
            }}
        """)

    def _gen_table_tab(self, tab: dict[str, Any]) -> str:
        """Generate a table tab for rendered spreadsheet data."""
        tab_comp = f"{_pascal_case(tab['id'])}Tab"

        return textwrap.dedent(f"""\
            'use client';

            import {{ useEffect, useState }} from 'react';
            import DashboardWidget from '@/features/components/DashboardWidget';
            import FileActions from '@/components/bridge/FileActions';
            import {{ FileSpreadsheet }} from 'lucide-react';

            interface RowData {{
              [key: string]: string | number | null;
            }}

            export default function {tab_comp}() {{
              const [data, setData] = useState<RowData[]>([]);
              const [columns, setColumns] = useState<string[]>([]);
              const [loading, setLoading] = useState(true);

              useEffect(() => {{
                fetch('/api/{self.hub_id}/data?tab={tab["id"]}')
                  .then(res => res.json())
                  .then(result => {{
                    if (result.success) {{
                      setData(result.data?.rows ?? []);
                      setColumns(result.data?.columns ?? []);
                    }}
                  }})
                  .catch(() => {{}})
                  .finally(() => setLoading(false));
              }}, []);

              if (loading) return <div className="text-neutral-500">Loading...</div>;

              return (
                <div className="space-y-4">
                  <FileActions hubId="{self.hub_id}" />

                  <DashboardWidget title="{tab.get('label', 'Data')}" icon={{FileSpreadsheet}}>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-white/10">
                            {{columns.map(col => (
                              <th key={{col}} className="px-3 py-2 text-left text-neutral-400 font-medium">
                                {{col}}
                              </th>
                            ))}}
                          </tr>
                        </thead>
                        <tbody>
                          {{data.map((row, i) => (
                            <tr key={{i}} className="border-b border-white/5 hover:bg-white/5">
                              {{columns.map(col => (
                                <td key={{col}} className="px-3 py-2 text-neutral-300">
                                  {{String(row[col] ?? '')}}
                                </td>
                              ))}}
                            </tr>
                          ))}}
                        </tbody>
                      </table>
                    </div>
                  </DashboardWidget>
                </div>
              );
            }}
        """)

    def _gen_time_series_tab(self, tab: dict[str, Any]) -> str:
        """Generate a time-series tab for multi-file temporal data."""
        tab_comp = f"{_pascal_case(tab['id'])}Tab"

        return textwrap.dedent(f"""\
            'use client';

            import {{ useEffect, useState }} from 'react';
            import DashboardWidget from '@/features/components/DashboardWidget';
            import ExternalDataCards from '@/components/bridge/ExternalDataCards';
            import {{ CalendarDays }} from 'lucide-react';

            export default function {tab_comp}() {{
              const [periods, setPeriods] = useState<string[]>([]);
              const [selected, setSelected] = useState<string>('');

              useEffect(() => {{
                fetch('/api/{self.hub_id}/data?tab={tab["id"]}&list=periods')
                  .then(res => res.json())
                  .then(result => {{
                    if (result.success && result.data?.periods) {{
                      setPeriods(result.data.periods);
                      setSelected(result.data.periods[0] ?? '');
                    }}
                  }})
                  .catch(() => {{}});
              }}, []);

              return (
                <div className="space-y-4">
                  <DashboardWidget title="{tab.get('label', 'Timeline')}" icon={{CalendarDays}}>
                    <div className="p-4 space-y-4">
                      <div className="flex gap-2 flex-wrap">
                        {{periods.map(p => (
                          <button
                            key={{p}}
                            onClick={{() => setSelected(p)}}
                            className={{`px-3 py-1 rounded-full text-sm ${{
                              selected === p
                                ? 'bg-blue-500 text-white'
                                : 'bg-white/10 text-neutral-400 hover:bg-white/20'
                            }}`}}
                          >
                            {{p}}
                          </button>
                        ))}}
                      </div>
                      <div className="text-sm text-neutral-500">
                        {{selected ? `Showing data for ${{selected}}` : 'Select a period'}}
                      </div>
                    </div>
                  </DashboardWidget>

                  <ExternalDataCards hubId="{self.hub_id}" />
                </div>
              );
            }}
        """)

    def _gen_folder_browser_tab(self, tab: dict[str, Any]) -> str:
        """Generate a folder-browser tab."""
        tab_comp = f"{_pascal_case(tab['id'])}Tab"

        return textwrap.dedent(f"""\
            'use client';

            import DashboardWidget from '@/features/components/DashboardWidget';
            import FileActions from '@/components/bridge/FileActions';
            import {{ FolderOpen }} from 'lucide-react';

            export default function {tab_comp}() {{
              return (
                <div className="space-y-4">
                  <DashboardWidget title="{tab.get('label', 'Files')}" icon={{FolderOpen}}>
                    <div className="p-4">
                      <FileActions hubId="{self.hub_id}" />
                    </div>
                  </DashboardWidget>
                </div>
              );
            }}
        """)

    def _gen_rendered_content_tab(self, tab: dict[str, Any]) -> str:
        """Generate a rendered-content tab for markdown files."""
        tab_comp = f"{_pascal_case(tab['id'])}Tab"

        return textwrap.dedent(f"""\
            'use client';

            import {{ useEffect, useState }} from 'react';
            import DashboardWidget from '@/features/components/DashboardWidget';
            import {{ FileType }} from 'lucide-react';

            export default function {tab_comp}() {{
              const [content, setContent] = useState<string>('');
              const [loading, setLoading] = useState(true);

              useEffect(() => {{
                fetch('/api/{self.hub_id}/data?tab={tab["id"]}&format=html')
                  .then(res => res.json())
                  .then(result => {{
                    if (result.success) {{
                      setContent(result.data?.html ?? '');
                    }}
                  }})
                  .catch(() => {{}})
                  .finally(() => setLoading(false));
              }}, []);

              if (loading) return <div className="text-neutral-500">Loading...</div>;

              return (
                <DashboardWidget title="{tab.get('label', 'Content')}" icon={{FileType}}>
                  <div
                    className="p-4 prose prose-invert max-w-none"
                    dangerouslySetInnerHTML={{{{ __html: content }}}}
                  />
                </DashboardWidget>
              );
            }}
        """)

    def _gen_default_tab(self, tab: dict[str, Any]) -> str:
        """Generate a generic placeholder tab."""
        tab_comp = f"{_pascal_case(tab['id'])}Tab"

        return textwrap.dedent(f"""\
            'use client';

            import DashboardWidget from '@/features/components/DashboardWidget';
            import {{ LayoutDashboard }} from 'lucide-react';

            export default function {tab_comp}() {{
              return (
                <DashboardWidget title="{tab.get('label', tab['id'])}" icon={{LayoutDashboard}}>
                  <div className="p-4">
                    <div className="text-sm text-neutral-500">Content for {tab.get('label', tab['id'])}</div>
                  </div>
                </DashboardWidget>
              );
            }}
        """)

    def _gen_health_route(self) -> str:
        """Generate api/health/route.ts."""
        return textwrap.dedent(f"""\
            import {{ NextResponse }} from 'next/server';

            export async function GET() {{
              return NextResponse.json({{
                status: 'healthy',
                plugin: '{self.hub_id}',
                version: '1.0.0',
                timestamp: new Date().toISOString(),
              }});
            }}
        """)

    def _gen_data_route(self) -> str:
        """Generate api/data/route.ts for rendered file data."""
        return textwrap.dedent(f"""\
            import {{ NextResponse }} from 'next/server';
            import {{ execSync }} from 'child_process';
            import path from 'path';

            export async function GET(request: Request) {{
              try {{
                const {{ searchParams }} = new URL(request.url);
                const tab = searchParams.get('tab') ?? 'overview';
                const format = searchParams.get('format') ?? 'json';

                // Read data via the bridge scan CLI
                const scriptDir = path.join(
                  process.cwd(),
                  'skills/frontend/scripts'
                );
                const result = execSync(
                  `python3 excel_reader.py --hub {self.hub_id} --tab ${{tab}} --format ${{format}}`,
                  {{ cwd: scriptDir, timeout: 10000 }}
                );

                const data = JSON.parse(result.toString());

                return NextResponse.json({{
                  success: true,
                  data,
                }});
              }} catch (error) {{
                return NextResponse.json(
                  {{ success: false, error: String(error) }},
                  {{ status: 500 }}
                );
              }}
            }}
        """)

    def _gen_connections_yaml(self) -> str:
        """Generate initial data/connections.yaml."""
        source = self.bp.get("source", {})
        strategies = self.bp.get("file_strategies", [])

        lines = [
            f"# Connections config for {self.hub_title}",
            f"# Auto-generated by /import on {datetime.now().strftime('%Y-%m-%d')}",
            "version: 1",
            f"hub: {self.hub_id}",
            "",
            "connections:",
            f"  - id: {self.hub_id}-{source.get('type', 'folder')}",
            f"    source_type: {source.get('type', 'folder')}",
            f"    source_path: {source.get('path', '')}",
            f"    connected_at: {datetime.now().isoformat()}",
            "    integrations:",
        ]

        for fs in strategies:
            if fs.get("mode") == "ignore":
                continue
            lines.append(f"      - id: {_slugify(Path(fs['path']).stem)}")
            lines.append(f"        file: {fs['path']}")
            lines.append(f"        mode: {fs['mode']}")

        ext_only = self.bp.get("external_only", [])
        if ext_only:
            lines.append("    ignored: []")

        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # File writing
    # ------------------------------------------------------------------

    def _write_files(self, files: dict[str, str]) -> None:
        """Write all generated files to disk.

        Args:
            files: Dict mapping relative path -> content.
        """
        for rel_path, content in files.items():
            full_path = self.skill_dir / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _pascal_case(text: str) -> str:
    """Convert kebab/snake case to PascalCase."""
    return re.sub(r"(?:^|[-_])(\w)", lambda m: m.group(1).upper(), text)


def _slugify(text: str) -> str:
    """Convert text to kebab-case slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower())
    return slug.strip("-") or "item"
