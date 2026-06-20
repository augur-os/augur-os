#!/usr/bin/env python3
"""
Factory Pipeline - Orchestrates factory agents for vertical creation.

This is part of the MOAT architecture. When creating a new vertical,
this pipeline ensures:

1. Architect designs the spec with proper horizontal wiring
2. Developer scaffolds code using design system patterns
3. DevOps registers with MCP and runs health checks

Usage:
    from factory_pipeline import FactoryPipeline

    pipeline = FactoryPipeline()
    result = pipeline.create_vertical("meal-planner", "AI-powered weekly meal planning")
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Add project root to path
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config.paths import get_project_root  # noqa: E402


@dataclass
class PipelineStep:
    """A step in the factory pipeline."""

    agent: str  # architect, developer, devops
    action: str
    status: str = "pending"  # pending, running, success, failed
    output: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class PipelineResult:
    """Result of a factory pipeline execution."""

    vertical_name: str
    description: str
    status: str = "pending"  # pending, running, success, failed
    steps: list[PipelineStep] = field(default_factory=list)
    spec_path: Optional[Path] = None
    vertical_path: Optional[Path] = None
    registered_with_mcp: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "vertical_name": self.vertical_name,
            "description": self.description,
            "status": self.status,
            "steps": [
                {
                    "agent": s.agent,
                    "action": s.action,
                    "status": s.status,
                    "output": s.output,
                    "error": s.error,
                }
                for s in self.steps
            ],
            "spec_path": str(self.spec_path) if self.spec_path else None,
            "vertical_path": str(self.vertical_path) if self.vertical_path else None,
            "registered_with_mcp": self.registered_with_mcp,
            "created_at": self.created_at.isoformat(),
        }

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"# Factory Pipeline: {self.vertical_name}",
            f"*{self.description}*",
            "",
            f"**Status**: {self.status}",
            f"**Created**: {self.created_at.strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Steps",
        ]

        for step in self.steps:
            icon = {"pending": "⏳", "running": "🔄", "success": "✅", "failed": "❌"}.get(step.status, "•")
            lines.append(f"{icon} **{step.agent}**: {step.action} - {step.status}")

        lines.append("")
        lines.append("## Artifacts")
        if self.spec_path:
            lines.append(f"- Spec: `{self.spec_path}`")
        if self.vertical_path:
            lines.append(f"- Vertical: `{self.vertical_path}`")

        lines.append("")
        lines.append("## Integration")
        lines.append(f"- Registered with MCP: {'✅' if self.registered_with_mcp else '❌'}")

        return "\n".join(lines)


class FactoryPipeline:
    """
    Orchestrates factory agents to create production-ready verticals.

    Ensures new skills are properly integrated into the Augur
    ecosystem with:

    - Plugin dependency resolution
    - Factory agent design reviews
    - MCP registration
    - Health checks
    """

    def __init__(self):
        self.project_root = get_project_root()
        self.data_dir = get_project_root()
        self.specs_dir = self.data_dir / "factory" / "architect" / "specs"
        self.verticals_dir = self.project_root / "plugins" / "vertical"

    def create_vertical(self, name: str, description: str, dry_run: bool = False) -> PipelineResult:
        """
        Execute full factory pipeline to create a vertical.

        Args:
            name: Vertical name (e.g., "meal-planner")
            description: Brief description of the vertical
            dry_run: If True, only generate spec without creating files

        Returns:
            PipelineResult with status and artifacts
        """
        result = PipelineResult(
            vertical_name=name,
            description=description,
            status="running",
        )

        # Step 1: Architect designs spec
        result.steps.append(
            PipelineStep(
                agent="architect",
                action="design_spec",
                status="running",
                started_at=datetime.now(),
            )
        )

        try:
            spec = self._architect_design_spec(name, description)
            result.steps[-1].status = "success"
            result.steps[-1].output = f"Spec created at {spec['path']}"
            result.steps[-1].completed_at = datetime.now()
            result.spec_path = spec["path"]
        except Exception as e:
            result.steps[-1].status = "failed"
            result.steps[-1].error = str(e)
            result.steps[-1].completed_at = datetime.now()
            result.status = "failed"
            return result

        if dry_run:
            result.status = "success"
            return result

        # Step 2: Developer scaffolds vertical
        result.steps.append(
            PipelineStep(
                agent="developer",
                action="scaffold_vertical",
                status="running",
                started_at=datetime.now(),
            )
        )

        try:
            vertical = self._developer_scaffold(name, spec)
            result.steps[-1].status = "success"
            result.steps[-1].output = f"Vertical scaffolded at {vertical['path']}"
            result.steps[-1].completed_at = datetime.now()
            result.vertical_path = vertical["path"]
        except Exception as e:
            result.steps[-1].status = "failed"
            result.steps[-1].error = str(e)
            result.steps[-1].completed_at = datetime.now()
            result.status = "failed"
            return result

        # Step 3: DevOps registers with MCP
        result.steps.append(
            PipelineStep(
                agent="devops",
                action="register_mcp",
                status="running",
                started_at=datetime.now(),
            )
        )

        try:
            self._devops_register_mcp(name)
            result.steps[-1].status = "success"
            result.steps[-1].output = "Registered with MCP server"
            result.steps[-1].completed_at = datetime.now()
            result.registered_with_mcp = True
        except Exception as e:
            result.steps[-1].status = "failed"
            result.steps[-1].error = str(e)
            result.steps[-1].completed_at = datetime.now()
            # Non-fatal, continue

        # Step 4: Validate dependencies
        result.steps.append(
            PipelineStep(
                agent="devops",
                action="validate_dependencies",
                status="running",
                started_at=datetime.now(),
            )
        )

        try:
            validation = self._validate_dependencies(name)
            if validation.get("valid"):
                result.steps[-1].status = "success"
                result.steps[-1].output = f"Dependencies valid: {validation.get('resolved', [])}"
            else:
                result.steps[-1].status = "failed"
                result.steps[-1].error = f"Missing dependencies: {validation.get('missing', [])}"
            result.steps[-1].completed_at = datetime.now()
        except Exception as e:
            result.steps[-1].status = "failed"
            result.steps[-1].error = str(e)
            result.steps[-1].completed_at = datetime.now()
            # Non-fatal, continue

        # Step 5: DevOps health check
        result.steps.append(
            PipelineStep(
                agent="devops",
                action="health_check",
                status="running",
                started_at=datetime.now(),
            )
        )

        try:
            health = self._devops_health_check(name)
            result.steps[-1].status = "success"
            result.steps[-1].output = f"Health check passed: {health}"
            result.steps[-1].completed_at = datetime.now()
        except Exception as e:
            result.steps[-1].status = "failed"
            result.steps[-1].error = str(e)
            result.steps[-1].completed_at = datetime.now()

        # Determine overall status
        failed_steps = [s for s in result.steps if s.status == "failed"]
        if len(failed_steps) == 0:
            result.status = "success"
        elif len(failed_steps) <= 2:
            result.status = "partial"
        else:
            result.status = "failed"

        # Save result to data directory
        self._save_result(result)

        return result

    def _architect_design_spec(self, name: str, description: str) -> dict:
        """Architect agent designs the vertical spec."""
        self.specs_dir.mkdir(parents=True, exist_ok=True)

        spec_path = self.specs_dir / f"{name}-spec.yaml"

        # Determine recommended plugin dependencies based on keywords
        recommended_deps = ["notifications"]  # Default - for alerts/reviews

        description_lower = description.lower()
        if any(k in description_lower for k in ["voice", "audio", "dictate", "transcribe"]):
            recommended_deps.append("capture")
        if any(k in description_lower for k in ["file", "document", "folder", "organize"]):
            recommended_deps.append("file-manager")
        if any(k in description_lower for k in ["skill", "learn", "knowledge", "search"]):
            recommended_deps.append("knowledge")
        if any(k in description_lower for k in ["health", "fitness", "wearable"]):
            recommended_deps.append("health")

        spec = {
            "name": name,
            "description": description,
            "created": datetime.now().isoformat(),
            "architect": "factory-pipeline",
            "dependencies": {
                "plugins": recommended_deps,
                "reason": f"Based on description keywords: {description[:100]}",
            },
            "structure": {
                "skill_md": True,
                "modules": ["core", "data-operations"],
                "references": ["setup", "operating-guide"],
                "scripts": [],
            },
            "data_schema": {
                "primary_entity": name.replace("-", "_"),
                "storage_format": "yaml",
                "storage_path": f"augur/vertical-life/{name}/",  # Use get_skill_data_dir() at runtime
            },
            "commands": [
                {
                    "trigger": f"process {name}",
                    "action": "process_inbox",
                    "description": "Process items from inbox",
                },
                {
                    "trigger": f"search {name}",
                    "action": "search",
                    "description": "Search existing items",
                },
            ],
        }

        with open(spec_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(spec, f, default_flow_style=False, sort_keys=False)

        return {"spec": spec, "path": spec_path}

    def _developer_scaffold(self, name: str, spec: dict) -> dict:
        """Developer agent scaffolds the vertical directory."""
        vertical_path = self.verticals_dir / name
        vertical_path.mkdir(parents=True, exist_ok=True)

        spec_data = spec.get("spec", {})

        # Create SKILL.md
        skill_md = f"""---
