---
name: code-doc-sync
trigger: sync docs, verify docs, doc sync check
---

# Code-Documentation Sync Module

## Overview

Verifies that documentation accurately reflects the actual source code. Catches mismatches between what docs say and what code does.

## Why Sync Matters

| Mismatch Type | User Impact |
|---------------|-------------|
| Wrong function signature | TypeError at runtime |
| Missing parameter | Silent failures |
| Outdated return type | Incorrect error handling |
| Deleted export | Import errors |

## Sync Verification Checks

### 1. Function Signature Match

Extract and compare function signatures:

```python
# From source code
def parse_code_signature(file_path: str) -> dict:
    """Extract function name, params, return type"""

# From documentation
def parse_doc_signature(doc_path: str) -> dict:
    """Extract documented signature"""

# Compare
def compare_signatures(code_sig, doc_sig) -> list[Mismatch]:
    mismatches = []
    if code_sig['params'] != doc_sig['params']:
        mismatches.append(Mismatch('params', code_sig, doc_sig))
    return mismatches
```

### 2. Export Verification

Check all documented exports exist:

```typescript
// Documentation says:
// Available exports: getUser, createUser, deleteUser

// Actual exports in code:
export { getUser, createUser }  // ← deleteUser missing!
```

### 3. Command Availability

Verify documented commands are implemented:

```yaml
# SKILL.md documents:
commands:
  - tdd start
  - tdd watch
  - tdd report

# Check if handlers exist:
# scripts/tdd.py → look for start(), watch(), report()
```

### 4. Example Validation

Test that code examples actually work:

```python
def validate_examples(doc_path: str) -> list[Result]:
    """Extract code blocks and validate syntax"""
    examples = extract_code_blocks(doc_path)
    results = []

    for ex in examples:
        if ex.lang == 'python':
            try:
                compile(ex.code, '<string>', 'exec')
                results.append(Result(ex, 'PASS'))
            except SyntaxError as e:
                results.append(Result(ex, 'FAIL', str(e)))

    return results
```

## Sync Report Format

```markdown
## Code-Doc Sync Report

**Skill**: developer
**Checked**: 2026-01-26
**Status**: 🛑 3 MISMATCHES

### Signature Mismatches

| Function | Doc Says | Code Has |
|----------|----------|----------|
| `getUser` | `(id: number)` | `(id: string)` |
| `createUser` | `returns User` | `returns Promise<User>` |

### Missing Exports

| Export | Documented In | Status |
|--------|---------------|--------|
| `deleteUser` | api.md:45 | ❌ Not in code |
| `bulkUpdate` | api.md:67 | ❌ Not in code |

### Example Failures

| Doc | Line | Error |
|-----|------|-------|
| guide.md | 45 | SyntaxError: unexpected token |
| workflow.md | 89 | ImportError: no module 'old_api' |

### Remediation

1. **getUser**: Update doc param type to `string`
2. **createUser**: Add `Promise<>` wrapper to doc return type
3. **deleteUser**: Either implement or remove from docs
4. **guide.md:45**: Fix syntax in example
```

## Command Usage

```
sync docs: [skill]
sync docs: all --fix-examples
```

## Sync Confidence Scoring

| Score | Meaning | Action |
|-------|---------|--------|
| 100% | Perfect sync | No action |
| 80-99% | Minor drift | Review recommended |
| 50-79% | Significant drift | Update required |
| < 50% | Critical | Block until fixed |

## Integration with Validator

When validator runs code review, trigger sync check:

```yaml
# In chain definition
- name: librarian
  action: sync_docs
  input: { skill: "{{ changed_skill }}" }
  on_fail: warn  # Don't block, but flag
```

## Automated Sync Suggestions

When mismatch detected, generate fix:

```markdown
### Suggested Fix for api.md

```diff
- getUser(id: number): User
+ getUser(id: string): Promise<User>
```

**Evidence**: src/api.ts:45
```
