# Agent Digest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a nightly auto-loop that compiles violation signals into a token-capped layered digest at the top of MEMORY.md, so every agent on every platform starts each session knowing which decisions are actively being violated and what recently changed.

**Architecture:** Three signal collectors (git scanner, session log parser, `/flag` command) feed an append-only JSONL journal. A nightly compiler scores directives by violation frequency with recency decay, then writes two token-capped tiers (Hot: 500 tokens / 7 days, Warm: 500 tokens / 30 days) to intermediate files. `memory_assembler.py` prepends these into MEMORY.md during its normal assembly, distributing to all agent targets.

**Tech Stack:** Python 3.11+, `src.lib.ops_protocol` (OpsCommand contract), `src.config.paths` (path resolution), `src.lib.frontmatter_utils` (YAML frontmatter parsing), JSONL event journal, YAML config files.

**Spec:** `docs/superpowers/specs/2026-03-24-agent-digest-design.md`

---

## File Structure

```
skills/auto-agent-digest/
├── SKILL.md                                    # Auto-loop registration + frontmatter
├── __init__.py                                 # Package init (empty)
├── commands/
│   └── flag.md                                 # /flag slash command definition
├── scripts/
│   ├── __init__.py                             # Package init (empty)
│   ├── compile_digest.py                       # Main compiler: OpsCommand (scan/fix), scoring, formatting
│   ├── collect_git_signals.py                  # Git log scanner — pattern matching against commits
│   ├── collect_session_signals.py              # Session log parser — correction signal extraction
│   ├── flag.py                                 # /flag command executor — appends to events.jsonl
│   ├── journal.py                              # Shared journal I/O: read, append, archive, purge
│   └── scoring.py                              # Scoring engine: weights, decay, budget, formatting
├── assets/
│   ├── violation-patterns.yaml                 # Git anti-pattern definitions
│   ├── directive-map.yaml                      # Violation → directive mapping
│   └── seeds/
│       └── example-auto-agent-digest.yaml      # Cold start directive set
└── augur/
    ├── __init__.py                             # Package init (empty)
    └── tests/
        ├── __init__.py                         # Package init (empty)
        ├── conftest.py                         # Adds project root to sys.path
        ├── test_journal.py                     # Journal read/write/archive
        ├── test_scoring.py                     # Score calculation, decay, budget
        ├── test_git_collector.py               # Git pattern matching
        ├── test_session_collector.py           # Correction signal extraction
        ├── test_compiler.py                    # End-to-end compile + format
        └── test_flag.py                        # /flag command parsing + append

# Modified external file:
skills/auto-memory-sync/scripts/memory_assembler.py  # Add _prepend_digest_sections()
```

**Responsibilities per file:**

| File | Single responsibility |
|------|---------------------|
| `journal.py` | JSONL I/O: `append_event()`, `read_events()`, `archive_old()`, `purge_archives()` |
| `collect_git_signals.py` | Parse git log, match patterns from `violation-patterns.yaml`, yield events |
| `collect_session_signals.py` | Scan session logs for correction phrases, yield events |
| `flag.py` | Parse CLI args, resolve directive mapping, call `journal.append_event()` |
| `compile_digest.py` | OpsCommand entry point: orchestrate collectors, score, format, write digest files |
| `directive-map.yaml` | Static mapping: directive ID → label, sources, patterns, scope |
| `violation-patterns.yaml` | Git scanner patterns: regex, target scope, mapped rule |

---

### Task 1: Scaffold skill directory and SKILL.md

**Files:**
- Create: `skills/auto-agent-digest/SKILL.md`
- Create: `skills/auto-agent-digest/assets/violation-patterns.yaml`
- Create: `skills/auto-agent-digest/assets/directive-map.yaml`
- Create: `skills/auto-agent-digest/assets/seeds/example-auto-agent-digest.yaml`
- Create: `skills/auto-agent-digest/augur/tests/.gitkeep`

- [ ] **Step 1: Create SKILL.md with full frontmatter**

```markdown
---
name: auto-agent-digest
description: >-
  Nightly loop that compiles violation signals into a token-capped layered
  digest at the top of MEMORY.md — Hot tier (actively violated directives,
  7-day window) and Warm tier (recent ADR decisions, 30-day window).
  Collects from git diffs, session logs, and /flag command.
x-augur-type: autoloop
x-augur-hub: adaptive
x-augur-tab: advisor
x-augur-commands: [flag]
x-augur-callable: skills/auto-agent-digest/scripts/compile_digest.py
x-augur-dependencies:
  optional: [attention]
x-augur-loop:
  name: auto-agent-digest
  tier: 1
  trigger: nightly
  config:
    scan_timeout: 120
    fix_timeout: 300
    max_turns: 12
---

# auto-agent-digest

Compiles violation signals into a layered digest prepended to MEMORY.md.

## Difficulty Levels

| Level | Behavior |
|-------|----------|
| d=0 | Collect signals only — append to journal, report stats, no digest write |
| d=1 | Collect + compile Hot tier, write digest-hot.md |
| d=2 | Full run — collect, compile both tiers, distribute, archive journal |

## How It Works

1. **Collect** — git scanner checks last 24h commits for anti-patterns; session log parser finds user corrections; /flag command adds manual signals
2. **Score** — each directive gets a weighted score: user_correction=5, manual_flag=4, git_violation=3, hook_rejection=2, with recency decay (0-2d=1.0x, 3-5d=0.7x, 6-7d=0.4x)
3. **Compile** — top-N directives by score, capped at 500 tokens per tier, written to intermediate digest files
4. **Distribute** — memory_assembler.py prepends digest into MEMORY.md during its normal assembly

## Evolution

- d=0 with 0 events for 7 days → flag collector may be broken
- d=1 with all scores < 2 → directive-map.yaml needs more patterns
- d=2 with empty Hot for 14 days → propose d=3 (auto-discovery)
```

- [ ] **Step 2: Create violation-patterns.yaml**

```yaml
# Git anti-pattern definitions for collect_git_signals.py
# Each pattern maps a regex to a directive ID from directive-map.yaml

patterns:
  - id: rule_11_no_fs
    regex: "import\\s+(fs|\\{\\s*readFile)"
    scope: "apps/dashboard/"
    directive: no_fs_in_dashboard

  - id: rule_11_no_spawn
    regex: "(execSync|execFile|spawn)\\("
    scope: "apps/dashboard/"
    directive: no_fs_in_dashboard

  - id: rule_5_no_suppression
    regex: "(@ts-ignore|eslint-disable|@pytest\\.mark\\.skip)"
    scope: null  # any file
    directive: no_suppression

  - id: rule_5_no_fallback_fix
    regex: "(pluginFallback|fallbackData)"
    scope: "apps/dashboard/"
    directive: no_fallback_fixes

  - id: rule_2_no_central_registry
    regex: "(registry\\.ts|registry\\.yaml|central.*config)"
    scope: "config/"
    directive: no_central_registry
```

- [ ] **Step 3: Create directive-map.yaml**

```yaml
# Maps directive IDs to labels, sources, and patterns
# Used by scoring engine and /flag inference

directives:
  no_fs_in_dashboard:
    label: "NO fs/spawn in dashboard"
    sources: ["rule_11", "ADR-453"]
    description: "All data via useMcpQuery/useMcpMutation. No import fs, no execSync, no spawn."

  no_fallback_fixes:
    label: "NO fallback-path fixes"
    sources: ["rule_5", "ADR-453"]
    description: "When MCP call fails, fix the wiring (tool name, args, response shape), never improve the fallback."

  no_suppression:
    label: "NO error suppression"
    sources: ["rule_5"]
    description: "No @ts-ignore, eslint-disable, @pytest.mark.skip. Fix root cause."

  no_generated_edits:
    label: "NO generated file edits"
    sources: ["memory:never-edit-generated-files"]
    description: "Check for AUTO-GENERATED header before editing; edit the source."

  no_emojis:
    label: "NO emojis"
    sources: ["preference:no-emojis-unless-explicitly-requested"]
    description: "Unless user explicitly requests them."

  no_central_registry:
    label: "NO centralized registry additions"
    sources: ["rule_2", "ADR-163"]
    description: "Data belongs in skill's SKILL.md x-augur-* frontmatter, not centralized config."

  fix_root_cause:
    label: "Fix root cause, not tests"
    sources: ["rule_5"]
    description: "Never update assertions to match broken behavior. Never mock to silence failures."
```

