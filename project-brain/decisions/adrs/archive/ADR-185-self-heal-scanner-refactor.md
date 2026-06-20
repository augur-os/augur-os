---
status: Implemented
date: ''
deciders: []
related: []
hub: null
tags:
- self
- heal
- scanner
- refactor
superseded_by: null
---

# ADR-185: Self-Heal Scanner Refactor

**Date:** 2026-02-28
**Source:** `/learn refactor` analysis (344 learnings, 7-day window)

## Context

The self-heal scanner subsystem (`plugins/observability/skills/daemon/scripts/ai_self_healer.py`, 1453 lines) has accumulated the highest bug density of any infrastructure area over the last 7 days — 8 real bugs out of 310 total learning entries (most entries are automated regeneration commits).

Recurring issues traced to three structural weaknesses:

### 1. Dual Scanner Implementations (80% Duplicated)

`scan_with_ripgrep()` (line 434) and `_scan_incremental()` (line 497) implement nearly identical logic:
- Both load/save watermarks via `_load_watermarks()` / `_save_watermarks()`
- Both read new lines via `_read_new_lines()` (shared)
- Both cap at `new_lines[-100:]` (magic number)
- Both filter INFO-level logs via `_is_info_level_log()`
- Both build regex via `"|".join(re.escape(p) for p in patterns)`
- Both create `ErrorFinding` with canonical source path and dedup key

The only difference: `scan_with_ripgrep()` was originally designed to use the ripgrep binary for speed, but the current implementation doesn't actually invoke `rg` — it reads new lines with Python's `f.seek()` and matches with `re.compile()`, identical to the fallback. The function name is now misleading.

A bug fixed in one scanner (e.g., adding `_is_info_level_log()` filtering) must be manually replicated in the other.

### 2. Non-Atomic Watermark Persistence

Watermarks are persisted at the end of each scan function (`_save_watermarks(watermarks)` at lines 488 and 541). If the scanner crashes mid-scan after updating the in-memory dict (`watermarks[fpath] = new_offset` at lines 461 and 521) but before persisting, the next scan re-reads the stale watermark file and reprocesses the same errors.

Conversely, if the scanner crashes *after* persisting watermarks but *before* the findings are processed by the pipeline, those errors are permanently lost — the watermark advanced past them but no fix was attempted.

The `json.dumps` write (line 272) is also not atomic — a crash mid-write leaves a corrupt JSON file, and `_load_watermarks()` catches the exception and returns `{}`, causing a full re-scan of all files.

### 3. Pattern Duplication Between Scanner and Classifier

`SHELL_ACTIONS` in `classifier.py` (line 19) duplicates patterns from `SEVERITY_TIERS` (line 57). For example, the Turbopack cache corruption regex appears in both:
- `SHELL_ACTIONS[0]` — triggers the `rm -rf .next/dev` fix
- `SEVERITY_TIERS["transient"][0]` — classifies as transient/runtime

Adding a new auto-fixable error requires updating both lists. If only one is updated, the error is either classified but not auto-fixed, or auto-fixed but not properly classified.

### Evidence from Daily Logs

| Date | Issue |
|------|-------|
| 2026-02-28 | Mock client detection needed 4 patterns (MagicMock, `<Mock`, unittest.mock, mock.MagicMock) |
| 2026-02-28 | Tiered SEVERITY_TIERS replaces flat SEVERITY_HINTS — backwards-compatible flat list still maintained |
| 2026-02-28 | HTTP access log filter needs exact Next.js response format match |
| 2026-02-25 | HTTP health check replaces port-binding check (Turbopack returns 500 while process alive) |
| 2026-02-25 | 3-consecutive-failure threshold to avoid false positives during HMR recompilation |
| 2026-02-18 | Structured JSON log level must be checked before pattern matching (3-layer defense) |
| 2026-02-18 | LLM retry WARNING messages are expected graceful degradation, not bugs |

## Decision

### Phase 1: Merge Dual Scanners (M effort)

Consolidate `scan_with_ripgrep()` and `_scan_incremental()` into a single `scan_logs()` function. Since both implementations already use pure Python for line reading and regex matching, the "ripgrep" distinction is vestigial.

```python
def scan_logs(targets: list[dict]) -> list[ErrorFinding]:
    """Incremental log scanner with watermark tracking.

    Reads only new lines since last scan (byte-offset watermarks).
    Filters INFO-level logs before pattern matching.
    Caps at MAX_NEW_LINES_PER_FILE (100) per scan cycle.
    """
```

Remove `scan_with_python()`, `_scan_incremental()`, and the `_has_ripgrep()` check in `scan_runtime()` (line 838). The `scan_runtime()` dispatcher calls `scan_logs()` directly.

