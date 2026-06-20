# Voice Profile Personalization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the end-to-end voice-profile journey — onboarding, inline 100-question interview with auto-save + pause/resume, dashboard view with progress + completed states, and manual maintenance with visible age — using existing Augur capabilities (vault, MCP, slash commands, dashboard, Browse).

**Architecture:** A pure-Python state module (`profile_state.py`) owns reads/writes of `vault/profile/interview-in-progress.yaml`. Four MCP tools (`profile-status`, `profile-read`, `profile-write`, `profile-get-age`) wrap it for the dashboard and slash-command surfaces. The `/profile` slash command embeds Almaya Prompt 1 + Prompt 2 + an agent-step contract that auto-saves after every answer. The dashboard polls `profile-status` to render 3 visual states (not-started / in-progress / complete). The Browse category `profile` slots into journey_group `knowledge` at order 4, coordinating with ADR-728's reservation table.

**Tech Stack:** Python 3.11+ (dataclasses, PyYAML, datetime, shutil for archive). Dashboard: Next.js 16, TypeScript, Vitest. No new runtime deps.

**Spec:** `docs/superpowers/specs/2026-05-11-voice-profile-personalization-design.md`

---

## Boundary rules (apply to every task)

- **No LLM calls from server.** The agent step lives in the AI client (per `docs/what-is-augur.md`). MCP tools only persist + retrieve state.
- **Auto-save after every answer is a contract.** Every step in the agent-side flow that gets an answer MUST persist it before asking the next question. Fail loud if vault-write fails.
- **No clipboard.** The `/profile interview` slash command is the interview; the agent reads its body and conducts the interview inline.
- **No daemon scheduling.** Maintenance is manual; dashboard surfaces age + soft amber banner only.
- **Voice-to-text is out of scope.** Document Wispr Flow as a recommendation; don't integrate.
- **One profile per user for v1.** Multi-profile (professional vs casual) is deferred.

After every commit, run the relevant test files. Task 13 runs full integration + browser verification per rule 28.

---

## Amendment 2026-05-11 — Bilingual Support (Model B)

> **Read this FIRST.** Where this amendment conflicts with Tasks 1–13 below, this amendment wins. The spec at `docs/superpowers/specs/2026-05-11-voice-profile-personalization-design.md` §0 carries the canonical design rationale; this section translates that design into task-level deltas.

### What changed

The original plan assumed a single-language profile with one Almaya prompt embedded in the slash-command body. The amended design ships 4 prompts with the system, adds a `language` ('en' | 'he') axis throughout, and treats per-language profiles as parallel artifacts (Model B). A bilingual user can have both EN and HE profiles simultaneously; running the interview in one language does not touch the other.

### Shipped this session (Task 0 — COMPLETE before plan execution starts)

The 4 prompts + README are saved in the repo. Verification: `ls shared-vault/skills/knowledge/prompts/voice-profile/` returns exactly:

```
README.md
interview-en.md
interview-he.md
summary-en.md
summary-he.md
```

Task 0 is verifiable but requires no further work. Treat it as already-done and move on.

### Path & data-model deltas (apply to Tasks 1–5, 7, 11, 12)

The vault layout becomes per-language:

```
vault/profile/
├── en/
│   ├── about-me.md
│   ├── interview-in-progress.yaml
│   └── archive/
└── he/
    ├── about-me.md
    ├── interview-in-progress.yaml
    └── archive/
```

The in-progress YAML schema gains one field:

```yaml
version: 1
language: en          # NEW — "en" | "he"; set once at interview start, never mutated
total: 100
answered: 23
# ... rest unchanged
```

### MCP tool signature deltas (apply to Tasks 2–5, 6)

All four tools take an optional or required `language` parameter:

- **`profile-status(language: 'en' | 'he' | None)`** — `None` returns a dict keyed by language (`{"en": {...}, "he": {...}}`); a given language returns the same payload shape as the original (single object). Existing return-shape fields (in_progress, answered, total, about_me sub-object) are preserved per-language. Update tests to cover all three call shapes.
- **`profile-read(language: 'en' | 'he')`** — `language` is **required**. Reads `vault/profile/<lang>/about-me.md`. Missing-file error includes `"language": "<lang>"`.
- **`profile-write(content, mode, language: 'en' | 'he')`** — `language` is **required**. Writes `vault/profile/<lang>/about-me.md`. Archives only that language's in-progress yaml.
- **`profile-get-age(language: 'en' | 'he')`** — `language` is **required**. Reads only that language's mtime.

Task 6's `capability_exposure.yaml` entries get one line added to each tool's `description:` noting the `language` parameter.

### Task 7 deltas (`/profile` slash command — the largest amendment)

The command body changes substantially. Instead of embedding the Almaya prompts (sections "Embedded Prompt 1" and "Embedded Prompt 2" in the existing plan), the body:

1. **Asks the user for language at the start of `/profile interview`** — "Run the interview in English (en) or Hebrew (he)?" Wait. Re-ask once on invalid input; on second invalid input, default to `en`.
2. **Uses the chosen language to scope all state operations** — `vault/profile/<lang>/interview-in-progress.yaml`, `vault/profile/<lang>/about-me.md`, `vault/profile/<lang>/archive/...`.
3. **Loads the interview prompt from disk at runtime** — read `shared-vault/skills/knowledge/prompts/voice-profile/interview-<lang>.md` using the AI client's native file-read mechanism. The file content IS the prompt. The agent then follows that prompt's instructions verbatim, layered with the auto-save behavior the command body specifies (auto-save remains a `/profile` contract, not in the prompt files).
4. **Loads the summary prompt at compression time** — same pattern with `summary-<lang>.md`.
5. **`/profile update`** — asks the user which language profile to update (only languages with an existing `about-me.md` are valid; abort if neither exists). Loads `summary-<lang>.md` for re-compression. The delta-question template remains shared across languages; the agent translates dynamically when interviewing in HE (acceptable — short questions, bounded translation surface).
6. **`/profile view`** — takes optional `<language>`; with no argument, prints the only existing profile, or asks the user which to view if both exist.

The "Embedded Prompt 1" and "Embedded Prompt 2" sections in Task 7 of the original plan become obsolete — DELETE them when implementing Task 7. Replace with two short subsections that document the file-load pattern.

### Task 8 deltas (`useVoiceProfile` hook)

The hook polls `profile-status()` (no-arg form, returns dict keyed by language) instead of `profile-status()` returning a single object. It exposes a `profiles` shape:

```typescript
type ProfilesState = {
  en: ProfileSlot | null;
  he: ProfileSlot | null;
};

type ProfileSlot = {
  in_progress: boolean;
  answered: number;
  total: number;
  // ... existing fields
  about_me: { exists: boolean; last_updated_at: string | null; age_days: number | null };
};
```

`null` means the language is genuinely empty (no in-progress, no about-me.md). Existing fields retained.

### Task 9 deltas (`VoiceProfile` React component)

The component renders 0, 1, or 2 cards keyed by language:

- **0 cards** — both `profiles.en` and `profiles.he` are null. Render the existing State C call-to-action ONCE with body text noting both languages are available.
- **1 card** — one of `profiles.en` / `profiles.he` is non-null. Render the matching card (State A or B from the original plan) with a small "EN" or "HE" badge in the corner.
- **2 cards** — both slots non-null. Render two cards stacked, each with its own state, each with action buttons scoped to its language (the `/profile interview` link copies `/profile interview` and the user picks language at the agent prompt; the `/profile update` button copies `/profile update he` or `/profile update en`).

Test coverage: 5 cases — 0-card, 1-card-en-A, 1-card-en-B, 1-card-he-B, 2-card (mixed A+B).

### Task 11 deltas (Browse category `profile`)

The Browse card shows a small badge with completed-profile count: "1/2 languages" or "2/2 languages" or "Not yet started". No structural change to BROWSE_CATEGORIES; only the card body text adapts.

### Task 12 deltas (ADR-722 probe + action)

The probe is satisfied if EITHER `vault/profile/en/about-me.md` OR `vault/profile/he/about-me.md` exists with size >256 bytes:

```yaml
- id: human-profile
  label: Build human profile
  probe: foundation.voice_profile     # any language's about-me.md ≥256b
  action: { type: command, command: "/profile interview", label: "Run /profile interview" }
```

The probe test covers three cases: (a) EN exists, milestone done; (b) HE exists, milestone done; (c) neither, milestone pending.

### Task 13 deltas (integration verification)

Browser verification per rule 28 must cover all four `<VoiceProfile>` states (0-card, 1-card-en, 1-card-he, 2-card), not three. End-to-end smoke covers: pick EN → answer 1 question → exit → resume → confirm vault path; then pick HE on a separate `/profile interview` invocation → confirm it does not touch the EN state.

### Nothing changes for

The agent-step contract, auto-save discipline, no-LLM-on-server boundary, no-daemon-scheduling rule, /brain/profile page coexistence with `<HumanApiProfile>`, ADR-728 coordination at journey_order=4, and the overall five-checkpoint shape remain exactly as the original plan describes.

---

## Task 1: `profile_state.py` — state helpers + unit tests

**Files:**
- Create: `shared-vault/skills/knowledge/scripts/profile_state.py`
- Create: `tests/unit/test_voice_profile_state.py`

This module owns the state file. Pure functions, no MCP plumbing, no dashboard concerns. The MCP tools in Task 2 import these helpers.

- [ ] **Step 1: Create the state module**

Write to `shared-vault/skills/knowledge/scripts/profile_state.py`:

