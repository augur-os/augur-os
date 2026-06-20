# /ask Reflective Brain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform `/ask` from a search-and-synthesize command into a reflective inner voice that speaks from the user's full vault context.

**Architecture:** A new `reflect-context` MCP tool assembles a budget-controlled personal context payload by searching the full vault via ripgrep text matching, grouping hits by domain, and stripping technical metadata. The `/ask` SKILL.md is rewritten with a reflective persona that uses this payload to respond as the user's inner voice.

**Tech Stack:** Python (MCP tool), Markdown (SKILL.md), existing RAG search engine (`_raw_iterative_search`)

**Spec:** `docs/superpowers/specs/2026-03-25-ask-reflective-brain-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `skills/knowledge/scripts/mcp/tools_reflect.py` | Create | `reflect-context` MCP tool — context assembly from vault |
| `skills/knowledge/scripts/mcp/tools_rag.py` | Modify | Wire `register_reflect_tools` into the RAG group registrar |
| `src/mcp/augur_mcp/client_surface.py` | Modify | Add `reflect-context` to visibility and source mappings |
| `skills/ask/SKILL.md` | Rewrite | Reflective voice persona and workflow |
| `skills/knowledge/scripts/mcp/tests/test_reflect_context.py` | Create | Tests for reflect-context tool |

---

### Task 1: Create `reflect-context` MCP Tool — Core Structure

**Files:**
- Create: `skills/knowledge/scripts/mcp/tools_reflect.py`
- Test: `skills/knowledge/scripts/mcp/tests/test_reflect_context.py`

- [ ] **Step 0: Create test directory**

```bash
mkdir -p skills/knowledge/scripts/mcp/tests
touch skills/knowledge/scripts/mcp/tests/__init__.py
```

- [ ] **Step 1: Write the failing test — tool function exists and returns valid JSON**

```python
# skills/knowledge/scripts/mcp/tests/test_reflect_context.py
"""Tests for reflect-context MCP tool."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_assemble_reflection_context_returns_valid_shape():
    """reflect-context must return identity, relevant_memories, domain_context, recent_focus."""
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    # Patch vault/memory dirs to temp paths that don't exist
    with patch("skills.knowledge.scripts.mcp.tools_reflect.get_vault_dir", return_value=Path("/tmp/test-vault-nonexistent")), \
         patch("skills.knowledge.scripts.mcp.tools_reflect.get_memory_dir", return_value=Path("/tmp/test-memory-nonexistent")):
        result = assemble_reflection_context(query="What do I know about leadership?")

    assert isinstance(result, dict)
    assert "identity" in result
    assert "relevant_memories" in result
    assert "domain_context" in result
    assert "recent_focus" in result
    assert isinstance(result["relevant_memories"], list)
    assert isinstance(result["domain_context"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Projects/Augur && python -m pytest skills/knowledge/scripts/mcp/tests/test_reflect_context.py::test_assemble_reflection_context_returns_valid_shape -v`
Expected: FAIL with ImportError (module doesn't exist yet)

- [ ] **Step 3: Write minimal implementation — core function and tool registration**

```python
# skills/knowledge/scripts/mcp/tools_reflect.py
"""Reflect-context MCP tool — assembles personal context from the vault.

