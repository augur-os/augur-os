---
name: staleness-detection
trigger: check staleness, outdated docs, stale documentation
---

# Staleness Detection Module

## Overview

Automatically detects documentation that has fallen out of sync with source code. Based on doc-updater reference pattern.

## Why Staleness Matters

| Problem | Impact |
|---------|--------|
| Outdated API docs | Developers use wrong parameters |
| Stale examples | Code doesn't compile |
| Missing features | Users don't know capabilities exist |
| Deleted references | Links go nowhere |

## Detection Methods

### 1. Timestamp Comparison

Compare doc modification time vs related code:

```bash
# Get last modified times
doc_time=$(stat -f %m docs/api.md)
code_time=$(stat -f %m src/api.ts)

# Flag if code newer by > 7 days
if [ $((code_time - doc_time)) -gt 604800 ]; then
  echo "STALE: docs/api.md"
fi
```

**Thresholds:**
| Gap | Status |
|-----|--------|
| < 7 days | ✅ FRESH |
| 7-30 days | ⚠️ REVIEW |
| > 30 days | 🛑 STALE |

### 2. Reference Validation

Check if documented files/functions still exist:

```python
# Extract file references from doc
refs = extract_file_refs("docs/workflow.md")

for ref in refs:
    if not os.path.exists(ref):
        print(f"BROKEN: {ref} no longer exists")
```

**Common patterns:**
```markdown
# In documentation
See `src/utils/helper.ts:45`  # ← Validate this exists
Run `npm run build`           # ← Validate command works
```

### 3. Version Drift

Compare documented version vs actual:

```yaml
# In SKILL.md frontmatter
version: 0.3.0

# In package.json
"version": "0.5.0"  # ← Drift detected!
```

### 4. API Signature Comparison

Parse actual function signatures and compare to docs:

```typescript
// Code: src/api.ts
export function getUser(id: string, options?: Options): Promise<User>

// Doc says:
// getUser(id: number): User
// ← Wrong param type, missing options, wrong return type
```

## Staleness Report Format

```markdown
## Staleness Report

**Skill**: developer
**Checked**: 2026-01-26
**Status**: ⚠️ 2 STALE, 5 FRESH

### Stale Documents

| File | Issue | Evidence |
|------|-------|----------|
| SKILL.md | Version drift | Doc: 0.3.0, Code: 0.5.0 |
| modules/tdd.md | Missing command | `tdd start` not in code |

### Broken References

| Doc | Reference | Status |
|-----|-----------|--------|
| workflow.md | src/old-api.ts | ❌ File deleted |
| guide.md | utils/deprecated.ts:45 | ❌ Line range invalid |

### Recommended Actions

1. **SKILL.md**: Update version to 0.5.0
2. **modules/tdd.md**: Remove or implement `tdd start` command
3. **workflow.md**: Update reference to new API location
```

## Command Usage

```
check staleness: [skill]
check staleness: all
```

## Integration with CI

Add to pre-commit or CI pipeline:

```yaml
# .github/workflows/docs.yml
- name: Check doc staleness
  run: |
    python scripts/check_staleness.py --threshold 30
    # Fails if any doc > 30 days stale
```

## Automation Triggers

| Event | Action |
|-------|--------|
| Code file modified | Queue related docs for review |
| PR merged | Run staleness check on affected skills |
| Weekly cron | Full staleness scan |
| New release | Mandatory doc freshness check |