```python
"""Voice-profile state file helpers (vault/profile/interview-in-progress.yaml).

Pure functions — no MCP plumbing, no dashboard concerns. Testable in isolation.

The state file schema (see spec §4.1):
  version: 1
  total: 100
  answered: 23
  started_at: 2026-05-11T14:00:00Z
  last_answered_at: 2026-05-11T14:42:00Z
  mode: full | update
  qa_pairs:
    - n: 1
      category: "..."
      q: "..."
      a: "..."
      asked_at: "..."
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


SCHEMA_VERSION = 1
DEFAULT_TOTAL = 100


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class QAPair:
    n: int
    category: str
    q: str
    a: str
    asked_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InterviewState:
    version: int = SCHEMA_VERSION
    total: int = DEFAULT_TOTAL
    answered: int = 0
    started_at: str = ""
    last_answered_at: str = ""
    mode: str = "full"          # "full" | "update"
    qa_pairs: list[QAPair] = field(default_factory=list)

    @classmethod
    def fresh(cls, mode: str = "full", total: int = DEFAULT_TOTAL) -> "InterviewState":
        now = _iso_now()
        return cls(
            version=SCHEMA_VERSION,
            total=total,
            answered=0,
            started_at=now,
            last_answered_at=now,
            mode=mode,
            qa_pairs=[],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "total": self.total,
            "answered": self.answered,
            "started_at": self.started_at,
            "last_answered_at": self.last_answered_at,
            "mode": self.mode,
            "qa_pairs": [qa.to_dict() for qa in self.qa_pairs],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InterviewState":
        return cls(
            version=int(data.get("version", SCHEMA_VERSION)),
            total=int(data.get("total", DEFAULT_TOTAL)),
            answered=int(data.get("answered", 0)),
            started_at=str(data.get("started_at", "")),
            last_answered_at=str(data.get("last_answered_at", "")),
            mode=str(data.get("mode", "full")),
            qa_pairs=[QAPair(**qa) for qa in data.get("qa_pairs", [])],
        )

    @property
    def is_complete(self) -> bool:
        return self.answered >= self.total

    @property
    def percentage(self) -> int:
        if self.total <= 0:
            return 0
        return int(round((self.answered / self.total) * 100))


def load_state(state_path: Path) -> InterviewState | None:
    """Load interview state from disk. Returns None if file doesn't exist."""
    if not state_path.exists():
        return None
    try:
        data = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed state file at {state_path}: {exc}") from exc
    return InterviewState.from_dict(data)


def save_state(state_path: Path, state: InterviewState) -> None:
    """Write state to disk (atomic via tmp + rename)."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    tmp.write_text(
        yaml.safe_dump(state.to_dict(), default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    tmp.replace(state_path)


def append_answer(
    state: InterviewState,
    *,
    category: str,
    question: str,
    answer: str,
) -> InterviewState:
    """Append a Q&A pair to the state. Returns updated state (mutates in place
    and also returns for chaining)."""
    next_n = state.answered + 1
    qa = QAPair(
        n=next_n,
        category=category,
        q=question,
        a=answer,
        asked_at=_iso_now(),
    )
    state.qa_pairs.append(qa)
    state.answered = next_n
    state.last_answered_at = _iso_now()
    return state


def archive_state(state_path: Path, archive_dir: Path, run_date_iso: str | None = None) -> Path:
    """Move the in-progress state file into the archive subdirectory.

    Filename: interview-<YYYY-MM-DD>.yaml. Returns the archive path.
    """
    archive_dir.mkdir(parents=True, exist_ok=True)
    run_date = run_date_iso or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    archive_path = archive_dir / f"interview-{run_date}.yaml"

    # If a same-day archive exists, append a -N suffix
    if archive_path.exists():
        i = 2
        while (archive_dir / f"interview-{run_date}-{i}.yaml").exists():
            i += 1
        archive_path = archive_dir / f"interview-{run_date}-{i}.yaml"

    shutil.move(str(state_path), str(archive_path))
    return archive_path


def get_about_me_age_days(about_me_path: Path, now: datetime | None = None) -> int | None:
    """Return days since about_me.md was last modified. None if file absent."""
    if not about_me_path.exists():
        return None
    mtime = datetime.fromtimestamp(about_me_path.stat().st_mtime, tz=timezone.utc)
    ref = now or datetime.now(timezone.utc)
    return max(0, (ref - mtime).days)
```

- [ ] **Step 2: Write unit tests**

Write to `tests/unit/test_voice_profile_state.py`:

```python
"""Unit tests for profile_state helpers."""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "shared-vault"))

import yaml

from skills.knowledge.scripts.profile_state import (  # noqa: E402
    SCHEMA_VERSION,
    DEFAULT_TOTAL,
    InterviewState,
    QAPair,
    load_state,
    save_state,
    append_answer,
    archive_state,
    get_about_me_age_days,
)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

def test_interview_state_fresh_initializes_correctly():
    s = InterviewState.fresh()
    assert s.version == SCHEMA_VERSION
    assert s.total == DEFAULT_TOTAL
    assert s.answered == 0
    assert s.mode == "full"
    assert s.qa_pairs == []
    assert s.started_at != ""
    assert s.last_answered_at == s.started_at


def test_interview_state_fresh_with_update_mode():
    s = InterviewState.fresh(mode="update", total=15)
    assert s.mode == "update"
    assert s.total == 15


def test_interview_state_is_complete_when_answered_equals_total():
    s = InterviewState.fresh()
    s.answered = 100
    assert s.is_complete


def test_interview_state_percentage():
    s = InterviewState.fresh()
    s.answered = 23
    assert s.percentage == 23
    s.answered = 100
    assert s.percentage == 100
    s.answered = 0
    assert s.percentage == 0


def test_interview_state_percentage_with_zero_total():
    s = InterviewState(total=0)
    assert s.percentage == 0


# ---------------------------------------------------------------------------
# Roundtrip dict serialization
# ---------------------------------------------------------------------------

def test_state_dict_roundtrip():
    original = InterviewState.fresh()
    original.qa_pairs = [
        QAPair(n=1, category="BELIEFS", q="Q1?", a="A1.", asked_at="2026-05-11T14:00Z"),
    ]
    original.answered = 1
    d = original.to_dict()
    restored = InterviewState.from_dict(d)
    assert restored.answered == 1
    assert len(restored.qa_pairs) == 1
    assert restored.qa_pairs[0].q == "Q1?"


# ---------------------------------------------------------------------------
# load_state / save_state
# ---------------------------------------------------------------------------

def test_load_state_returns_none_when_file_missing():
    assert load_state(Path("/nonexistent/path/xyz.yaml")) is None


def test_save_then_load_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "state.yaml"
        original = InterviewState.fresh()
        original = append_answer(original, category="BELIEFS", question="Q?", answer="A.")
        save_state(path, original)

        loaded = load_state(path)
        assert loaded is not None
        assert loaded.answered == 1
        assert loaded.qa_pairs[0].q == "Q?"


def test_load_state_raises_on_malformed_yaml():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "state.yaml"
        path.write_text("not: valid: yaml: too: many: colons:")
        # Some YAML loaders accept this; if so, the resulting dict won't have
        # the right shape but won't raise. Force-malformed input:
        path.write_text("{ unclosed: brace")
        try:
            load_state(path)
            # If no exception, the YAML loader was lenient — this is OK
        except ValueError as exc:
            assert "Malformed" in str(exc) or "state file" in str(exc)


# ---------------------------------------------------------------------------
# append_answer
# ---------------------------------------------------------------------------

def test_append_answer_increments_count():
    s = InterviewState.fresh()
    s = append_answer(s, category="WRITING", question="How do you start?", answer="With a bang.")
    assert s.answered == 1
    assert len(s.qa_pairs) == 1
    assert s.qa_pairs[0].n == 1
    assert s.qa_pairs[0].category == "WRITING"


def test_append_answer_assigns_sequential_n():
    s = InterviewState.fresh()
    s = append_answer(s, category="C", question="Q1?", answer="A1.")
    s = append_answer(s, category="C", question="Q2?", answer="A2.")
    s = append_answer(s, category="C", question="Q3?", answer="A3.")
    assert [qa.n for qa in s.qa_pairs] == [1, 2, 3]
    assert s.answered == 3


def test_append_answer_updates_last_answered_at():
    s = InterviewState.fresh()
    first_ts = s.last_answered_at
    s = append_answer(s, category="C", question="Q?", answer="A.")
    # Different instant than the fresh-state ts (within sub-second is OK)
    assert s.last_answered_at >= first_ts


# ---------------------------------------------------------------------------
# archive_state
# ---------------------------------------------------------------------------

def test_archive_state_moves_file_to_dated_path():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        state_path = td_path / "in-progress.yaml"
        archive_dir = td_path / "archive"
        state_path.write_text("version: 1\n")

        result_path = archive_state(state_path, archive_dir, run_date_iso="2026-05-11")

        assert not state_path.exists()
        assert result_path.exists()
        assert result_path.name == "interview-2026-05-11.yaml"


def test_archive_state_suffixes_when_same_day_exists():
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        archive_dir = td_path / "archive"
        archive_dir.mkdir()
        (archive_dir / "interview-2026-05-11.yaml").write_text("first run\n")

        state_path = td_path / "in-progress.yaml"
        state_path.write_text("second run\n")

        result_path = archive_state(state_path, archive_dir, run_date_iso="2026-05-11")
        assert result_path.name == "interview-2026-05-11-2.yaml"


# ---------------------------------------------------------------------------
# get_about_me_age_days
# ---------------------------------------------------------------------------

def test_get_about_me_age_days_missing_file_returns_none():
    assert get_about_me_age_days(Path("/nonexistent.md")) is None


def test_get_about_me_age_days_returns_zero_for_just_modified():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "about-me.md"
        path.write_text("# profile\n")
        age = get_about_me_age_days(path)
        assert age == 0


def test_get_about_me_age_days_returns_positive_for_old_file():
    import os
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "about-me.md"
        path.write_text("# profile\n")
        # Set mtime to 10 days ago
        ten_days_ago = (datetime.now(timezone.utc) - timedelta(days=10)).timestamp()
        os.utime(path, (ten_days_ago, ten_days_ago))
        age = get_about_me_age_days(path)
        assert age == 10
```

- [ ] **Step 3: Run tests — verify pass**