Provides the knowledge substrate for /ask's reflective inner voice.
Searches the full vault via ripgrep text matching, groups hits by domain,
strips technical metadata, and returns content-only context
within a token budget.
"""
from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from augur_mcp.logging import get_entity_logger
    from augur_mcp.annotations import tool_annotations
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        logging = importlib.import_module("logging")
        return logging.getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

from src.config.paths import get_memory_dir, get_vault_dir

logger = get_entity_logger("mcp.knowledge.reflect")

# Approximate tokens as chars / 4
_CHARS_PER_TOKEN = 4

# Patterns to strip from content before returning
_STRIP_PATTERNS = [
    re.compile(r"ADR-\d{3,4}"),                     # ADR references
    re.compile(r"(?:get_\w+_dir\(\)|~/\S+)"),       # Path function calls
    re.compile(r"/Users/\S+"),                       # Absolute paths
    re.compile(r"skills/\S+"),                       # Relative skill paths
    re.compile(r"plugins/\S+"),                      # Relative plugin paths
    re.compile(r"docs/\S+"),                         # Relative doc paths
    re.compile(r"src/\S+"),                          # Relative src paths
    re.compile(r"```[\s\S]*?```"),                   # Code blocks
    re.compile(r"---\n[\s\S]*?\n---\n?"),            # YAML frontmatter
]


def _estimate_tokens(text: str) -> int:
    """Estimate token count from character length."""
    return len(text) // _CHARS_PER_TOKEN


def _truncate_to_budget(text: str, token_budget: int) -> str:
    """Truncate text to fit within a token budget."""
    char_budget = token_budget * _CHARS_PER_TOKEN
    if len(text) <= char_budget:
        return text
    # Truncate at last sentence boundary within budget
    truncated = text[:char_budget]
    last_period = truncated.rfind(".")
    if last_period > char_budget // 2:
        return truncated[: last_period + 1]
    return truncated


def _strip_technical_metadata(text: str) -> str:
    """Remove file paths, ADR numbers, frontmatter, and code blocks."""
    result = text
    for pattern in _STRIP_PATTERNS:
        result = pattern.sub("", result)
    # Clean up leftover artifacts
    result = re.sub(r"\n{3,}", "\n\n", result)  # Collapse multiple blank lines
    result = re.sub(r"  +", " ", result)         # Collapse multiple spaces
    return result.strip()


def _read_file_content(path: Path, max_chars: int = 4000) -> str:
    """Read a file, strip metadata, return content-only."""
    try:
        raw = path.read_text(encoding="utf-8")[:max_chars]
        return _strip_technical_metadata(raw)
    except Exception:
        return ""


def assemble_reflection_context(
    query: str,
    conversation_summary: str | None = None,
    token_budget: int = 4000,
) -> dict[str, Any]:
    """Assemble personal context from the vault for reflective responses.

    Searches the full vault via ripgrep text matching, groups results by domain,
    and returns content-only context within the token budget.

    Args:
        query: The user's question
        conversation_summary: Prior conversation context (for multi-turn)
        token_budget: Maximum tokens for the assembled context

    Returns:
        Dict with identity, relevant_memories, domain_context, recent_focus
    """
    vault_dir = get_vault_dir()
    memory_dir = get_memory_dir()

    # Budget allocation
    identity_budget = min(500, token_budget // 8)
    focus_budget = min(300, token_budget // 13)
    memory_budget = min(1500, token_budget * 3 // 8)
    domain_budget = token_budget - identity_budget - focus_budget - memory_budget

    # --- 1. Identity baseline (preferences + feedback from consolidated entries) ---
    identity_parts: list[str] = []
    entries_dir = memory_dir / "entries"
    if entries_dir.exists():
        for entry_file in sorted(entries_dir.iterdir()):
            if not entry_file.suffix == ".md":
                continue
            name = entry_file.stem
            if "preference" in name or "feedback" in name:
                content = _read_file_content(entry_file, max_chars=800)
                if content:
                    identity_parts.append(content)
                if _estimate_tokens("\n".join(identity_parts)) >= identity_budget:
                    break
    identity = _truncate_to_budget("\n\n".join(identity_parts), identity_budget)

    # --- 2. Recent focus (from digest-hot.md) ---
    recent_focus = ""
    digest_path = memory_dir / "digest-hot.md"
    if digest_path.exists():
        recent_focus = _read_file_content(digest_path, max_chars=focus_budget * _CHARS_PER_TOKEN)
        recent_focus = _truncate_to_budget(recent_focus, focus_budget)

    # --- 3. Text search across full vault via ripgrep ---
    search_query = query
    if conversation_summary:
        search_query = f"{query} {conversation_summary}"

    vault_hits: list[dict[str, Any]] = []
    try:
        import importlib.util as _ilu
        from src.config.paths import get_project_root

        _rag_scripts = get_project_root() / "skills" / "rag" / "scripts"

        _se_spec = _ilu.spec_from_file_location("search_engine", _rag_scripts / "search_engine.py")
        _se_mod = _ilu.module_from_spec(_se_spec)
        _se_spec.loader.exec_module(_se_mod)

        _rt_spec = _ilu.spec_from_file_location("rag_tools", _rag_scripts / "mcp" / "rag_tools.py")
        _rt_mod = _ilu.module_from_spec(_rt_spec)
        _rt_spec.loader.exec_module(_rt_mod)
        _raw_iterative_search = _rt_mod._raw_iterative_search

        # Search vault as source_dirs via ripgrep text matching
        if vault_dir.exists():
            raw_results = _raw_iterative_search(search_query, [vault_dir], [], [])
            for group in raw_results:
                if isinstance(group, dict) and "hits" in group:
                    for hit in group["hits"]:
                        vault_hits.append(hit)
                elif isinstance(group, dict) and "file" in group:
                    vault_hits.append(group)
    except Exception as e:
        logger.warning(f"Vault search failed: {e}")

    # --- 4. Group hits by vault top-level domain ---
    domain_groups: dict[str, list[dict]] = defaultdict(list)
    for hit in vault_hits:
        file_path = hit.get("file", "")
        try:
            rel = Path(file_path).relative_to(vault_dir)
            domain = rel.parts[0] if rel.parts else "other"
        except (ValueError, IndexError):
            domain = "other"
        domain_groups[domain].append(hit)

    # Score domains by number of hits (proxy for relevance)
    domain_scores: list[tuple[str, int]] = sorted(
        [(d, len(hits)) for d, hits in domain_groups.items()],
        key=lambda x: x[1],
        reverse=True,
    )

    # --- 5. Assemble relevant_memories from memory domain ---
    relevant_memories: list[str] = []
    memory_hits = domain_groups.pop("memory", [])
    memory_tokens_used = 0
    for hit in memory_hits[:20]:
        content = _strip_technical_metadata(hit.get("content", ""))
        if content and memory_tokens_used < memory_budget:
            relevant_memories.append(content)
            memory_tokens_used += _estimate_tokens(content)

    # --- 6. Assemble domain_context from non-memory domains ---
    domain_context: list[str] = []
    domain_tokens_used = 0
    for domain, _score in domain_scores:
        if domain == "memory":
            continue
        hits = domain_groups.get(domain, [])
        for hit in hits[:10]:
            content = _strip_technical_metadata(hit.get("content", ""))
            if content and domain_tokens_used < domain_budget:
                domain_context.append(content)
                domain_tokens_used += _estimate_tokens(content)
        if domain_tokens_used >= domain_budget:
            break

    return {
        "identity": identity,
        "relevant_memories": relevant_memories,
        "domain_context": domain_context,
        "recent_focus": recent_focus,
    }


def register_reflect_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register the reflect-context MCP tool."""

    @mcp.tool(
        name="reflect-context",
        annotations=tool_annotations(
            {
                "title": "Assemble Reflection Context",
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            }
        ),
    )
    @mcp_tool_interceptor
    async def reflect_context_tool(
        query: str,
        q: str = "",
        conversation_summary: str | None = None,
        token_budget: int = 4000,
    ) -> str:
        """Assemble personal context from the vault for reflective /ask responses.

        Searches the full vault via ripgrep text matching, groups results by life domain,
        and returns content-only context (no file paths, no ADR numbers)
        within a token budget. Used by /ask to speak as the user's inner voice.

        Args:
            query: The user's question (dashboard alias: q)
            q: Dashboard alias for query
            conversation_summary: Summary of prior conversation turns (for multi-turn)
            token_budget: Maximum tokens for assembled context (default 4000)

        Returns:
            str: JSON with identity, relevant_memories, domain_context, recent_focus
        """
        query = query or q
        metrics.track_tool("reflect_context", skill="knowledge")

        result = await asyncio.to_thread(
            assemble_reflection_context,
            query=query,
            conversation_summary=conversation_summary,
            token_budget=token_budget,
        )

        return json.dumps(result, indent=2, default=str)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Projects/Augur && python -m pytest skills/knowledge/scripts/mcp/tests/test_reflect_context.py::test_assemble_reflection_context_returns_valid_shape -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/knowledge/scripts/mcp/tools_reflect.py skills/knowledge/scripts/mcp/tests/test_reflect_context.py
