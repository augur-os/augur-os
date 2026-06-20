"""
Pydantic input models for core MCP tools.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResponseFormat(str, Enum):
    """Output format for responses."""

    MARKDOWN = "markdown"
    JSON = "json"


class ListSkillsInput(BaseModel):
    """Input for listing available skills."""

    model_config = ConfigDict(str_strip_whitespace=True, extra='allow')

    format: ResponseFormat = Field(
        default=ResponseFormat.JSON, description="Output format: 'json' for compact, 'markdown' for readable"
    )
    ownership: str | None = None  # Filter by ownership: augur, adopted, external


class GetSkillInput(BaseModel):
    """Input for getting skill overview."""

    model_config = ConfigDict(str_strip_whitespace=True, extra='allow')

    skill_name: str = Field(
        ..., description="Name of the skill (e.g., 'job-analyzer', 'recipe-manager')", min_length=1, max_length=50
    )
    include_modules: bool = Field(default=False, description="Include module list in response")


class LoadModuleInput(BaseModel):
    """Input for loading a specific module."""

    model_config = ConfigDict(str_strip_whitespace=True, extra='allow')

    skill_name: str = Field(..., description="Parent skill name", min_length=1)
    module_name: str = Field(..., description="Module filename without .md extension", min_length=1)


class LoadReferenceInput(BaseModel):
    """Input for loading reference documentation."""

    model_config = ConfigDict(str_strip_whitespace=True, extra='allow')

    skill_name: str = Field(..., description="Parent skill name", min_length=1)
    reference_name: str = Field(..., description="Reference filename without .md extension", min_length=1)


class FindSkillInput(BaseModel):
    """Input for finding best skill for a query."""

    model_config = ConfigDict(str_strip_whitespace=True, extra='allow')

    query: str = Field(..., description="Natural language query describing the task", min_length=3)
    top_k: int = Field(default=3, description="Number of top matches to return", ge=1, le=10)


class CacheControlInput(BaseModel):
    """Input for cache management."""

    model_config = ConfigDict(str_strip_whitespace=True, extra='allow')

    action: str = Field(..., description="Action: 'stats', 'invalidate', 'invalidate_skill'")
    skill_name: str | None = Field(None, description="Skill to invalidate (for invalidate_skill)")


class GetContextInput(BaseModel):
    """Input for getting enriched Augur context.

    This is the KEY MOAT tool - provides personalized context that
    standalone IDE agents cannot replicate.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra='allow')

    skill_hint: str | None = Field(
        None, description="Optional skill name to focus context on (e.g., 'recipes', 'careers')"
    )
    format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for readable prompt, 'json' for structured data",
    )


class GetPreferencesInput(BaseModel):
    """Input for getting user preferences."""

    model_config = ConfigDict(str_strip_whitespace=True, extra='allow')

    key: str | None = Field(None, description="Specific preference key to retrieve (returns all if None)")


class UpdatePreferenceInput(BaseModel):
    """Input for updating a user preference."""

    model_config = ConfigDict(str_strip_whitespace=True, extra='allow')

    key: str = Field(..., description="Preference key to update")
    value: Any = Field(
        ...,
        description="New value (string, number, boolean, object, array, or null)",
        json_schema_extra={
            "anyOf": [
                {"type": "string"},
                {"type": "number"},
                {"type": "boolean"},
                {"type": "object"},
                {"type": "array"},
                {"type": "null"},
            ]
        },
    )


__all__ = [
    "ResponseFormat",
    "ListSkillsInput",
    "GetSkillInput",
    "LoadModuleInput",
    "LoadReferenceInput",
    "FindSkillInput",
    "CacheControlInput",
    "GetContextInput",
    "GetPreferencesInput",
    "UpdatePreferenceInput",
]
