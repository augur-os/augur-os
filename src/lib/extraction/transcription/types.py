"""Provider-neutral transcription data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Segment:
    """One contiguous speech segment within a transcript."""

    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass(frozen=True)
class Transcript:
    """Full transcript returned by a transcription provider."""

    text: str
    segments: list[Segment]
    duration_seconds: float
    language: str
    provider: str
    provider_version: str
    extra: dict[str, Any] = field(default_factory=dict)

    def speaker_count(self) -> int:
        """Return the number of distinct labeled speakers."""
        return len({segment.speaker for segment in self.segments if segment.speaker})
