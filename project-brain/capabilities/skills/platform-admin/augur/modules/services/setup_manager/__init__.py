"""Setup manager utilities for platform-admin tooling.

Provides skill analyzers that integrate with:
- src/lib/skills/registry.py for skill metadata
- skill_maintenance.py patterns for health checks
"""

from .analyzers import DataAnalyzer, DocAnalyzer, TestAnalyzer

__all__ = [
    "DataAnalyzer",
    "DocAnalyzer",
    "TestAnalyzer",
]
