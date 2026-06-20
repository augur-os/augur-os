# In-Code TODO_ Marker System

Track work items **directly in code** using `TODO_` markers. CI scans nightly to surface all items.

## Quick Reference

| Marker | Purpose | Example |
|--------|---------|---------|
| `TODO_BUG(cat/sev)` | Code bugs | `# TODO_BUG(security/high): SQL injection risk` |
| `TODO_OUTDATED` | Outdated docs/code | `# TODO_OUTDATED: API changed in v2` |
| `TODO_WORKAROUND` | Temp fixes to remove | `# TODO_WORKAROUND: Remove after upgrade` |
| `TODO_IMPROVE(cat)` | Enhancements | `# TODO_IMPROVE(performance): Add caching` |
| `TODO_MISPLACED` | Wrong file location | `# TODO_MISPLACED: Should be in src/` |
| `TODO_CLEANUP` | Dead code/tech debt | `# TODO_CLEANUP: Remove deprecated fn` |
| `TODO_SECURITY` | Needs audit | `# TODO_SECURITY: Validate inputs` |
| `TODO_PERFORMANCE` | Perf optimization | `# TODO_PERFORMANCE: N+1 query here` |
| `TODO_REFACTOR` | Structure issues | `# TODO_REFACTOR: Extract to module` |
| `TODO_IDEA` | Future ideas | `# TODO_IDEA: Add real-time sync feature` |

**ADR-249 recurrence rule**: before adding a marker for an operational/bootstrap failure, normalize it to a stable incident fingerprint and reuse the same owner path. One recurring root cause should produce one durable marker, not a trail of near-duplicate TODOs.

## Marker Details

### TODO_BUG(category/severity): Description

For bugs with a clear code location.

```python
# TODO_BUG(security/high): Symlink traversal not blocked
# FIX: Use realpath() and verify resolved path is within allowed roots
result = await read_file_impl(symlink_path)
```

```typescript
// TODO_BUG(performance/medium): Query runs on every render
// FIX: Memoize with useMemo or move to useEffect
const data = expensiveQuery();
```

**Categories**: `security`, `performance`, `ux`, `data`, `integration`
**Severity**: `critical`, `high`, `medium`, `low`

### TODO_OUTDATED: Description

For outdated documentation, comments, or code patterns.

```python
# TODO_OUTDATED: This uses the old auth flow, update to use SSO
def authenticate_user(username, password):
    ...
```

```typescript
// TODO_OUTDATED: Component uses class syntax, convert to hooks
class OldComponent extends React.Component {
```

### TODO_WORKAROUND: Description

For temporary workarounds that should be removed.

```python
# TODO_WORKAROUND: Remove after upgrading to Python 3.12 (fixes asyncio issue)
import nest_asyncio
nest_asyncio.apply()
```

```typescript
// TODO_WORKAROUND: Polyfill needed until Next.js 15 supports this natively
import 'client-only-polyfill';
```

### TODO_IMPROVE(category): Description

For enhancement opportunities.

```python
# TODO_IMPROVE(performance): Cache this API response (called 50+ times/session)
def get_user_preferences():
    return api.fetch('/preferences')
```

```typescript
// TODO_IMPROVE(ux): Add loading skeleton instead of spinner
const [loading, setLoading] = useState(true);
```

**Categories**: `performance`, `ux`, `maintainability`, `security`, `testing`

### TODO_MISPLACED: Description

For files or code in the wrong location.

```python
# TODO_MISPLACED: This helper should be in src/utils/, not in this skill
def format_date(dt):
    ...
```

```typescript
// TODO_MISPLACED: This type should be in types/api.ts with other API types
interface UserResponse {
```

### TODO_CLEANUP: Description

For dead code, unused imports, or tech debt.

```python
# TODO_CLEANUP: Remove this deprecated function after v3.0 migration
def old_process_data():
    ...
```

```typescript
// TODO_CLEANUP: Unused import, was needed for old feature
import { deprecatedUtil } from './legacy';
```

### TODO_SECURITY: Description

For code that needs a security audit.

```python
# TODO_SECURITY: Ensure this input is properly sanitized before SQL query
user_input = request.get('query')
cursor.execute(f"SELECT * FROM users WHERE name = '{user_input}'")
```

