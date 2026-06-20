#!/usr/bin/env python3
"""
Skill UI utilities.

NOTE: The auto-page-generation flow (generate_dashboard/generate_layout that emitted
into retired /lifestyle/, /hands/, /agents/ hub routes) was removed with ADR-802.
Skill dashboard pages are now declared via x-augur-dashboard-pages in SKILL.md or
as ADR-491 config pages in augur/pages/*.yaml.
"""

from pathlib import Path
import sys


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


REPO_ROOT = Path(__file__).resolve().parents[3]
DASHBOARD_DIR = REPO_ROOT / "apps" / "dashboard"
APP_DIR = DASHBOARD_DIR / "app"


def slug_to_title(slug: str) -> str:
    """Convert kebab-case to Title Case."""
    return slug.replace("-", " ").replace("_", " ").title()
