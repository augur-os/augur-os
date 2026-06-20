"""
Stage 2: Hardening.

Enrich the skill with triggers, tiers, safety constraints, and dependencies.

Outputs:
- Complete SKILL.md with @augur markers for Layer 2 fields
- Triggers defined
- Tiers configured (for standard+ profiles)
- Dependencies declared
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

import yaml

from .base_stage import BaseStage
from ._imports import (
    ValidationResult,
    ValidationIssue,
    validate_augur_markers,
)

if TYPE_CHECKING:
    from ._imports import StageOutput, WorkflowState


class Stage2Hardening(BaseStage):
    """Stage 2: Hardening - Enrich SKILL.md with triggers, tiers, safety."""

    @property
    def stage_num(self) -> int:
        return 2

    @property
    def stage_name(self) -> str:
        return "Hardening"

    @property
    def description(self) -> str:
        return "Enrich skill with triggers, tiers, and safety constraints"

    def get_acceptance_criteria(self) -> List[str]:
        return [
            "At least 2 triggers defined",
            "Tiers section complete (if standard+ profile)",
            "@augur markers properly applied to Layer 2 fields",
            "Dependencies declared (even if empty)",
            "Category is valid enum",
        ]

    def plan(
        self,
        state: "WorkflowState",
        previous_output: Optional["StageOutput"] = None,
        user_answers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create execution plan for hardening."""
        skill_path = state.skill_path
        skill_md_path = skill_path / "SKILL.md"

        # Get current content
        current_content = ""
        if skill_md_path.exists():
            current_content = skill_md_path.read_text(encoding="utf-8")

        plan = {
            "skill_path": str(skill_path),
            "skill_md_path": str(skill_md_path),
            "current_content": current_content,
            "target_profile": state.target_profile,
            "steps": [
                {"action": "parse_existing_skill_md"},
                {"action": "add_triggers"},
                {"action": "add_category_and_mode"},
                {"action": "add_tiers_if_needed"},
                {"action": "add_dependencies"},
                {"action": "write_updated_skill_md"},
            ],
            "files_to_modify": [str(skill_md_path)],
        }

        # Include user answers if retrying
        if user_answers:
            plan["user_inputs"] = user_answers

        return plan

    def execute(
        self,
        state: "WorkflowState",
        plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the hardening plan."""
        skill_path = state.skill_path
        skill_md_path = skill_path / "SKILL.md"

        # Read current content
        content = skill_md_path.read_text(encoding="utf-8") if skill_md_path.exists() else ""

        # Parse existing frontmatter
        frontmatter = {}
        body = ""
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                except yaml.YAMLError:
                    frontmatter = {}
                body = parts[2].strip()

        # Get user answers or defaults
        user_inputs = plan.get("user_inputs", {})

        # Add triggers
        existing_triggers = frontmatter.get("triggers", [])
        additional_triggers = user_inputs.get("additional_triggers", [])
        if isinstance(additional_triggers, str):
            additional_triggers = [t.strip() for t in additional_triggers.split(",") if t.strip()]

        all_triggers = list(set(existing_triggers + additional_triggers))
        if len(all_triggers) < 2:
            # Generate default triggers based on skill name
            name = state.skill_name.replace("-", " ")
            all_triggers = [f"process {name}", f"search {name}"]

        # Build Layer 2 fields
        category = user_inputs.get("category", "personal")
        mode = user_inputs.get("mode", "all")

        # Build tiers if standard+ profile
        tiers = {}
        if state.target_profile in ("standard", "full"):
            fast_tools = user_inputs.get("fast_tools", ["Read", "Glob"])
            if isinstance(fast_tools, str):
                fast_tools = [t.strip() for t in fast_tools.split(",")]

            tiers = {
                "low": {
                    "capability": "fast",
                    "mode": "advisory",
                    "tools": fast_tools,
                    "max_files": 3,
                },
                "medium": {
                    "capability": "balanced",
                    "mode": "executor",
                    "tools": ["Read", "Glob", "Grep", "Edit"],
                    "max_files": 10,
                },
                "high": {
                    "capability": "reasoning",
                    "mode": "executor",
                    "tools": ["Read", "Glob", "Grep", "Edit", "Write", "Bash"],
                    "max_files": "unlimited",
                },
            }

        # Build dependencies
        dependencies = {
            "plugins": user_inputs.get("plugin_dependencies", []),
            "mcp_servers": [],
            "python": [],
            "npm": [],
        }

        # Generate new SKILL.md content
        new_content = self._generate_hardened_skill_md(
            name=frontmatter.get("name", state.skill_name),
            version=frontmatter.get("version", "1.0.0"),
            description=frontmatter.get("description", ""),
            triggers=all_triggers,
            category=category,
            mode=mode,
            tiers=tiers,
            dependencies=dependencies,
            body=body,
        )

        skill_md_path.write_text(new_content, encoding="utf-8")

        return {
            "files_modified": [str(skill_md_path)],
            "files_created": [],
            "data": {
                "skill_md_content": new_content,
                "triggers": all_triggers,
                "category": category,
                "mode": mode,
                "tiers": tiers,
                "dependencies": dependencies,
            },
        }

    def test(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run automated tests on the hardened skill."""
        skill_md_path = state.skill_path / "SKILL.md"
        results = {}

        if not skill_md_path.exists():
            results["skill_md_exists"] = {"passed": False, "message": "SKILL.md not found"}
            return results

        content = skill_md_path.read_text(encoding="utf-8")

        # Parse frontmatter
        try:
            parts = content.split("---", 2)
            frontmatter = yaml.safe_load(parts[1]) if len(parts) >= 3 else {}
        except Exception:
            frontmatter = {}

        # Test 1: At least 2 triggers
        triggers = frontmatter.get("triggers", [])
        results["triggers_count"] = {
            "passed": len(triggers) >= 2,
            "message": f"Has {len(triggers)} triggers (need >= 2)",
        }

        # Test 2: Category is valid
        valid_categories = ["system", "productivity", "personal", "business"]
        category = frontmatter.get("category", "")
        results["category_valid"] = {
            "passed": category in valid_categories,
            "message": (
                f"Category '{category}' is valid" if category in valid_categories else f"Invalid category '{category}'"
            ),
        }

        # Test 3: @augur markers present for Layer 2 fields
        layer2_fields = ["category", "mode", "tiers", "dependencies"]
        augur_marked = all(
            "# @augur" in content.split(f"{field}:")[1][:50] if f"{field}:" in content else True
            for field in layer2_fields
        )
        results["augur_markers"] = {
            "passed": augur_marked,
            "message": "@augur markers checked" if augur_marked else "Missing @augur markers",
        }

        # Test 4: Dependencies declared
        deps = frontmatter.get("dependencies", {})
        results["dependencies_declared"] = {
            "passed": isinstance(deps, dict),
            "message": "Dependencies section present",
        }

        return results

    def validate(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
        test_results: Dict[str, Any],
    ) -> "ValidationResult":
        """Validate against acceptance criteria."""
        skill_md_path = state.skill_path / "SKILL.md"

        # Use the @augur marker validator
        result = validate_augur_markers(skill_md_path)

        # Add test-specific issues
        for test_name, test_result in test_results.items():
            if not test_result.get("passed", False):
                result.add_issue(
                    ValidationIssue(
                        rule=f"test_{test_name}",
                        message=test_result.get("message", f"Test {test_name} failed"),
                        severity="error",
                    )
                )

        return result

    def generate_questions(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
        validation: Optional["ValidationResult"] = None,
    ) -> List[Dict[str, Any]]:
        """Generate context-aware questions for hardening."""
        data = artifacts.get("data", {})
        current_triggers = data.get("triggers", [])

        questions = [
            {
                "id": "additional_triggers",
                "text": f"Current triggers: {', '.join(current_triggers) or 'none'}. Add more?",
                "type": "text",
                "default": "",
                "required": False,
                "context": "Enter comma-separated trigger phrases, e.g., 'process data, analyze results'",
            },
            {
                "id": "category",
                "text": "What category best describes this skill?",
                "type": "choice",
                "options": ["system", "productivity", "personal", "business"],
                "default": "personal",
                "required": True,
            },
            {
                "id": "fast_tools",
                "text": "For FAST mode (advisory only), what tools should be available?",
                "type": "text",
                "default": "Read, Glob",
                "required": True,
                "context": "Common tools: Read, Glob, Grep, Edit, Write, Bash",
            },
            {
                "id": "plugin_dependencies",
                "text": "Does this skill depend on other plugins? (comma-separated)",
                "type": "text",
                "default": "",
                "required": False,
                "context": "e.g., knowledge, notifications, apple",
            },
        ]

        return questions

    def get_output(self, state: "WorkflowState") -> Dict[str, Any]:
        """Get the stage output data."""
        skill_md_path = state.skill_path / "SKILL.md"
        output = {}

        if skill_md_path.exists():
            content = skill_md_path.read_text(encoding="utf-8")
            try:
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    output["triggers"] = frontmatter.get("triggers", [])
                    output["category"] = frontmatter.get("category")
                    output["mode"] = frontmatter.get("mode")
                    output["tiers"] = frontmatter.get("tiers", {})
                    output["dependencies"] = frontmatter.get("dependencies", {})
            except Exception:
                pass

        return output

    def get_default_answers(self, state: "WorkflowState") -> Dict[str, Any]:
        """Get default answers for auto mode."""
        name = state.skill_name.replace("-", " ")
        return {
            "additional_triggers": f"{name} status",
            "category": "personal",
            "fast_tools": "Read, Glob",
            "plugin_dependencies": "",
        }

    def _generate_hardened_skill_md(
        self,
        name: str,
        version: str,
        description: str,
        triggers: List[str],
        category: str,
        mode: str,
        tiers: Dict,
        dependencies: Dict,
        body: str,
    ) -> str:
        """Generate a hardened SKILL.md with Layer 2 fields."""
        # Build frontmatter as structured data
        frontmatter = {
            "name": name,
            "version": version,
            "description": description,
            "triggers": triggers,
        }

        # Layer 2 fields (marked with @augur comments after YAML)
        layer2 = {
            "category": category,
            "mode": mode,
        }

        if tiers:
            layer2["tiers"] = tiers

        layer2["dependencies"] = {
            "plugins": dependencies.get("plugins", []),
            "mcp_servers": dependencies.get("mcp_servers", []),
            "python": dependencies.get("python", []),
            "npm": dependencies.get("npm", []),
        }

        # Generate clean YAML for Layer 1
        layer1_yaml = yaml.dump(
            frontmatter,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()

        # Generate clean YAML for Layer 2
        layer2_yaml = yaml.dump(
            layer2,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()

        # Add @augur markers to Layer 2 section
        layer2_lines = layer2_yaml.split("\n")
        marked_layer2_lines = []
        in_tiers = False
        for line in layer2_lines:
            if line.startswith("tiers:"):
                marked_layer2_lines.append(f"{line}  # @augur-start")
                in_tiers = True
            elif in_tiers and not line.startswith(" "):
                # Exiting tiers block
                marked_layer2_lines.append("# @augur-end")
                in_tiers = False
                if line.strip():
                    marked_layer2_lines.append(f"{line}  # @augur")
            elif in_tiers:
                marked_layer2_lines.append(f"{line}  # @augur")
            elif line.startswith("dependencies:"):
                if in_tiers:
                    marked_layer2_lines.append("# @augur-end")
                    in_tiers = False
                marked_layer2_lines.append(f"{line}  # @augur")
            elif line.strip():
                marked_layer2_lines.append(f"{line}  # @augur")
            else:
                marked_layer2_lines.append(line)

        # Close tiers block if still open
        if in_tiers:
            marked_layer2_lines.append("# @augur-end")

        marked_layer2 = "\n".join(marked_layer2_lines)

        return f"""---
# === Standard Core (Layer 1) - portable, survives export ===
{layer1_yaml}

# === Augur Extensions (Layer 2) - stripped on export ===
{marked_layer2}
---

{body}
"""
