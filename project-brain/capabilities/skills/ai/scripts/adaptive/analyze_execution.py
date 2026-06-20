"""
Execution Analysis Engine for Adaptive Slash Commands (ADR-102)

Analyzes execution logs to extract patterns and improvement opportunities.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .execution_tracker import ExecutionLog, PhaseStatus


class ImprovementType(str, Enum):
    ADD_STEP = "add_step"
    ADD_HINT = "add_hint"
    ADD_CHECK = "add_check"
    REORDER_PHASE = "reorder_phase"
    REMOVE_STEP = "remove_step"
    CHANGE_MODEL = "change_model"
    ADD_TIMEOUT = "add_timeout"
    ADD_CACHE = "add_cache"
    FIX_ERROR_PATTERN = "fix_error_pattern"


class ImprovementPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AutoApply(str, Enum):
    YES = "yes"
    NO = "no"
    CONDITIONAL = "conditional"


@dataclass
class Improvement:
    type: ImprovementType
    priority: ImprovementPriority
    auto_apply: AutoApply
    description: str
    target_phase: str | None = None
    target_step: str | None = None
    suggested_content: str | None = None
    evidence: str | None = None


@dataclass
class AnalysisResult:
    success_patterns: list[str] = field(default_factory=list)
    failure_patterns: list[dict[str, Any]] = field(default_factory=list)
    missing_steps: list[dict[str, Any]] = field(default_factory=list)
    optimizations: list[dict[str, Any]] = field(default_factory=list)
    edge_cases: list[dict[str, Any]] = field(default_factory=list)
    incidents: list[dict[str, Any]] = field(default_factory=list)
    improvements: list[Improvement] = field(default_factory=list)


def analyze_execution(log: ExecutionLog) -> AnalysisResult:
    """Analyze execution log and extract improvement opportunities."""
    result = AnalysisResult()

    # Extract success patterns
    for phase in log.phases:
        if phase.status == PhaseStatus.COMPLETED and not phase.issues:
            duration = (phase.completed_at - phase.started_at) if phase.completed_at and phase.started_at else 0
            if duration < 60:  # Fast completion
                result.success_patterns.append(f"{phase.name} completed in {duration:.0f}s without issues")

        # Check for retries
        for step in phase.steps:
            if step.retry_count > 0:
                result.failure_patterns.append(
                    {
                        "phase": phase.name,
                        "step": step.name,
                        "error": step.error,
                        "resolution": step.resolution,
                        "retry_count": step.retry_count,
                    }
                )

        # Check for phase issues
        for issue in phase.issues:
            result.failure_patterns.append(
                {
                    "phase": phase.name,
                    "issue": issue,
                }
            )

    known_incident_messages = {incident.message for incident in log.incidents}

    # Analyze blockers that were not normalized into known incidents.
    for blocker in log.blockers:
        if blocker in known_incident_messages:
            continue
        result.edge_cases.append(
            {
                "trigger": blocker,
                "suggestion": f"Add pre-check to detect and handle: {blocker}",
            }
        )

    for incident in log.incidents:
        result.incidents.append(incident.to_dict())

    # Generate improvements from patterns
    result.improvements = _generate_improvements(log, result)

    return result


def _generate_improvements(log: ExecutionLog, analysis: AnalysisResult) -> list[Improvement]:
    """Generate specific improvements from analysis."""
    improvements = []

    for incident in analysis.incidents:
        improvements.append(
            Improvement(
                type=ImprovementType.FIX_ERROR_PATTERN,
                priority=ImprovementPriority.HIGH,
                auto_apply=AutoApply.CONDITIONAL,
                description=f"Investigate recurring incident {incident['fingerprint']}",
                suggested_content=(
                    f"Owner path: {incident['owner_path']} | "
                    f"category: {incident['category']} | "
                    f"severity: {incident['severity']}"
                ),
                evidence=incident["message"],
            )
        )

    # Failure patterns → add checks or hints
    for pattern in analysis.failure_patterns:
        if pattern.get("error"):
            error_msg = pattern.get("error", "")
            step_name = pattern.get("step", "unknown")

            # Check for common error patterns
            if "timeout" in error_msg.lower():
                improvements.append(
                    Improvement(
                        type=ImprovementType.ADD_TIMEOUT,
                        priority=ImprovementPriority.HIGH,
                        auto_apply=AutoApply.YES,
                        description=f"Add timeout handling for {step_name}",
                        target_phase=pattern.get("phase"),
                        target_step=step_name,
                        suggested_content="Add timeout hint: 'Split into smaller subtasks if exceeds 5 minutes'",
                        evidence=error_msg,
                    )
                )

            elif "not found" in error_msg.lower() or "missing" in error_msg.lower():
                improvements.append(
                    Improvement(
                        type=ImprovementType.ADD_CHECK,
                        priority=ImprovementPriority.HIGH,
                        auto_apply=AutoApply.YES,
                        description=f"Add existence check before {step_name}",
                        target_phase=pattern.get("phase"),
                        target_step=step_name,
                        suggested_content="Verify required files/modules exist before proceeding",
                        evidence=error_msg,
                    )
                )

            elif pattern.get("retry_count", 0) >= 2:
                improvements.append(
                    Improvement(
                        type=ImprovementType.FIX_ERROR_PATTERN,
                        priority=ImprovementPriority.HIGH,
                        auto_apply=AutoApply.CONDITIONAL,
                        description=f"Persistent failure in {step_name} - needs investigation",
                        target_phase=pattern.get("phase"),
                        target_step=step_name,
                        suggested_content="Consider alternative approach or add fallback logic",
                        evidence=f"Retried {pattern.get('retry_count')} times: {error_msg}",
                    )
                )

    # Blockers → add pre-checks
    for edge_case in analysis.edge_cases:
        improvements.append(
            Improvement(
                type=ImprovementType.ADD_CHECK,
                priority=ImprovementPriority.MEDIUM,
                auto_apply=AutoApply.YES,
                description=f"Add pre-check for: {edge_case.get('trigger', 'unknown')}",
                suggested_content=edge_case.get("suggestion"),
                evidence=edge_case.get("trigger"),
            )
        )

    # Success patterns → consider caching
    for pattern in analysis.success_patterns:
        if "completed" in pattern and "without issues" in pattern:
            improvements.append(
                Improvement(
                    type=ImprovementType.ADD_CACHE,
                    priority=ImprovementPriority.LOW,
                    auto_apply=AutoApply.YES,
                    description="Consider caching results for repeated success patterns",
                    evidence=pattern,
                )
            )

    # Learnings → add as improvements
    for learning in log.learnings:
        improvements.append(
            Improvement(
                type=ImprovementType.ADD_HINT,
                priority=ImprovementPriority.MEDIUM,
                auto_apply=AutoApply.YES,
                description=f"Learning: {learning}",
                suggested_content=f"Add note to command: {learning}",
                evidence="Recorded learning from execution",
            )
        )

    return improvements


def classify_improvements(
    improvements: list[Improvement],
) -> dict[str, list[Improvement]]:
    """Classify improvements into auto-apply and needs-review categories."""
    return {
        "auto_apply": [i for i in improvements if i.auto_apply == AutoApply.YES],
        "needs_review": [i for i in improvements if i.auto_apply in (AutoApply.NO, AutoApply.CONDITIONAL)],
    }


def save_analysis(
    command_name: str,
    analysis: AnalysisResult,
    runtime_dir: Path,
) -> Path:
    """Save analysis results to disk."""
    timestamp = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    analysis_dir = runtime_dir / "command-evolution" / command_name / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    analysis_path = analysis_dir / f"{timestamp}.json"

    data = {
        "timestamp": timestamp,
        "success_patterns": analysis.success_patterns,
        "failure_patterns": analysis.failure_patterns,
        "missing_steps": analysis.missing_steps,
        "optimizations": analysis.optimizations,
        "edge_cases": analysis.edge_cases,
        "incidents": analysis.incidents,
        "improvements": [
            {
                "type": i.type.value,
                "priority": i.priority.value,
                "auto_apply": i.auto_apply.value,
                "description": i.description,
                "target_phase": i.target_phase,
                "target_step": i.target_step,
                "suggested_content": i.suggested_content,
                "evidence": i.evidence,
            }
            for i in analysis.improvements
        ],
    }

    analysis_path.write_text(json.dumps(data, indent=2))
    return analysis_path
