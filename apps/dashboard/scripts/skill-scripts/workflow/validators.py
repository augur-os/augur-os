"""
Workflow Validators.

Acceptance criteria validators for each stage of the plugin generation workflow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from shutil import which
from subprocess import TimeoutExpired, run as subprocess_run  # nosec B404
from typing import Any, Dict, List, Optional

import yaml


def _resolve_command(command: str) -> str:
    """Resolve executable path for safer subprocess invocation."""
    resolved = which(command)
    return resolved or command


@dataclass
class ValidationIssue:
    """A single validation issue."""

    rule: str
    message: str
    severity: str = "error"  # error, warning, info
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    fixable: bool = False
    fix_suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validation."""

    passed: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)
    score: float = 100.0
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def add_issue(self, issue: ValidationIssue):
        self.issues.append(issue)
        # Recalculate passed and score
        self.passed = len(self.errors) == 0
        total = len(self.issues) or 1
        passed = sum(1 for i in self.issues if i.severity != "error")
        self.score = (passed / total) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "passed": self.passed,
            "score": self.score,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "issues": [
                {
                    "rule": i.rule,
                    "message": i.message,
                    "severity": i.severity,
                    "file_path": i.file_path,
                }
                for i in self.issues
            ],
            "details": self.details,
        }


def validate_skill_md_layer1(skill_md_path: Path) -> ValidationResult:
    """Validate SKILL.md for Layer 1 compliance.

    Checks:
    - File exists
    - Valid YAML frontmatter
    - Required fields: name, version, description
    - Name is kebab-case
    - No @augur markers in Layer 1 section (before triggers)
    """
    result = ValidationResult(passed=True)

    if not skill_md_path.exists():
        result.add_issue(
            ValidationIssue(
                rule="skill_md_exists",
                message=f"SKILL.md not found at {skill_md_path}",
                severity="error",
            )
        )
        return result

    content = skill_md_path.read_text(encoding="utf-8")

    # Check for YAML frontmatter
    if not content.startswith("---"):
        result.add_issue(
            ValidationIssue(
                rule="yaml_frontmatter",
                message="SKILL.md must start with YAML frontmatter (---)",
                severity="error",
                file_path=str(skill_md_path),
            )
        )
        return result

    # Parse frontmatter
    try:
        parts = content.split("---", 2)
        if len(parts) < 3:
            result.add_issue(
                ValidationIssue(
                    rule="yaml_frontmatter",
                    message="Invalid YAML frontmatter format",
                    severity="error",
                    file_path=str(skill_md_path),
                )
            )
            return result

        frontmatter = yaml.safe_load(parts[1])
        if not frontmatter:
            frontmatter = {}
    except yaml.YAMLError as e:
        result.add_issue(
            ValidationIssue(
                rule="yaml_syntax",
                message=f"Invalid YAML syntax: {e}",
                severity="error",
                file_path=str(skill_md_path),
            )
        )
        return result

    # Check required fields
    required_fields = ["name", "version", "description"]
    for field_name in required_fields:
        if field_name not in frontmatter:
            result.add_issue(
                ValidationIssue(
                    rule=f"required_field_{field_name}",
                    message=f"Required field '{field_name}' missing from frontmatter",
                    severity="error",
                    file_path=str(skill_md_path),
                    fixable=True,
                )
            )

    # Validate name format (kebab-case)
    name = frontmatter.get("name", "")
    if name and not re.match(r"^[a-z][a-z0-9-]*$", name):
        result.add_issue(
            ValidationIssue(
                rule="name_format",
                message=f"Name '{name}' must be kebab-case (lowercase letters, numbers, hyphens)",
                severity="error",
                file_path=str(skill_md_path),
                fixable=True,
                fix_suggestion=name.lower().replace("_", "-").replace(" ", "-"),
            )
        )

    # Validate version format (semver)
    version = frontmatter.get("version", "")
    if version and not re.match(r"^\d+\.\d+\.\d+", version):
        result.add_issue(
            ValidationIssue(
                rule="version_format",
                message=f"Version '{version}' should follow semver (e.g., 1.0.0)",
                severity="warning",
                file_path=str(skill_md_path),
            )
        )

    # Check for @augur markers in Layer 1 section
    # Layer 1 is everything before the first @augur marker or @augur-start
    frontmatter_raw = parts[1]
    lines = frontmatter_raw.split("\n")

    layer1_fields = ["name", "version", "description", "triggers"]
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Check if a Layer 1 field has an @augur marker
        for field_name in layer1_fields:
            if stripped.startswith(f"{field_name}:") and "# @augur" in line:
                result.add_issue(
                    ValidationIssue(
                        rule="layer1_no_augur_markers",
                        message=f"Layer 1 field '{field_name}' should not have @augur marker",
                        severity="error",
                        file_path=str(skill_md_path),
                        line_number=i,
                        fixable=True,
                    )
                )

    result.details["frontmatter"] = frontmatter
    return result