```typescript
// TODO_SECURITY: Verify CORS settings are restrictive enough
app.use(cors({ origin: '*' }));
```

### TODO_PERFORMANCE: Description

For code that needs performance optimization.

```python
# TODO_PERFORMANCE: N+1 query - fetches user for each order in loop
for order in orders:
    user = db.get_user(order.user_id)  # Should batch fetch
```

```typescript
// TODO_PERFORMANCE: Re-renders entire list on single item change
const ItemList = ({ items }) => {
  return items.map(item => <Item key={item.id} {...item} />);
};
```

### TODO_REFACTOR: Description

For code structure that needs improvement.

```python
# TODO_REFACTOR: Extract validation logic to separate validator class
def process_order(order):
    # 50 lines of validation...
    # 20 lines of processing...
```

```typescript
// TODO_REFACTOR: Split this 500-line component into smaller pieces
function MegaComponent() {
```

### TODO_IDEA: Description

For future ideas, features, and enhancements to capture for the plugin backlog.

```python
# TODO_IDEA: Add batch processing support for large datasets
def process_single_item(item):
    ...
```

```typescript
// TODO_IDEA: Add dark mode toggle to settings panel
const SettingsPanel = () => {
```

**Note**: IDEAS are low priority and don't block CI. They're collected nightly and added to the plugin's `BACKLOG.md`.

## Plugin Backlogs

Each plugin can have a `BACKLOG.md` file for tracking future work:

**Location**: `plugins/{bundle}/skills/{skill}/BACKLOG.md`

**Contents**:
- Ideas (from `TODO_IDEA` markers)
- Feature requests
- Long-term improvements
- Tech debt items

**Template**: `docs/templates/BACKLOG.md`

**Workflow**:
1. During work: Add `TODO_IDEA:` marker in code
2. Nightly CI: Collects all `TODO_IDEA` markers
3. Review session: Move to `BACKLOG.md` if worth keeping
4. Remove marker from code

## Viewing Markers

```bash
# View all markers
python3 src/scripts/scan_code_markers.py

# View specific type
python3 src/scripts/scan_code_markers.py --type bug
python3 src/scripts/scan_code_markers.py --type workaround

# Summary counts
python3 src/scripts/scan_code_markers.py --summary

# JSON output for tooling
python3 src/scripts/scan_code_markers.py --json

# CI mode (fails on critical)
python3 src/scripts/scan_code_markers.py --ci
```

## System Bugs (No Code Location)

For bugs WITHOUT a clear code location, use `data/operations/bugs/bugs.yaml`:

- UX/flow issues: "Dashboard feels slow" - no specific file
- External service bugs: "GitHub sync fails intermittently"
- Cross-cutting concerns: "Error messages inconsistent across app"

```yaml
bugs:
  - id: BUG-001
    priority: P1
    category: ux
    title: Dashboard initial load feels sluggish
    description: |
      When opening the dashboard, there's a ~2s delay.
    related_files:
      - apps/dashboard/app/page.tsx
    created_at: 2026-01-23T10:00:00Z
    status: new
```

## CI Integration

Code markers are scanned during nightly CI:

```bash
# Run manually
python3 src/scripts/scan_code_markers.py --ci

# Critical bugs fail the build
# High-priority items generate warnings
```

## Quick Decision Guide

| Situation | Action |
|-----------|--------|
| Found a security hole in this function | `# TODO_BUG(security/high):` |
| This component re-renders too much | `// TODO_BUG(performance/medium):` |
| These docs reference old API | `# TODO_OUTDATED:` |
| Added a hack to fix build | `# TODO_WORKAROUND:` |
| This could be faster with caching | `# TODO_IMPROVE(performance):` |
| This file should be elsewhere | `# TODO_MISPLACED:` |
| Dead code that can be removed | `# TODO_CLEANUP:` |
| Unsure if this is secure | `# TODO_SECURITY:` |
| Slow query or N+1 problem | `# TODO_PERFORMANCE:` |
| This function does too much | `# TODO_REFACTOR:` |
| Had a cool feature idea | `# TODO_IDEA:` |
| Onboarding flow is confusing | Add to `bugs.yaml` (UX) |
| Email notifications fail randomly | Add to `bugs.yaml` (integration) |
| Long-term feature request | Add to plugin `BACKLOG.md` |