- [ ] **Step 4: Create example-auto-agent-digest.yaml (cold start seed)**

```yaml
# Seed directives for cold start (first run with empty journal)
# Each gets score=1 so they appear in Hot tier on first compile

seed_directives:
  - directive: no_fs_in_dashboard
    initial_score: 1
  - directive: no_fallback_fixes
    initial_score: 1
  - directive: no_suppression
    initial_score: 1
  - directive: no_generated_edits
    initial_score: 1
  - directive: no_emojis
    initial_score: 1
```

- [ ] **Step 5: Create package __init__.py files and test conftest.py**

```bash
mkdir -p skills/auto-agent-digest/scripts skills/auto-agent-digest/augur/tests
touch skills/auto-agent-digest/__init__.py
touch skills/auto-agent-digest/scripts/__init__.py
touch skills/auto-agent-digest/augur/__init__.py
touch skills/auto-agent-digest/augur/tests/__init__.py
```

Create `skills/auto-agent-digest/augur/tests/conftest.py`:
```python
"""Ensure project root is on sys.path for imports."""
import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[4])
if project_root not in sys.path:
    sys.path.insert(0, project_root)
```

- [ ] **Step 6: Commit scaffold**

```bash
git add skills/auto-agent-digest/
git commit -m "feat(auto-agent-digest): scaffold skill directory with SKILL.md and config files"
```

---

### Task 2: Journal I/O module

**Files:**
- Create: `skills/auto-agent-digest/scripts/journal.py`
- Create: `skills/auto-agent-digest/augur/tests/test_journal.py`

- [ ] **Step 1: Write failing tests for journal module**

```python
# skills/auto-agent-digest/augur/tests/test_journal.py
"""Tests for the event journal I/O module."""

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from skills.auto_agent_digest.scripts.journal import (
    append_event,
    archive_old,
    purge_archives,
    read_events,
)


@pytest.fixture
def journal_dir(tmp_path: Path) -> Path:
    d = tmp_path / "agent-digest"
    d.mkdir()
    return d


def test_append_event_creates_file(journal_dir: Path):
    event = {
        "ts": "2026-03-24T02:00:00Z",
        "source": "git",
        "type": "pattern_violation",
        "rule": "rule_11_no_fs",
        "evidence": "import fs in dashboard",
    }
    append_event(journal_dir, event)
    journal = journal_dir / "events.jsonl"
    assert journal.exists()
    lines = journal.read_text().strip().split("\n")
    assert len(lines) == 1
    assert json.loads(lines[0])["rule"] == "rule_11_no_fs"


def test_append_event_appends_to_existing(journal_dir: Path):
    for i in range(3):
        append_event(journal_dir, {"ts": f"2026-03-24T0{i}:00:00Z", "source": "test", "type": "test", "rule": f"rule_{i}"})
    lines = (journal_dir / "events.jsonl").read_text().strip().split("\n")
    assert len(lines) == 3


def test_read_events_filters_by_window(journal_dir: Path):
    old = {"ts": "2026-03-10T00:00:00Z", "source": "git", "type": "test", "rule": "old"}
    recent = {"ts": "2026-03-23T00:00:00Z", "source": "git", "type": "test", "rule": "recent"}
    append_event(journal_dir, old)
    append_event(journal_dir, recent)
    since = datetime(2026, 3, 20, tzinfo=timezone.utc)
    events = read_events(journal_dir, since=since)
    assert len(events) == 1
    assert events[0]["rule"] == "recent"


def test_read_events_empty_journal(journal_dir: Path):
    events = read_events(journal_dir)
    assert events == []


def test_archive_old_compresses_events(journal_dir: Path):
    append_event(journal_dir, {"ts": "2026-03-24T00:00:00Z", "source": "test", "type": "test", "rule": "r1"})
    archive_old(journal_dir, date_str="2026-03-24")
    assert (journal_dir / "events.jsonl").read_text().strip() == ""
    archive = journal_dir / "events.2026-03-24.jsonl.gz"
    assert archive.exists()
    with gzip.open(archive, "rt") as f:
        lines = f.read().strip().split("\n")
    assert len(lines) == 1


def test_purge_archives_removes_old(journal_dir: Path, tmp_path: Path):
    # Create a fake archive with old date
    old_archive = journal_dir / "events.2026-01-01.jsonl.gz"
    with gzip.open(old_archive, "wt") as f:
        f.write('{"old": true}\n')
    recent_archive = journal_dir / "events.2026-03-20.jsonl.gz"
    with gzip.open(recent_archive, "wt") as f:
        f.write('{"recent": true}\n')
    purge_archives(journal_dir, retention_days=30, reference_date=datetime(2026, 3, 24, tzinfo=timezone.utc))
    assert not old_archive.exists()
    assert recent_archive.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-agent-digest/augur/tests/test_journal.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skills.auto_agent_digest'`

- [ ] **Step 3: Implement journal.py**

```python
# skills/auto-agent-digest/scripts/journal.py
"""Event journal I/O for the agent-digest nightly loop.

Append-only JSONL journal at {runtime_dir}/agent-digest/events.jsonl.
Supports read with time window filtering, archive to .gz, and retention purge.
"""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _journal_path(journal_dir: Path) -> Path:
    return journal_dir / "events.jsonl"


def append_event(journal_dir: Path, event: dict) -> None:
    """Append a single event to the journal. Creates file if needed."""
    journal_dir.mkdir(parents=True, exist_ok=True)
    with _journal_path(journal_dir).open("a") as f:
        f.write(json.dumps(event, separators=(",", ":")) + "\n")


def read_events(
    journal_dir: Path,
    since: datetime | None = None,
) -> list[dict]:
    """Read events from journal, optionally filtered to those after `since`."""
    path = _journal_path(journal_dir)
    if not path.exists():
        return []
    events = []
    for line in path.read_text().strip().split("\n"):
        if not line:
            continue
        event = json.loads(line)
        if since is not None:
            ts = datetime.fromisoformat(event["ts"].replace("Z", "+00:00"))
            if ts < since:
                continue
        events.append(event)
    return events


def archive_old(journal_dir: Path, date_str: str) -> Path | None:
    """Move current journal to a dated gzip archive. Returns archive path."""
    src = _journal_path(journal_dir)
    if not src.exists() or src.stat().st_size == 0:
        return None
    archive = journal_dir / f"events.{date_str}.jsonl.gz"
    with src.open("r") as fin, gzip.open(archive, "wt") as fout:
        fout.write(fin.read())
    src.write_text("")
    return archive


def purge_archives(
    journal_dir: Path,
    retention_days: int = 30,
    reference_date: datetime | None = None,
) -> list[Path]:
    """Remove archives older than retention_days. Returns list of purged paths."""
    ref = reference_date or datetime.now(timezone.utc)
    cutoff = ref - timedelta(days=retention_days)
    purged = []
    for gz in sorted(journal_dir.glob("events.*.jsonl.gz")):
        date_part = gz.name.replace("events.", "").replace(".jsonl.gz", "")
        try:
            archive_date = datetime.strptime(date_part, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if archive_date < cutoff:
            gz.unlink()
            purged.append(gz)
    return purged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-agent-digest/augur/tests/test_journal.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/auto-agent-digest/scripts/journal.py skills/auto-agent-digest/augur/tests/test_journal.py
git commit -m "feat(auto-agent-digest): add journal I/O module with tests"
```

---

### Task 3: Scoring engine

**Files:**
- Create: `skills/auto-agent-digest/scripts/scoring.py`
- Create: `skills/auto-agent-digest/augur/tests/test_scoring.py`

- [ ] **Step 1: Write failing tests for scoring**