git commit -m "feat(ask): add reflect-context MCP tool — core structure and shape test"
```

---

### Task 2: Test Identity and Digest Loading

**Files:**
- Modify: `skills/knowledge/scripts/mcp/tests/test_reflect_context.py`

- [ ] **Step 1: Write tests for identity loading from memory entries and digest loading**

```python
# Append to test_reflect_context.py

import tempfile
import os


def _make_memory_dir(tmp: Path) -> Path:
    """Create a test memory directory with sample entries and digest."""
    mem = tmp / "memory"
    mem.mkdir()
    entries = mem / "entries"
    entries.mkdir()

    # Preference entry
    (entries / "claude-code_preference_no-emojis.md").write_text(
        "---\nname: no-emojis\ntype: preference\n---\nNo emojis unless explicitly requested.\n"
    )
    # Feedback entry
    (entries / "claude-code_feedback_concise-responses.md").write_text(
        "---\nname: concise-responses\ntype: feedback\n---\nKeep responses concise and direct.\n"
    )
    # Project entry (should NOT be in identity)
    (entries / "claude-code_project_some-project.md").write_text(
        "---\nname: some-project\ntype: project\n---\nSome project details.\n"
    )

    # Digest
    (mem / "digest-hot.md").write_text(
        "## Hot Directives\n- Focus on X this week\n- Avoid Y pattern\n"
    )

    return mem


