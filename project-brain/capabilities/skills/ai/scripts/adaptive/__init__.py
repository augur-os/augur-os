"""
Adaptive Command System (ADR-102)

Provides automatic improvement for slash commands.
"""

from .adaptive_loop import (
    AdaptiveCommand,
    create_adaptive_wrapper,
    run_adaptive_command,
)
from .analyze_execution import (
    AnalysisResult,
    AutoApply,
    Improvement,
    ImprovementPriority,
    ImprovementType,
    analyze_execution,
    classify_improvements,
    save_analysis,
)
from .command_rewriter import (
    apply_improvement_to_chain,
    apply_improvement_to_skill,
    commit_skill_update,
    find_chain_definition,
    find_skill_definition,
    log_improvement,
)
from .incidents import (
    IncidentRecord,
    aggregate_incidents,
    normalize_incident,
    should_promote_incident,
    summarize_incidents,
)
from .execution_tracker import (
    ExecutionLog,
    ExecutionTracker,
    Outcome,
    PhaseStatus,
)

__all__ = [
    "AdaptiveCommand",
    "create_adaptive_wrapper",
    "run_adaptive_command",
    "analyze_execution",
    "classify_improvements",
    "save_analysis",
    "apply_improvement_to_skill",
    "apply_improvement_to_chain",
    "log_improvement",
    "commit_skill_update",
    "find_skill_definition",
    "find_chain_definition",
    "ExecutionTracker",
    "ExecutionLog",
    "IncidentRecord",
    "normalize_incident",
    "aggregate_incidents",
    "summarize_incidents",
    "should_promote_incident",
    "Outcome",
    "PhaseStatus",
    "AnalysisResult",
    "Improvement",
    "ImprovementType",
    "ImprovementPriority",
    "AutoApply",
]
