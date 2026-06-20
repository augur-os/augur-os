from typing import Optional
from pydantic import BaseModel, Field


class LLMLogEntry(BaseModel):
    """
    Strict schema for LLM interaction logs.
    This ensures all written logs follow a consistent contract for analytics.
    """

    timestamp: str = Field(..., description="ISO 8601 timestamp")
    provider: str = Field(..., description="Provider name (e.g. openai, anthropic, or agentic_ide)")
    profile: str = Field(..., description="Profile name used from config")
    model: str = Field(..., description="Specific model identifier")

    # Usage Metrics
    prompt_tokens: int = Field(0, ge=0)
    completion_tokens: int = Field(0, ge=0)
    total_tokens: int = Field(0, ge=0)
    cost: float = Field(0.0, ge=0.0)

    # Status
    success: bool = True
    error: Optional[str] = None

    # content (optional/nullable)
    prompt: Optional[str] = None
    response: Optional[str] = None