Run:
```bash
pytest tests/unit/test_voice_profile_state.py -v
```
Expected: ~16 tests pass.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/knowledge/scripts/profile_state.py tests/unit/test_voice_profile_state.py
git commit -m "$(cat <<'EOF'
feat(knowledge): profile_state helpers — state file load/save/append/archive

Pure-Python module for vault/profile/interview-in-progress.yaml lifecycle.
No MCP plumbing — testable in isolation.

Provides:
  - InterviewState dataclass + QAPair (mirrors spec §4.1 schema)
  - load_state(path) / save_state(path, state) — atomic roundtrip
  - append_answer(state, category, question, answer) — appends + bumps counters
  - archive_state(state_path, archive_dir, run_date) — moves to archive/interview-<date>.yaml
                                                       with -N suffix on same-day collisions
  - get_about_me_age_days(about_me_path) — days since mtime, None if absent

~16 unit tests covering fresh-init, percentage edges, dict roundtrip,
load/save, append sequencing, archive same-day collisions, age computation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: MCP tool `profile-status`

**Files:**
- Create: `shared-vault/skills/knowledge/scripts/mcp/tools_voice_profile.py`
- Create: `tests/unit/test_voice_profile_mcp.py`

- [ ] **Step 1: Write the failing test first**

Write to `tests/unit/test_voice_profile_mcp.py`:

```python
"""Unit tests for the voice-profile MCP tools."""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "shared-vault"))

import yaml

from skills.knowledge.scripts.profile_state import InterviewState, append_answer, save_state


# ---------------------------------------------------------------------------
# Helper: build a sandbox vault dir + paths
# ---------------------------------------------------------------------------

class _PathSandbox:
    """Holds tmp vault paths for tests — vault_dir/profile/{about-me.md,
    interview-in-progress.yaml, archive/}."""

    def __init__(self, td: Path):
        self.vault_dir = td / "vault"
        self.profile_dir = self.vault_dir / "profile"
        self.profile_dir.mkdir(parents=True)
        self.archive_dir = self.profile_dir / "archive"
        self.state_path = self.profile_dir / "interview-in-progress.yaml"
        self.about_me_path = self.profile_dir / "about-me.md"


# ---------------------------------------------------------------------------
# profile_status: no interview yet, no about-me.md
# ---------------------------------------------------------------------------

def test_profile_status_returns_empty_when_nothing_exists():
    from skills.knowledge.scripts.mcp.tools_voice_profile import _profile_status_sync

    with tempfile.TemporaryDirectory() as td:
        sb = _PathSandbox(Path(td))
        result = _profile_status_sync(state_path=sb.state_path, about_me_path=sb.about_me_path)

        assert result["success"] is True
        assert result["in_progress"] is False
        assert result["complete"] is False
        assert result["about_me"]["exists"] is False
        assert result["answered"] == 0


def test_profile_status_in_progress_state():
    from skills.knowledge.scripts.mcp.tools_voice_profile import _profile_status_sync

    with tempfile.TemporaryDirectory() as td:
        sb = _PathSandbox(Path(td))
        s = InterviewState.fresh()
        for i in range(23):
            s = append_answer(s, category="BELIEFS", question=f"Q{i+1}", answer=f"A{i+1}")
        save_state(sb.state_path, s)

        result = _profile_status_sync(state_path=sb.state_path, about_me_path=sb.about_me_path)
        assert result["in_progress"] is True
        assert result["answered"] == 23
        assert result["total"] == 100
        assert result["percentage"] == 23
        assert result["complete"] is False
        assert result["about_me"]["exists"] is False


def test_profile_status_complete_state():
    from skills.knowledge.scripts.mcp.tools_voice_profile import _profile_status_sync

    with tempfile.TemporaryDirectory() as td:
        sb = _PathSandbox(Path(td))
        sb.about_me_path.write_text("# voice profile\n\nbody.")
        # No in-progress file — interview was completed and archived

        result = _profile_status_sync(state_path=sb.state_path, about_me_path=sb.about_me_path)
        assert result["in_progress"] is False
        assert result["complete"] is True
        assert result["about_me"]["exists"] is True
        assert result["about_me"]["age_days"] == 0
```

- [ ] **Step 2: Create the MCP module skeleton**

Write to `shared-vault/skills/knowledge/scripts/mcp/tools_voice_profile.py`:

```python
"""Voice-profile MCP tools.

Four tools:
  - profile-status: dashboard polls for interview progress + about-me.md metadata
  - profile-read:   dashboard reads about-me.md content + metadata
  - profile-write:  agent writes about-me.md and archives in-progress state
  - profile-get-age: explicit "days since last update" helper

Mutations to vault/profile/interview-in-progress.yaml during the interview
are done by the AGENT via the generic vault-write tool — these MCP tools
don't intermediate per-answer state changes. Keeping the surface read-mostly.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from skills.knowledge.scripts.profile_state import (
    InterviewState,
    archive_state,
    get_about_me_age_days,
    load_state,
)


def _resolve_paths() -> tuple[Path, Path, Path]:
    """Resolve profile state path, about_me path, archive dir.

    Imported lazily to avoid import-time path resolution in tests.
    """
    from src.config.paths import get_vault_dir
    vault = get_vault_dir()
    profile_dir = vault / "profile"
    return (
        profile_dir / "interview-in-progress.yaml",
        profile_dir / "about-me.md",
        profile_dir / "archive",
    )


def _profile_status_sync(*, state_path: Path, about_me_path: Path) -> dict[str, Any]:
    """Sync implementation of profile-status; testable without async/MCP setup."""
    state = load_state(state_path)
    about_me_exists = about_me_path.exists()
    age_days = get_about_me_age_days(about_me_path) if about_me_exists else None
    about_me_mtime_iso: str | None = None
    if about_me_exists:
        about_me_mtime_iso = (
            datetime.fromtimestamp(about_me_path.stat().st_mtime, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    answered = state.answered if state else 0
    total = state.total if state else 100
    percentage = state.percentage if state else 0
    in_progress = state is not None and not state.is_complete
    complete = about_me_exists

    return {
        "success": True,
        "in_progress": in_progress,
        "answered": answered,
        "total": total,
        "percentage": percentage,
        "started_at": state.started_at if state else None,
        "last_answered_at": state.last_answered_at if state else None,
        "complete": complete,
        "about_me": {
            "exists": about_me_exists,
            "last_updated_at": about_me_mtime_iso,
            "age_days": age_days,
        },
    }


def register_voice_profile_tools(mcp, tool_annotations, mcp_tool_interceptor, metrics):
    """Register the 4 voice-profile MCP tools. Called from the knowledge skill's
    MCP registration entry point."""

    @mcp.tool(
        name="profile-status",
        annotations=tool_annotations({
            "title": "Voice Profile Status",
            "readOnlyHint": True, "destructiveHint": False,
            "idempotentHint": True, "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def profile_status_tool() -> str:
        """Interview progress + about-me.md metadata."""
        metrics.track_tool("profile_status", skill="knowledge")
        try:
            state_path, about_me_path, _ = _resolve_paths()
            result = _profile_status_sync(state_path=state_path, about_me_path=about_me_path)
            return json.dumps(result, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    # profile_read, profile_write, profile_get_age registered in Tasks 3-5
```

- [ ] **Step 3: Run tests → verify pass**

Run:
```bash
pytest tests/unit/test_voice_profile_mcp.py -v -k "profile_status"
```
Expected: 3 tests pass.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/knowledge/scripts/mcp/tools_voice_profile.py tests/unit/test_voice_profile_mcp.py
git commit -m "$(cat <<'EOF'
feat(knowledge): profile-status MCP tool

First of 4 voice-profile MCP tools. Reads the in-progress state file
(if present) + the about-me.md file (if present) and returns a
unified status payload the dashboard polls every 30s.

Body extracted into _profile_status_sync() sync helper so tests
can drive it directly without async/MCP plumbing.

Three unit tests covering: nothing-exists, in-progress, complete.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: MCP tool `profile-read`

**Files:**
- Modify: `shared-vault/skills/knowledge/scripts/mcp/tools_voice_profile.py` (append the tool)
- Modify: `tests/unit/test_voice_profile_mcp.py` (append tests)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_voice_profile_mcp.py`:

```python


# ---------------------------------------------------------------------------
# profile_read
# ---------------------------------------------------------------------------

def test_profile_read_returns_content_when_exists():
    from skills.knowledge.scripts.mcp.tools_voice_profile import _profile_read_sync

    with tempfile.TemporaryDirectory() as td:
        sb = _PathSandbox(Path(td))
        sb.about_me_path.write_text("---\ntitle: Voice Profile\n---\n# body\n")

        result = _profile_read_sync(about_me_path=sb.about_me_path)
        assert result["success"] is True
        assert "title: Voice Profile" in result["content"]
        assert result["metadata"]["age_days"] == 0


def test_profile_read_returns_error_when_missing():
    from skills.knowledge.scripts.mcp.tools_voice_profile import _profile_read_sync

    with tempfile.TemporaryDirectory() as td:
        sb = _PathSandbox(Path(td))
        result = _profile_read_sync(about_me_path=sb.about_me_path)
        assert result["success"] is False
        assert result["error"] == "profile_not_found"
        assert "/profile interview" in result["hint"]