```python
# skills/auto-agent-digest/augur/tests/test_scoring.py
"""Tests for the directive scoring engine."""

from datetime import datetime, timezone

import pytest

from skills.auto_agent_digest.scripts.scoring import (
    TOKEN_BUDGET_HOT,
    estimate_tokens,
    format_hot_directive,
    recency_decay,
    score_directives,
)


def test_recency_decay_recent():
    assert recency_decay(days_old=1) == 1.0


def test_recency_decay_mid():
    assert recency_decay(days_old=4) == 0.7


def test_recency_decay_old():
    assert recency_decay(days_old=6) == 0.4


def test_recency_decay_expired():
    assert recency_decay(days_old=8) == 0.0


def test_score_single_git_violation():
    events = [
        {"ts": "2026-03-24T02:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard"},
    ]
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    scores = score_directives(events, reference_date=ref)
    assert "no_fs_in_dashboard" in scores
    assert scores["no_fs_in_dashboard"]["score"] == 3.0  # git weight=3, decay=1.0


def test_score_user_correction_higher():
    events = [
        {"ts": "2026-03-24T02:00:00Z", "source": "session_log", "type": "user_correction", "rule": "no_emojis"},
    ]
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    scores = score_directives(events, reference_date=ref)
    assert scores["no_emojis"]["score"] == 5.0  # user_correction weight=5


def test_score_manual_flag_with_boost():
    events = [
        {"ts": "2026-03-24T02:00:00Z", "source": "manual", "type": "flag", "rule": "no_central_registry", "priority": "boost"},
    ]
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    scores = score_directives(events, reference_date=ref)
    assert scores["no_central_registry"]["score"] == 4.0 * 1.5  # flag=4, boost=1.5x


def test_score_repeated_violation_boost():
    events = [
        {"ts": "2026-03-24T01:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard"},
        {"ts": "2026-03-24T02:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard"},
        {"ts": "2026-03-24T03:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard"},
    ]
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    scores = score_directives(events, reference_date=ref)
    # 3 events * weight 3 * decay 1.0 * repeated boost 1.3 = 11.7
    assert scores["no_fs_in_dashboard"]["score"] == pytest.approx(11.7)


def test_score_multiple_directives_ranked():
    events = [
        {"ts": "2026-03-24T02:00:00Z", "source": "session_log", "type": "user_correction", "rule": "no_emojis"},
        {"ts": "2026-03-24T02:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard"},
    ]
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    scores = score_directives(events, reference_date=ref)
    assert scores["no_emojis"]["score"] > scores["no_fs_in_dashboard"]["score"]


def test_format_hot_directive():
    line = format_hot_directive("NO fs/spawn in dashboard", ["rule_11", "ADR-453"], 3)
    assert "NO fs/spawn in dashboard" in line
    assert "rule_11" in line
    assert "3x" in line


def test_estimate_tokens():
    text = "This is a test line with some words in it."
    tokens = estimate_tokens(text)
    assert 5 < tokens < 20  # rough estimate


def test_token_budget_constant():
    assert TOKEN_BUDGET_HOT == 500
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-agent-digest/augur/tests/test_scoring.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement scoring.py**

```python
# skills/auto-agent-digest/scripts/scoring.py
"""Directive scoring engine for the agent-digest nightly loop.

Scores directives by violation frequency with recency decay and boost multipliers.
Produces ranked, token-capped directive lists for Hot tier.
"""

from __future__ import annotations

from datetime import datetime, timezone

TOKEN_BUDGET_HOT = 500
TOKEN_BUDGET_WARM = 500

EVENT_WEIGHTS: dict[str, float] = {
    "user_correction": 5.0,
    "flag": 4.0,
    "pattern_violation": 3.0,
    "hook_rejection": 2.0,
}

REPEATED_THRESHOLD = 3
REPEATED_BOOST = 1.3
FLAG_BOOST = 1.5


def recency_decay(days_old: float) -> float:
    """Return decay multiplier based on event age in days."""
    if days_old <= 2:
        return 1.0
    if days_old <= 5:
        return 0.7
    if days_old <= 7:
        return 0.4
    return 0.0


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


def score_directives(
    events: list[dict],
    reference_date: datetime | None = None,
) -> dict[str, dict]:
    """Score directives from events. Returns {directive_id: {score, count, events}}."""
    ref = reference_date or datetime.now(timezone.utc)
    grouped: dict[str, list[dict]] = {}
    for event in events:
        rule = event.get("rule", "unknown")
        grouped.setdefault(rule, []).append(event)

    result = {}
    for directive_id, directive_events in grouped.items():
        total_score = 0.0
        for event in directive_events:
            ts = datetime.fromisoformat(event["ts"].replace("Z", "+00:00"))
            days_old = (ref - ts).total_seconds() / 86400
            decay = recency_decay(days_old)
            if decay == 0.0:
                continue
            weight = EVENT_WEIGHTS.get(event.get("type", ""), 1.0)
            event_score = weight * decay
            if event.get("priority") == "boost":
                event_score *= FLAG_BOOST
            total_score += event_score

        count = len(directive_events)
        if count >= REPEATED_THRESHOLD:
            total_score *= REPEATED_BOOST

        if total_score > 0:
            result[directive_id] = {
                "score": round(total_score, 2),
                "count": count,
                "events": directive_events,
            }

    return result


def format_hot_directive(label: str, sources: list[str], count: int) -> str:
    """Format a single Hot tier directive line."""
    source_str = ", ".join(sources)
    return f"- **{label}** [{source_str}] (violated {count}x this week)"


def select_top_directives(
    scored: dict[str, dict],
    directive_map: dict[str, dict],
    budget: int = TOKEN_BUDGET_HOT,
) -> list[str]:
    """Select top directives that fit within token budget. Returns formatted lines."""
    ranked = sorted(scored.items(), key=lambda x: x[1]["score"], reverse=True)
    lines = []
    used_tokens = 0
    for directive_id, data in ranked:
        info = directive_map.get(directive_id, {})
        label = info.get("label", directive_id)
        sources = info.get("sources", [])
        description = info.get("description", "")
        line = f"- **{label}** — {description} [{', '.join(sources)}] (violated {data['count']}x this week)"
        line_tokens = estimate_tokens(line)
        if used_tokens + line_tokens > budget:
            remaining = len(ranked) - len(lines)
            if remaining > 0:
                lines.append(f"- *+ {remaining} more directives below threshold*")
            break
        lines.append(line)
        used_tokens += line_tokens
    return lines
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-agent-digest/augur/tests/test_scoring.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/auto-agent-digest/scripts/scoring.py skills/auto-agent-digest/augur/tests/test_scoring.py
git commit -m "feat(auto-agent-digest): add scoring engine with recency decay and token budgets"
```

---

### Task 4: Git signal collector

**Files:**
- Create: `skills/auto-agent-digest/scripts/collect_git_signals.py`
- Create: `skills/auto-agent-digest/augur/tests/test_git_collector.py`

- [ ] **Step 1: Write failing tests**

```python
# skills/auto-agent-digest/augur/tests/test_git_collector.py
"""Tests for the git signal collector."""

from pathlib import Path

import pytest

from skills.auto_agent_digest.scripts.collect_git_signals import (
    match_patterns,
    parse_git_diff_files,
)


@pytest.fixture
def patterns() -> list[dict]:
    return [
        {"id": "rule_11_no_fs", "regex": r"import\s+(fs|\{\s*readFile)", "scope": "apps/dashboard/", "directive": "no_fs_in_dashboard"},
        {"id": "rule_5_no_suppression", "regex": r"(@ts-ignore|eslint-disable|@pytest\.mark\.skip)", "scope": None, "directive": "no_suppression"},
    ]


def test_match_fs_import(patterns: list[dict]):
    diff_line = "+import fs from 'node:fs'"
    file_path = "apps/dashboard/lib/utils.ts"
    matches = match_patterns(diff_line, file_path, patterns)
    assert len(matches) == 1
    assert matches[0]["directive"] == "no_fs_in_dashboard"


def test_match_readfile_import(patterns: list[dict]):
    diff_line = "+import { readFile } from 'fs/promises'"
    file_path = "apps/dashboard/api/route.ts"
    matches = match_patterns(diff_line, file_path, patterns)
    assert len(matches) == 1
    assert matches[0]["directive"] == "no_fs_in_dashboard"


