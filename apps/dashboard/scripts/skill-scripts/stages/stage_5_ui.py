"""
Stage 5: UI Generation.

Generate dashboard components for the skill.

Outputs:
- dashboard/page.tsx (main page component)
- dashboard/tabs/*.tsx (tab components)
- dashboard/components/*.tsx (src/lib components)
- Loading skeletons
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import yaml

from .base_stage import BaseStage
from ._imports import ValidationResult, ValidationIssue

if TYPE_CHECKING:
    from ._imports import StageOutput, WorkflowState


class Stage5UI(BaseStage):
    """Stage 5: UI Generation - Generate dashboard components."""

    @property
    def stage_num(self) -> int:
        return 5

    @property
    def stage_name(self) -> str:
        return "UI Generation"

    @property
    def description(self) -> str:
        return "Generate dashboard components for the skill"

    def get_acceptance_criteria(self) -> List[str]:
        return [
            "dashboard/page.tsx exists and compiles",
            "First tab is 'overview' with default: true",
            "No TypeScript errors",
            "Loading skeleton matches structure",
        ]

    def plan(
        self,
        state: "WorkflowState",
        previous_output: Optional["StageOutput"] = None,
        user_answers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create execution plan for UI generation."""
        skill_path = state.skill_path
        dashboard_dir = skill_path / "dashboard"

        # Get tabs from dashboard.yaml
        tabs = self._get_tabs_from_dashboard_yaml(skill_path)

        plan = {
            "skill_path": str(skill_path),
            "dashboard_dir": str(dashboard_dir),
            "target_profile": state.target_profile,
            "tabs": tabs,
            "steps": [
                {"action": "create_dashboard_directory"},
                {"action": "generate_layout"},
                {"action": "generate_page"},
                {"action": "generate_tabs"},
                {"action": "generate_loading_skeleton"},
            ],
            "files_to_create": [
                str(dashboard_dir / "layout.tsx"),
                str(dashboard_dir / "page.tsx"),
                str(dashboard_dir / "loading.tsx"),
            ],
        }

        # Add tab files
        for tab in tabs:
            if tab.get("id") != "overview":
                tab_path = dashboard_dir / "tabs" / f"{self._tab_id_to_component_name(tab['id'])}Tab.tsx"
                plan["files_to_create"].append(str(tab_path))

        if user_answers:
            plan["user_inputs"] = user_answers

        return plan

    def execute(
        self,
        state: "WorkflowState",
        plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the UI generation plan."""
        skill_path = state.skill_path
        dashboard_dir = skill_path / "dashboard"
        user_inputs = plan.get("user_inputs", {})
        tabs = plan.get("tabs", [])

        files_created = []

        # Create dashboard directory
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        tabs_dir = dashboard_dir / "tabs"
        tabs_dir.mkdir(exist_ok=True)

        # Get UI preferences
        include_charts = user_inputs.get("include_charts", False)

        # Generate layout.tsx
        layout_content = self._generate_layout(state.skill_name)
        layout_path = dashboard_dir / "layout.tsx"
        layout_path.write_text(layout_content, encoding="utf-8")
        files_created.append(str(layout_path))

        # Generate page.tsx (overview)
        page_content = self._generate_page(state.skill_name, tabs)
        page_path = dashboard_dir / "page.tsx"
        page_path.write_text(page_content, encoding="utf-8")
        files_created.append(str(page_path))

        # Generate loading.tsx
        loading_content = self._generate_loading(state.skill_name)
        loading_path = dashboard_dir / "loading.tsx"
        loading_path.write_text(loading_content, encoding="utf-8")
        files_created.append(str(loading_path))

        # Generate tab components
        for tab in tabs:
            if tab.get("id") != "overview":
                component_name = self._tab_id_to_component_name(tab["id"])
                tab_content = self._generate_tab_component(
                    tab_id=tab["id"],
                    tab_label=tab.get("label", tab["id"].title()),
                    skill_name=state.skill_name,
                    include_charts=include_charts,
                )
                tab_path = tabs_dir / f"{component_name}Tab.tsx"
                tab_path.write_text(tab_content, encoding="utf-8")
                files_created.append(str(tab_path))

        return {
            "files_created": files_created,
            "files_modified": [],
            "data": {
                "dashboard_dir": str(dashboard_dir),
                "tabs_generated": [t["id"] for t in tabs],
            },
        }

    def test(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run automated tests on the UI."""
        skill_path = state.skill_path
        dashboard_dir = skill_path / "dashboard"
        results = {}

        # Test 1: dashboard directory exists
        results["dashboard_dir_exists"] = {
            "passed": dashboard_dir.exists(),
            "message": "Dashboard directory exists" if dashboard_dir.exists() else "Dashboard directory missing",
        }

        # Test 2: page.tsx exists
        page_tsx = dashboard_dir / "page.tsx"
        results["page_tsx_exists"] = {
            "passed": page_tsx.exists(),
            "message": "page.tsx exists" if page_tsx.exists() else "page.tsx missing",
        }

        # Test 3: layout.tsx exists
        layout_tsx = dashboard_dir / "layout.tsx"
        results["layout_tsx_exists"] = {
            "passed": layout_tsx.exists(),
            "message": "layout.tsx exists" if layout_tsx.exists() else "layout.tsx missing",
        }

        # Test 4: loading.tsx exists
        loading_tsx = dashboard_dir / "loading.tsx"
        results["loading_tsx_exists"] = {
            "passed": loading_tsx.exists(),
            "message": "loading.tsx exists" if loading_tsx.exists() else "loading.tsx missing",
        }

        # Test 5: page.tsx has valid structure
        if page_tsx.exists():
            content = page_tsx.read_text(encoding="utf-8")
            has_export = "export default" in content
            has_function = "function" in content or "=>" in content
            results["page_tsx_valid"] = {
                "passed": has_export and has_function,
                "message": (
                    "page.tsx has valid React structure"
                    if has_export and has_function
                    else "page.tsx missing export or function"
                ),
            }

        # Test 6: Check dashboard.yaml has overview as first tab with default: true
        dashboard_yaml = skill_path / "dashboard.yaml"
        if dashboard_yaml.exists():
            try:
                with open(dashboard_yaml) as f:
                    config = yaml.safe_load(f) or {}
                tabs = config.get("tabs", [])
                if tabs:
                    first_tab = tabs[0]
                    is_overview = first_tab.get("id") == "overview"
                    is_default = first_tab.get("default", False)
                    results["overview_first_default"] = {
                        "passed": is_overview and is_default,
                        "message": (
                            "Overview is first tab with default: true"
                            if is_overview and is_default
                            else f"First tab is '{first_tab.get('id')}' with default: {is_default}"
                        ),
                    }
                else:
                    results["overview_first_default"] = {
                        "passed": False,
                        "message": "No tabs defined in dashboard.yaml",
                    }
            except Exception as e:
                results["overview_first_default"] = {
                    "passed": False,
                    "message": f"Failed to parse dashboard.yaml: {e}",
                }

        return results

    def validate(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
        test_results: Dict[str, Any],
    ) -> "ValidationResult":
        """Validate against acceptance criteria."""
        result = ValidationResult()

        for test_name, test_result in test_results.items():
            if not test_result.get("passed", False):
                severity = "error" if "exists" in test_name else "warning"
                result.add_issue(
                    ValidationIssue(
                        rule=f"test_{test_name}",
                        message=test_result.get("message", f"Test {test_name} failed"),
                        severity=severity,
                    )
                )

        return result

    def generate_questions(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
        validation: Optional["ValidationResult"] = None,
    ) -> List[Dict[str, Any]]:
        """Generate context-aware questions for UI generation."""
        tabs = self._get_tabs_from_dashboard_yaml(state.skill_path)
        current_tabs = ", ".join(t.get("label", t["id"]) for t in tabs)

        questions = [
            {
                "id": "additional_tabs",
                "text": f"Current tabs: {current_tabs}. Add more? (comma-separated)",
                "type": "text",
                "default": "",
                "required": False,
                "context": "Common tabs: Settings, Analytics, History, Logs",
            },
            {
                "id": "color_scheme",
                "text": "What color scheme should the UI use?",
                "type": "choice",
                "options": ["default", "blue", "green", "purple", "orange"],
                "default": "default",
                "required": True,
            },
            {
                "id": "include_charts",
                "text": "Should the UI include data visualization charts?",
                "type": "yes_no",
                "default": False,
                "required": True,
                "context": "If yes, recharts library will be used for visualizations",
            },
        ]

        return questions

    def get_output(self, state: "WorkflowState") -> Dict[str, Any]:
        """Get the stage output data."""
        skill_path = state.skill_path
        dashboard_dir = skill_path / "dashboard"
        output = {}

        if dashboard_dir.exists():
            output["dashboard_dir"] = str(dashboard_dir)
            output["files"] = [str(f.relative_to(skill_path)) for f in dashboard_dir.rglob("*.tsx")]

        return output

    def get_default_answers(self, state: "WorkflowState") -> Dict[str, Any]:
        """Get default answers for auto mode."""
        return {
            "additional_tabs": "",
            "color_scheme": "default",
            "include_charts": False,
        }

    def _get_tabs_from_dashboard_yaml(self, skill_path: Path) -> List[Dict[str, Any]]:
        """Get tabs configuration from dashboard.yaml."""
        dashboard_yaml = skill_path / "dashboard.yaml"
        if dashboard_yaml.exists():
            try:
                with open(dashboard_yaml) as f:
                    config = yaml.safe_load(f) or {}
                return config.get("tabs", [])
            except Exception:
                pass

        # Default tabs
        return [
            {"id": "overview", "label": "Overview", "default": True},
        ]

    def _tab_id_to_component_name(self, tab_id: str) -> str:
        """Convert tab ID to React component name."""
        return "".join(word.title() for word in tab_id.replace("-", "_").split("_"))

    def _generate_layout(self, skill_name: str) -> str:
        """Generate layout.tsx content."""
        title = skill_name.replace("-", " ").title()
        return f'''/**
 * Layout for {skill_name} dashboard.
 * Auto-generated by mcp-app-factory Stage 5.
 */

import {{ Metadata }} from "next";

export const metadata: Metadata = {{
  title: "{title}",
  description: "{title} dashboard",
}};

export default function Layout({{{{
  children,
}}}}: {{{{
  children: React.ReactNode;
}}}}) {{{{
  return <>{{children}}</>;
}}}}
'''

    def _generate_page(self, skill_name: str, tabs: List[Dict[str, Any]]) -> str:
        """Generate page.tsx content."""
        title = skill_name.replace("-", " ").title()
        return f'''/**
 * Overview page for {skill_name}.
 * Auto-generated by mcp-app-factory Stage 5.
 */

"use client";

import {{ Card, CardContent, CardHeader, CardTitle }} from "@/components/ui/card";

export default function {self._tab_id_to_component_name(skill_name)}Page() {{
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Welcome to {title}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              This is the overview page for {title}.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Quick Stats</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">0</div>
            <p className="text-muted-foreground text-sm">Items</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">No recent activity</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}}
'''

    def _generate_loading(self, skill_name: str) -> str:
        """Generate loading.tsx content."""
        return f'''/**
 * Loading skeleton for {skill_name}.
 * Auto-generated by mcp-app-factory Stage 5.
 */

import {{ Skeleton }} from "@/components/ui/skeleton";

export default function Loading() {{
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {{[1, 2, 3].map((i) => (
          <div key={{i}} className="rounded-lg border p-6">
            <Skeleton className="h-4 w-1/2 mb-4" />
            <Skeleton className="h-8 w-full" />
          </div>
        ))}}
      </div>
    </div>
  );
}}
'''

    def _generate_tab_component(
        self,
        tab_id: str,
        tab_label: str,
        skill_name: str,
        include_charts: bool = False,
    ) -> str:
        """Generate a tab component."""
        component_name = self._tab_id_to_component_name(tab_id)

        chart_import = ""
        chart_component = ""
        if include_charts:
            chart_import = (
                '\nimport { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";'
            )
            chart_component = '''
        <Card className="col-span-2">
          <CardHeader>
            <CardTitle>Data Visualization</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={[]}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="value" fill="hsl(var(--primary))" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>'''

        return f'''/**
 * {tab_label} tab for {skill_name}.
 * Auto-generated by mcp-app-factory Stage 5.
 */

"use client";

import {{ Card, CardContent, CardHeader, CardTitle }} from "@/components/ui/card";{chart_import}

export default function {component_name}Tab() {{
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{tab_label}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              {tab_label} content for {skill_name.replace("-", " ").title()}.
            </p>
          </CardContent>
        </Card>{chart_component}
      </div>
    </div>
  );
}}
'''
