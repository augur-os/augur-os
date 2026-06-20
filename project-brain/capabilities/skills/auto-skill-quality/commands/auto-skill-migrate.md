# /auto-skill-migrate

Run the absorbed skill-migration hardening loop under `auto-skill-quality`.

Purpose:
- detect banned or deprecated skill-directory layouts
- move safe legacy paths into canonical locations
- report remaining manual structure debt

Implementation:
- `scripts/skill_migrate_ops.py`

Usage:
- `/routines run hardening`