### Phase 2: Atomic Watermark Persistence (S effort)

Replace the current pattern of mutating in-memory dict + final persist with atomic write-after-process:

```python
def _save_watermarks_atomic(wm: dict[str, int]) -> None:
    """Atomic watermark persistence via temp file + rename."""
    tmp = _WATERMARK_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(wm, indent=2))
    tmp.rename(_WATERMARK_FILE)  # atomic on POSIX
```

Move watermark persistence to *after* findings are handed to the pipeline, not inside the scan function. This ensures watermarks only advance when findings are safely queued:

```python
findings = scan_logs(targets)
pipeline.process(findings)  # queue findings first
_save_watermarks_atomic(watermarks)  # then advance watermarks
```

### Phase 3: Unify Pattern Registry (S effort)

Create a single `PATTERNS` registry that both the scanner and classifier consume:

```python
# In a new file: self_heal/patterns.py
@dataclass
class ErrorPattern:
    regex: re.Pattern
    tier: str          # "dismiss" | "transient" | "actionable"
    severity: str      # "transient" | "high" | "critical"
    category: str      # "runtime" | "integration" | "infrastructure"
    shell_fix: Optional[list[str]] = None  # auto-fix command if available
    description: str = ""

PATTERNS: list[ErrorPattern] = [
    ErrorPattern(
        regex=re.compile(r"TurbopackInternalError|Turbopack.*panic|..."),
        tier="transient",
        severity="transient",
        category="runtime",
        shell_fix=["bash", "-c", "rm -rf src/dashboard/.next/dev ..."],
        description="Clear corrupted Turbopack dev cache",
    ),
    # ... all patterns defined once
]
```

`SEVERITY_TIERS` and `SHELL_ACTIONS` become derived views:

```python
def get_tier_patterns(tier: str) -> list[ErrorPattern]:
    return [p for p in PATTERNS if p.tier == tier]

def get_shell_actions() -> list[ErrorPattern]:
    return [p for p in PATTERNS if p.shell_fix is not None]
```

### Phase 4: Extract Constants (S effort)

Replace magic numbers with named constants:

```python
MAX_NEW_LINES_PER_FILE = 100    # Cap per scan cycle (was hardcoded in [-100:])
MAX_MESSAGE_LENGTH = 300         # Truncation limit (was hardcoded in [:300])
WATERMARK_FILE = "self_heal_watermarks.json"
```

## Consequences

### Positive

- Single scanner implementation eliminates divergence bugs — fixes apply once
- Atomic watermark persistence prevents both reprocessing and lost errors on crash
- Unified pattern registry makes "add new error pattern" a single-location edit
- Named constants improve readability and make thresholds configurable

### Negative

- Phase 1 removes the `scan_with_ripgrep` name that appears in daemon logs and monitoring — log queries filtering on this name need updating
- Phase 3 changes the import paths for `SEVERITY_TIERS` and `SHELL_ACTIONS` — any external consumers (tests, CLI tools) need updating

### Neutral

- No behavioral change to end users — the scanner produces the same findings
- Test coverage for the scanner is currently implicit (daemon integration tests) — this refactor is an opportunity to add unit tests for `scan_logs()` directly

## Impact Manifest

```yaml
paths_renamed:
  - from: "SHELL_ACTIONS in classifier.py"
    to: "PATTERNS in self_heal/patterns.py"
  - from: "SEVERITY_TIERS in classifier.py"
    to: "derived from PATTERNS via get_tier_patterns()"

apis_changed:
  - function: "scan_with_ripgrep()"
    change: "removed, replaced by scan_logs()"
  - function: "scan_with_python()"
    change: "removed, replaced by scan_logs()"
  - function: "_scan_incremental()"
    change: "removed, absorbed into scan_logs()"
  - function: "_save_watermarks()"
    change: "replaced by _save_watermarks_atomic()"

files_affected:
  - plugins/observability/skills/daemon/scripts/ai_self_healer.py
  - plugins/observability/skills/daemon/scripts/self_heal/classifier.py
  - plugins/observability/skills/daemon/scripts/self_heal/patterns.py  # NEW

patterns_deprecated:
  - pattern: "dual scanner with _has_ripgrep() dispatch"
    replacement: "single scan_logs() function"
  - pattern: "SHELL_ACTIONS + SEVERITY_TIERS as separate pattern lists"
    replacement: "unified ErrorPattern registry"
```

## References

- ADR-177: Infrastructure reliability refactor (self-heal pre-filter, sync --fix mode)
- `/learn refactor` report (2026-02-28): Self-heal scored highest priority (310 points, 8 real bugs)
- Daily logs: `docs/memory/daily/2026-02-{18,25,28}.md`
