# `/ask` Native UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/ask` feel like a native one-turn reflective conversation by hiding retention footers by default while preserving automatic retention and follow-up continuity guidance.

**Architecture:** Keep the existing `/ask` architecture intact: `reflect-context` still builds reflective context, `ask-retain` still persists durable outcomes, and session-end compounding still updates the wiki later. The implementation is a narrow contract change across the `/ask` command doc, the `ask-retain` MCP surface, and targeted tests that lock in silent retention as the new default.

**Tech Stack:** Python 3.11+, pytest, FastMCP registration in `src/mcp/augur_mcp/core`, markdown command contracts in `skills/augur-core`

---

### Task 1: Add Failing Tests For Silent Retention Defaults

**Files:**
- Modify: `~/Projects/Augur/skills/augur-core/augur/tests/test_ask_retention.py`
- Test: `~/Projects/Augur/skills/augur-core/augur/tests/test_ask_retention.py`

- [ ] **Step 1: Write the failing command-contract assertions**

Add these assertions near the top of `test_ask_retention.py`, replacing the existing default-footer expectation:

```python
from pathlib import Path

import pytest

from src.mcp.augur_mcp.core.ask_retention import (
    build_retention_footer,
    classify_ask_outcome,
    retain_ask_outcome_impl,
    route_ask_retention,
)


def test_ask_command_mentions_second_brain_and_silent_retention_default():
    command_path = Path(__file__).resolve().parents[2] / "commands" / "ask.md"
    text = command_path.read_text(encoding="utf-8")
    assert "Ask your second brain" in text
    assert "--retain" in text
    assert "--private" in text
    assert "--no-retain" in text
    assert "ask-retain" in text
    assert "conversation_summary" in text
    assert "Do not append a retention footer by default" in text
    assert "If `ask-retain` returns a footer, append it verbatim" not in text
```

- [ ] **Step 2: Add failing async tests for the new `surface_footer` behavior**

Append these tests to the same file:

```python
@pytest.mark.asyncio
async def test_retain_ask_outcome_hides_footer_by_default(monkeypatch):
    monkeypatch.setattr(
        "skills.knowledge.scripts.mcp.memory.DailyLogger.log_user_preference",
        lambda self, preference, value, source=None: None,
    )

    async def fake_save_synthesis_impl(query: str = "", synthesis: str = "", sources=None, tags=None) -> str:
        return '{"success": true, "path": "/tmp/fake-synthesis.md"}'

    monkeypatch.setattr(
        "src.mcp.augur_mcp.core.ask_retention.save_synthesis_impl",
        fake_save_synthesis_impl,
    )
    monkeypatch.setattr(
        "src.mcp.augur_mcp.core.ask_retention._flag_wiki_update_needed",
        lambda: "/tmp/wiki.flag",
    )

    raw = await retain_ask_outcome_impl(
        question="How do I work best?",
        answer="You work best with long uninterrupted blocks in the morning.",
        explicit_signals=["I prefer deep work before noon"],
        inferred_signals=[],
    )

    payload = __import__("json").loads(raw)
    assert payload["retained"] is True
    assert payload["footer"] is None


@pytest.mark.asyncio
async def test_retain_ask_outcome_surfaces_footer_when_requested(monkeypatch):
    monkeypatch.setattr(
        "skills.knowledge.scripts.mcp.memory.DailyLogger.log_user_preference",
        lambda self, preference, value, source=None: None,
    )

    async def fake_save_synthesis_impl(query: str = "", synthesis: str = "", sources=None, tags=None) -> str:
        return '{"success": true, "path": "/tmp/fake-synthesis.md"}'

    monkeypatch.setattr(
        "src.mcp.augur_mcp.core.ask_retention.save_synthesis_impl",
        fake_save_synthesis_impl,
    )
    monkeypatch.setattr(
        "src.mcp.augur_mcp.core.ask_retention._flag_wiki_update_needed",
        lambda: "/tmp/wiki.flag",
    )

    raw = await retain_ask_outcome_impl(
        question="How do I work best?",
        answer="You work best with long uninterrupted blocks in the morning.",
        explicit_signals=["I prefer deep work before noon"],
        inferred_signals=[],
        surface_footer=True,
    )

    payload = __import__("json").loads(raw)
    assert payload["retained"] is True
    assert payload["footer"] == "retained: preference"
```

- [ ] **Step 3: Run the focused test file to verify it fails for the right reasons**

Run:

```bash
pytest ~/Projects/Augur/skills/augur-core/augur/tests/test_ask_retention.py -q
```

Expected:
- FAIL because `retain_ask_outcome_impl()` does not yet accept `surface_footer`
- FAIL because `ask.md` still describes visible footer behavior as default

- [ ] **Step 4: Leave the test file dirty and move straight into implementation**

Do not commit a knowingly red state. Move directly to Task 2 while the failure is fresh.

### Task 2: Implement Silent Retention In The MCP Surface

**Files:**
- Modify: `~/Projects/Augur/src/mcp/augur_mcp/core/ask_retention.py`
- Modify: `~/Projects/Augur/src/mcp/augur_mcp/core/__init__.py`
- Test: `~/Projects/Augur/skills/augur-core/augur/tests/test_ask_retention.py`

- [ ] **Step 1: Add the new parameter to `retain_ask_outcome_impl()`**

Update the function signature and footer handling in `ask_retention.py` to:

```python
async def retain_ask_outcome_impl(
    *,
    question: str,
    answer: str,
    explicit_signals: Sequence[str] | None = None,
    inferred_signals: Sequence[str] | None = None,
    kinds: Sequence[str] | None = None,
    retain_mode: str = "default",
    sources: Sequence[str] | None = None,
    tags: Sequence[str] | None = None,
    surface_footer: bool = False,
) -> str:
```

