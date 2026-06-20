"""
Augur Skill Wizard

CLI tool for creating and validating skills from the command line.
Works both in the monorepo and in starter template scenarios.

Usage:
    augur-wizard create --name my-skill --patterns inbox,database --layer vertical
    augur-wizard create  # Interactive mode
    augur-wizard validate --skill-dir ./skills/finance

Environment Variables:
    AUGUR_ROOT: Path to monorepo root
"""

from .cli import app

__all__ = ['app']