```

- [ ] **Step 2: Implement the tool**

Append to `shared-vault/skills/knowledge/scripts/mcp/tools_voice_profile.py` (above `register_voice_profile_tools`):

```python
def _profile_read_sync(*, about_me_path: Path) -> dict[str, Any]:
    """Sync implementation of profile-read."""
    if not about_me_path.exists():
        return {
            "success": False,
            "error": "profile_not_found",
            "hint": "Run /profile interview in your AI client to create your voice profile.",
        }

    content = about_me_path.read_text(encoding="utf-8")
    age_days = get_about_me_age_days(about_me_path)
    mtime_iso = (
        datetime.fromtimestamp(about_me_path.stat().st_mtime, tz=timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    return {
        "success": True,
        "content": content,
        "metadata": {
            "last_updated_at": mtime_iso,
            "age_days": age_days,
            "size_bytes": about_me_path.stat().st_size,
        },
    }
```

Then INSIDE `register_voice_profile_tools`, append after the `profile_status_tool` definition:

```python
    @mcp.tool(
        name="profile-read",
        annotations=tool_annotations({
            "title": "Voice Profile Read",
            "readOnlyHint": True, "destructiveHint": False,
            "idempotentHint": True, "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def profile_read_tool() -> str:
        """Return rendered about-me.md content + metadata, or a not-found error."""
        metrics.track_tool("profile_read", skill="knowledge")
        try:
            _, about_me_path, _ = _resolve_paths()
            return json.dumps(_profile_read_sync(about_me_path=about_me_path), indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})
```

- [ ] **Step 3: Run tests → verify pass**

Run:
```bash
pytest tests/unit/test_voice_profile_mcp.py -v -k "profile_read"
```
Expected: 2 tests pass.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/knowledge/scripts/mcp/tools_voice_profile.py tests/unit/test_voice_profile_mcp.py
git commit -m "$(cat <<'EOF'
feat(knowledge): profile-read MCP tool

Reads vault/profile/about-me.md and returns content + metadata
(last_updated_at, age_days, size_bytes). Returns structured
profile_not_found error when the file doesn't exist — points
the user at /profile interview.

Two unit tests: happy path + not-found error.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: MCP tool `profile-write` (with archive logic)

**Files:**
- Modify: `shared-vault/skills/knowledge/scripts/mcp/tools_voice_profile.py` (append)
- Modify: `tests/unit/test_voice_profile_mcp.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_voice_profile_mcp.py`:

```python


# ---------------------------------------------------------------------------
# profile_write
# ---------------------------------------------------------------------------

def test_profile_write_creates_about_me_and_archives_state():
    from skills.knowledge.scripts.mcp.tools_voice_profile import _profile_write_sync

    with tempfile.TemporaryDirectory() as td:
        sb = _PathSandbox(Path(td))
        # Pre-create the in-progress state file (completed)
        s = InterviewState.fresh()
        for i in range(100):
            s = append_answer(s, category="C", question=f"Q{i}", answer=f"A{i}")
        save_state(sb.state_path, s)

        content = "# Voice Profile\n\nMy compressed identity.\n"
        result = _profile_write_sync(
            content=content,
            mode="full",
            about_me_path=sb.about_me_path,
            state_path=sb.state_path,
            archive_dir=sb.archive_dir,
        )

        assert result["success"] is True
        assert sb.about_me_path.exists()
        assert sb.about_me_path.read_text() == content
        # In-progress file moved to archive
        assert not sb.state_path.exists()
        archived = list(sb.archive_dir.glob("interview-*.yaml"))
        assert len(archived) == 1


def test_profile_write_succeeds_without_state_file_for_manual_edits():
    """If user hand-edits about-me.md via the dashboard, there's no
    in-progress state to archive. profile-write should still succeed."""
    from skills.knowledge.scripts.mcp.tools_voice_profile import _profile_write_sync

    with tempfile.TemporaryDirectory() as td:
        sb = _PathSandbox(Path(td))
        content = "# Edited content\n"
        result = _profile_write_sync(
            content=content,
            mode="manual",
            about_me_path=sb.about_me_path,
            state_path=sb.state_path,
            archive_dir=sb.archive_dir,
        )
        assert result["success"] is True
        assert sb.about_me_path.read_text() == content
        # No state file to archive — archive_dir may or may not exist
```

- [ ] **Step 2: Implement the tool**

Append to `shared-vault/skills/knowledge/scripts/mcp/tools_voice_profile.py`:

```python
def _profile_write_sync(
    *,
    content: str,
    mode: str,
    about_me_path: Path,
    state_path: Path,
    archive_dir: Path,
) -> dict[str, Any]:
    """Write about-me.md and archive any in-progress state file."""
    about_me_path.parent.mkdir(parents=True, exist_ok=True)
    about_me_path.write_text(content, encoding="utf-8")

    archived_to: str | None = None
    if state_path.exists() and mode in ("full", "update"):
        archive_path = archive_state(state_path, archive_dir)
        archived_to = str(archive_path)

    return {
        "success": True,
        "about_me_path": str(about_me_path),
        "mode": mode,
        "archived_to": archived_to,
    }
```

Append inside `register_voice_profile_tools`:

```python
    @mcp.tool(
        name="profile-write",
        annotations=tool_annotations({
            "title": "Voice Profile Write",
            "readOnlyHint": False, "destructiveHint": False,
            "idempotentHint": False, "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def profile_write_tool(content: str, mode: str = "full") -> str:
        """Write vault/profile/about-me.md.

        Args:
          content: full markdown body for about-me.md
          mode: "full" (after /profile interview) | "update" (after /profile update) | "manual" (dashboard edit)
        """
        metrics.track_tool("profile_write", skill="knowledge")
        try:
            state_path, about_me_path, archive_dir = _resolve_paths()
            result = _profile_write_sync(
                content=content,
                mode=mode,
                about_me_path=about_me_path,
                state_path=state_path,
                archive_dir=archive_dir,
            )
            return json.dumps(result, indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})
```

- [ ] **Step 3: Run tests → verify pass**

Run:
```bash
pytest tests/unit/test_voice_profile_mcp.py -v -k "profile_write"
```
Expected: 2 tests pass.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/knowledge/scripts/mcp/tools_voice_profile.py tests/unit/test_voice_profile_mcp.py
git commit -m "$(cat <<'EOF'
feat(knowledge): profile-write MCP tool — atomic about-me.md write + archive

Writes vault/profile/about-me.md. If an in-progress state file
exists AND mode is full/update, moves it to vault/profile/archive/
interview-<YYYY-MM-DD>.yaml. mode="manual" (dashboard edits) does
NOT archive.

Two unit tests: write-after-completion archives state; manual edit
doesn't archive.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: MCP tool `profile-get-age`

**Files:**
- Modify: `shared-vault/skills/knowledge/scripts/mcp/tools_voice_profile.py` (append)
- Modify: `tests/unit/test_voice_profile_mcp.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_voice_profile_mcp.py`:

```python


# ---------------------------------------------------------------------------
# profile_get_age
# ---------------------------------------------------------------------------

def test_profile_get_age_missing_returns_exists_false():
    from skills.knowledge.scripts.mcp.tools_voice_profile import _profile_get_age_sync

    with tempfile.TemporaryDirectory() as td:
        sb = _PathSandbox(Path(td))
        result = _profile_get_age_sync(about_me_path=sb.about_me_path)
        assert result["success"] is True
        assert result["exists"] is False
        assert "age_days" not in result


def test_profile_get_age_returns_zero_for_just_written():
    from skills.knowledge.scripts.mcp.tools_voice_profile import _profile_get_age_sync

    with tempfile.TemporaryDirectory() as td:
        sb = _PathSandbox(Path(td))
        sb.about_me_path.write_text("# x")
        result = _profile_get_age_sync(about_me_path=sb.about_me_path)
        assert result["success"] is True
        assert result["exists"] is True
        assert result["age_days"] == 0
```

- [ ] **Step 2: Implement the tool**

Append to `shared-vault/skills/knowledge/scripts/mcp/tools_voice_profile.py`:

```python
def _profile_get_age_sync(*, about_me_path: Path) -> dict[str, Any]:
    """Lightweight age helper."""
    if not about_me_path.exists():
        return {"success": True, "exists": False}
    age = get_about_me_age_days(about_me_path)
    return {"success": True, "exists": True, "age_days": age}
```

Append inside `register_voice_profile_tools`:

```python
    @mcp.tool(
        name="profile-get-age",
        annotations=tool_annotations({
            "title": "Voice Profile Age",
            "readOnlyHint": True, "destructiveHint": False,
            "idempotentHint": True, "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def profile_get_age_tool() -> str:
        """Days since about-me.md was last modified, or exists=false."""
        metrics.track_tool("profile_get_age", skill="knowledge")
        try:
            _, about_me_path, _ = _resolve_paths()
            return json.dumps(_profile_get_age_sync(about_me_path=about_me_path), indent=2, default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})
```

- [ ] **Step 3: Run tests → verify pass**

Run:
```bash
pytest tests/unit/test_voice_profile_mcp.py -v -k "profile_get_age"
```
Expected: 2 tests pass.

- [ ] **Step 4: Wire up `register_voice_profile_tools` from the knowledge skill's MCP entry point**

Find the existing knowledge MCP registration:
```bash
grep -rln "register_.*_tools\b" shared-vault/skills/knowledge --include="*.py" | head -3
```

Find where `tools_memory_core` is registered. Add the new module alongside it. The exact wiring depends on the skill's structure — typically a `__init__.py` or registration loop. If a clear single registration point exists, append:

```python
from skills.knowledge.scripts.mcp.tools_voice_profile import register_voice_profile_tools
# ...
register_voice_profile_tools(mcp, tool_annotations, mcp_tool_interceptor, metrics)
```

If the skill auto-discovers MCP tool modules under `scripts/mcp/`, the new file is picked up automatically — verify by running `aug --list-tools | grep profile-`.

- [ ] **Step 5: Verify registration works end-to-end**

Run:
```bash
aug --list-tools 2>&1 | grep -i "profile-" | head -10
```
Expected: see `profile-status`, `profile-read`, `profile-write`, `profile-get-age` listed.

- [ ] **Step 6: Run the full MCP test suite for this feature**

Run:
```bash
pytest tests/unit/test_voice_profile_mcp.py -v
```
Expected: ~9 tests pass.

- [ ] **Step 7: Commit**

```bash
git add shared-vault/skills/knowledge/scripts/mcp/tools_voice_profile.py tests/unit/test_voice_profile_mcp.py shared-vault/skills/knowledge
git commit -m "$(cat <<'EOF'
feat(knowledge): profile-get-age MCP tool + register all 4 voice-profile tools

Final of 4 voice-profile MCP tools. Lightweight "days since
about-me.md last modified" helper for the dashboard age banner.

Also wires register_voice_profile_tools() into the knowledge skill's
MCP entry point so the 4 new tools (profile-status, profile-read,
profile-write, profile-get-age) are discoverable from the CLI and
dashboard.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `capability_exposure.yaml` — register the 4 new tools

**Files:**
- Modify: `config/system/capability_exposure.yaml`

- [ ] **Step 1: Verify the file's existing structure**

Run:
```bash
grep -n "mcp-tool:memory-profile-regenerate" config/system/capability_exposure.yaml
```

- [ ] **Step 2: Add 4 new entries**

Use Edit to insert above the existing `mcp-tool:memory-profile-regenerate` entry:

```yaml
  mcp-tool:profile-status:
    type: mcp-tool
    owner_kind: skill
    skill: knowledge
    management: read-only
    scope: vault
    primary_surface: mcp via dashboard
    preferred_client: dashboard
    export_to: [mcp]
    description: "Status of the voice-profile interview (progress count + about-me.md metadata) for the Browse profile card and /brain/profile page."
  mcp-tool:profile-read:
    type: mcp-tool
    owner_kind: skill
    skill: knowledge
    management: read-only
    scope: vault
    primary_surface: mcp via dashboard
    preferred_client: dashboard
    export_to: [mcp]
    description: "Read about-me.md content + metadata, or return profile_not_found pointing at /profile interview."
  mcp-tool:profile-write:
    type: mcp-tool
    owner_kind: skill
    skill: knowledge
    management: read-write
    scope: vault
    primary_surface: cli via shell
    preferred_client: cli
    export_to: [mcp]
    description: "Write vault/profile/about-me.md (and archive in-progress interview state). Called by the agent at the end of /profile interview or /profile update."
  mcp-tool:profile-get-age:
    type: mcp-tool
    owner_kind: skill
    skill: knowledge
    management: read-only
    scope: vault
    primary_surface: mcp via dashboard
    preferred_client: dashboard
    export_to: [mcp]
    description: "Days since vault/profile/about-me.md last modified — drives the dashboard's 'last updated' badge and the 6-month amber banner."
```

- [ ] **Step 3: Verify YAML parses**

Run:
```bash
python3 -c "
import yaml
with open('config/system/capability_exposure.yaml') as f:
    data = yaml.safe_load(f)
caps = data.get('capabilities', data)
for k in ['mcp-tool:profile-status', 'mcp-tool:profile-read', 'mcp-tool:profile-write', 'mcp-tool:profile-get-age']:
    assert k in caps, f'{k} missing'
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add config/system/capability_exposure.yaml
git commit -m "$(cat <<'EOF'
chore(config): register 4 voice-profile MCP tools in capability_exposure

profile-status, profile-read, profile-get-age: read-only,
primary_surface=mcp via dashboard (the dashboard is the canonical
caller).

profile-write: read-write, primary_surface=cli via shell (the agent
calls it from inside an AI-client session).

All four export_to: [mcp] so they ship via the MCP transport.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `/profile` slash command (3 actions)

**Files:**
- Create: `shared-vault/skills/knowledge/commands/profile.md`

This is the most user-facing artifact: the slash command body that the AI-client agent reads when the user types `/profile`. It must embed:
- Almaya Prompt 1 (interview) verbatim
- Almaya Prompt 2 (compression) verbatim
- Per-answer auto-save instructions
- Resume logic
- Delta-question template (for `/profile update`)

The Almaya prompts live at `vault/prompts/voice-profile-almaya.md` — the slash command copies the verbatim text.

- [ ] **Step 1: Read the source prompt verbatim**

Run:
```bash
cat ~/Projects/Au-vault/prompts/voice-profile-almaya.md | head -200
```
Note: copy Prompt 1 + Prompt 2 sections — they will be embedded into the slash-command body.

- [ ] **Step 2: Create the slash command**

Write to `shared-vault/skills/knowledge/commands/profile.md`:

```markdown
---
id: profile
label: Profile
description: "Voice-profile lifecycle: 100-question interview (interview), delta re-interview (update), inline view (view)."
x-augur-export-command: true
visibility: core
---

# /profile

Voice-profile lifecycle command. Three actions:

  /profile interview   Conduct the Almaya 100-question voice-profile interview inline.
                       Auto-saves after every answer. Pause/resume across sessions.
  /profile update      Re-interview with 10-20 delta questions (after an existing profile).
  /profile view        Print current about-me.md to chat.

## Argument resolution

Parse the action token after `/profile`. If absent, show usage.

| Action       | Behavior                                                                 |
|--------------|---------------------------------------------------------------------------|
| `interview`  | Full 100-question interview → compress → write vault/profile/about-me.md  |
| `update`     | 10-20 delta questions → re-compress with existing about-me.md → overwrite |
| `view`       | Print vault/profile/about-me.md content to chat                          |

Unknown action → print usage, do not silently default.

---

## /profile interview

Conduct the 100-question voice-profile interview inline in this AI-client session. Auto-saves after every answer. Resumable across sessions.

### State management (MANDATORY behavior)

1. **State check on entry** — call `vault-read` on `vault/profile/interview-in-progress.yaml`.
   - **If absent**: create fresh state via `vault-write` with this content:

     ```yaml
     version: 1
     total: 100
     answered: 0
     started_at: <ISO-8601 UTC now>
     last_answered_at: <ISO-8601 UTC now>
     mode: full
     qa_pairs: []
     ```

   - **If present and `answered < total`**: load all `qa_pairs` into your context as conversation memory; resume at question `answered + 1`. Greet the user: "Welcome back. You've answered {answered} of {total}. Continuing with question {answered + 1}."

   - **If present and `answered == total`**: the interview was completed but `about-me.md` was never written. Prompt the user: "Interview complete (100 of 100). Compress now into about-me.md?" If yes → run compression (step 5 below). If no → exit.

2. **Conduct the interview** following the Almaya 8-category structure with quotas (totaling 100):
   - BELIEFS & UNCONVENTIONAL VIEWS (15)
   - WRITING PRACTICES (20)
   - AESTHETIC OFFENSES (15)
   - PERSONALITY & UNIQUENESS (15)
   - INTELLECTUAL HABITS (10)
   - SELF-PERCEPTION & GROWTH (10)
   - VALUES & WORK STYLE (10)
   - ANTI-PATTERNS YOU'D NEVER WRITE (5)

3. **Per-question loop**:
   a. Generate the next question in the Almaya interviewer voice (see Embedded Prompt 1 below for the persona).
   b. Ask the user, wait for their answer.
   c. **CONTRACT — auto-save**: call `vault-write` on `vault/profile/interview-in-progress.yaml` with the appended qa_pair:
      ```yaml
      # bumped `answered`, updated `last_answered_at`, appended:
      qa_pairs:
        - n: <next number>
          category: <one of the 8 categories above>
          q: <verbatim question you asked>
          a: <verbatim user answer>
          asked_at: <ISO-8601 UTC>
      ```
   d. Confirm to the user: "✓ Saved. {answered + 1} of {total} done."
   e. If user types `/exit` or stops responding → exit gracefully (state is already saved).
   f. Continue to next question.

4. **Voice-to-text**: recommend the user use Wispr Flow or macOS dictation for faster answering (cuts 2h → ~90min). Don't integrate any TTS/STT — user picks their own tool.

5. **After question 100**:
   a. Transition into compression (Embedded Prompt 2 below).
   b. Read all 100 qa_pairs from state.
   c. Generate the compressed `about-me.md` body using Prompt 2.
   d. Call `profile-write(content=<markdown>, mode="full")` MCP tool. This writes about-me.md and archives the in-progress state file.
   e. Notify the user: "Voice profile saved at vault/profile/about-me.md. View it at http://localhost:3000/brain/profile."

### Embedded Prompt 1 — Interviewer voice

```text
You are an unyielding interviewer tasked with uncovering the essence of my thoughts, writing style, and worldview.

Your job is to compile an exhaustive dossier that embodies my distinctive voice so accurately that another instance of Claude could replicate my thoughts and writing perfectly.

<interview_philosophy>
You're not here to play nice. You're here to uncover the truth. Many individuals struggle to express their own preferences — they often provide ambiguous, socially approved responses. Your role is to penetrate that surface.
</interview_philosophy>

<interview_structure>
Conduct a comprehensive total of 100 questions distributed among the 8 categories (BELIEFS, WRITING, AESTHETIC, PERSONALITY, INTELLECTUAL HABITS, SELF-PERCEPTION, VALUES, ANTI-PATTERNS).

Ask ONE question at a time. Wait for the user's answer. Then ask the next. Probe deeper when something interesting surfaces.
</interview_structure>

(Verbatim from vault/prompts/voice-profile-almaya.md — full Almaya Prompt 1 here; copy from that file.)
```

### Embedded Prompt 2 — Compression

```text
Now compress the 100 Q&A pairs into a high-fidelity voice profile that another instance of Claude could load to replicate my thoughts and writing perfectly.

Output a single markdown document with this structure:

  # Voice Profile — <user name from context>
  
  ## Beliefs
  ## Writing
  ## Aesthetics
  ## Personality
  ## Intellectual habits
  ## Self-perception
  ## Values
  ## Anti-patterns
  
Each section: 2-4 paragraphs synthesizing the answers from that category. Quote the user's exact phrasing where it's distinctive. Don't summarize — preserve voice.

(Verbatim from vault/prompts/voice-profile-almaya.md — full Almaya Prompt 2 here; copy from that file.)
```

### Failure modes

- **vault-write fails** while saving an answer → report the error; do NOT proceed with the next question (answers must persist).
- **profile-write fails** during compression → keep the in-progress state; report the error so the user can retry.
- **Malformed YAML in interview-in-progress.yaml** → report the path and the parse error; do not overwrite. User can fix or delete the file.

---

## /profile update

Delta-question re-interview for an existing profile. 10-20 questions targeting "what's changed since last interview," re-compresses with the existing about-me.md.

### Precondition check

Call `profile-status`. If `about_me.exists == false`, abort with: "No existing voice profile found. Run `/profile interview` for the full interview."

### State management

Create a fresh `vault/profile/interview-in-progress.yaml` with `mode: update`, `total: 15` (or whatever the delta-question count is for this run). Same auto-save loop as `/profile interview`, just with fewer questions.

### Delta-question template (15 questions)

```text
You're conducting a 15-question delta interview to update an existing voice profile. The previous profile is loaded below. Ask 15 questions focused on what may have shifted in the user's beliefs, writing, aesthetics, or values in the past few months.

Categories (3 questions each):
  - BELIEFS — new convictions; abandoned positions
  - WRITING — new habits; styles that now grate
  - AESTHETICS — fresh offenses; new appreciations
  - PERSONALITY — emerging patterns; new contexts
  - VALUES — shifts in priorities; new work patterns

Same Almaya interviewer voice. Same auto-save contract. After 15 questions, compress using existing about-me.md + new answers, overwriting about-me.md.
```

### After question 15

a. Call `profile-read` to load the existing about-me.md.
b. Run the merge-compression prompt: existing profile + new delta answers → updated about-me.md.
c. Call `profile-write(content=<updated>, mode="update")` — archives the delta state file.
d. Notify the user with a brief summary of what changed.

---

## /profile view

Print the current voice profile to chat for inline reference.

1. Call `profile-read`.
2. If `success: true` → print `result.content` (the markdown) to chat with appropriate formatting.
3. If `error: "profile_not_found"` → print the hint: "No voice profile yet. Run `/profile interview` to create one."

Convenience command — most users view the profile in `/brain/profile` instead.

---

## See also

- Source prompt: `vault/prompts/voice-profile-almaya.md` (Roey Parel, Almaya)
- Dashboard surface: `/brain/profile` — Voice Profile section
- ADR-729 (this command's spec): `docs/superpowers/specs/2026-05-11-voice-profile-personalization-design.md`
```

- [ ] **Step 3: Verify the command surfaces correctly**

Run sync_agents to regenerate command surfaces:
```bash
cd shared-vault && python3 -m skills.ai.scripts.sync_agents sync commands all 2>&1 | tail -5 && cd ..
```
Expected: command discovered, surfaces regenerated.

- [ ] **Step 4: Manual smoke (optional, recommended)**

In Claude Code, run `/profile interview`. The agent reads the command body, asks the user to confirm starting, then asks the first question. Verify the auto-save loop persists after each answer.

(This is a manual check — the engineer skips this step in pure automation but should at least eyeball the rendered command in Claude before committing.)

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/knowledge/commands/profile.md
git commit -m "$(cat <<'EOF'
feat(knowledge): /profile slash command with 3 actions

interview, update, view — the user-facing surface for the voice-
profile journey.

/profile interview embeds Almaya Prompt 1 (interviewer voice) +
Prompt 2 (compression) verbatim. The agent-step contract
explicitly mandates auto-save via vault-write after every answer
so pause/resume works across sessions. Resume flow loads prior
qa_pairs into agent context.

/profile update runs a 15-question delta interview against an
existing about-me.md, then re-compresses with existing + delta
answers.

/profile view prints about-me.md to chat for inline reference.

Failure modes documented: vault-write failure, profile-write
failure, malformed YAML. No skeleton fallback — fail loud.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `useVoiceProfile` dashboard hook

**Files:**
- Create: `apps/dashboard/features/pages/brain/profile/hooks/useVoiceProfile.ts`

- [ ] **Step 1: Create the hook**

Write to `apps/dashboard/features/pages/brain/profile/hooks/useVoiceProfile.ts`:

```typescript
"use client";

import { useEffect, useState } from "react";
import { useMcpQuery, useMcpMutation } from "@/hooks/useMcpQuery";

export interface VoiceProfileStatus {
  success: true;
  in_progress: boolean;
  answered: number;
  total: number;
  percentage: number;
  started_at: string | null;
  last_answered_at: string | null;
  complete: boolean;
  about_me: {
    exists: boolean;
    last_updated_at: string | null;
    age_days: number | null;
  };
}

export interface VoiceProfileReadResult {
  success: boolean;
  content?: string;
  metadata?: {
    last_updated_at: string;
    age_days: number;
    size_bytes: number;
  };
  error?: string;
  hint?: string;
}

/**
 * Polls profile-status every 30s while the page is open.
 * Returns the unified status payload.
 */
export function useVoiceProfile() {
  const statusQuery = useMcpQuery<VoiceProfileStatus>(
    "voice-profile-status",
    "profile-status",
    "live",         // preset = poll-friendly stale/refetch behavior
    { refetchInterval: 30000 },
  );

  // Only fetch about-me.md content when status says it exists
  const aboutMeExists = statusQuery.data?.about_me?.exists ?? false;
  const profileReadQuery = useMcpQuery<VoiceProfileReadResult>(
    "voice-profile-read",
    "profile-read",
    "user-data",
    { enabled: aboutMeExists },
  );

  return {
    status: statusQuery.data,
    statusLoading: statusQuery.isLoading,
    profile: profileReadQuery.data,
    profileLoading: profileReadQuery.isLoading,
    refetch: () => {
      statusQuery.refetch();
      profileReadQuery.refetch();
    },
  };
}

/**
 * Hook for the manual "Edit" save flow. Writes about-me.md with mode="manual"
 * (does NOT archive any in-progress state).
 */
export function useVoiceProfileSave() {
  const mutation = useMcpMutation<{ success: boolean; about_me_path: string }>("profile-write");
  return {
    save: async (content: string) => {
      return await mutation.mutateAsync({ content, mode: "manual" });
    },
    isSaving: mutation.isPending,
    error: mutation.error,
  };
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run:
```bash
cd apps/dashboard && pnpm exec tsc --noEmit 2>&1 | head -10
```
Expected: no new errors (existing errors are unrelated).

- [ ] **Step 3: Commit**

```bash
cd ~/Projects/Augur
git add apps/dashboard/features/pages/brain/profile/hooks/useVoiceProfile.ts
git commit -m "$(cat <<'EOF'
feat(dashboard): useVoiceProfile + useVoiceProfileSave hooks

useVoiceProfile: polls profile-status every 30s, also fetches
about-me.md content when status.about_me.exists is true (avoids
unnecessary reads while interview is in progress).

useVoiceProfileSave: wraps profile-write with mode="manual" for
the dashboard hand-edit flow.

Both use the existing useMcpQuery/useMcpMutation primitives — no
new transport layer.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `VoiceProfile` React component

**Files:**
- Create: `apps/dashboard/features/pages/brain/profile/components/VoiceProfile.tsx`
- Create: `apps/dashboard/features/pages/brain/profile/components/__tests__/VoiceProfile.test.tsx`

- [ ] **Step 1: Write the failing tests first**

Write to `apps/dashboard/features/pages/brain/profile/components/__tests__/VoiceProfile.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { VoiceProfile } from "../VoiceProfile";

const baseStatus = {
  success: true as const,
  in_progress: false,
  answered: 0,
  total: 100,
  percentage: 0,
  started_at: null,
  last_answered_at: null,
  complete: false,
  about_me: { exists: false, last_updated_at: null, age_days: null },
};

describe("VoiceProfile", () => {
  it("renders not-started state when no interview and no about-me.md", () => {
    render(<VoiceProfile status={baseStatus} profile={undefined} />);
    expect(screen.getByText(/voice profile captures/i)).toBeInTheDocument();
    expect(screen.getByText(/run \/profile interview/i)).toBeInTheDocument();
  });

  it("renders in-progress state with progress bar and count", () => {
    const status = {
      ...baseStatus,
      in_progress: true,
      answered: 23,
      percentage: 23,
      started_at: "2026-05-11T14:00:00Z",
      last_answered_at: "2026-05-11T14:42:00Z",
    };
    render(<VoiceProfile status={status} profile={undefined} />);
    expect(screen.getByText(/23 of 100 questions answered/i)).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "23");
  });

  it("renders complete state with markdown content", () => {
    const status = {
      ...baseStatus,
      complete: true,
      about_me: { exists: true, last_updated_at: "2026-05-09T12:00:00Z", age_days: 2 },
    };
    const profile = {
      success: true,
      content: "# Voice Profile\n\n## Beliefs\n\nSample.",
      metadata: { last_updated_at: "2026-05-09T12:00:00Z", age_days: 2, size_bytes: 100 },
    };
    render(<VoiceProfile status={status} profile={profile} />);
    expect(screen.getByText(/voice profile/i)).toBeInTheDocument();
    expect(screen.getByText(/last updated.*2.*ago/i)).toBeInTheDocument();
  });

  it("shows amber banner when profile is older than 180 days", () => {
    const status = {
      ...baseStatus,
      complete: true,
      about_me: { exists: true, last_updated_at: "2025-11-01T00:00:00Z", age_days: 190 },
    };
    const profile = {
      success: true,
      content: "# Voice Profile\n",
      metadata: { last_updated_at: "2025-11-01T00:00:00Z", age_days: 190, size_bytes: 50 },
    };
    render(<VoiceProfile status={status} profile={profile} />);
    expect(screen.getByText(/consider running \/profile update/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement the component**

Write to `apps/dashboard/features/pages/brain/profile/components/VoiceProfile.tsx`:

```tsx
"use client";

import { useState } from "react";
import { User } from "lucide-react";
import { Markdown } from "@/components/ui/Markdown";  // existing project component for markdown rendering
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/GlassCard";
import { Badge } from "@/components/ui/badge";
import { formatRelativeTime } from "@/lib/browse/routine-format";  // from ADR-728

interface VoiceProfileStatus {
  success: true;
  in_progress: boolean;
  answered: number;
  total: number;
  percentage: number;
  started_at: string | null;
  last_answered_at: string | null;
  complete: boolean;
  about_me: {
    exists: boolean;
    last_updated_at: string | null;
    age_days: number | null;
  };
}

interface VoiceProfileReadResult {
  success: boolean;
  content?: string;
  metadata?: { last_updated_at: string; age_days: number; size_bytes: number };
  error?: string;
}

interface Props {
  status: VoiceProfileStatus | undefined;
  profile: VoiceProfileReadResult | undefined;
}

const AMBER_AGE_THRESHOLD_DAYS = 180;

export function VoiceProfile({ status, profile }: Props) {
  if (!status) {
    return <GlassCard className="p-6 animate-pulse h-48" />;
  }

  // ── State A: complete (about-me.md exists) ───────────────────────────────
  if (status.complete && status.about_me.exists && profile?.success && profile.content) {
    const ageDays = profile.metadata?.age_days ?? 0;
    const isStale = ageDays > AMBER_AGE_THRESHOLD_DAYS;
    return (
      <GlassCard className="p-6">
        <header className="flex items-start gap-3 mb-4">
          <div className="rounded-xl border border-purple-500/25 bg-purple-500/10 p-3">
            <User className="h-5 w-5 text-purple-400" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Voice Profile</h2>
            <p className="mt-1 text-sm text-[var(--text-muted)]">
              User-authored. Slow-changing. Who you are.
            </p>
          </div>
        </header>

        {isStale && (
          <div className="mb-4 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
            Profile is {ageDays} days old. Consider running <code>/profile update</code> in your AI client.
          </div>
        )}

        <Markdown>{profile.content}</Markdown>

        <div className="mt-4 text-xs text-[var(--text-muted)] flex items-center justify-between">
          <span>
            Last updated: {formatRelativeTime(profile.metadata?.last_updated_at ?? null)}
          </span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => copyToClipboard("/profile update")}>
              Update (delta)
            </Button>
            <Button size="sm" variant="outline" onClick={() => copyToClipboard("/profile interview")}>
              Re-run full interview
            </Button>
          </div>
        </div>
      </GlassCard>
    );
  }

  // ── State B: in-progress (interview started but not finished) ───────────
  if (status.in_progress && !status.about_me.exists) {
    return (
      <GlassCard className="p-6">
        <header className="flex items-start gap-3 mb-4">
          <div className="rounded-xl border border-purple-500/25 bg-purple-500/10 p-3">
            <User className="h-5 w-5 text-purple-400" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Voice Profile</h2>
            <p className="mt-1 text-sm text-[var(--text-muted)]">Interview in progress.</p>
          </div>
        </header>

        <div className="text-base font-medium mb-2">
          {status.answered} of {status.total} questions answered
        </div>
        <div
          role="progressbar"
          aria-valuenow={status.percentage}
          aria-valuemin={0}
          aria-valuemax={100}
          className="h-2 w-full rounded bg-[var(--bg-elevated)] overflow-hidden mb-4"
        >
          <div
            className="h-full bg-purple-500 transition-all"
            style={{ width: `${status.percentage}%` }}
          />
        </div>

        <div className="text-sm text-[var(--text-muted)] mb-4">
          Started: {formatRelativeTime(status.started_at)} · Last answered:{" "}
          {formatRelativeTime(status.last_answered_at)}
        </div>

        <p className="text-sm mb-3">
          Continue by running <code>/profile interview</code> in your AI client. Your progress saves automatically after every answer.
        </p>

        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => copyToClipboard("/profile interview")}>
            Copy /profile interview
          </Button>
        </div>
      </GlassCard>
    );
  }

  // ── State C: not started (no interview, no about-me.md) ─────────────────
  return (
    <GlassCard className="p-6">
      <header className="flex items-start gap-3 mb-4">
        <div className="rounded-xl border border-purple-500/25 bg-purple-500/10 p-3">
          <User className="h-5 w-5 text-purple-400" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">Voice Profile</h2>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            Your voice profile captures how you think, write, and speak so AI clients can personalize their responses to you.
          </p>
        </div>
      </header>

      <p className="text-sm mb-4">
        Run <code>/profile interview</code> in your AI client to create one. About 90 minutes with voice-to-text; pause and resume anytime.
      </p>

      <Button size="sm" onClick={() => copyToClipboard("/profile interview")}>
        Copy /profile interview to clipboard
      </Button>
    </GlassCard>
  );
}

function copyToClipboard(text: string) {
  if (typeof navigator !== "undefined" && navigator.clipboard) {
    navigator.clipboard.writeText(text);
    // Optional: project's toast system would fire here. Skipped for v1.
  }
}
```

- [ ] **Step 3: Run tests → verify pass**

Run:
```bash
cd apps/dashboard && pnpm test VoiceProfile 2>&1 | tail -15
```
Expected: 4 tests pass.

If the project uses a different test runner command, substitute appropriately. If `@/components/ui/Markdown` doesn't exist, swap to the project's actual markdown component (find via `grep -rln "react-markdown\|<Markdown" apps/dashboard/components`).

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/Augur
git add apps/dashboard/features/pages/brain/profile/components/VoiceProfile.tsx apps/dashboard/features/pages/brain/profile/components/__tests__/VoiceProfile.test.tsx
git commit -m "$(cat <<'EOF'
feat(dashboard): <VoiceProfile> component with 3 visual states

Per spec §7.2:
  A. complete (about-me.md exists) — renders markdown + "last updated"
     + Update / Re-run buttons. Amber banner if age_days > 180.
  B. in-progress (interview started, no about-me.md yet) — progress bar
     "23 of 100 answered" + started/last-answered timestamps + "Copy
     /profile interview" button.
  C. not-started (no in-progress, no about-me.md) — onboarding copy +
     "Copy /profile interview" button.

Reuses formatRelativeTime from ADR-728's routine-format.ts.

Four Vitest tests covering all three states + the amber-banner branch.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Wire `<VoiceProfile>` into `/brain/profile` page

**Files:**
- Modify: `apps/dashboard/features/pages/brain/profile/page.tsx`

- [ ] **Step 1: Read the current page to identify the insertion point**

Run:
```bash
cat apps/dashboard/features/pages/brain/profile/page.tsx
```

- [ ] **Step 2: Add `<VoiceProfile>` above `<HumanApiProfile>`**

Use Edit on `apps/dashboard/features/pages/brain/profile/page.tsx`. Find the top imports block and add:

```typescript
import { VoiceProfile } from './components/VoiceProfile';
import { useVoiceProfile } from './hooks/useVoiceProfile';
```

Find the existing `export default function MemoryProfilePage()` function. Inside it, before the `return` statement, add the hook call:

```typescript
  const voiceProfile = useVoiceProfile();
```

Find the existing `<DeferredSection fallback={<SectionSkeleton />}>` block that wraps `<HumanApiProfile>`. Add a sibling `<DeferredSection>` ABOVE it that wraps `<VoiceProfile>`:

```tsx
      <DeferredSection fallback={<SectionSkeleton />}>
        <VoiceProfile status={voiceProfile.status} profile={voiceProfile.profile} />
      </DeferredSection>

      <DeferredSection fallback={<SectionSkeleton />}>
        <HumanApiProfile
          {...}
        />
      </DeferredSection>
```

(Reuse `<DeferredSection>` and `<SectionSkeleton>` exactly as they are — they're already imported.)

Also update the page title since now there are two profiles:

Find:
```tsx
<h2 className="text-2xl font-bold text-[var(--text-primary)]">Memory Profile</h2>
```

The PAGE-level header (not the VoiceProfile/HumanApiProfile internal headers). Change the page-level h2 if it exists separately — or remove it if both child components have their own headers. Inspect and decide. Most likely keep one page-level h1 "Profile" and let the two child components each have their own h2.

- [ ] **Step 3: Verify TypeScript compiles**

Run:
```bash
cd apps/dashboard && pnpm exec tsc --noEmit 2>&1 | head -10
```
Expected: no new errors.

- [ ] **Step 4: Real-browser verification (rule 28)**

Use `/dev-build` to ensure the dashboard is current, then open `/brain/profile` in a browser. Verify:
1. The Voice Profile section renders ABOVE the Memory Profile section.
2. Without a profile: Voice Profile shows "Run /profile interview" CTA.
3. Manually create `vault/profile/interview-in-progress.yaml` with `answered: 23`; reload → Voice Profile shows progress bar.
4. Manually create `vault/profile/about-me.md` with sample content; reload → Voice Profile shows the rendered markdown.
5. Memory Profile section continues to render unchanged below.

Document the verification result in the commit message.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/Augur
git add apps/dashboard/features/pages/brain/profile/page.tsx
git commit -m "$(cat <<'EOF'
feat(dashboard): /brain/profile shows VoiceProfile above HumanApiProfile

Spec §7.1: extend the existing /brain/profile page with the new
<VoiceProfile> component above the existing <HumanApiProfile>.

Both sections wrapped in <DeferredSection> for loading skeletons.
useVoiceProfile() hook polls profile-status every 30s.

Browser verification (rule 28):
  - Not-started state renders the CTA
  - Manually seeded interview-in-progress.yaml → progress bar shows
  - Manually seeded about-me.md → markdown rendered with metadata
  - Memory Profile section unchanged

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Browse category `profile` (coordinates with ADR-728)

**Files:**
- Modify: `apps/dashboard/lib/browse/types.ts`

- [ ] **Step 1: Locate the BROWSE_CATEGORIES list**

Run:
```bash
grep -n "BROWSE_CATEGORIES" apps/dashboard/lib/browse/types.ts
```

- [ ] **Step 2: Add the `profile` entry**

Use Edit. Find the existing `wiki` entry (or whatever's at the end of the knowledge journey_group). Add `profile` after it:

```typescript
  { id: "wiki", label: "Wiki", singularLabel: "Wiki Page", icon: "NotebookTabs", devOnly: false, group: "content", journey_group: "knowledge", journey_order: 2 },
  // pages = journey_order 3 (added by ADR-723 implementation)
  { id: "profile", label: "Profile", singularLabel: "Voice Profile", icon: "User", devOnly: false, group: "content", journey_group: "knowledge", journey_order: 4, viewLayout: "card" },
```

(Note: this assumes ADR-728's `journey_group` + `journey_order` fields are already on the type. If they're not — i.e., ADR-728 hasn't been implemented yet — this task is a soft dependency. Either: (a) ship this profile entry without the journey fields, then ADR-728 implementation adds them later; or (b) implement ADR-728 first. The plan body assumes ADR-728's fields are present.)

Also extend the `ViewMode` union:

Find:
```typescript
  | "pages"
```

If absent (because ADR-723 hasn't shipped either), add:
```typescript
  | "profile"
```

Otherwise add after `"pages"`:
```typescript
  | "profile"
```

- [ ] **Step 3: Add Browse data source for the profile category**

`apps/dashboard/lib/browse/transforms.ts` — add a case statement so the profile category transforms correctly. Find the existing `wiki` or another knowledge case and add:

```typescript
case "profile":
  // Profile is single-item; click navigates to /brain/profile
  primaryAction = {
    label: "Open Profile",
    type: "navigate",
    target: "/brain/profile",
  };
  break;
```

Repeat for the description, actions, and badge case branches following the pattern of nearby cases.

- [ ] **Step 4: Verify TypeScript compiles**

Run:
```bash
cd apps/dashboard && pnpm exec tsc --noEmit 2>&1 | head -10
```
Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
cd ~/Projects/Augur
git add apps/dashboard/lib/browse/types.ts apps/dashboard/lib/browse/transforms.ts
git commit -m "$(cat <<'EOF'
feat(dashboard): Browse category `profile` in knowledge journey_group

Per spec §9 (coordinates with ADR-728's reservation table):
  journey_group: knowledge
  journey_order: 4   (after notes=1, wiki=2, pages=3)

Click → navigates to /brain/profile.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: ADR-722 milestone 3 — strengthen probe + change action

**Files:**
- Modify: `shared-vault/skills/onboard/config/setup-items.yaml` (if it exists per ADR-722 implementation)

This task is a soft dependency on ADR-722. If ADR-722 hasn't been implemented yet, this task is deferred to ADR-722's implementation (which would absorb the new probe).

- [ ] **Step 1: Check if setup-items.yaml exists**

Run:
```bash
test -f shared-vault/skills/onboard/config/setup-items.yaml && echo EXISTS || echo NOT YET
```

If `NOT YET` → skip this task; document the strengthened probe in the ADR's status notes for ADR-722 to pick up. Move to Task 13.

If `EXISTS` → continue with steps 2-4.

- [ ] **Step 2: Update milestone 3**

Use Edit on `shared-vault/skills/onboard/config/setup-items.yaml`. Find the `human-profile` item:

```yaml
- id: human-profile
  label: Build human profile
  probe: foundation.human_profile
  action: { type: mcp, mcp_tool: "memory-profile-regenerate", label: "Generate profile" }
```

Replace with:

```yaml
- id: human-profile
  label: Build your voice profile
  description: A 100-question interview that captures how you think, write, and speak so AI clients can personalize responses to you.
  probe: foundation.voice_profile     # strengthened: checks vault/profile/about-me.md specifically
  action:
    type: command
    command: "/profile interview"
    label: "Run /profile interview"
```

- [ ] **Step 3: Update the corresponding probe in the onboard skill**

Find the probe implementation:
```bash
grep -rln "foundation.human_profile\|def human_profile" shared-vault/skills/onboard --include="*.py"
```

Update the probe to check for `vault/profile/about-me.md` specifically, with size > 256 bytes:

```python
def voice_profile() -> ProbeResult:
    """Check that vault/profile/about-me.md exists and has substantive content."""
    from src.config.paths import get_vault_dir
    about_me = get_vault_dir() / "profile" / "about-me.md"
    if not about_me.exists():
        return ProbeResult(status="pending", details="No voice profile yet.")
    if about_me.stat().st_size < 256:
        return ProbeResult(status="pending", details="Profile exists but is too short — re-run /profile interview.")
    return ProbeResult(status="done", details=f"Profile present ({about_me.stat().st_size} bytes).")
```

- [ ] **Step 4: Verify the probe by setting up a fixture vault**

```bash
mkdir -p /tmp/test-vault/profile && echo "# voice profile body of more than 256 bytes" > /tmp/test-vault/profile/about-me.md
python3 -c "..." # invoke the probe with vault_dir override
```

(Adapt to the project's actual probe-testing pattern.)

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/onboard/
git commit -m "$(cat <<'EOF'
feat(onboard): ADR-722 milestone 3 — strengthen probe to require about-me.md

Replaces the lenient 'any profile file >256 bytes' probe with a
specific check for vault/profile/about-me.md > 256 bytes.

Changes the action: instead of calling memory-profile-regenerate
(which produces HUMAN_API.md), point the user at /profile interview
(which produces the voice profile via the Almaya flow).

memory-profile-regenerate is unchanged — it still produces HUMAN_API.md
on demand; just no longer the onboarding action for milestone 3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If Task 12 was skipped because setup-items.yaml doesn't exist yet, **add the strengthened probe spec as a coordination note in ADR-722's status_notes** so the ADR-722 implementation picks it up.

---

## Task 13: Final integration verification + push

**Files:** none — verification only.

- [ ] **Step 1: Run all new test files**

Run:
```bash
pytest tests/unit/test_voice_profile_state.py tests/unit/test_voice_profile_mcp.py -v --tb=short
```
Expected: ~25 tests pass.

- [ ] **Step 2: Dashboard TypeScript + Vitest**

```bash
cd apps/dashboard && pnpm exec tsc --noEmit && pnpm test VoiceProfile 2>&1 | tail -5
```
Expected: no TypeScript errors; 4 Vitest tests pass.

- [ ] **Step 3: End-to-end manual smoke**

Outside the test suite, verify:

1. **MCP tool discovery:**
   ```bash
   aug --list-tools 2>&1 | grep "profile-" | head
   ```
   Expected: profile-status, profile-read, profile-write, profile-get-age listed.

2. **`/profile` slash command surface:**
   ```bash
   ls .claude/commands/profile.md
   # OR equivalent — verify the command was generated by sync_agents
   ```
   Expected: file exists with the embedded prompts.

3. **Dashboard browser verification (rule 28):**
   - Visit `http://localhost:3000/brain/profile`
   - Three states visible per the fixture: not-started → in-progress (with manually-seeded yaml) → complete (with manually-seeded about-me.md)
   - Browser console: no errors.

4. **Browse category appears:**
   - Visit `http://localhost:3000/browse?category=profile`
   - Category renders with the appropriate cards / messaging.

- [ ] **Step 4: Push all commits to origin**

```bash
git push origin main 2>&1 | tail -3
```

- [ ] **Step 5: Final summary**

Report:
- N commits across 12 tasks (or N-1 if Task 12 was deferred to ADR-722)
- ~25 pytest tests + 4 Vitest tests passing
- 4 new MCP tools live (`profile-status`, `profile-read`, `profile-write`, `profile-get-age`)
- `/profile` slash command with 3 actions (interview, update, view)
- `<VoiceProfile>` component live at `/brain/profile`
- Browse `profile` category at journey_group=knowledge, journey_order=4
- Coordination with ADR-722, ADR-723, ADR-728 documented

---

## Self-Review

**Spec coverage:**

| Spec section | Implementing task |
|---|---|
| §3 pipeline (4 phases) | Tasks 7 (process), 9-10 (view), 12 (onboarding) |
| §4.1 interview-in-progress.yaml schema | Task 1 (Python dataclass mirrors it) + Task 7 (slash command uses it) |
| §4.2 about-me.md schema | Task 4 (write tool); Task 7 (slash command embeds Prompt 2 that generates it) |
| §4.3 archive | Task 1 (archive_state); Task 4 (profile-write calls it) |
| §5 MCP tools (4 tools) | Tasks 2-5 |
| §5.3 capability_exposure | Task 6 |
| §6 /profile slash command (3 actions) | Task 7 |
| §7.2 VoiceProfile component (3 states) | Task 9 |
| §7.3 Browse category | Task 11 |
| §8 ADR-722 milestone 3 | Task 12 |
| §9 ADR-728 coordination | Task 11 |
| §10 implementation order | Aligned (Tasks 1-12 follow C1-C5 from spec) |

All spec sections covered. No gaps.

**Type consistency:**

- `InterviewState` (Python dataclass) ↔ `VoiceProfileStatus` (TypeScript interface, Task 8) — both have `answered`, `total`, `percentage`, `started_at`, `last_answered_at`
- `profile-status` JSON shape consistent across Tasks 2, 6, 8
- `profile-read` JSON shape consistent across Tasks 3, 8
- `profile-write` arg signature (`content`, `mode`) consistent across Tasks 4, 6, 8

**Placeholder scan:**

No "TBD", no "fill in details". The two prompt-embedding sections in Task 7 explicitly tell the engineer "copy verbatim from `vault/prompts/voice-profile-almaya.md`" — a concrete action, not a placeholder. The action verb is "copy", the source is named.

**Risk areas:**

- **Task 5 step 4** (MCP registration): depends on the knowledge skill's existing MCP registration entry-point convention. The plan provides two paths (explicit register call, or auto-discovery) — the engineer picks based on what they find.
- **Task 7** (slash command body): embeds prompts verbatim from another file. If `vault/prompts/voice-profile-almaya.md` is missing on the implementation machine, the engineer needs to recover it (probably from git history) OR the user has it locally. Task 7 step 1 has a `cat` to verify availability.
- **Task 9** (React component): assumes `@/components/ui/Markdown` exists. If not, fallback path (find via grep) is documented in step 3.
- **Task 11** (Browse types): assumes ADR-728's `journey_group` + `journey_order` fields are present on `BrowseCategory`. If ADR-728 hasn't shipped, fallback: ship without those fields; ADR-728 implementation adds them.
- **Task 12** (ADR-722 milestone): explicitly soft-deferred if setup-items.yaml doesn't exist yet. Plan provides the skip-instruction in step 1.
