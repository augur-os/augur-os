# /auto-skill-structure

Run the absorbed structure-validation loop under `auto-skill-quality`.

Purpose:
- scan `skills/` for banned files and directories
- validate required structure conventions
- expose `scan-skill-structure` over MCP for diagnostics

Implementation:
- `scripts/scan_structure.py`
- `scripts/mcp/__init__.py`

Usage:
- `/a-loops run hardening`