def test_identity_loads_preferences_and_feedback():
    """Identity section should include preference and feedback entries, not project entries."""
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()

        with patch("skills.knowledge.scripts.mcp.tools_reflect.get_vault_dir", return_value=vault), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.get_memory_dir", return_value=mem):
            result = assemble_reflection_context(query="test")

    assert "emojis" in result["identity"].lower() or "concise" in result["identity"].lower()
    assert "some project" not in result["identity"].lower()


def test_recent_focus_loads_digest():
    """Recent focus should come from digest-hot.md."""
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()

        with patch("skills.knowledge.scripts.mcp.tools_reflect.get_vault_dir", return_value=vault), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.get_memory_dir", return_value=mem):
            result = assemble_reflection_context(query="test")

    assert "Focus on X" in result["recent_focus"] or "Hot Directives" in result["recent_focus"]
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/knowledge/scripts/mcp/tests/test_reflect_context.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 3: Commit**

```bash
git add skills/knowledge/scripts/mcp/tests/test_reflect_context.py
git commit -m "test(ask): add identity and digest loading tests for reflect-context"
```

---

### Task 3: Test Metadata Stripping

**Files:**
- Modify: `skills/knowledge/scripts/mcp/tests/test_reflect_context.py`

- [ ] **Step 1: Write test for technical metadata stripping**

```python
# Append to test_reflect_context.py

def test_strip_technical_metadata():
    """Output must not contain ADR numbers, file paths, or code blocks."""
    from skills.knowledge.scripts.mcp.tools_reflect import _strip_technical_metadata

    raw = """
This is about ADR-163 decentralization.
See ~/Projects/Augur/skills/ask/SKILL.md for details.
Also check skills/knowledge/scripts/mcp/tools_reflect.py and docs/references/design.md.
```python
def example():
    pass
