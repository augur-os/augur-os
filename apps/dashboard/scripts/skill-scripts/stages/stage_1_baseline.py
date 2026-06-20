"""
Stage 1: Baseline Generation.

Import existing plugin OR generate new baseline conforming to Layer 1 standard.

Outputs:
- Valid SKILL.md with Layer 1 fields (name, version, description)
- Skill directory structure created
- (Refactor) Original files backed up
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import yaml

from .base_stage import BaseStage
from ._imports import (
    WorkflowMode,
    ValidationResult,
    ValidationIssue,
    validate_skill_md_layer1,
)

if TYPE_CHECKING:
    from ._imports import StageOutput, WorkflowState


class Stage1Baseline(BaseStage):
    """Stage 1: Baseline Generation."""

    @property
    def stage_num(self) -> int:
        return 1

    @property
    def stage_name(self) -> str:
        return "Baseline Generation"

    @property
    def description(self) -> str:
        return "Import/generate Layer 1 compliant skill baseline"

    def get_acceptance_criteria(self) -> List[str]:
        return [
            "SKILL.md exists with valid YAML frontmatter",
            "Required fields present: name, version, description",
            "Name is kebab-case and matches directory",
            "No @augur markers in Layer 1 section",
            "(Refactor) Original files backed up",
        ]

    def plan(
        self,
        state: "WorkflowState",
        previous_output: Optional["StageOutput"] = None,
        user_answers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create execution plan for baseline generation."""
        skill_path = state.skill_path
        is_new = state.mode == WorkflowMode.NEW

        plan = {
            "mode": state.mode.value,
            "skill_name": state.skill_name,
            "skill_path": str(skill_path),
            "bundle": state.bundle,
            "target_profile": state.target_profile,
            "steps": [],
            "files_to_create": [],
            "files_to_modify": [],
            "expected_output": {
                "skill_md_exists": True,
                "valid_frontmatter": True,
                "layer1_compliant": True,
            },
        }

        if is_new:
            # New plugin generation
            plan["steps"] = [
                {"action": "create_directory", "path": str(skill_path)},
                {"action": "create_skill_md", "path": str(skill_path / "SKILL.md")},
                {"action": "create_scripts_dir", "path": str(skill_path / "scripts")},
            ]
            plan["files_to_create"] = [
                str(skill_path / "SKILL.md"),
            ]
        else:
            # Refactor existing plugin
            source = Path(state.source_path) if state.source_path else skill_path

            plan["source_path"] = str(source)
            plan["steps"] = [
                {"action": "analyze_existing", "path": str(source)},
                {"action": "extract_layer1", "source": str(source / "SKILL.md")},
                {"action": "normalize_skill_md", "path": str(skill_path / "SKILL.md")},
            ]

            if (source / "SKILL.md").exists():
                plan["files_to_modify"] = [str(source / "SKILL.md")]
            else:
                plan["files_to_create"] = [str(skill_path / "SKILL.md")]

            # Detect existing profile
            plan["detected_profile"] = self._detect_profile(source)

        return plan

    def execute(
        self,
        state: "WorkflowState",
        plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute the baseline generation plan."""
        skill_path = state.skill_path
        artifacts = {
            "files_created": [],
            "files_modified": [],
            "data": {},
        }

        if state.mode == WorkflowMode.NEW:
            # Create new skill directory
            skill_path.mkdir(parents=True, exist_ok=True)

            # Create scripts directory
            (skill_path / "scripts").mkdir(exist_ok=True)

            # Create SKILL.md with Layer 1 content
            skill_md_content = self._generate_skill_md(
                name=state.skill_name,
                description=f"A new {state.skill_name.replace('-', ' ')} skill",
                version="1.0.0",
            )

            skill_md_path = skill_path / "SKILL.md"
            skill_md_path.write_text(skill_md_content, encoding="utf-8")
            artifacts["files_created"].append(str(skill_md_path))
            artifacts["data"]["skill_md_content"] = skill_md_content

        else:
            # Refactor existing
            source = Path(state.source_path) if state.source_path else skill_path

            # Analyze existing SKILL.md
            existing_skill_md = source / "SKILL.md"
            if existing_skill_md.exists():
                content = existing_skill_md.read_text(encoding="utf-8")
                layer1_data = self._extract_layer1(content)
                body_content = self._extract_body(content)

                # For refactor mode: preserve the body, only normalize frontmatter
                skill_md_content = self._generate_skill_md_with_body(
                    name=layer1_data.get("name", state.skill_name),
                    description=layer1_data.get("description", ""),
                    version=layer1_data.get("version", "1.0.0"),
                    triggers=layer1_data.get("triggers", []),
                    body=body_content,
                )

                # Write normalized version
                skill_md_path = skill_path / "SKILL.md"
                skill_md_path.write_text(skill_md_content, encoding="utf-8")
                artifacts["files_modified"].append(str(skill_md_path))
                artifacts["data"]["original_content"] = content
                artifacts["data"]["skill_md_content"] = skill_md_content
                artifacts["data"]["layer1_data"] = layer1_data
                artifacts["data"]["body_preserved"] = True

            else:
                # No existing SKILL.md, create new one
                skill_md_content = self._generate_skill_md(
                    name=state.skill_name,
                    description=f"Refactored {state.skill_name.replace('-', ' ')} skill",
                    version="1.0.0",
                )

                skill_md_path = skill_path / "SKILL.md"
                skill_md_path.write_text(skill_md_content, encoding="utf-8")
                artifacts["files_created"].append(str(skill_md_path))
                artifacts["data"]["skill_md_content"] = skill_md_content

            # Collect existing files info
            artifacts["data"]["existing_files"] = self._list_existing_files(source)
            artifacts["data"]["detected_profile"] = plan.get("detected_profile", "minimal")

        return artifacts

    def test(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run automated tests on the baseline."""
        skill_path = state.skill_path
        results = {}

        # Test 1: SKILL.md exists
        skill_md_path = skill_path / "SKILL.md"
        results["skill_md_exists"] = {
            "passed": skill_md_path.exists(),
            "message": "SKILL.md exists" if skill_md_path.exists() else "SKILL.md not found",
        }

        if not skill_md_path.exists():
            return results

        # Test 2: Valid YAML frontmatter
        content = skill_md_path.read_text(encoding="utf-8")
        try:
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1])
                    results["yaml_syntax"] = {
                        "passed": True,
                        "message": "YAML frontmatter is valid",
                    }
                else:
                    results["yaml_syntax"] = {
                        "passed": False,
                        "message": "Invalid frontmatter format",
                    }
            else:
                results["yaml_syntax"] = {
                    "passed": False,
                    "message": "File must start with ---",
                }
        except yaml.YAMLError as e:
            results["yaml_syntax"] = {
                "passed": False,
                "message": f"YAML error: {e}",
            }
            return results

        # Test 3: Required fields
        required_fields = ["name", "version", "description"]
        missing = [f for f in required_fields if f not in frontmatter]
        results["required_fields"] = {
            "passed": len(missing) == 0,
            "message": "All required fields present" if not missing else f"Missing: {missing}",
            "details": {"missing": missing, "present": [f for f in required_fields if f in frontmatter]},
        }

        # Test 4: Name format (kebab-case)
        name = frontmatter.get("name", "")
        is_kebab = bool(re.match(r"^[a-z][a-z0-9-]*$", name))
        results["name_format"] = {
            "passed": is_kebab,
            "message": "Name is kebab-case" if is_kebab else f"Name '{name}' should be kebab-case",
        }

        # Test 5: No @augur in Layer 1
        frontmatter_raw = parts[1] if len(parts) >= 3 else ""
        layer1_fields = ["name", "version", "description", "triggers"]
        augur_in_layer1 = False
        for line in frontmatter_raw.split("\n"):
            for field in layer1_fields:
                if line.strip().startswith(f"{field}:") and "# @augur" in line:
                    augur_in_layer1 = True
                    break

        results["no_augur_in_layer1"] = {
            "passed": not augur_in_layer1,
            "message": "No @augur markers in Layer 1" if not augur_in_layer1 else "@augur found in Layer 1 fields",
        }

        return results

    def validate(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
        test_results: Dict[str, Any],
    ) -> "ValidationResult":
        """Validate against acceptance criteria."""
        skill_path = state.skill_path
        skill_md_path = skill_path / "SKILL.md"

        # Use the Layer 1 validator
        result = validate_skill_md_layer1(skill_md_path)

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

        # Check backup for refactor mode
        if state.mode == WorkflowMode.REFACTOR:
            if state.backup_path:
                backup_exists = Path(state.backup_path).exists()
                if not backup_exists:
                    result.add_issue(
                        ValidationIssue(
                            rule="backup_exists",
                            message="Backup was not created",
                            severity="error",
                        )
                    )
            else:
                result.add_issue(
                    ValidationIssue(
                        rule="backup_exists",
                        message="No backup path recorded",
                        severity="warning",
                    )
                )

        return result

    def generate_questions(
        self,
        state: "WorkflowState",
        artifacts: Dict[str, Any],
        validation: Optional["ValidationResult"] = None,
    ) -> List[Dict[str, Any]]:
        """Generate context-aware questions for the user."""
        questions = []
        data = artifacts.get("data", {})

        # Get current SKILL.md content
        skill_md_content = data.get("skill_md_content", "")
        if skill_md_content and skill_md_content.startswith("---"):
            try:
                parts = skill_md_content.split("---", 2)
                frontmatter = yaml.safe_load(parts[1]) if len(parts) >= 3 else {}
            except Exception:
                frontmatter = {}
        else:
            frontmatter = {}

        description = frontmatter.get("description", "")
        name = frontmatter.get("name", state.skill_name)

        # Question 1: Confirm description
        questions.append(
            {
                "id": "description_ok",
                "text": f"The skill '{name}' has been created. Does this description accurately capture its purpose?\n\n\"{description}\"",
                "type": "yes_no",
                "default": True,
                "required": True,
            }
        )

        # Question 2: Profile selection (for refactor, show detected; for new, let them choose)
        if state.mode == WorkflowMode.REFACTOR:
            detected = data.get("detected_profile", "minimal")
            questions.append(
                {
                    "id": "target_profile",
                    "text": f"Detected profile: {detected}. Would you like to target a different profile?",
                    "type": "choice",
                    "options": ["minimal", "standard", "full"],
                    "default": detected,
                    "required": True,
                    "context": "Profiles:\n- minimal: Agent-only (SKILL.md + scripts)\n- standard: With dashboard UI\n- full: Complete app with API, MCP, data",
                }
            )
        else:
            questions.append(
                {
                    "id": "target_profile",
                    "text": "Which profile should this skill target?",
                    "type": "choice",
                    "options": ["minimal", "standard", "full"],
                    "default": state.target_profile,
                    "required": True,
                    "context": "Profiles:\n- minimal: Agent-only (SKILL.md + scripts)\n- standard: With dashboard UI\n- full: Complete app with API, MCP, data",
                }
            )

        # Question 3: For refactor mode, ask about existing files
        if state.mode == WorkflowMode.REFACTOR:
            existing_files = data.get("existing_files", [])
            if existing_files:
                # Show only script files
                scripts = [f for f in existing_files if f.endswith(".py") or f.endswith(".ts")]
                if scripts:
                    questions.append(
                        {
                            "id": "exclude_files",
                            "text": f"Found {len(scripts)} script files. Should any be excluded from refactoring?",
                            "type": "multi_choice",
                            "options": scripts[:20],  # Limit to 20
                            "default": [],
                            "required": False,
                            "context": "Select files to exclude from the refactoring process.",
                        }
                    )

        # Question 4: Confirm description change if user said no
        if not questions[0].get("default", True):
            questions.append(
                {
                    "id": "new_description",
                    "text": "Please provide a better description for this skill:",
                    "type": "text",
                    "default": description,
                    "required": True,
                }
            )

        return questions

    def get_output(self, state: "WorkflowState") -> Dict[str, Any]:
        """Get the stage output data."""
        skill_path = state.skill_path
        skill_md_path = skill_path / "SKILL.md"

        output = {
            "skill_name": state.skill_name,
            "skill_path": str(skill_path),
            "skill_md_path": str(skill_md_path),
        }

        if skill_md_path.exists():
            content = skill_md_path.read_text(encoding="utf-8")
            output["skill_md_content"] = content

            # Extract frontmatter
            if content.startswith("---"):
                try:
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = yaml.safe_load(parts[1])
                        output["frontmatter"] = frontmatter
                except Exception as e:
                    warnings.warn(
                        f"Unable to parse SKILL.md frontmatter at {skill_md_path}: {e}",
                        RuntimeWarning,
                        stacklevel=2,
                    )

        # Include profile
        output["profile_detected"] = self._detect_profile(skill_path)

        return output

    def get_default_answers(self, state: "WorkflowState") -> Dict[str, Any]:
        """Get default answers for auto mode."""
        return {
            "description_ok": True,
            "target_profile": state.target_profile,
            "exclude_files": [],
        }

    # Helper methods

    def _generate_skill_md(
        self,
        name: str,
        description: str,
        version: str = "1.0.0",
        triggers: Optional[List[str]] = None,
    ) -> str:
        """Generate a Layer 1 compliant SKILL.md."""
        triggers = triggers or []
        triggers_yaml = "\n".join(f"  - {t}" for t in triggers) if triggers else ""

        return f"""---
# === Standard Core (Layer 1) - portable, survives export ===
name: {name}
version: {version}
description: {description}
{"triggers:" if triggers else "triggers: []"}
{triggers_yaml}
---

# {name.replace('-', ' ').title()}

## Overview

{description}

## Capabilities

- Core functionality (to be defined in Stage 2)

## Usage

This skill was generated by the Augur Plugin Factory.
Complete the remaining workflow stages to add:
- Triggers and capabilities (Stage 2)
- Data schemas (Stage 3)
- MCP tools and actions (Stage 4)
- Dashboard UI (Stage 5)
"""

    def _extract_layer1(self, content: str) -> Dict[str, Any]:
        """Extract Layer 1 fields from existing SKILL.md."""
        layer1 = {}

        if not content.startswith("---"):
            return layer1

        try:
            parts = content.split("---", 2)
            if len(parts) < 3:
                return layer1

            frontmatter = yaml.safe_load(parts[1])
            if not frontmatter:
                return layer1

            # Extract only Layer 1 fields
            layer1_fields = ["name", "version", "description", "triggers"]
            for field in layer1_fields:
                if field in frontmatter:
                    layer1[field] = frontmatter[field]

        except Exception as e:
            warnings.warn(
                f"Failed to extract Layer 1 frontmatter: {e}",
                RuntimeWarning,
                stacklevel=2,
            )

        return layer1

    def _extract_body(self, content: str) -> str:
        """Extract the body content (after frontmatter) from SKILL.md."""
        if not content.startswith("---"):
            return content

        try:
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
        except Exception as e:
            warnings.warn(
                f"Failed to extract SKILL.md body: {e}",
                RuntimeWarning,
                stacklevel=2,
            )

        return ""

    def _generate_skill_md_with_body(
        self,
        name: str,
        description: str,
        version: str = "1.0.0",
        triggers: Optional[List[str]] = None,
        body: str = "",
    ) -> str:
        """Generate a Layer 1 compliant SKILL.md preserving existing body content."""
        triggers = triggers or []
        triggers_yaml = "\n".join(f"  - {t}" for t in triggers) if triggers else ""

        frontmatter = f"""---
# === Standard Core (Layer 1) - portable, survives export ===
name: {name}
version: {version}
description: {description}
{"triggers:" if triggers else "triggers: []"}
{triggers_yaml}
---"""

        # If body exists, use it; otherwise generate placeholder
        if body:
            return f"{frontmatter}\n\n{body}\n"
        else:
            return self._generate_skill_md(name, description, version, triggers)

    def _detect_profile(self, skill_path: Path) -> str:
        """Detect plugin profile from directory contents."""
        if (skill_path / "api").is_dir():
            return "full"
        elif (skill_path / "dashboard.yaml").exists():
            return "standard"
        else:
            return "minimal"

    def _list_existing_files(self, skill_path: Path) -> List[str]:
        """List existing files in the skill directory."""
        if not skill_path.exists():
            return []

        files = []
        for f in skill_path.rglob("*"):
            if f.is_file():
                try:
                    rel_path = f.relative_to(skill_path)
                    files.append(str(rel_path))
                except ValueError:
                    pass

        return sorted(files)
