---
name: stage-release
description: Create or validate a staged release payload in the vault draft staging root.
x-augur-export-command: false
---

# /stage-release

Create or validate a staged release payload under the vault drafts root at `get_vault_dir()/drafts/staging/rX/`.

## Usage

```text
/stage-release init --release r2 --motive "creation and ingestion expansion"
/stage-release validate --release r2
```

## Backing Commands

```bash
python3 scripts/manage_porting_payload.py init-release --drafts-root "$(python3 - <<'PY'
from src.config.paths import get_vault_staging_dir
print(get_vault_staging_dir())
PY
)" --release r2 --motive "creation and ingestion expansion"
python3 scripts/manage_porting_payload.py validate-release --release-root "$(python3 - <<'PY'
from src.config.paths import get_vault_staging_dir
print(get_vault_staging_dir() / 'r2')
PY
)"
```

## Rules

- Use this command to prepare or validate the staged payload before any porting step.
- Keep staged page files under `get_vault_dir()/drafts/staging/rX/pages/` using repo-relative paths.
- Keep staged skill copies under `get_vault_dir()/drafts/staging/rX/skills/`.
- Treat `manifest.md` as the required entrypoint for the staged payload.
