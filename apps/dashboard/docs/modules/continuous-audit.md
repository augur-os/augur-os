# Continuous Audit Mode

Instead of manual-only audits, plugin compliance checking runs automatically.

## Triggers

| Trigger | When | Action |
|---------|------|--------|
| **Pre-commit hook** | Plugin files changed in commit | Run compliance audit on changed plugins |
| **Nightly gate** | During `/nightly` chain | Full compliance audit of all plugins |
| **Release gate** | During devops `/prepare release` | Block release if compliance score < 90% |

## Nightly Compliance Gate

The `plugin_compliance` chain runs during `/nightly`:
1. Scan all plugins for compliance
2. Generate report with scores
3. Create backlog items for non-compliant plugins
4. Block release pipeline if critical violations found

## Pre-commit Integration

When plugin files change (`plugins/**/*.{py,ts,yaml,md}`), the audit runs automatically:
```bash
# In .github/scripts or pre-commit hook
python3 skills/mcp-app-factory/scripts/audit_plugin.py --changed-only
```

## Chain Integration

This skill participates in chains:
- `plugin_compliance` action -- nightly compliance gate
- `plugin_audit` chain -- full audit workflow
- Connected to devops release gate (blocks on compliance < 90%)
