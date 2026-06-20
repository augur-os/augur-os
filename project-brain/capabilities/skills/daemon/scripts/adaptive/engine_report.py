"""Executive report generation for the adaptive engine."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ReportMixin:
    """Mixin providing generate_report()."""

    def generate_report(self, *, days: int = 1) -> str:
        """Generate the `/routines report` executive report."""
        try:
            from .loop_reporter import generate_executive_report
            return generate_executive_report(
                self,
                self._config,
                days=days,
            )
        except Exception as exc:
            logger.warning("generate_report failed: %s", exc)
            raise
