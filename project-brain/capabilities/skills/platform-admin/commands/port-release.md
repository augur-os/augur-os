---
name: port-release
description: Port a staged release payload from the vault draft staging root into canonical main locations.
x-augur-export-command: false
---

# /port-release

Port a staged release payload from `get_vault_dir()/drafts/staging/rX/` into canonical locations on `main`.

## Usage

```text
/port-release r2
/port-release r2 --consume
```

## Backing Commands

```bash
python3 scripts/port_release_into_main.py --repo-root . --release r2 --release-root "$(python3 - <<'PY'
from src.config.paths import get_vault_staging_dir
print(get_vault_staging_dir() / 'r2')
PY
)"
python3 scripts/port_release_into_main.py --repo-root . --release r2 --release-root "$(python3 - <<'PY'
from src.config.paths import get_vault_staging_dir
print(get_vault_staging_dir() / 'r2')
PY
)" --consume
```

## Rules

- Run this from `main`, not from the staging branch.
- Read `get_vault_dir()/drafts/staging/rX/manifest.md` first.
- Adapt staged content to current canonical destinations instead of trusting the staged copy blindly.
- Use `--consume` only when the staged payload should be removed after porting.
