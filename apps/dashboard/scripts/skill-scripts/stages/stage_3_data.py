"""
Stage 3: Data Structures.

Define schemas and storage patterns for the skill.

Outputs:
- schemas/*.yaml (JSON Schema format)
- data_dir configuration
- Storage pattern files
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

import yaml

from .base_stage import BaseStage
from ._imports import ValidationResult, ValidationIssue

if TYPE_CHECKING:
    from ._imports import StageOutput, WorkflowState


class Stage3Data(BaseStage):
    """Stage 3: Data Structures - Define schemas and storage patterns."""

    @property
    def stage_num(self) -> int:
        return 3

    @property
    def stage_name(self) -> str:
        return "Data Structures"

    @property
    def description(self) -> str:
        return "Define schemas and storage patterns for the skill"

    def get_acceptance_criteria(self) -> List[str]:
        return [
            "Schema file exists (if standard+ profile)",
            "Schema follows JSON Schema format",
            "data_dir matches hub.id in SKILL.md",
            "Storage pattern files exist",
        ]

    def plan(
        self,
        state: "WorkflowState",
        previous_output: Optional["StageOutput"] = None,
        user_answers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create execution plan for data structures."""
        skill_path = state.skill_path
        schemas_dir = skill_path / "schemas"

        plan = {
            "skill_path": str(skill_path),
            "schemas_dir": str(schemas_dir),
            "target_profile": state.target_profile,
            "steps": [
                {"action": "analyze_data_needs"},
                {"action": "create_schemas_directory"},
                {"action": "generate_primary_schema"},
                {"action": "update_skill_md_data_dir"},
            ],
            "files_to_create": [],
            "files_to_modify": [str(skill_path / "SKILL.md")],
        }

        # Only create schemas for standard+ profiles
        if state.target_profile in ("standard", "full"):
            plan["files_to_create"].append(str(schemas_dir / "main.yaml"))

        if user_answers:
            plan["user_inputs"] = user_answers

        return plan

    def execute(
        self,
        state: "WorkflowState",
        plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the data structures plan."""
        skill_path = state.skill_path
        schemas_dir = skill_path / "schemas"
        user_inputs = plan.get("user_inputs", {})

        files_created = []
        files_modified = []

        # Only create schemas for standard+ profiles
        if state.target_profile in ("standard", "full"):
            schemas_dir.mkdir(parents=True, exist_ok=True)

            # Get schema configuration from user or defaults
            primary_entity = user_inputs.get("primary_entity", state.skill_name.replace("-", "_"))
            entity_fields = user_inputs.get("entity_fields", [])
            if isinstance(entity_fields, str):
                entity_fields = [f.strip() for f in entity_fields.split(",") if f.strip()]

            # Generate primary schema
            schema = self._generate_schema(
                entity_name=primary_entity,
                fields=entity_fields,
                description=f"Primary data schema for {state.skill_name}",
            )

            schema_path = schemas_dir / "main.yaml"
            with open(schema_path, "w", encoding="utf-8") as f:
                yaml.dump(schema, f, default_flow_style=False, allow_unicode=True)
            files_created.append(str(schema_path))

        # Update SKILL.md with data_dir - use line insertion to preserve formatting
        skill_md_path = skill_path / "SKILL.md"
        if skill_md_path.exists():
            content = skill_md_path.read_text(encoding="utf-8")

            # Check if data_dir already exists
            if "data_dir:" not in content:
                # Find the closing --- and insert data_dir before it
                # Parse to get the hub_id for the value
                hub_id = state.skill_name
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        try:
                            frontmatter = yaml.safe_load(parts[1]) or {}
                            hub_id = frontmatter.get("hub", {}).get("id", state.skill_name)
                        except yaml.YAMLError:
                            pass

                # Insert data_dir line before the Layer 2 section or at end of frontmatter
                lines = content.split("\n")
                new_lines = []
                inserted = False
                in_frontmatter = False

                for i, line in enumerate(lines):
                    if line.strip() == "---" and not in_frontmatter:
                        in_frontmatter = True
                        new_lines.append(line)
                    elif line.strip() == "---" and in_frontmatter:
                        # End of frontmatter - insert data_dir before this
                        if not inserted:
                            new_lines.append(f"data_dir: {hub_id}")
                            inserted = True
                        new_lines.append(line)
                        in_frontmatter = False
                    elif "# === Augur Extensions" in line and not inserted:
                        # Insert before Layer 2 section
                        new_lines.append(f"data_dir: {hub_id}")
                        new_lines.append("")
                        inserted = True
                        new_lines.append(line)
                    else:
                        new_lines.append(line)

                if inserted:
                    skill_md_path.write_text("\n".join(new_lines), encoding="utf-8")
                    files_modified.append(str(skill_md_path))

        return {
            "files_created": files_created,
            "files_modified": files_modified,
            "data": {
                "schemas_dir": str(schemas_dir) if schemas_dir.exists() else None,
                "primary_entity": user_inputs.get("primary_entity", state.skill_name.replace("-", "_")),
            },
        }

    def test(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run automated tests on the data structures."""
        skill_path = state.skill_path
        schemas_dir = skill_path / "schemas"
        results = {}

        # Test 1: Schema directory exists (if standard+ profile)
        if state.target_profile in ("standard", "full"):
            results["schemas_dir_exists"] = {
                "passed": schemas_dir.exists(),
                "message": "Schemas directory exists" if schemas_dir.exists() else "Schemas directory missing",
            }

            # Test 2: Main schema file exists
            main_schema = schemas_dir / "main.yaml"
            results["main_schema_exists"] = {
                "passed": main_schema.exists(),
                "message": "Main schema file exists" if main_schema.exists() else "Main schema file missing",
            }

            # Test 3: Schema is valid YAML and has required fields
            if main_schema.exists():
                try:
                    with open(main_schema) as f:
                        schema = yaml.safe_load(f)

                    has_type = "type" in schema
                    has_properties = "properties" in schema

                    results["schema_structure"] = {
                        "passed": has_type and has_properties,
                        "message": (
                            "Schema has valid JSON Schema structure"
                            if has_type and has_properties
                            else "Schema missing type or properties"
                        ),
                    }
                except Exception as e:
                    results["schema_structure"] = {
                        "passed": False,
                        "message": f"Failed to parse schema: {e}",
                    }
        else:
            results["minimal_profile"] = {
                "passed": True,
                "message": "Minimal profile - schemas not required",
            }

        # Test 4: data_dir in SKILL.md
        skill_md_path = skill_path / "SKILL.md"
        if skill_md_path.exists():
            try:
                content = skill_md_path.read_text(encoding="utf-8")
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    has_data_dir = "data_dir" in frontmatter
                    results["data_dir_configured"] = {
                        "passed": has_data_dir,
                        "message": (
                            f"data_dir: {frontmatter.get('data_dir')}" if has_data_dir else "data_dir not configured"
                        ),
                    }
            except Exception:
                results["data_dir_configured"] = {
                    "passed": False,
                    "message": "Failed to read SKILL.md",
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
                result.add_issue(
                    ValidationIssue(
                        rule=f"test_{test_name}",
                        message=test_result.get("message", f"Test {test_name} failed"),
                        severity="error" if "schema" in test_name.lower() else "warning",
                    )
                )

        return result

    def generate_questions(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
        validation: Optional["ValidationResult"] = None,
    ) -> List[Dict[str, Any]]:
        """Generate context-aware questions for data structures."""
        # Skip questions for minimal profile
        if state.target_profile == "minimal":
            return []

        questions = [
            {
                "id": "primary_entity",
                "text": f"What is the primary data entity for {state.skill_name}?",
                "type": "text",
                "default": state.skill_name.replace("-", "_"),
                "required": True,
                "context": "e.g., 'recipe' for a recipes skill, 'task' for a task manager",
            },
            {
                "id": "entity_fields",
                "text": "What fields should the primary entity have? (comma-separated)",
                "type": "text",
                "default": "id, name, description, created_at, updated_at",
                "required": True,
                "context": "Common fields: id, name, description, status, tags, created_at, updated_at",
            },
            {
                "id": "storage_type",
                "text": "What storage pattern should be used?",
                "type": "choice",
                "options": ["yaml_files", "sqlite", "json_files", "hybrid"],
                "default": "yaml_files",
                "required": True,
                "context": "yaml_files: Human-readable, git-friendly. sqlite: Structured queries. hybrid: Both.",
            },
        ]

        return questions

    def get_output(self, state: "WorkflowState") -> Dict[str, Any]:
        """Get the stage output data."""
        skill_path = state.skill_path
        schemas_dir = skill_path / "schemas"
        output = {}

        if schemas_dir.exists():
            output["schemas_dir"] = str(schemas_dir)
            output["schema_files"] = [str(f) for f in schemas_dir.glob("*.yaml")]

        # Get data_dir from SKILL.md
        skill_md_path = skill_path / "SKILL.md"
        if skill_md_path.exists():
            try:
                content = skill_md_path.read_text(encoding="utf-8")
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    output["data_dir"] = frontmatter.get("data_dir")
            except Exception:
                pass

        return output

    def get_default_answers(self, state: "WorkflowState") -> Dict[str, Any]:
        """Get default answers for auto mode."""
        return {
            "primary_entity": state.skill_name.replace("-", "_"),
            "entity_fields": "id, name, description, created_at, updated_at",
            "storage_type": "yaml_files",
        }

    def _generate_schema(
        self,
        entity_name: str,
        fields: List[str],
        description: str,
    ) -> Dict[str, Any]:
        """Generate a JSON Schema for the entity."""
        # Default field types
        field_types = {
            "id": {"type": "string", "description": "Unique identifier"},
            "name": {"type": "string", "description": "Display name"},
            "description": {"type": "string", "description": "Detailed description"},
            "status": {"type": "string", "enum": ["draft", "active", "archived"]},
            "tags": {"type": "array", "items": {"type": "string"}},
            "created_at": {"type": "string", "format": "date-time"},
            "updated_at": {"type": "string", "format": "date-time"},
        }

        properties = {}
        required = []

        for field in fields:
            field = field.strip().lower().replace(" ", "_")
            if not field:
                continue

            if field in field_types:
                properties[field] = field_types[field]
            else:
                properties[field] = {"type": "string", "description": f"{field} field"}

            if field in ("id", "name"):
                required.append(field)

        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": entity_name.title().replace("_", " "),
            "description": description,
            "type": "object",
            "properties": properties,
            "required": required,
        }