And replace:

```python
footer = build_retention_footer(note_kinds)
```

with:

```python
footer = build_retention_footer(note_kinds) if surface_footer else None
```

Keep the rest of the persistence behavior unchanged.

- [ ] **Step 2: Add the MCP parameter to `ask_retain()` registration**

Update `src/mcp/augur_mcp/core/__init__.py` to accept and pass through the parameter:

```python
    async def ask_retain(
        question: str = "",
        answer: str = "",
        explicit_signals: list[str] | None = None,
        inferred_signals: list[str] | None = None,
        kinds: list[str] | None = None,
        retain_mode: str = "default",
        sources: list[str] | None = None,
        tags: list[str] | None = None,
        surface_footer: bool = False,
    ) -> str:
```

And in the call:

```python
        return await retain_ask_outcome_impl(
            question=question,
            answer=answer,
            explicit_signals=explicit_signals,
            inferred_signals=inferred_signals,
            kinds=kinds,
            retain_mode=retain_mode,
            sources=sources,
            tags=tags,
            surface_footer=surface_footer,
        )
```

- [ ] **Step 3: Re-run the focused tests to verify green**

Run:

```bash
pytest ~/Projects/Augur/skills/augur-core/augur/tests/test_ask_retention.py -q
```

Expected:
- PASS for the new async footer-visibility tests
- remaining failure should be the command-contract test until `ask.md` is updated

- [ ] **Step 4: Commit the MCP change**

```bash
git -C ~/Projects/Augur add src/mcp/augur_mcp/core/ask_retention.py src/mcp/augur_mcp/core/__init__.py skills/augur-core/augur/tests/test_ask_retention.py
git -C ~/Projects/Augur commit -m "feat: make ask retention footer optional"
```

### Task 3: Rewrite The `/ask` Contract For Native Conversation

**Files:**
- Modify: `~/Projects/Augur/skills/augur-core/commands/ask.md`
- Test: `~/Projects/Augur/skills/augur-core/augur/tests/test_ask_retention.py`

- [ ] **Step 1: Replace the visible-footer workflow text**

Rewrite the workflow section in `skills/augur-core/commands/ask.md` so the retention behavior is silent by default:

```markdown
## Workflow

1. Parse the question from `$ARGUMENTS`.
   If no arguments are provided, ask what is on the user's mind.
2. If this is a follow-up in the same reflective thread, summarize the prior exchange and pass that summary as `conversation_summary` to `reflect-context`.
3. Read personal context with `reflect-context`.
4. Answer once in a reflective voice.
   - Lead with the answer, not the process.
   - Avoid clarifying questions unless the prompt is too empty to answer responsibly.
   - Do not mention tools, sources, routing, or retention mechanics in the reply.
5. Identify the result as one or more of:
   - `decision`
   - `preference`
   - `insight`
   - `inferred-pattern`
   - `contradiction`
   - `open-question`
   - `ephemeral`
6. If retention is allowed, call `ask-retain` with:
   - the final `question`
   - the final `answer`
   - any `explicit_signals`
   - any `inferred_signals`
   - the active `retain_mode`
   - `surface_footer: false`
   - optional explicit `kinds` when the conversation clearly warrants them
7. Keep retention silent by default.
   - Do not append a retention footer by default.
   - Only surface retention state when the user explicitly asks for it, or when retention fails in a way that affects trust.
8. Session-end compounding later decides whether retained outcomes should strengthen wiki pages.
```

- [ ] **Step 2: Tighten the notes section to reinforce the UX**

Ensure the notes block includes these lines:

```markdown
## Notes

- `/ask` is not `/search`
- `/ask` should feel conversational, not like a logging UI
- follow-up `/ask` turns should continue the same reflective thread when the topic is clearly ongoing
- inferred patterns may be surfaced in the reply when useful, but should not require confirmation every time
- `/ask` does not write wiki pages directly
```

- [ ] **Step 3: Run the same focused test file again**

Run:

```bash
pytest ~/Projects/Augur/skills/augur-core/augur/tests/test_ask_retention.py -q
```

Expected:
- PASS

- [ ] **Step 4: Commit the command-contract change**

```bash
git -C ~/Projects/Augur add skills/augur-core/commands/ask.md skills/augur-core/augur/tests/test_ask_retention.py
git -C ~/Projects/Augur commit -m "docs: redefine ask as native conversation"
```

### Task 4: Verify The Narrow Change Surface

**Files:**
- Modify: none
- Test: `~/Projects/Augur/skills/augur-core/augur/tests/test_ask_retention.py`

- [ ] **Step 1: Search for stale visible-footer contract text**

Run:

```bash
rg -n "If `ask-retain` returns a footer|retained: preference|retained: synthesis" \
  ~/Projects/Augur/skills/augur-core \
  ~/Projects/Augur/src/mcp/augur_mcp/core
```

Expected:
- only the explicit footer-builder code and footer-specific tests should remain
- no `/ask` command-contract text should describe visible footers as the default

- [ ] **Step 2: Run the targeted verification command**

Run:

```bash
pytest ~/Projects/Augur/skills/augur-core/augur/tests/test_ask_retention.py -q
```

Expected:
- PASS

- [ ] **Step 3: Summarize the behavioral delta in the final handoff**

Include this summary in the execution handoff:

```text
Default /ask now answers reflectively, retains silently, and keeps visible retention as an optional surfaced behavior rather than the default UX.
```

- [ ] **Step 4: Stop after verification and prepare the implementation handoff**

Do not create an empty verification commit. The final handoff should reference the passing test command and the behavioral delta from Step 3.