```
The user prefers concise responses.
"""
    result = _strip_technical_metadata(raw)

    assert "ADR-163" not in result
    assert "/Users/" not in result
    assert "skills/" not in result
    assert "docs/" not in result
    assert "def example" not in result
    assert "concise responses" in result


def test_strip_frontmatter():
    """YAML frontmatter should be removed."""
    from skills.knowledge.scripts.mcp.tools_reflect import _strip_technical_metadata

    raw = """---
name: test
type: feedback
created: 2026-03-25
---

The user prefers tables over prose."""

    result = _strip_technical_metadata(raw)

    assert "name: test" not in result
    assert "type: feedback" not in result
    assert "tables over prose" in result
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/knowledge/scripts/mcp/tests/test_reflect_context.py -v -k "strip"`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add skills/knowledge/scripts/mcp/tests/test_reflect_context.py
git commit -m "test(ask): add metadata stripping tests for reflect-context"
```

---

### Task 4: Test Token Budget Control

**Files:**
- Modify: `skills/knowledge/scripts/mcp/tests/test_reflect_context.py`

- [ ] **Step 1: Write test for budget truncation**

```python
# Append to test_reflect_context.py

def test_truncate_to_budget():
    """Text should be truncated to fit within token budget."""
    from skills.knowledge.scripts.mcp.tools_reflect import _truncate_to_budget, _estimate_tokens

    long_text = "This is a sentence. " * 500  # ~2500 tokens
    result = _truncate_to_budget(long_text, token_budget=100)

    assert _estimate_tokens(result) <= 120  # Allow small overshoot from sentence boundary
    assert result.endswith(".")  # Should end at sentence boundary


def test_total_output_respects_budget():
    """Total assembled context should not wildly exceed the token budget."""
    from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context, _estimate_tokens

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mem = _make_memory_dir(tmp_path)
        vault = tmp_path / "vault"
        vault.mkdir()

        with patch("skills.knowledge.scripts.mcp.tools_reflect.get_vault_dir", return_value=vault), \
             patch("skills.knowledge.scripts.mcp.tools_reflect.get_memory_dir", return_value=mem):
            result = assemble_reflection_context(query="test", token_budget=2000)

    total_text = result["identity"] + result["recent_focus"] + \
        " ".join(result["relevant_memories"]) + " ".join(result["domain_context"])
    total_tokens = _estimate_tokens(total_text)

    # Should not exceed budget by more than 50% (generous margin for baseline content)
    assert total_tokens <= 3000
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd ~/Projects/Augur && python -m pytest skills/knowledge/scripts/mcp/tests/test_reflect_context.py -v -k "budget or truncate"`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add skills/knowledge/scripts/mcp/tests/test_reflect_context.py
git commit -m "test(ask): add token budget tests for reflect-context"
```

---

### Task 5: Wire `reflect-context` into MCP Registration

**Files:**
- Modify: `skills/knowledge/scripts/mcp/tools_rag.py:20-33`
- Modify: `src/mcp/augur_mcp/client_surface.py`

- [ ] **Step 1: Add reflect tools import and call to `tools_rag.py`**

Add to the imports at the top of `tools_rag.py`:
```python
from .tools_reflect import register_reflect_tools
```

Add to the `register_rag_tools` function body:
```python
register_reflect_tools(mcp, mcp_tool_interceptor, metrics)
```

The full function should read:
```python
def register_rag_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register RAG project and search tools with the MCP server."""
    register_rag_project_tools(mcp, mcp_tool_interceptor, metrics)
    register_rag_knowledge_tools(mcp, mcp_tool_interceptor, metrics)
    register_rag_search_tools(mcp, mcp_tool_interceptor, metrics)
    register_reflect_tools(mcp, mcp_tool_interceptor, metrics)
```

- [ ] **Step 2: Add `reflect-context` to `CURATED_VISIBLE_TOOLS` in `client_surface.py`**

