"""Interfaces for augur-mcp extensibility."""

from .skill_registry import SkillRecord, SkillRegistry

# Backward-compat alias — new code should use SkillRecord directly.
SkillMetadata = SkillRecord

__all__ = ["SkillRecord", "SkillMetadata", "SkillRegistry"]