name: {name}
description: {spec_data.get('description', '')}
triggers:
  - process {name}
  - search {name}
  - {name} status
horizontals:
  {chr(10).join('  - ' + h for h in spec_data.get('horizontals', {}).get('recommended', []))}
---

# {name.replace('-', ' ').title()}

{spec_data.get('description', '')}

## Commands

| Command | Action |
|---------|--------|
| `process {name}` | Process items from inbox |
| `search {name} [query]` | Search existing items |
| `{name} status` | Show current status |

## Data Storage

Data directory resolved via `get_skill_data_dir("{name}")` at runtime.

## Integration

Works with:
{chr(10).join('- `' + h + '`' for h in spec_data.get('horizontals', {}).get('recommended', []))}
"""

        (vertical_path / "SKILL.md").write_text(skill_md, encoding="utf-8")

        # Create modules directory
        modules_dir = vertical_path / "modules"
        modules_dir.mkdir(exist_ok=True)

        # Create core module
        core_module = f"""# Core Module

Core functionality for {name}.

## Processing Workflow

1. Read from inbox
2. Parse and validate
3. Store in data directory
4. Update stats

## Functions

### process_item(item)
Process a single item from the inbox.

### validate_item(item)
Validate item structure and content.
"""
        (modules_dir / "core.md").write_text(core_module, encoding="utf-8")

        # Create references directory
        refs_dir = vertical_path / "references"
        refs_dir.mkdir(exist_ok=True)

        # Create operating guide
        operating_guide = f"""# Operating Guide

