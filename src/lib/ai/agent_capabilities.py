"""Agent capabilities and scoring system for smart routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class AgentCapabilities:
    """
    Defines what context and tools an agent can access.

    Used for smart routing - agents with more relevant capabilities
    score higher for specific tasks.
    """

    agent_name: str
    agent_type: str  # "ide", "cli", "sdk"

    # Context access capabilities
    has_sprint_context: bool = False
    has_slash_commands: bool = False
    has_mcp_tools: bool = False
    has_rag_access: bool = False
    has_voice_transcripts: bool = False
    has_factory_insights: bool = False

    # Execution capabilities
    can_execute_code: bool = False
    can_modify_files: bool = False
    can_create_commits: bool = False
    can_run_tests: bool = False

    # Specializations (for smart routing)
    specializations: list[str] = field(default_factory=list)
    # Examples: ["ui_development", "data_analysis", "debugging", "code_review", "testing"]

    # Health and availability
    health_status: str = "unknown"  # "healthy", "degraded", "unavailable"
    last_used: Optional[datetime] = None

    # Execution metadata
    execution_mode: str = "cli"  # "cli", "sdk", "mcp", "chat_prompt"
    supported_fallbacks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "agent_name": self.agent_name,
            "agent_type": self.agent_type,
            "context_access": {
                "sprint": self.has_sprint_context,
                "slash_commands": self.has_slash_commands,
                "mcp_tools": self.has_mcp_tools,
                "rag": self.has_rag_access,
                "voice": self.has_voice_transcripts,
                "factory_insights": self.has_factory_insights,
            },
            "execution_capabilities": {
                "execute_code": self.can_execute_code,
                "modify_files": self.can_modify_files,
                "create_commits": self.can_create_commits,
                "run_tests": self.can_run_tests,
            },
            "specializations": self.specializations,
            "health_status": self.health_status,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "execution_mode": self.execution_mode,
            "supported_fallbacks": self.supported_fallbacks,
        }


@dataclass
class AgentScore:
    """
    Scoring result for an agent on a specific task.

    Higher scores indicate better fit for the task.
    """

    agent_name: str
    total_score: float = 0.0  # 0-100

    # Score components
    health_score: float = 0.0  # 0-50 (50% weight)
    capability_score: float = 0.0  # 0-30 (30% weight)
    availability_score: float = 0.0  # 0-20 (20% weight)

    # Explanation for user
    reasoning: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "agent_name": self.agent_name,
            "total_score": round(self.total_score, 2),
            "components": {
                "health": round(self.health_score, 2),
                "capability": round(self.capability_score, 2),
                "availability": round(self.availability_score, 2),
            },
            "reasoning": self.reasoning,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
        }


@dataclass
class AgentSelection:
    """
    Result of routing decision with recommended agent and alternatives.
    """

    recommended_agent: str
    recommended_score: AgentScore
    alternative_agents: list[AgentScore] = field(default_factory=list)

    # Context that will be injected
    context_preset: str = "standard"
    context_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "recommended": {"agent": self.recommended_agent, "score": self.recommended_score.to_dict()},
            "alternatives": [score.to_dict() for score in self.alternative_agents[:3]],  # Top 3
            "context": {"preset": self.context_preset, "summary": self.context_summary},
        }


def score_agent_for_task(
    capabilities: AgentCapabilities, task_keywords: list[str], required_capabilities: Optional[list[str]] = None
) -> AgentScore:
    """
    Score an agent for a specific task.

    Args:
        capabilities: Agent's capabilities
        task_keywords: Keywords from task description (e.g., ["debug", "authentication"])
        required_capabilities: Optional list of required capability names

    Returns:
        AgentScore with breakdown
    """
    score = AgentScore(agent_name=capabilities.agent_name)

    # Health score (0-50 points, 50% weight)
    if capabilities.health_status == "healthy":
        score.health_score = 50.0
        score.strengths.append("Fully operational")
    elif capabilities.health_status == "degraded":
        score.health_score = 25.0
        score.weaknesses.append("Degraded health status")
    else:  # unavailable or unknown
        score.health_score = 0.0
        score.weaknesses.append("Not available")

    # Capability score (0-30 points, 30% weight)
    capability_points = 0.0

    # Check required capabilities first (disqualify if missing)
    if required_capabilities:
        has_all_required = all(getattr(capabilities, cap, False) for cap in required_capabilities)
        if not has_all_required:
            score.capability_score = 0.0
            score.weaknesses.append("Missing required capabilities")
            score.total_score = score.health_score + score.capability_score + score.availability_score
            return score

    # Score based on context access (15 points possible)
    context_caps = 0
    if capabilities.has_sprint_context:
        context_caps += 1
        score.strengths.append("Has sprint context")
    if capabilities.has_slash_commands:
        context_caps += 1
    if capabilities.has_mcp_tools:
        context_caps += 1
        score.strengths.append("Has MCP tools")
    if capabilities.has_factory_insights:
        context_caps += 1
    if capabilities.has_rag_access:
        context_caps += 1
    if capabilities.has_voice_transcripts:
        context_caps += 1

    capability_points += (context_caps / 6.0) * 15.0

    # Score based on execution capabilities (10 points possible)
    exec_caps = 0
    if capabilities.can_execute_code:
        exec_caps += 1
    if capabilities.can_modify_files:
        exec_caps += 1
        score.strengths.append("Can modify files")
    if capabilities.can_create_commits:
        exec_caps += 1
    if capabilities.can_run_tests:
        exec_caps += 1

    capability_points += (exec_caps / 4.0) * 10.0

    # Score based on specializations matching task keywords (5 points possible)
    if capabilities.specializations and task_keywords:
        matches = sum(
            1
            for spec in capabilities.specializations
            if any(keyword.lower() in spec.lower() for keyword in task_keywords)
        )
        if matches > 0:
            capability_points += min(matches * 2.5, 5.0)
            score.strengths.append(f"Specialized in {', '.join(capabilities.specializations[:2])}")

    score.capability_score = capability_points

    # Availability score (0-20 points, 20% weight)
    if capabilities.agent_type == "cli":
        # CLI agents are lightweight and always available
        score.availability_score = 20.0
    elif capabilities.agent_type == "sdk":
        # SDK agents require Python environment but generally available
        score.availability_score = 15.0
    elif capabilities.agent_type == "ide":
        # IDE agents require the IDE to be running
        if capabilities.health_status == "healthy":
            score.availability_score = 20.0
        else:
            score.availability_score = 5.0
            score.weaknesses.append("IDE must be running")

    # Calculate total
    score.total_score = score.health_score + score.capability_score + score.availability_score

    # Generate reasoning
    if score.total_score >= 80:
        score.reasoning = f"Excellent fit - {capabilities.agent_name} has all the capabilities needed"
    elif score.total_score >= 60:
        score.reasoning = f"Good fit - {capabilities.agent_name} can handle this task well"
    elif score.total_score >= 40:
        score.reasoning = f"Moderate fit - {capabilities.agent_name} may work but has limitations"
    else:
        score.reasoning = f"Poor fit - {capabilities.agent_name} lacks key capabilities or availability"

    return score
