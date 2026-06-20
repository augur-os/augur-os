#!/usr/bin/env python3
"""
Shared behavior threshold definitions for dashboard and orchestrator sync.

This file is the SINGLE SOURCE OF TRUTH for autonomy and learning thresholds.
The dashboard (TaskVisibilityPanel.tsx) should match these definitions.

Copyright 2026 Augur Contributors
Licensed under the Apache License, Version 2.0
"""

from typing import List, Dict, Any

# =============================================================================
# AUTONOMY THRESHOLDS
# Controls what actions agents can take at each autonomy level
# =============================================================================

AUTONOMY_THRESHOLDS: List[Dict[str, Any]] = [
    {"level": 0, "action": "explicit_only", "keywords": [], "desc": "Follow explicit triggers only"},
    {
        "level": 20,
        "action": "read",
        "keywords": ["list", "search", "report", "analyze", "check", "get", "fetch", "view", "read"],
        "desc": "Safe read operations",
    },
    {
        "level": 40,
        "action": "test",
        "keywords": ["test", "validate", "verify", "lint", "audit", "scan"],
        "desc": "Run tests & analysis",
    },
    {
        "level": 60,
        "action": "code",
        "keywords": [
            "implement",
            "fix",
            "refactor",
            "create",
            "update",
            "modify",
            "write",
            "edit",
            "add",
            "remove",
            "delete",
        ],
        "desc": "Make code changes",
    },
    {
        "level": 80,
        "action": "chain",
        "keywords": ["execute_chain", "run_workflow", "trigger", "orchestrate", "pipeline"],
        "desc": "Trigger automation chains",
    },
    {
        "level": 90,
        "action": "deploy",
        "keywords": ["deploy", "publish", "release", "push", "staging"],
        "desc": "Deploy to staging",
    },
    {
        "level": 95,
        "action": "config",
        "keywords": ["configure", "settings", "preferences", "config", "weights"],
        "desc": "Modify configurations",
    },
    {
        "level": 100,
        "action": "self_modify",
        "keywords": ["autonomy", "permissions", "access", "self_modify"],
        "desc": "Change autonomy level",
    },
]


# =============================================================================
# LEARNING THRESHOLDS
# Controls retrospective and self-improvement behavior intensity
# =============================================================================

LEARNING_THRESHOLDS: List[Dict[str, Any]] = [
    {"level": 0, "behavior": "fast_execution", "desc": "Minimal logging, no retrospectives"},
    {"level": 20, "behavior": "basic_logging", "desc": "Record completion summaries"},
    {"level": 40, "behavior": "run_retrospectives", "desc": "Analyze outcomes after each chain"},
    {"level": 60, "behavior": "generate_learnings", "desc": "Extract insights for improvement backlog"},
    {"level": 75, "behavior": "pattern_detection", "desc": "Identify recurring issues and successes"},
    {"level": 85, "behavior": "auto_generate_tasks", "desc": "Create improvement items from patterns"},
    {"level": 95, "behavior": "historical_analysis", "desc": "Cross-reference with past performance"},
    {"level": 100, "behavior": "pure_research", "desc": "Prioritize learning over execution"},
]


def get_action_required_level(action: str) -> float:
    """
    Determine minimum autonomy level required for an action.

    Args:
        action: The action name to check (e.g., "implement_feature")

    Returns:
        Float between 0.0 and 1.0 representing required autonomy level
    """
    action_lower = action.lower()

    # Check from highest to lowest level (most restrictive first)
    for threshold in reversed(AUTONOMY_THRESHOLDS):
        keywords = threshold.get("keywords", [])
        if any(keyword in action_lower for keyword in keywords):
            return threshold["level"] / 100.0

    return 0.0  # Explicit-only by default


def get_learning_behavior_at_level(level: float) -> str:
    """
    Get the learning behavior mode for a given investment level.

    Args:
        level: Float between 0.0 and 1.0

    Returns:
        String describing the current learning behavior mode
    """
    level_percent = level * 100

    # Find highest threshold that's at or below current level
    active_behavior = "fast_execution"
    for threshold in LEARNING_THRESHOLDS:
        if threshold["level"] <= level_percent:
            active_behavior = threshold["behavior"]
        else:
            break

    return active_behavior


def is_behavior_enabled(level: float, behavior: str) -> bool:
    """
    Check if a specific learning behavior is enabled at the given level.

    Args:
        level: Float between 0.0 and 1.0
        behavior: Behavior name to check

    Returns:
        True if behavior is enabled at this level
    """
    level_percent = level * 100

    for threshold in LEARNING_THRESHOLDS:
        if threshold["behavior"] == behavior:
            return level_percent >= threshold["level"]

    return False


# Export threshold levels for easy access
AUTONOMY_LEVELS = {t["action"]: t["level"] / 100.0 for t in AUTONOMY_THRESHOLDS}
LEARNING_LEVELS = {t["behavior"]: t["level"] / 100.0 for t in LEARNING_THRESHOLDS}