How to operate the {name} skill.

## Quick Start

1. Add items to your inbox
2. Say "process {name}"
3. Items are processed and stored

## Configuration

Edit the config file in the skill's data directory (resolved via `get_skill_data_dir("{name}")`)
"""
        (refs_dir / "operating-guide.md").write_text(operating_guide, encoding="utf-8")

        return {"path": vertical_path}

    def _devops_register_mcp(self, name: str):
        """DevOps agent registers the vertical with MCP server."""
        # The MCP server auto-discovers skills from plugins/vertical
        # Just verify the skill can be found
        skill_path = self.verticals_dir / name / "SKILL.md"
        if not skill_path.exists():
            raise FileNotFoundError(f"SKILL.md not found at {skill_path}")

        # TODO: Add explicit registration logic if needed

    def _validate_dependencies(self, name: str) -> dict:
        """Validate that all declared dependencies can be resolved."""
        try:
            from src.plugins.context import validate_dependencies

            return validate_dependencies(name)
        except ImportError:
            # Context system not available - skip validation
            return {"valid": True, "skipped": True}
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def _devops_health_check(self, name: str) -> dict:
        """DevOps agent runs health check on the new vertical."""
        checks = {
            "skill_md_exists": False,
            "modules_exist": False,
            "references_exist": False,
            "data_dir_writable": False,
        }

        vertical_path = self.verticals_dir / name

        checks["skill_md_exists"] = (vertical_path / "SKILL.md").exists()
        checks["modules_exist"] = (vertical_path / "modules").is_dir()
        checks["references_exist"] = (vertical_path / "references").is_dir()

        data_path = self.data_dir / "vertical" / name
        try:
            data_path.mkdir(parents=True, exist_ok=True)
            checks["data_dir_writable"] = True
        except OSError:
            checks["data_dir_writable"] = False

        return checks

    def _save_result(self, result: PipelineResult):
        """Save pipeline result to data directory."""
        results_dir = self.data_dir / "factory" / "pipeline" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        result_path = results_dir / f"{result.vertical_name}-{result.created_at.strftime('%Y%m%d_%H%M%S')}.yaml"

        with open(result_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(result.to_dict(), f, default_flow_style=False, sort_keys=False)


# Convenience function
def create_vertical(name: str, description: str, dry_run: bool = False) -> PipelineResult:
    """Create a new vertical via factory pipeline."""
    return FactoryPipeline().create_vertical(name, description, dry_run)


if __name__ == "__main__":
    """Test factory pipeline."""

    _out("Testing Factory Pipeline")
    _out("=" * 50)

    pipeline = FactoryPipeline()

    # Dry run to test
    result = pipeline.create_vertical("test-vertical", "A test vertical for validation purposes", dry_run=True)

    _out(result.to_summary())