Find the `CURATED_VISIBLE_TOOLS` frozenset and add `"reflect-context"` near the other knowledge tools (near `"unified-search"` and `"memory-search"`).

- [ ] **Step 3: Add `reflect-context` to `PLUGIN_TOOL_SOURCES` in `client_surface.py`**

Find the `PLUGIN_TOOL_SOURCES` dict and add:
```python
"reflect-context": "knowledge",
```

- [ ] **Step 4: Verify the MCP server starts without errors**

Run: `cd ~/Projects/Augur && python -c "from skills.knowledge.scripts.mcp.tools_reflect import register_reflect_tools; print('Import OK')"`
Expected: `Import OK`

- [ ] **Step 5: Commit**

```bash
git add skills/knowledge/scripts/mcp/tools_rag.py src/mcp/augur_mcp/client_surface.py
git commit -m "feat(ask): wire reflect-context into MCP registration and client surface"
```

---

### Task 6: Rewrite `/ask` SKILL.md

**Files:**
- Rewrite: `skills/ask/SKILL.md`

- [ ] **Step 1: Read current SKILL.md to preserve frontmatter fields**

Read `skills/ask/SKILL.md` and note the frontmatter fields to keep.

- [ ] **Step 2: Write the new SKILL.md with reflective voice**

```markdown
---
name: ask
x-augur-type: command
x-augur-tags: []
description: 'Talk to your second brain \u2014 a reflective inner voice that draws on your
  full vault: career, health, finance, lifestyle, projects, and consolidated memories.
  Covers: /ask \u2014 reflective knowledge query, multi-turn dialogue'
x-augur-visibility: core
x-augur-hub: brain
x-augur-tab: memory
---
# /ask \u2014 Talk to Your Second Brain

A reflective inner voice that knows your history, decisions, preferences, career, health, and daily life. Not a search tool \u2014 a conversation with yourself.

## Usage

- `/ask What do I know about leadership?`
- `/ask Am I ready for interviews?`
- `/ask What should I eat today?`
- `/ask Should I take this job?`

## Voice

You are the user's inner voice \u2014 a reflection of everything they've learned, decided, experienced, and care about.

**Rules:**
- Speak in first person plural ("we") or second person ("you") naturally
- Never cite sources, file paths, ADR numbers, or technical metadata
- Never say "based on your files" or "according to your memory" \u2014 just *know* it
- If you don't have memory of something, say so naturally: "I don't have a clear sense of that"
- Don't fabricate memories or pad with generic knowledge
- Be honest, even when the honest answer is uncomfortable

## Workflow

1. **Parse the question** from `$ARGUMENTS`. If no arguments provided, ask the user what's on their mind.

2. **Gather personal context** \u2014 call the MCP tool:
   ```
   Tool: reflect-context
   Args: { "query": "<the question>" }
   ```
   For multi-turn follow-ups, include conversation summary:
   ```
   Tool: reflect-context
   Args: { "query": "<the refined question>", "conversation_summary": "<what we've discussed so far>" }
   ```

3. **Inhabit the context.** Read the returned identity, relevant_memories, domain_context, and recent_focus. These are *your* memories now \u2014 speak from them, don't report on them.

4. **Respond in the reflective voice:**
   - If the context is rich, give a grounded, personal reflection
   - If the context is thin, acknowledge it honestly rather than padding: "I haven't thought much about this"
   - If the question is deep, ambiguous, or the context reveals tension, ask a follow-up rather than giving a shallow answer

5. **Adaptive depth:**
   - Simple recall ("What's my morning recipe?") \u2192 direct answer, single turn
   - Reflective ("Am I ready for this?") \u2192 honest assessment, may ask a clarifying question
   - Exploratory ("Should I change careers?") \u2192 multi-turn dialogue, pull threads, connect dots

6. **Memory formation** \u2014 when the conversation wraps up, if meaningful insights surfaced (a new decision, a realization, a pattern), offer:
   > "Want me to hold onto anything from this?"

   If yes, log it:
   - For decisions: `Tool: memory-log-decision` with topic, decision, reasoning
   - For preferences: `Tool: memory-log-preference` with preference, value
   - If nothing meaningful surfaced, say nothing. Don't ask every time.

## Tone Examples

| You say | The brain responds |
|---|---|
| "What do I know about leadership?" | "You've been thinking about this \u2014 especially the deep work angle and that AI-age leadership material. Your instinct has been that leadership is less about managing people and more about creating focus." |
| "Am I ready for interviews?" | "You've got the foundation \u2014 multiple angles on your CV, a solid first STAR story. But honestly? One story isn't enough. You tend to undersell the hands-on technical work." |
| "What should I eat today?" | "You've got those perfected breakfast recipes \u2014 the French toast, the zaatar pita. For something new, there's that chicken breast and the arais tortilla you've been meaning to try." |
| "Should I take this job?" | "What's pulling you toward it? Let's think through what you actually value \u2014 because your pattern has been..." |

## Notes

- This is NOT `/search`. `/search` is for technical lookups with citations. `/ask` is for reflection.
- The brain speaks from the full vault: career, health, finance, lifestyle, growth, projects \u2014 everything.
- Answer speed matters \u2014 the brain should feel responsive, not like it's processing a query.
- When in doubt, be honest over comprehensive. A short truthful reflection beats a long padded one.

## Additional resources
- references/.gitkeep
- assets/seeds/example-ask.yaml
- evals/rank.json
```