def test_no_match_outside_scope(patterns: list[dict]):
    diff_line = "+import fs from 'node:fs'"
    file_path = "scripts/build.ts"
    matches = match_patterns(diff_line, file_path, patterns)
    assert len(matches) == 0


def test_match_ts_ignore(patterns: list[dict]):
    diff_line = "+// @ts-ignore"
    file_path = "src/lib/helper.ts"
    matches = match_patterns(diff_line, file_path, patterns)
    assert len(matches) == 1
    assert matches[0]["directive"] == "no_suppression"


def test_no_match_removed_line(patterns: list[dict]):
    diff_line = "-import fs from 'node:fs'"
    file_path = "apps/dashboard/lib/utils.ts"
    matches = match_patterns(diff_line, file_path, patterns)
    assert len(matches) == 0  # removals are good, not violations


def test_parse_git_diff_files():
    diff_output = """diff --git a/apps/dashboard/lib/utils.ts b/apps/dashboard/lib/utils.ts
--- a/apps/dashboard/lib/utils.ts
+++ b/apps/dashboard/lib/utils.ts
@@ -1,3 +1,4 @@
+import fs from 'node:fs'
 export function util() {}"""
    files = parse_git_diff_files(diff_output)
    assert "apps/dashboard/lib/utils.ts" in files
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-agent-digest/augur/tests/test_git_collector.py -v`
Expected: FAIL

- [ ] **Step 3: Implement collect_git_signals.py**

```python
# skills/auto-agent-digest/scripts/collect_git_signals.py
"""Git signal collector for agent-digest.

Scans recent git commits for anti-patterns defined in violation-patterns.yaml.
Yields events for each matched violation.
"""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml


def load_patterns(patterns_path: Path) -> list[dict]:
    """Load violation patterns from YAML config."""
    with patterns_path.open() as f:
        data = yaml.safe_load(f)
    return data.get("patterns", [])


def match_patterns(
    diff_line: str,
    file_path: str,
    patterns: list[dict],
) -> list[dict]:
    """Match a single added diff line against violation patterns.

    Only matches lines starting with '+' (additions, not removals).
    Returns list of matched pattern dicts.
    """
    if not diff_line.startswith("+"):
        return []
    # Strip the leading '+' for matching
    content = diff_line[1:]
    matches = []
    for pattern in patterns:
        scope = pattern.get("scope")
        if scope and not file_path.startswith(scope):
            continue
        if re.search(pattern["regex"], content):
            matches.append(pattern)
    return matches


def parse_git_diff_files(diff_output: str) -> dict[str, list[str]]:
    """Parse git diff output into {file_path: [added_lines]}."""
    files: dict[str, list[str]] = {}
    current_file = None
    for line in diff_output.split("\n"):
        if line.startswith("+++ b/"):
            current_file = line[6:]
            files.setdefault(current_file, [])
        elif line.startswith("+") and not line.startswith("+++") and current_file:
            files[current_file].append(line)
    return files


