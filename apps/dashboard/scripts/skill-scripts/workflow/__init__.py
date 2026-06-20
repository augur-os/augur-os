"""
Staged Plugin Generation/Refactoring Workflow Engine.

Provides a 5-stage workflow for plugin generation and refactoring:
1. Baseline - Import/generate Layer 1 compliant skill
2. Hardening - Enrich with triggers, tiers, safety
3. Data Structures - Define schemas and storage patterns
4. MCP/Actions - Define tools and dashboard actions
5. UI Generation - Generate dashboard components

Each stage follows: Plan → Execute → Test → Validate → Questions → Complete
"""

from .engine import WorkflowEngine
from .state_manager import WorkflowState, StateManager
from .stage_runner import StageRunner, StageResult, PhaseResult
from .validators import (
    ValidationResult,
    validate_skill_md_layer1,
    validate_augur_markers,
    validate_dashboard_yaml,
)

__all__ = [
    "WorkflowEngine",
    "WorkflowState",
    "StateManager",
    "StageRunner",
    "StageResult",
    "PhaseResult",
    "ValidationResult",
    "validate_skill_md_layer1",
    "validate_augur_markers",
    "validate_dashboard_yaml",
]