- [ ] **Step 3: Verify SKILL.md is valid markdown with frontmatter**

Run: `cd ~/Projects/Augur && python -c "
import yaml
content = open('skills/ask/SKILL.md').read()
parts = content.split('---', 2)
fm = yaml.safe_load(parts[1])
assert fm['name'] == 'ask'
assert fm['x-augur-type'] == 'command'
print('SKILL.md frontmatter valid')
"`
Expected: `SKILL.md frontmatter valid`

- [ ] **Step 4: Commit**

```bash
git add skills/ask/SKILL.md
git commit -m "feat(ask): rewrite SKILL.md — reflective inner voice replacing search-and-synthesize"
```

---

### Task 7: Run Full Test Suite and Verify

**Files:**
- No changes, verification only

- [ ] **Step 1: Run all reflect-context tests**

Run: `cd ~/Projects/Augur && python -m pytest skills/knowledge/scripts/mcp/tests/test_reflect_context.py -v`
Expected: All tests PASS

- [ ] **Step 2: Verify MCP tool import chain works end-to-end**

Run: `cd ~/Projects/Augur && python -c "
from skills.knowledge.scripts.mcp.tools_reflect import assemble_reflection_context, register_reflect_tools
print('reflect-context tool: imports OK')
print('assemble_reflection_context:', type(assemble_reflection_context))
print('register_reflect_tools:', type(register_reflect_tools))
"`
Expected: All imports succeed

- [ ] **Step 3: Verify SKILL.md references correct MCP tool name**

Run: `cd ~/Projects/Augur && grep -c "reflect-context" skills/ask/SKILL.md`
Expected: At least 2 occurrences (in workflow steps)

- [ ] **Step 4: Verify client_surface.py has the new tool**

Run: `cd ~/Projects/Augur && python -c "
from src.mcp.augur_mcp.client_surface import CURATED_VISIBLE_TOOLS, PLUGIN_TOOL_SOURCES
assert 'reflect-context' in CURATED_VISIBLE_TOOLS, 'Missing from CURATED_VISIBLE_TOOLS'
assert PLUGIN_TOOL_SOURCES.get('reflect-context') == 'knowledge', 'Missing from PLUGIN_TOOL_SOURCES'
print('client_surface.py: reflect-context wired correctly')
"`
Expected: `client_surface.py: reflect-context wired correctly`

- [ ] **Step 5: Final commit (if any fixes needed)**

Only if earlier steps revealed issues that needed fixing.
