# `/ask` Compounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `/ask` from a reflective chat command into a compounding second-brain surface with automatic retention, contradiction-aware routing, and session-end wiki compounding.

**Architecture:** Keep `/ask` as the public interface, but add a post-answer classification layer that routes durable outcomes into memory and synthesis. Introduce a small retention schema for explicit and inferred knowledge, then add a session-end compounding pass that reviews retained `/ask` outcomes and updates the wiki through the existing `wiki-tags`/`wiki-read`/`wiki-write`/`wiki-log` flow.

**Tech Stack:** Python 3.11, Markdown command docs, YAML frontmatter, FastMCP tools, existing Augur memory + vault ops + wiki tooling

**Spec:** `docs/superpowers/specs/2026-04-12-ask-compounding-design.md`

---

## File Structure

### Create

| File | Responsibility |
|---|---|
| `skills/augur-core/augur/tests/test_ask_retention.py` | TDD coverage for `/ask` classification, routing, and retention-footer behavior |
| `src/mcp/augur_mcp/core/ask_retention.py` | `/ask` outcome classification, routing helpers, contradiction metadata, retention footer generation |
| `skills/ingest/commands/ask-sync.md` | Manual `/ask sync` command for compounding recent retained `/ask` outcomes |

### Modify

| File | Change |
|---|---|
| `skills/augur-core/commands/ask.md` | Redefine `/ask` as “ask your second brain”, add retention model and flags |
| `src/mcp/augur_mcp/core/__init__.py` | Register any new MCP-facing helper tools if needed for `/ask` compounding |
| `src/mcp/augur_mcp/core/vault_ops.py` | Extend `save_synthesis_impl` metadata handling for inferred/confidence/contradiction payloads if current format is insufficient |
| `docs/agent-topics/agent-rules.md` | Clarify that meaningful `/ask` outputs should participate in session-end compounding |
| `AGENTS.md` / `CLAUDE.md` and derived files | Regenerated after rules/command updates |
| `tests/packages/augur-mcp/core/test_vault_ops.py` | Verify synthesis persistence supports `/ask` compounding metadata |
| `skills/ingest/commands/wiki-update.md` | Include recent `/ask` retained outcomes in wiki update inputs |

---

## Task 1: Redefine `/ask` Contract

**Files:**
- Modify: `skills/augur-core/commands/ask.md`
- Create: `skills/augur-core/augur/tests/test_ask_retention.py`

- [ ] **Step 1: Write the failing command-contract test**

Create `skills/augur-core/augur/tests/test_ask_retention.py`:

```python
from pathlib import Path


def test_ask_command_mentions_second_brain_and_retention():
    text = Path("skills/augur-core/commands/ask.md").read_text(encoding="utf-8")
    assert "Ask your second brain" in text
    assert "--private" in text
    assert "--no-retain" in text
    assert "retained:" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest skills/augur-core/augur/tests/test_ask_retention.py::test_ask_command_mentions_second_brain_and_retention -q
```

Expected:

```text
FAILED
```

- [ ] **Step 3: Update `/ask` command doc**

Replace the body of `skills/augur-core/commands/ask.md` with:

