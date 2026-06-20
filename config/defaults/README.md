# Default Data Templates

Upstream-owned YAML templates for new user initialization.
These files are copied to `data/` when running `augur_init.py` (only files that don't already exist).

**Rules:**
- NEVER edit these files to add personal data
- Keep all values as sensible defaults or empty placeholders
- Every YAML file MUST have `schema_version: 1` at the top level
- Structure mirrors `data/` directory layout