def collect(
    project_root: Path,
    patterns_path: Path,
    since_hours: int = 24,
) -> list[dict]:
    """Collect git violation events from recent commits.

    Returns list of event dicts ready for journal.append_event().
    """
    patterns = load_patterns(patterns_path)
    since = f"{since_hours} hours ago"

    try:
        result = subprocess.run(
            ["git", "log", f"--since={since}", "--format=%H", "--diff-filter=AM"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        commits = [c.strip() for c in result.stdout.strip().split("\n") if c.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    if not commits:
        return []

    events = []
    now = datetime.now(timezone.utc).isoformat()

    for commit in commits:
        try:
            diff_result = subprocess.run(
                ["git", "diff", f"{commit}~1", commit, "--unified=0"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            continue

        file_lines = parse_git_diff_files(diff_result.stdout)
        for file_path, added_lines in file_lines.items():
            for line in added_lines:
                matches = match_patterns(line, file_path, patterns)
                for match in matches:
                    events.append({
                        "ts": now,
                        "source": "git",
                        "type": "pattern_violation",
                        "rule": match["directive"],
                        "evidence": f"commit {commit[:7]} added '{line[1:].strip()[:80]}' in {file_path}",
                        "commit": commit[:7],
                    })
    return events
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-agent-digest/augur/tests/test_git_collector.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/auto-agent-digest/scripts/collect_git_signals.py skills/auto-agent-digest/augur/tests/test_git_collector.py
git commit -m "feat(auto-agent-digest): add git signal collector with pattern matching"
```

---

### Task 5: Session log signal collector

**Files:**
- Create: `skills/auto-agent-digest/scripts/collect_session_signals.py`
- Create: `skills/auto-agent-digest/augur/tests/test_session_collector.py`

- [ ] **Step 1: Write failing tests**

```python
# skills/auto-agent-digest/augur/tests/test_session_collector.py
"""Tests for the session log signal collector."""

from pathlib import Path

import pytest

from skills.auto_agent_digest.scripts.collect_session_signals import (
    extract_corrections,
    infer_directive,
)


def test_extract_no_correction():
    lines = ["Great, I'll implement that now.", "Let me read the file."]
    corrections = extract_corrections(lines)
    assert len(corrections) == 0


def test_extract_dont_correction():
    lines = ["no don't mock the database, use real integration tests"]
    corrections = extract_corrections(lines)
    assert len(corrections) == 1
    assert "mock" in corrections[0].lower()


def test_extract_stop_correction():
    lines = ["stop adding emojis to the commit messages"]
    corrections = extract_corrections(lines)
    assert len(corrections) == 1


def test_extract_wrong_correction():
    lines = ["that's wrong, the file should not import fs directly"]
    corrections = extract_corrections(lines)
    assert len(corrections) == 1


def test_extract_no_as_negation():
    lines = ["no, don't use fallbacks here"]
    corrections = extract_corrections(lines)
    assert len(corrections) == 1


def test_extract_skips_false_positive():
    lines = ["yes that's fine, no issues there"]
    corrections = extract_corrections(lines)
    assert len(corrections) == 0


def test_infer_directive_emoji():
    text = "stop adding emojis to the commit messages"
    directive_map = {
        "no_emojis": {"label": "NO emojis", "sources": [], "description": "Unless user explicitly requests them."},
        "no_fs_in_dashboard": {"label": "NO fs/spawn in dashboard", "sources": [], "description": "All data via MCP."},
    }
    result = infer_directive(text, directive_map)
    assert result == "no_emojis"


def test_infer_directive_unknown():
    text = "don't use that library"
    directive_map = {
        "no_emojis": {"label": "NO emojis", "sources": [], "description": "Unless user explicitly requests them."},
    }
    result = infer_directive(text, directive_map)
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-agent-digest/augur/tests/test_session_collector.py -v`
Expected: FAIL

- [ ] **Step 3: Implement collect_session_signals.py**

```python
# skills/auto-agent-digest/scripts/collect_session_signals.py
"""Session log signal collector for agent-digest.

Scans session logs for user correction signals (phrases indicating
the user corrected the agent's behavior).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

# Correction patterns: must start with or contain a negation signal
# followed by substantive content (not just "no issues" or "no problem")
CORRECTION_PATTERNS = [
    # "no, don't..." / "no don't..."
    re.compile(r"\bno[,.]?\s+(don'?t|do not|never|stop)\b", re.IGNORECASE),
    # "don't do X" / "do not do X" (standalone)
    re.compile(r"\b(don'?t|do not)\s+\w+", re.IGNORECASE),
    # "stop doing X"
    re.compile(r"\bstop\s+\w+", re.IGNORECASE),
    # "wrong" / "that's wrong"
    re.compile(r"\b(that'?s\s+)?wrong\b", re.IGNORECASE),
    # "I said" (user repeating themselves = correction)
    re.compile(r"\bI\s+said\b", re.IGNORECASE),
]

# False positive filters: lines matching these are NOT corrections
FALSE_POSITIVE_PATTERNS = [
    re.compile(r"\bno\s+(issues?|problems?|worries|thanks)\b", re.IGNORECASE),
    re.compile(r"\bno\s+need\b", re.IGNORECASE),
]


def extract_corrections(lines: list[str]) -> list[str]:
    """Extract lines that contain user correction signals."""
    corrections = []
    for line in lines:
        # Check false positives first
        if any(fp.search(line) for fp in FALSE_POSITIVE_PATTERNS):
            continue
        if any(cp.search(line) for cp in CORRECTION_PATTERNS):
            corrections.append(line)
    return corrections


def infer_directive(
    text: str,
    directive_map: dict[str, dict],
) -> str | None:
    """Try to match correction text to a known directive by keyword overlap."""
    text_lower = text.lower()
    best_match = None
    best_score = 0
    for directive_id, info in directive_map.items():
        label = info.get("label", "").lower()
        description = info.get("description", "").lower()
        keywords = set(re.findall(r"\w+", label + " " + description))
        text_words = set(re.findall(r"\w+", text_lower))
        overlap = len(keywords & text_words)
        if overlap > best_score:
            best_score = overlap
            best_match = directive_id
    # Require at least 2 keyword matches to avoid false positives
    if best_score >= 2:
        return best_match
    return None


def load_directive_map(map_path: Path) -> dict[str, dict]:
    """Load directive map from YAML."""
    with map_path.open() as f:
        data = yaml.safe_load(f)
    return data.get("directives", {})


def collect(
    logs_dir: Path,
    directive_map_path: Path,
    since_hours: int = 24,
) -> list[dict]:
    """Collect correction signals from session logs.

    Scans .jsonl and .md files in logs_dir for user messages containing
    correction patterns.

    Returns list of event dicts ready for journal.append_event().
    """
    directive_map = load_directive_map(directive_map_path)
    now = datetime.now(timezone.utc).isoformat()
    events = []

    if not logs_dir.exists():
        return events

    for log_file in sorted(logs_dir.glob("*.jsonl")):
        try:
            lines = log_file.read_text().strip().split("\n")
        except (OSError, UnicodeDecodeError):
            continue

        corrections = extract_corrections(lines)
        for correction in corrections:
            directive = infer_directive(correction, directive_map)
            rule = directive if directive else f"inferred:{correction[:50]}"
            events.append({
                "ts": now,
                "source": "session_log",
                "type": "user_correction",
                "signal": correction[:200],
                "rule": rule,
                "session": log_file.stem,
            })

    return events
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-agent-digest/augur/tests/test_session_collector.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/auto-agent-digest/scripts/collect_session_signals.py skills/auto-agent-digest/augur/tests/test_session_collector.py
git commit -m "feat(auto-agent-digest): add session log signal collector with correction detection"
```

---

### Task 6: `/flag` command

**Files:**
- Create: `skills/auto-agent-digest/scripts/flag.py`
- Create: `skills/auto-agent-digest/commands/flag.md`
- Create: `skills/auto-agent-digest/augur/tests/test_flag.py`

- [ ] **Step 1: Write failing tests**

```python
# skills/auto-agent-digest/augur/tests/test_flag.py
"""Tests for the /flag command executor."""

import json
from pathlib import Path

import pytest

from skills.auto_agent_digest.scripts.flag import build_event, parse_flag_args


def test_parse_simple_flag():
    args = parse_flag_args('"agent added to centralized config again"')
    assert args["description"] == "agent added to centralized config again"
    assert args["rule"] is None
    assert args["adr"] is None


def test_parse_with_rule():
    args = parse_flag_args('"used emoji" --rule no_emojis')
    assert args["description"] == "used emoji"
    assert args["rule"] == "no_emojis"


def test_parse_with_adr():
    args = parse_flag_args('"centralized config" --adr ADR-163')
    assert args["description"] == "centralized config"
    assert args["adr"] == "ADR-163"


def test_build_event_with_rule():
    event = build_event("used emoji", rule="no_emojis")
    assert event["source"] == "manual"
    assert event["type"] == "flag"
    assert event["rule"] == "no_emojis"
    assert event["priority"] == "boost"
    assert "ts" in event


def test_build_event_with_adr():
    event = build_event("centralized config", adr="ADR-163")
    assert event["rule"] == "ADR-163"


def test_build_event_no_mapping():
    event = build_event("something unmapped")
    assert event["rule"] == "manual:something unmapped"


def test_build_event_with_inferred_directive():
    directive_map = {
        "no_emojis": {"label": "NO emojis", "sources": [], "description": "Unless user explicitly requests them."},
    }
    event = build_event("stop adding emojis", directive_map=directive_map)
    assert event["rule"] == "no_emojis"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-agent-digest/augur/tests/test_flag.py -v`
Expected: FAIL

- [ ] **Step 3: Implement flag.py**

```python
# skills/auto-agent-digest/scripts/flag.py
"""Executor for the /flag slash command.

Parses user input, resolves directive mapping, and appends a boosted
event to the agent-digest journal.

Usage: /flag "<description>" [--rule <rule_id>] [--adr <ADR-NNN>]
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from skills.auto_agent_digest.scripts.collect_session_signals import infer_directive


def parse_flag_args(args_str: str) -> dict:
    """Parse /flag command arguments."""
    # Extract quoted description
    desc_match = re.search(r'"([^"]+)"', args_str)
    description = desc_match.group(1) if desc_match else args_str.strip().strip('"')

    # Extract --rule flag
    rule_match = re.search(r"--rule\s+(\S+)", args_str)
    rule = rule_match.group(1) if rule_match else None

    # Extract --adr flag
    adr_match = re.search(r"--adr\s+(\S+)", args_str)
    adr = adr_match.group(1) if adr_match else None

    return {"description": description, "rule": rule, "adr": adr}


def build_event(
    description: str,
    rule: str | None = None,
    adr: str | None = None,
    directive_map: dict[str, dict] | None = None,
) -> dict:
    """Build a journal event from /flag input."""
    # Resolve the rule/directive
    if rule:
        resolved_rule = rule
    elif adr:
        resolved_rule = adr
    elif directive_map:
        inferred = infer_directive(description, directive_map)
        resolved_rule = inferred if inferred else f"manual:{description}"
    else:
        resolved_rule = f"manual:{description}"

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "manual",
        "type": "flag",
        "rule": resolved_rule,
        "note": description,
        "priority": "boost",
    }
```

- [ ] **Step 4: Create commands/flag.md**

```markdown
---
description: Flag a decision violation for the agent-digest nightly loop
visibility: public
---

# flag

Manually flag when an agent violated a known decision. The violation is
recorded in the event journal and will appear in the next nightly digest
with boosted priority.

## Usage

```
/flag "<description>" [--rule <rule_id>] [--adr <ADR-NNN>]
```

## Examples

```
/flag "agent added to centralized config again" --adr ADR-163
/flag "used emoji in commit message"
/flag "edited generated file directly" --rule no_generated_edits
```

## Options

- `--rule <id>` — Map directly to a directive ID from directive-map.yaml
- `--adr <ADR-NNN>` — Map to a specific ADR number
- If neither flag is provided, the system infers the directive from description text
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-agent-digest/augur/tests/test_flag.py -v`
Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add skills/auto-agent-digest/scripts/flag.py skills/auto-agent-digest/commands/flag.md skills/auto-agent-digest/augur/tests/test_flag.py
git commit -m "feat(auto-agent-digest): add /flag command with directive inference"
```

---

### Task 7: Digest compiler (main OpsCommand module)

**Files:**
- Create: `skills/auto-agent-digest/scripts/compile_digest.py`
- Create: `skills/auto-agent-digest/augur/tests/test_compiler.py`

- [ ] **Step 1: Write failing tests**

```python
# skills/auto-agent-digest/augur/tests/test_compiler.py
"""Tests for the digest compiler (OpsCommand entry point)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from skills.auto_agent_digest.scripts.compile_digest import (
    compile_hot_tier,
    compile_warm_tier,
    format_hot_section,
    format_warm_section,
)


@pytest.fixture
def directive_map() -> dict[str, dict]:
    return {
        "no_fs_in_dashboard": {
            "label": "NO fs/spawn in dashboard",
            "sources": ["rule_11", "ADR-453"],
            "description": "All data via useMcpQuery/useMcpMutation. No import fs.",
        },
        "no_emojis": {
            "label": "NO emojis",
            "sources": ["preference"],
            "description": "Unless user explicitly requests them.",
        },
    }


@pytest.fixture
def sample_events() -> list[dict]:
    return [
        {"ts": "2026-03-24T02:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard"},
        {"ts": "2026-03-24T03:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard"},
        {"ts": "2026-03-23T10:00:00Z", "source": "session_log", "type": "user_correction", "rule": "no_emojis"},
    ]


def test_compile_hot_tier(sample_events: list[dict], directive_map: dict):
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    lines = compile_hot_tier(sample_events, directive_map, reference_date=ref)
    assert len(lines) >= 2
    assert "NO fs/spawn" in lines[0] or "NO emojis" in lines[0]


def test_compile_hot_empty():
    lines = compile_hot_tier([], {})
    assert len(lines) == 1
    assert "clean this week" in lines[0].lower()


def test_format_hot_section(sample_events: list[dict], directive_map: dict):
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    section = format_hot_section(sample_events, directive_map, reference_date=ref)
    assert "## Hot Directives" in section
    assert "auto-generated" in section
    assert "do not edit manually" in section


def test_compile_warm_tier_with_adrs(tmp_path: Path):
    # Create mock ADR files
    adr_dir = tmp_path / "adrs"
    adr_dir.mkdir()
    (adr_dir / "ADR-490-dashboard-imports.md").write_text(
        "---\ntitle: Dashboard import architecture\nstatus: accepted\ndate: 2026-03-18\n---\n\nSplit imports into @/ and @skill/.\n"
    )
    (adr_dir / "ADR-100-old-decision.md").write_text(
        "---\ntitle: Old decision\nstatus: accepted\ndate: 2025-01-01\n---\n\nSomething old.\n"
    )
    ref = datetime(2026, 3, 24, tzinfo=timezone.utc)
    lines = compile_warm_tier(adr_dir, days=30, reference_date=ref)
    assert len(lines) == 1  # only ADR-490, not ADR-100
    assert "ADR-490" in lines[0]


def test_format_warm_section(tmp_path: Path):
    adr_dir = tmp_path / "adrs"
    adr_dir.mkdir()
    (adr_dir / "ADR-490-dashboard-imports.md").write_text(
        "---\ntitle: Dashboard import architecture\nstatus: accepted\ndate: 2026-03-18\n---\n\nContent.\n"
    )
    ref = datetime(2026, 3, 24, tzinfo=timezone.utc)
    section = format_warm_section(adr_dir, reference_date=ref)
    assert "## Recent Decisions" in section
    assert "auto-generated" in section


def test_hot_section_within_token_budget(directive_map: dict):
    # Generate many events to test budget enforcement
    events = []
    for i in range(50):
        events.append({
            "ts": "2026-03-24T02:00:00Z",
            "source": "git",
            "type": "pattern_violation",
            "rule": f"rule_{i}",
        })
    big_map = {f"rule_{i}": {"label": f"Rule {i} violation with a long description", "sources": [f"src_{i}"], "description": f"Long description for rule {i} to consume token budget"} for i in range(50)}
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    section = format_hot_section(events, big_map, reference_date=ref)
    from skills.auto_agent_digest.scripts.scoring import estimate_tokens
    # Section should be reasonably bounded (header + directives + overflow line)
    body_lines = [l for l in section.split("\n") if l.startswith("- ")]
    assert len(body_lines) < 50  # budget truncated
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-agent-digest/augur/tests/test_compiler.py -v`
Expected: FAIL

- [ ] **Step 3: Implement compile_digest.py**

```python
# skills/auto-agent-digest/scripts/compile_digest.py
"""Agent-digest compiler — OpsCommand entry point for the nightly loop.

Orchestrates signal collectors, scores directives, formats digest sections,
and writes intermediate files for memory_assembler.py to prepend.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from src.config.paths import get_logs_dir, get_runtime_dir, get_skills_dir, get_vault_dir
from src.lib.ops_protocol import (
    FixResult,
    OpsContext,
    ScanResult,
    evolution_gap,
    make_issue,
)

from skills.auto_agent_digest.scripts.collect_git_signals import collect as collect_git
from skills.auto_agent_digest.scripts.collect_session_signals import collect as collect_session
from skills.auto_agent_digest.scripts.journal import (
    append_event,
    archive_old,
    purge_archives,
    read_events,
)
from skills.auto_agent_digest.scripts.scoring import (
    TOKEN_BUDGET_HOT,
    TOKEN_BUDGET_WARM,
    estimate_tokens,
    score_directives,
    select_top_directives,
)

name = "auto-agent-digest"

HOT_WINDOW_DAYS = 7
WARM_WINDOW_DAYS = 30


def _skill_root() -> Path:
    return get_skills_dir() / "auto-agent-digest"


def _journal_dir() -> Path:
    d = get_runtime_dir() / "agent-digest"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_directive_map() -> dict[str, dict]:
    map_path = _skill_root() / "assets" / "directive-map.yaml"
    with map_path.open() as f:
        data = yaml.safe_load(f)
    return data.get("directives", {})


def _load_seed_directives() -> list[dict]:
    seed_path = _skill_root() / "assets" / "seeds" / "example-auto-agent-digest.yaml"
    if not seed_path.exists():
        return []
    with seed_path.open() as f:
        data = yaml.safe_load(f)
    return data.get("seed_directives", [])


def compile_hot_tier(
    events: list[dict],
    directive_map: dict[str, dict],
    reference_date: datetime | None = None,
) -> list[str]:
    """Compile Hot tier directive lines from events."""
    if not events:
        return ["No active directives — all patterns clean this week."]
    scored = score_directives(events, reference_date=reference_date)
    return select_top_directives(scored, directive_map, budget=TOKEN_BUDGET_HOT)


def compile_warm_tier(
    adr_dir: Path,
    days: int = WARM_WINDOW_DAYS,
    reference_date: datetime | None = None,
) -> list[str]:
    """Compile Warm tier from recent ADRs."""
    ref = reference_date or datetime.now(timezone.utc)
    cutoff = ref - timedelta(days=days)
    lines = []
    used_tokens = 0

    if not adr_dir.exists():
        return lines

    for adr_file in sorted(adr_dir.glob("ADR-*.md"), reverse=True):
        try:
            content = adr_file.read_text()
        except OSError:
            continue

        # Parse frontmatter
        if not content.startswith("---"):
            continue
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            fm = yaml.safe_load(parts[1])
        except yaml.YAMLError:
            continue

        title = fm.get("title", adr_file.stem)
        date_str = fm.get("date", "")
        if not date_str:
            continue

        try:
            if isinstance(date_str, str):
                adr_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            else:
                adr_date = datetime.combine(date_str, datetime.min.time()).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        if adr_date < cutoff:
            continue

        # Extract ADR number from filename
        adr_num = adr_file.stem.split("-")[0] + "-" + adr_file.stem.split("-")[1] if "-" in adr_file.stem else adr_file.stem
        line = f"- **{adr_num}**: {title} ({date_str})"
        line_tokens = estimate_tokens(line)
        if used_tokens + line_tokens > TOKEN_BUDGET_WARM:
            break
        lines.append(line)
        used_tokens += line_tokens

    return lines


def format_hot_section(
    events: list[dict],
    directive_map: dict[str, dict],
    reference_date: datetime | None = None,
) -> str:
    """Format the complete Hot Directives section."""
    ref = reference_date or datetime.now(timezone.utc)
    lines = compile_hot_tier(events, directive_map, reference_date=ref)
    total_tokens = sum(estimate_tokens(l) for l in lines)

    header = (
        "## Hot Directives (violated in last 7 days)\n"
        f"<!-- auto-generated by auto-agent-digest nightly loop — do not edit manually -->\n"
        f"<!-- last updated: {ref.isoformat()} | signals: {len(events)} events | budget: {total_tokens}/{TOKEN_BUDGET_HOT} tokens -->\n"
    )
    return header + "\n" + "\n".join(lines) + "\n"


def format_warm_section(
    adr_dir: Path,
    reference_date: datetime | None = None,
) -> str:
    """Format the complete Recent Decisions section."""
    ref = reference_date or datetime.now(timezone.utc)
    lines = compile_warm_tier(adr_dir, reference_date=ref)

    header = (
        "## Recent Decisions (last 30 days)\n"
        f"<!-- auto-generated by auto-agent-digest weekly loop — do not edit manually -->\n"
        f"<!-- last updated: {ref.isoformat()} | ADRs scanned: {len(lines)} -->\n"
    )
    if not lines:
        return header + "\nNo recent ADRs in the last 30 days.\n"
    return header + "\n" + "\n".join(lines) + "\n"


def _write_digest_file(path: Path, content: str) -> None:
    """Write digest section to intermediate file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ---------------------------------------------------------------------------
# OpsCommand contract
# ---------------------------------------------------------------------------


def scan(ctx: OpsContext) -> ScanResult:
    """Collect violation signals and report stats."""
    journal_dir = _journal_dir()
    skill_root = _skill_root()
    patterns_path = skill_root / "assets" / "violation-patterns.yaml"
    directive_map_path = skill_root / "assets" / "directive-map.yaml"
    issues = []

    # Collect git signals
    git_events = collect_git(ctx.project_root, patterns_path)
    for event in git_events:
        append_event(journal_dir, event)

    # Collect session signals
    logs_dir = get_logs_dir()
    session_events = collect_session(logs_dir, directive_map_path)
    for event in session_events:
        append_event(journal_dir, event)

    total_new = len(git_events) + len(session_events)

    # Read full window for scoring
    since = datetime.now(timezone.utc) - timedelta(days=HOT_WINDOW_DAYS)
    all_events = read_events(journal_dir, since=since)

    if not all_events and ctx.difficulty >= 1:
        issues.append(
            evolution_gap(
                "No violation events in 7-day window — session log collector may not be capturing corrections. "
                "Next: verify session log paths and correction patterns."
            )
        )

    if ctx.difficulty >= 1:
        directive_map = _load_directive_map()
        scored = score_directives(all_events)
        low_scores = all(v["score"] < 2 for v in scored.values()) if scored else True
        if scored and low_scores:
            issues.append(
                evolution_gap(
                    "All Hot directives score < 2 — directive-map.yaml may need more patterns. "
                    "Next: review recent session logs for uncaptured correction signals."
                )
            )

    # Check for promotion candidates: directives in Hot for 30+ days with no decrease
    # TODO_BUG: Full promotion notification via `attention` skill is spec-required but
    # deferred to d=3. For now, report as evolution_gap so it surfaces in nightly output.
    if ctx.difficulty >= 2 and all_events:
        # Read 30-day window to check for persistent directives
        since_30d = datetime.now(timezone.utc) - timedelta(days=30)
        events_30d = read_events(journal_dir, since=since_30d)
        scored_30d = score_directives(events_30d)
        for directive_id, data in scored_30d.items():
            if data["count"] >= 10:  # persistent, high-count = promotion candidate
                issues.append(
                    evolution_gap(
                        f"Directive '{directive_id}' has {data['count']} violations over 30 days — "
                        f"candidate for CLAUDE.md rule promotion. "
                        f"Next: review and add to docs/agent-topics/agent-rules.md if warranted."
                    )
                )

    return ScanResult(
        issues=issues,
        summary=f"Collected {total_new} new events ({len(git_events)} git, {len(session_events)} session). "
                f"Journal has {len(all_events)} events in 7-day window.",
        severity="info" if not issues else "warning",
        items_scanned=total_new,
    )


def fix(ctx: OpsContext, issues: list[dict]) -> FixResult:
    """Compile digest sections and write intermediate files."""
    if ctx.dry_run:
        return FixResult(success=True, summary="Dry run: would compile digest sections")

    journal_dir = _journal_dir()
    directive_map = _load_directive_map()
    memory_dir = get_vault_dir() / "memory"
    changes = []

    ref = datetime.now(timezone.utc)

    # Hot tier (d>=1)
    if ctx.difficulty >= 1:
        since = ref - timedelta(days=HOT_WINDOW_DAYS)
        events = read_events(journal_dir, since=since)

        # Cold start: if no events, use seed directives
        if not events:
            seeds = _load_seed_directives()
            for seed in seeds:
                append_event(journal_dir, {
                    "ts": ref.isoformat(),
                    "source": "seed",
                    "type": "pattern_violation",
                    "rule": seed["directive"],
                })
            events = read_events(journal_dir, since=since)

        hot_section = format_hot_section(events, directive_map, reference_date=ref)
        hot_path = memory_dir / "digest-hot.md"
        _write_digest_file(hot_path, hot_section)
        changes.append(f"Wrote {hot_path}")

    # Warm tier (d>=2)
    if ctx.difficulty >= 2:
        adr_dir = get_vault_dir() / "dev" / "adrs"
        warm_section = format_warm_section(adr_dir, reference_date=ref)
        warm_path = memory_dir / "digest-warm.md"
        _write_digest_file(warm_path, warm_section)
        changes.append(f"Wrote {warm_path}")

        # Archive and purge
        date_str = ref.strftime("%Y-%m-%d")
        archive_old(journal_dir, date_str=date_str)
        purged = purge_archives(journal_dir, retention_days=30, reference_date=ref)
        if purged:
            changes.append(f"Purged {len(purged)} old archives")

    return FixResult(
        success=True,
        changes=changes,
        summary=f"Compiled {'hot' if ctx.difficulty == 1 else 'hot + warm'} digest. {len(changes)} files written.",
        fix_type="sync",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-agent-digest/augur/tests/test_compiler.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skills/auto-agent-digest/scripts/compile_digest.py skills/auto-agent-digest/augur/tests/test_compiler.py
git commit -m "feat(auto-agent-digest): add digest compiler with OpsCommand scan/fix contract"
```

---

### Task 8: Memory assembler integration

**Files:**
- Modify: `skills/auto-memory-sync/scripts/memory_assembler.py`

**Context:** The assembler's `generate_claude_index()` function generates the MEMORY.md content. We add a `_prepend_digest_sections()` step that reads `digest-hot.md` and `digest-warm.md` from the memory directory and prepends them before the Memory Index.

- [ ] **Step 1: Read memory_assembler.py to find the exact insertion point**

Run: Read `skills/auto-memory-sync/scripts/memory_assembler.py` and find the `generate_claude_index()` function. Identify where it writes the `# Augur Memory` header and the memory entry list.

- [ ] **Step 2: Implement _prepend_digest_sections()**

Add this function to `memory_assembler.py`:

```python
def _prepend_digest_sections(memory_dir: Path, index_content: str) -> str:
    """Prepend digest-hot.md and digest-warm.md sections before the Memory Index.

    If digest files don't exist, returns index_content unchanged.
    """
    sections = []

    hot_path = memory_dir / "digest-hot.md"
    if hot_path.exists():
        sections.append(hot_path.read_text().strip())

    warm_path = memory_dir / "digest-warm.md"
    if warm_path.exists():
        sections.append(warm_path.read_text().strip())

    if not sections:
        return index_content

    # Replace "# Augur Memory\n\n" header — digest sections go between header and index
    header = "# Augur Memory\n"
    if index_content.startswith(header):
        body = index_content[len(header):].lstrip("\n")
        return header + "\n" + "\n\n".join(sections) + "\n\n" + body
    return "\n\n".join(sections) + "\n\n" + index_content
```

- [ ] **Step 3: Wire _prepend_digest_sections into assemble()**

In the `assemble()` function, find the line that writes the Claude index:
```python
claude_memory.write_text(generate_claude_index(gated), encoding="utf-8")
```

Replace it with:
```python
claude_index = generate_claude_index(gated)
claude_index = _prepend_digest_sections(vault_memory_dir, claude_index)
claude_memory.write_text(claude_index, encoding="utf-8")
```

**Important:** Pass `vault_memory_dir` (the parameter already in `assemble()`), NOT `claude_native_dir`. The digest files (`digest-hot.md`, `digest-warm.md`) are written to `get_vault_dir() / "memory"` by `compile_digest.py`, which corresponds to `vault_memory_dir`.

- [ ] **Step 4: Test manually**

Run: Create test digest files and run the assembler to verify MEMORY.md includes digest sections:

```bash
# Create test digest files
mkdir -p "$(python -c 'from src.config.paths import get_vault_dir; print(get_vault_dir() / "memory")')"
echo "## Hot Directives (violated in last 7 days)
<!-- test -->
- **Test directive** [rule_1] (violated 1x this week)" > "$(python -c 'from src.config.paths import get_vault_dir; print(get_vault_dir() / "memory" / "digest-hot.md")')"
```

Then verify the Claude Code MEMORY.md at `~/.claude/projects/-Users-<user>-Projects-Augur/memory/MEMORY.md` gets the sections after a memory sync.

- [ ] **Step 5: Commit**

```bash
git add skills/auto-memory-sync/scripts/memory_assembler.py
git commit -m "feat(auto-agent-digest): add digest section prepend hook to memory_assembler"
```

---

### Task 9: Integration test — full pipeline

**Files:**
- Create: `skills/auto-agent-digest/augur/tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# skills/auto-agent-digest/augur/tests/test_integration.py
"""Integration tests for the full agent-digest pipeline."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from skills.auto_agent_digest.scripts.compile_digest import (
    compile_hot_tier,
    format_hot_section,
    format_warm_section,
)
from skills.auto_agent_digest.scripts.journal import append_event, read_events
from skills.auto_agent_digest.scripts.scoring import TOKEN_BUDGET_HOT, estimate_tokens


@pytest.fixture
def journal_dir(tmp_path: Path) -> Path:
    d = tmp_path / "agent-digest"
    d.mkdir()
    return d


@pytest.fixture
def directive_map() -> dict[str, dict]:
    return {
        "no_fs_in_dashboard": {"label": "NO fs/spawn in dashboard", "sources": ["rule_11"], "description": "All data via MCP."},
        "no_emojis": {"label": "NO emojis", "sources": ["preference"], "description": "Unless user explicitly requests."},
        "no_suppression": {"label": "NO error suppression", "sources": ["rule_5"], "description": "Fix root cause."},
    }


def test_cold_start_empty_journal(directive_map: dict):
    """First run with no events produces empty-state message."""
    lines = compile_hot_tier([], directive_map)
    assert len(lines) == 1
    assert "clean this week" in lines[0].lower()


def test_full_pipeline_journal_to_digest(journal_dir: Path, directive_map: dict):
    """Events → journal → read → score → compile → formatted section."""
    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)

    # Simulate events from different collectors
    events_to_add = [
        {"ts": "2026-03-24T02:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard", "evidence": "import fs"},
        {"ts": "2026-03-24T03:00:00Z", "source": "git", "type": "pattern_violation", "rule": "no_fs_in_dashboard", "evidence": "execSync"},
        {"ts": "2026-03-23T10:00:00Z", "source": "session_log", "type": "user_correction", "rule": "no_emojis", "signal": "stop adding emojis"},
        {"ts": "2026-03-24T08:00:00Z", "source": "manual", "type": "flag", "rule": "no_suppression", "priority": "boost"},
    ]
    for event in events_to_add:
        append_event(journal_dir, event)

    # Read back
    since = datetime(2026, 3, 17, tzinfo=timezone.utc)
    events = read_events(journal_dir, since=since)
    assert len(events) == 4

    # Compile
    section = format_hot_section(events, directive_map, reference_date=ref)
    assert "## Hot Directives" in section
    assert "auto-generated" in section
    assert "NO" in section  # at least one directive present


def test_budget_enforcement_50_violations(directive_map: dict):
    """50 unique violations must be truncated by token budget."""
    events = []
    big_map = {}
    for i in range(50):
        events.append({"ts": "2026-03-24T02:00:00Z", "source": "git", "type": "pattern_violation", "rule": f"rule_{i}"})
        big_map[f"rule_{i}"] = {"label": f"A verbose directive label number {i} with description", "sources": [f"src"], "description": f"Detailed description of rule {i}"}

    ref = datetime(2026, 3, 24, 12, tzinfo=timezone.utc)
    lines = compile_hot_tier(events, big_map, reference_date=ref)
    total_tokens = sum(estimate_tokens(l) for l in lines)
    # Budget is 500 tokens — we should be under, with truncation
    assert total_tokens <= TOKEN_BUDGET_HOT + 50  # small buffer for overflow line
    assert len(lines) < 50  # truncated


def test_warm_tier_filters_old_adrs(tmp_path: Path):
    """Warm tier excludes ADRs older than 30 days."""
    adr_dir = tmp_path / "adrs"
    adr_dir.mkdir()
    (adr_dir / "ADR-490-new.md").write_text("---\ntitle: New decision\nstatus: accepted\ndate: 2026-03-18\n---\nContent.\n")
    (adr_dir / "ADR-100-old.md").write_text("---\ntitle: Old decision\nstatus: accepted\ndate: 2025-06-01\n---\nContent.\n")

    ref = datetime(2026, 3, 24, tzinfo=timezone.utc)
    section = format_warm_section(adr_dir, reference_date=ref)
    assert "ADR-490" in section
    assert "ADR-100" not in section
```

- [ ] **Step 2: Run integration tests**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-agent-digest/augur/tests/test_integration.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add skills/auto-agent-digest/augur/tests/test_integration.py
git commit -m "test(auto-agent-digest): add integration tests for full pipeline"
```

---

### Task 10: Run full test suite and verify

**Files:** None (verification only)

- [ ] **Step 1: Run all unit tests**

Run: `cd ~/Projects/Augur && python -m pytest skills/auto-agent-digest/augur/tests/ -v`
Expected: All tests PASS (journal: 6, scoring: 10, git_collector: 6, session_collector: 8, flag: 7, compiler: 7, integration: 4 = ~48 tests)

- [ ] **Step 2: Verify skill discovery**

Run: `ls -la skills/auto-agent-digest/SKILL.md` and verify the file exists with correct frontmatter.

Check that the daemon would discover it by verifying `x-augur-type: autoloop` and `x-augur-loop.trigger: nightly` are in the frontmatter.

- [ ] **Step 3: Verify directory structure matches spec**

Run: `find skills/auto-agent-digest -type f | sort` and compare against the spec's file structure.

Expected:
```
skills/auto-agent-digest/__init__.py
skills/auto-agent-digest/SKILL.md
skills/auto-agent-digest/assets/directive-map.yaml
skills/auto-agent-digest/assets/seeds/example-auto-agent-digest.yaml
skills/auto-agent-digest/assets/violation-patterns.yaml
skills/auto-agent-digest/augur/__init__.py
skills/auto-agent-digest/augur/tests/__init__.py
skills/auto-agent-digest/augur/tests/conftest.py
skills/auto-agent-digest/augur/tests/test_compiler.py
skills/auto-agent-digest/augur/tests/test_flag.py
skills/auto-agent-digest/augur/tests/test_git_collector.py
skills/auto-agent-digest/augur/tests/test_integration.py
skills/auto-agent-digest/augur/tests/test_journal.py
skills/auto-agent-digest/augur/tests/test_scoring.py
skills/auto-agent-digest/augur/tests/test_session_collector.py
skills/auto-agent-digest/commands/flag.md
skills/auto-agent-digest/scripts/__init__.py
skills/auto-agent-digest/scripts/collect_git_signals.py
skills/auto-agent-digest/scripts/collect_session_signals.py
skills/auto-agent-digest/scripts/compile_digest.py
skills/auto-agent-digest/scripts/flag.py
skills/auto-agent-digest/scripts/journal.py
skills/auto-agent-digest/scripts/scoring.py
```

- [ ] **Step 4: Final commit if any fixes needed**

If any tests failed or structure was wrong, fix and commit:
```bash
git add -A skills/auto-agent-digest/
git commit -m "fix(auto-agent-digest): address test/structure issues from verification"
```