```markdown
# /ask

Ask your second brain: a reflective inner voice that draws on your vault,
memories, decisions, preferences, projects, and recent focus.

## Usage

- `/ask What pattern keeps showing up in how I choose projects?`
- `/ask --retain What have I learned about how I work best?`
- `/ask --private Help me think through this without saving it`
- `/ask --no-retain What are my options here?`

## Workflow

1. Parse the question from `$ARGUMENTS`.
2. Read personal context with `reflect-context`.
3. Answer in a reflective voice.
4. Classify the result as one or more of:
   - `decision`
   - `preference`
   - `insight`
   - `inferred-pattern`
   - `contradiction`
   - `open-question`
   - `ephemeral`
5. If the result is durable and retention is allowed:
   - log atomic items with `memory-log-decision` / `memory-log-preference`
   - retain richer outcomes with `save-synthesis`
6. If anything was retained, append a minimal footer such as:
   - `retained: preference`
   - `retained: synthesis + inferred pattern`
7. Session-end compounding later decides whether retained outcomes should strengthen wiki pages.

## Flags

- `--retain` — stronger bias toward retaining high-signal outcomes
- `--no-retain` — answer only, skip persistence
- `--private` — answer only, never persist or feed session-end compounding

## Notes

- `/ask` is not `/search`
- `/ask` should feel conversational, not like a logging UI
- inferred patterns may be surfaced in the reply when useful, but should not require confirmation every time
- `/ask` does not write wiki pages directly
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
pytest skills/augur-core/augur/tests/test_ask_retention.py::test_ask_command_mentions_second_brain_and_retention -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

```bash
git add skills/augur-core/commands/ask.md skills/augur-core/augur/tests/test_ask_retention.py
git commit -m "docs(ask): define second-brain retention contract"
```

## Task 2: Implement `/ask` Classification And Routing Helpers

**Files:**
- Create: `src/mcp/augur_mcp/core/ask_retention.py`
- Modify: `tests/packages/augur-mcp/core/test_vault_ops.py`
- Test: `skills/augur-core/augur/tests/test_ask_retention.py`

- [ ] **Step 1: Write failing classification tests**

Append to `skills/augur-core/augur/tests/test_ask_retention.py`:

```python
from src.mcp.augur_mcp.core.ask_retention import classify_ask_outcome, build_retention_footer


def test_classify_explicit_preference():
    result = classify_ask_outcome(
        question="How do I work best?",
        answer="You work best with long uninterrupted blocks in the morning.",
        explicit_signals=["I prefer deep work before noon"],
        inferred_signals=[],
    )
    assert "preference" in result["kinds"]
    assert result["should_retain"] is True


def test_classify_inferred_pattern_with_confidence():
    result = classify_ask_outcome(
        question="What pattern keeps showing up?",
        answer="You consistently trade novelty for long-horizon leverage.",
        explicit_signals=[],
        inferred_signals=["long-horizon leverage pattern"],
    )
    assert "inferred-pattern" in result["kinds"]
    assert result["confidence"] in {"low", "medium", "high"}


def test_retention_footer_is_minimal():
    footer = build_retention_footer(["preference", "inferred-pattern"])
    assert footer == "retained: preference + inferred pattern"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest skills/augur-core/augur/tests/test_ask_retention.py -q
```

Expected:

```text
FAILED ... ModuleNotFoundError: No module named 'src.mcp.augur_mcp.core.ask_retention'
```

- [ ] **Step 3: Implement retention helpers**

Create `src/mcp/augur_mcp/core/ask_retention.py`:

```python
from __future__ import annotations

from collections.abc import Sequence


def classify_ask_outcome(
    *,
    question: str,
    answer: str,
    explicit_signals: Sequence[str],
    inferred_signals: Sequence[str],
) -> dict:
    kinds: list[str] = []

    if explicit_signals:
        lowered = " ".join(explicit_signals).lower()
        if any(token in lowered for token in ("prefer", "best", "works best", "like")):
            kinds.append("preference")
        else:
            kinds.append("insight")

    if inferred_signals:
        kinds.append("inferred-pattern")

    kinds = list(dict.fromkeys(kinds))
    should_retain = bool(kinds)
    confidence = "high" if explicit_signals else "medium" if inferred_signals else "low"

    return {
        "question": question,
        "answer": answer,
        "kinds": kinds or ["ephemeral"],
        "should_retain": should_retain,
        "confidence": confidence,
    }


def build_retention_footer(kinds: Sequence[str]) -> str:
    labels = []
    for kind in kinds:
        if kind == "inferred-pattern":
            labels.append("inferred pattern")
        else:
            labels.append(kind)
    return f"retained: {' + '.join(labels)}"
