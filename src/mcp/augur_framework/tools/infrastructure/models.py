"""
Pydantic input models for infrastructure tools.
"""

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Background Job Management Models
# =============================================================================


class GetJobStatusInput(BaseModel):
    """Input for checking job status."""

    model_config = ConfigDict(str_strip_whitespace=True, extra='allow')

    job_id: str = Field(..., description="Job ID returned from async operation", min_length=1)


class CancelJobInput(BaseModel):
    """Input for cancelling a job."""

    model_config = ConfigDict(str_strip_whitespace=True, extra='allow')

    job_id: str = Field(..., description="Job ID to cancel", min_length=1)


__all__ = [
    # Job models
    "GetJobStatusInput",
    "CancelJobInput",
]