def validate_augur_markers(skill_md_path: Path) -> ValidationResult:
    """Validate proper use of @augur markers for Layer 2 fields.

    Checks:
    - Layer 2 fields have @augur markers
    - Block markers (@augur-start/@augur-end) are balanced
    - No orphaned @augur-end markers
    """
    result = ValidationResult(passed=True)

    if not skill_md_path.exists():
        result.add_issue(
            ValidationIssue(
                rule="skill_md_exists",
                message=f"SKILL.md not found at {skill_md_path}",
                severity="error",
            )
        )
        return result

    content = skill_md_path.read_text(encoding="utf-8")

    if not content.startswith("---"):
        return result  # No frontmatter to check

    try:
        parts = content.split("---", 2)
        frontmatter_raw = parts[1] if len(parts) > 1 else ""
    except Exception:
        return result

    lines = frontmatter_raw.split("\n")

    # Track block markers
    in_block = False
    block_start_line = 0

    # Layer 2 fields that should have @augur markers
    layer2_fields = ["category", "mode", "tiers", "safety", "dependencies"]

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Check block markers
        if "@augur-start" in stripped:
            if in_block:
                result.add_issue(
                    ValidationIssue(
                        rule="augur_block_nested",
                        message="Nested @augur-start markers not allowed",
                        severity="error",
                        file_path=str(skill_md_path),
                        line_number=i,
                    )
                )
            in_block = True
            block_start_line = i

        if "@augur-end" in stripped:
            if not in_block:
                result.add_issue(
                    ValidationIssue(
                        rule="augur_block_orphan_end",
                        message="@augur-end without matching @augur-start",
                        severity="error",
                        file_path=str(skill_md_path),
                        line_number=i,
                    )
                )
            in_block = False

        # Check Layer 2 fields outside blocks
        if not in_block:
            for field_name in layer2_fields:
                if stripped.startswith(f"{field_name}:"):
                    if "# @augur" not in line:
                        result.add_issue(
                            ValidationIssue(
                                rule="layer2_needs_marker",
                                message=f"Layer 2 field '{field_name}' should have # @augur marker",
                                severity="warning",
                                file_path=str(skill_md_path),
                                line_number=i,
                                fixable=True,
                            )
                        )

    # Check for unclosed block
    if in_block:
        result.add_issue(
            ValidationIssue(
                rule="augur_block_unclosed",
                message=f"@augur-start at line {block_start_line} has no matching @augur-end",
                severity="error",
                file_path=str(skill_md_path),
                line_number=block_start_line,
            )
        )

    return result