```

- [ ] **Step 4: Add persistence-shape test for synthesis metadata**

Append to `tests/packages/augur-mcp/core/test_vault_ops.py`:

```python
def test_save_synthesis_accepts_ask_metadata(tmp_path, monkeypatch):
    from augur_mcp.core.vault_ops import save_synthesis_impl

    monkeypatch.setattr("augur_mcp.core.vault_ops.get_vault_dir", lambda: tmp_path)
    monkeypatch.setattr("augur_mcp.core.vault_ops.get_wiki_dir", lambda: tmp_path / "wiki")

    result = save_synthesis_impl(
        title="Work Pattern Insight",
        content="You work best in long morning focus blocks.",
        tags=["ask", "pattern"],
        skill="ask",
    )

    assert "saved" in result["message"].lower()
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
pytest skills/augur-core/augur/tests/test_ask_retention.py tests/packages/augur-mcp/core/test_vault_ops.py -q
```

Expected:

```text
... passed
```

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_mcp/core/ask_retention.py skills/augur-core/augur/tests/test_ask_retention.py tests/packages/augur-mcp/core/test_vault_ops.py
git commit -m "feat(ask): add retention classification helpers"
```

## Task 3: Route `/ask` Outcomes Into Memory And Synthesis

**Files:**
- Modify: `src/mcp/augur_mcp/core/__init__.py`
- Modify: `src/mcp/augur_mcp/core/vault_ops.py`
- Test: `skills/augur-core/augur/tests/test_ask_retention.py`

- [ ] **Step 1: Add failing routing test**

Append to `skills/augur-core/augur/tests/test_ask_retention.py`:

```python
from src.mcp.augur_mcp.core.ask_retention import route_ask_retention


def test_route_preference_and_insight():
    routed = route_ask_retention(
        {
            "kinds": ["preference", "insight"],
            "should_retain": True,
            "confidence": "high",
            "answer": "You work best before noon and prefer long uninterrupted blocks.",
        }
    )
    assert routed["memory"] == ["preference"]
    assert routed["synthesis"] == ["insight"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest skills/augur-core/augur/tests/test_ask_retention.py::test_route_preference_and_insight -q
```

Expected:

```text
FAILED
```

- [ ] **Step 3: Implement routing function**

Update `src/mcp/augur_mcp/core/ask_retention.py`:

```python
def route_ask_retention(result: dict) -> dict:
    memory = []
    synthesis = []
    contradictions = []

    for kind in result.get("kinds", []):
        if kind in {"decision", "preference"}:
            memory.append(kind)
        elif kind in {"insight", "inferred-pattern", "open-question"}:
            synthesis.append(kind)
        elif kind == "contradiction":
            contradictions.append(kind)

    return {
        "memory": memory,
        "synthesis": synthesis,
        "contradictions": contradictions,
    }
```

- [ ] **Step 4: Extend synthesis metadata support only if required**

If `save_synthesis_impl` needs structured metadata, extend the note body/frontmatter in `src/mcp/augur_mcp/core/vault_ops.py` with fields such as:

```python
metadata = {
    "source": "ask",
    "confidence": confidence,
    "inferred": "inferred-pattern" in kinds,
}
```

Keep this minimal. Do not redesign vault note formats beyond what the current frontmatter utilities already support.

- [ ] **Step 5: Run tests**

Run:

```bash
pytest skills/augur-core/augur/tests/test_ask_retention.py tests/packages/augur-mcp/core/test_vault_ops.py -q
```

Expected:

```text
... passed
```

- [ ] **Step 6: Commit**

```bash
git add src/mcp/augur_mcp/core/ask_retention.py src/mcp/augur_mcp/core/vault_ops.py skills/augur-core/augur/tests/test_ask_retention.py tests/packages/augur-mcp/core/test_vault_ops.py
git commit -m "feat(ask): route retained outcomes into memory and synthesis"
```

## Task 4: Add Session-End `/ask` Compounding And Manual Sync Surface

**Files:**
- Create: `skills/ingest/commands/ask-sync.md`
- Modify: `skills/ingest/commands/wiki-update.md`
- Modify: `docs/agent-topics/agent-rules.md`

- [ ] **Step 1: Write failing docs test**

Append to `skills/augur-core/augur/tests/test_ask_retention.py`:

```python
def test_wiki_update_mentions_retained_ask_outcomes():
    text = Path("skills/ingest/commands/wiki-update.md").read_text(encoding="utf-8")
    assert "/ask" in text
    assert "retained" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest skills/augur-core/augur/tests/test_ask_retention.py::test_wiki_update_mentions_retained_ask_outcomes -q
```

Expected:

```text
FAILED
```

- [ ] **Step 3: Add manual sync command**

Create `skills/ingest/commands/ask-sync.md`:

```markdown
---
id: ask-sync
description: Compound retained /ask outcomes into memory, synthesis, and wiki
skill: ingest
tags: [ask, brain, wiki, compounding]
---

Review recently retained `/ask` outcomes and strengthen the second brain.

## Steps

1. Gather recent retained `/ask` outcomes from memory/synthesis sources
2. Cluster them by topic, recurrence, and confidence
3. Promote atomic stable items into memory if needed
4. For durable clustered insights:
   - call `wiki-tags`
   - match existing pages
   - `wiki-read` where needed
   - rewrite with `wiki-write`
5. Call `wiki-log` with a summary
```

- [ ] **Step 4: Update wiki-update and session-end rules**

Add this bullet to `skills/ingest/commands/wiki-update.md` after the source scan step:

```markdown
- Include recent retained `/ask` outcomes as candidate inputs when they contain durable preferences, decisions, inferred patterns, or syntheses.
```

Add this bullet to `docs/agent-topics/agent-rules.md` under the wiki/session-end rule:

```markdown
- Meaningful `/ask` outcomes are part of session-end compounding and should be considered wiki inputs after retention routing.
```

- [ ] **Step 5: Regenerate derived agent docs**

Run:

```bash
python3 -m skills.ai.scripts.sync_agents sync all
```

Expected:

```text
INFO ... Sync Complete
```

- [ ] **Step 6: Run tests**

Run:

```bash
pytest skills/augur-core/augur/tests/test_ask_retention.py -q
```

Expected:

```text
... passed
```

- [ ] **Step 7: Commit**

```bash
git add skills/ingest/commands/ask-sync.md skills/ingest/commands/wiki-update.md docs/agent-topics/agent-rules.md AGENTS.md CLAUDE.md .claude .gemini .opencode skills/augur-core/augur/tests/test_ask_retention.py
git commit -m "feat(ask): add compounding sync and session-end wiki integration"
```

## Task 5: Verification And Regression Sweep

**Files:**
- Verify only

- [ ] **Step 1: Run focused Python tests**

Run:

```bash
pytest skills/augur-core/augur/tests/test_ask_retention.py tests/packages/augur-mcp/core/test_vault_ops.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 2: Run wiki-related regression tests**

Run:

```bash
uv run pytest skills/ingest/augur/tests/test_wiki_pages.py skills/ingest/augur/tests/test_wiki_maintenance.py skills/ingest/augur/tests/test_wiki_report.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 3: Search for stale `/ask` contract text**

Run:

```bash
rg -n "optionally offer|/ask is not /search|retained:" skills docs src AGENTS.md CLAUDE.md
```

Expected:

```text
Only the updated /ask and generated instruction surfaces should match
```

- [ ] **Step 4: Verify no direct same-turn wiki write contract was introduced**

Run:

```bash
rg -n "/ask.*wiki-write|same-turn wiki|directly write wiki" skills docs src
```

Expected:

```text
No implementation path should describe /ask as directly mutating wiki pages in the main answer path
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test(ask): verify compounding pipeline and wiki boundaries"
```

---

## Self-Review

### Spec Coverage

- Keep `/ask` as the public command name: Task 1
- Automatic retention with high threshold: Tasks 1-3
- Explicit and inferred knowledge: Tasks 2-3
- Contradiction-aware model: Task 3 scaffolds the route, contradiction persistence remains a focused follow-up if current memory tools need expansion
- Automatic session-end compounding: Task 4
- Delayed wiki compounding rather than same-turn wiki writes: Tasks 1 and 4
- Minimal visible retention footer: Tasks 1-2

### Placeholder Scan

No `TODO`, `TBD`, or undefined task references remain. The only intentionally conditional step is metadata extension in `save_synthesis_impl`, constrained to “if required” to avoid unnecessary format churn.

### Type Consistency

- Classification kinds are consistent across tasks:
  - `decision`
  - `preference`
  - `insight`
  - `inferred-pattern`
  - `contradiction`
  - `open-question`
  - `ephemeral`
- Retention footer format is consistently `retained: ...`