def validate_dashboard_yaml(dashboard_yaml_path: Path, profile: str = "standard") -> ValidationResult:
    """Validate dashboard.yaml for compliance.

    Checks:
    - File exists (for standard+ profiles)
    - Valid YAML syntax
    - Required fields: hub.id, hub.title, tabs
    - First tab is 'overview' with default: true
    - Actions have required fields
    """
    result = ValidationResult(passed=True)

    if profile == "minimal":
        # dashboard.yaml not required for minimal profile
        if dashboard_yaml_path.exists():
            result.details["has_dashboard"] = True
        return result

    if not dashboard_yaml_path.exists():
        result.add_issue(
            ValidationIssue(
                rule="dashboard_yaml_exists",
                message=f"dashboard.yaml required for {profile} profile",
                severity="error",
            )
        )
        return result

    try:
        with open(dashboard_yaml_path) as f:
            config = yaml.safe_load(f)
        if not config:
            config = {}
    except yaml.YAMLError as e:
        result.add_issue(
            ValidationIssue(
                rule="yaml_syntax",
                message=f"Invalid YAML syntax: {e}",
                severity="error",
                file_path=str(dashboard_yaml_path),
            )
        )
        return result

    # Check hub section
    hub = config.get("hub", {})
    if not hub:
        # Check for flat structure (hub_id instead of hub.id)
        hub = {
            "id": config.get("hub_id"),
            "title": config.get("display_name"),
        }

    if not hub.get("id"):
        result.add_issue(
            ValidationIssue(
                rule="hub_id_required",
                message="hub.id (or hub_id) is required",
                severity="error",
                file_path=str(dashboard_yaml_path),
            )
        )

    if not hub.get("title") and not config.get("display_name"):
        result.add_issue(
            ValidationIssue(
                rule="hub_title_required",
                message="hub.title (or display_name) is required",
                severity="error",
                file_path=str(dashboard_yaml_path),
            )
        )

    # Check tabs
    tabs = config.get("tabs", [])
    if tabs:
        first_tab = tabs[0] if tabs else {}
        tab_id = first_tab.get("id", "").lower()
        is_default = first_tab.get("default", False)

        if tab_id != "overview":
            result.add_issue(
                ValidationIssue(
                    rule="first_tab_overview",
                    message="First tab must have id 'overview'",
                    severity="error",
                    file_path=str(dashboard_yaml_path),
                    fixable=True,
                )
            )

        if not is_default:
            result.add_issue(
                ValidationIssue(
                    rule="first_tab_default",
                    message="First tab must have 'default: true'",
                    severity="warning",
                    file_path=str(dashboard_yaml_path),
                    fixable=True,
                )
            )

    # Check actions
    actions = config.get("actions", [])
    for i, action in enumerate(actions):
        action_id = action.get("id")
        if not action_id:
            result.add_issue(
                ValidationIssue(
                    rule="action_id_required",
                    message=f"Action at index {i} missing 'id' field",
                    severity="error",
                    file_path=str(dashboard_yaml_path),
                )
            )
            continue

        required_action_fields = ["label", "icon"]
        for field_name in required_action_fields:
            if field_name not in action:
                result.add_issue(
                    ValidationIssue(
                        rule=f"action_{field_name}_required",
                        message=f"Action '{action_id}' missing '{field_name}' field",
                        severity="warning" if field_name == "icon" else "error",
                        file_path=str(dashboard_yaml_path),
                    )
                )

        if "dispatch" not in action and "flow" not in action:
            result.add_issue(
                ValidationIssue(
                    rule="action_dispatch_required",
                    message=f"Action '{action_id}' missing 'dispatch' field",
                    severity="error",
                    file_path=str(dashboard_yaml_path),
                )
            )

        # Validate dispatch type, with flow kept as a legacy fallback for old files.
        dispatch = action.get("dispatch")
        valid_dispatches = ["fire", "oneshot", "modal", "chat", "ide", "auto"]
        if dispatch and dispatch not in valid_dispatches:
            result.add_issue(
                ValidationIssue(
                    rule="action_dispatch_valid",
                    message=(
                        f"Action '{action_id}' has invalid dispatch '{dispatch}'. "
                        f"Must be one of: {valid_dispatches}"
                    ),
                    severity="error",
                    file_path=str(dashboard_yaml_path),
                )
            )

        flow = action.get("flow")
        valid_flows = ["fast", "llm", "modal"]
        if flow and flow not in valid_flows:
            result.add_issue(
                ValidationIssue(
                    rule="action_flow_valid",
                    message=f"Action '{action_id}' has invalid legacy flow '{flow}'. Must be one of: {valid_flows}",
                    severity="error",
                    file_path=str(dashboard_yaml_path),
                )
            )

    result.details["config"] = config
    return result


def validate_directory_structure(skill_path: Path, profile: str = "standard") -> ValidationResult:
    """Validate skill directory structure for the given profile.

    Checks files exist based on profile requirements.
    """
    result = ValidationResult(passed=True)

    # Minimal profile requirements
    if not (skill_path / "SKILL.md").exists():
        result.add_issue(
            ValidationIssue(
                rule="skill_md_exists",
                message="SKILL.md is required",
                severity="error",
            )
        )

    # Check for at least one of: scripts/, modules/, mcp/
    has_implementation = any(
        [
            (skill_path / "scripts").is_dir(),
            (skill_path / "modules").is_dir(),
            (skill_path / "mcp").is_dir(),
        ]
    )
    if not has_implementation:
        result.add_issue(
            ValidationIssue(
                rule="implementation_exists",
                message="At least one of scripts/, modules/, or mcp/ directory required",
                severity="warning",
            )
        )

    # Standard profile requirements
    if profile in ("standard", "full"):
        if not (skill_path / "dashboard.yaml").exists():
            result.add_issue(
                ValidationIssue(
                    rule="dashboard_yaml_exists",
                    message="dashboard.yaml required for standard profile",
                    severity="error",
                )
            )

        dashboard_dir = skill_path / "dashboard"
        if not dashboard_dir.is_dir():
            result.add_issue(
                ValidationIssue(
                    rule="dashboard_dir_exists",
                    message="dashboard/ directory required for standard profile",
                    severity="error",
                )
            )
        else:
            required_files = ["page.tsx", "layout.tsx", "loading.tsx"]
            for filename in required_files:
                if not (dashboard_dir / filename).exists():
                    result.add_issue(
                        ValidationIssue(
                            rule=f"dashboard_{filename}_exists",
                            message=f"dashboard/{filename} required for standard profile",
                            severity="error",
                        )
                    )

    # Full profile requirements
    if profile == "full":
        if not (skill_path / "api").is_dir():
            result.add_issue(
                ValidationIssue(
                    rule="api_dir_exists",
                    message="api/ directory required for full profile",
                    severity="error",
                )
            )
        elif not (skill_path / "api" / "health").is_dir():
            result.add_issue(
                ValidationIssue(
                    rule="api_health_exists",
                    message="api/health/ endpoint required for full profile",
                    severity="error",
                )
            )

        if not (skill_path / "mcp").is_dir():
            result.add_issue(
                ValidationIssue(
                    rule="mcp_dir_exists",
                    message="mcp/ directory required for full profile",
                    severity="error",
                )
            )
        else:
            if not (skill_path / "mcp" / "__init__.py").exists():
                result.add_issue(
                    ValidationIssue(
                        rule="mcp_init_exists",
                        message="mcp/__init__.py required for full profile",
                        severity="error",
                    )
                )

        if not (skill_path / "augur" / "version.yaml").exists():
            result.add_issue(
                ValidationIssue(
                    rule="version_yaml_exists",
                    message="augur/version.yaml required for full profile",
                    severity="warning",
                )
            )

    return result


def validate_typescript_syntax(files: List[Path]) -> ValidationResult:
    """Validate TypeScript files compile without errors.

    Uses tsc for checking.
    """
    result = ValidationResult(passed=True)

    # Filter to existing .tsx and .ts files
    ts_files = [f for f in files if f.exists() and f.suffix in (".ts", ".tsx")]

    if not ts_files:
        return result

    for ts_file in ts_files:
        try:
            # Run tsc --noEmit on the file
            npx_cmd = _resolve_command("npx")
            proc = subprocess_run(  # nosec B603
                [npx_cmd, "tsc", "--noEmit", "--skipLibCheck", str(ts_file)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=ts_file.parent,
            )
            if proc.returncode != 0:
                result.add_issue(
                    ValidationIssue(
                        rule="typescript_compiles",
                        message=f"TypeScript error in {ts_file.name}: {proc.stderr[:200]}",
                        severity="error",
                        file_path=str(ts_file),
                    )
                )
        except TimeoutExpired:
            result.add_issue(
                ValidationIssue(
                    rule="typescript_compiles",
                    message=f"TypeScript check timed out for {ts_file.name}",
                    severity="warning",
                    file_path=str(ts_file),
                )
            )
        except FileNotFoundError:
            # tsc not available, skip check
            result.add_issue(
                ValidationIssue(
                    rule="typescript_compiles",
                    message="TypeScript compiler (tsc) not found, skipping check",
                    severity="info",
                )
            )
            break

    return result
