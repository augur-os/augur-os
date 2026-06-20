# Existing Vault Wiki Compounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make existing-vault onboarding feel like a real LLM wiki: wiki `New` bootstraps or repairs the compiled brain, wiki `Update` performs focused hardening, wiki `Reindex` only refreshes search artifacts, and `/ask` prefers compiled wiki context before falling back to raw vault notes.

**Architecture:** Keep Augur's broad RAG/indexing infrastructure, but separate it cleanly from wiki compounding semantics. The backend change is intentionally small but decisive: `wiki-reindex` becomes index-only, `/ask` assembles context from wiki/memory/synthesis before raw vault hits, and the dashboard exposes wiki-specific `New` and `Update` actions that dispatch IDE work instead of pretending reindex is intelligence.

**Tech Stack:** Python 3.11, FastMCP tools, markdown command docs, generated `AGENTS.md`, Next.js/React 19, Jest, pytest

**Spec:** `docs/superpowers/specs/2026-04-13-existing-vault-wiki-compounding-design.md`

---

## File Structure

### Create

| File | Responsibility |
|---|---|
| `skills/ingest/augur/tests/test_wiki_command_contracts.py` | Contract tests for wiki/search/ask docs and agent-rule semantics |
| `apps/dashboard/components/shared/__tests__/BrowseCategoryActions.test.tsx` | Verify wiki `New` in Browse dispatches the right IDE prompt |
| `apps/dashboard/features/pages/brain/knowledge/memory/components/__tests__/WikiMaintenancePanel.test.tsx` | Verify wiki `Update` action is exposed and dispatches focused hardening work |

### Modify

| File | Change |
|---|---|
| `skills/rag/commands/wiki.md` | Redefine `/wiki reindex` as index-only and point wiki content work at `rebuild`/`update` |
| `skills/augur-core/commands/search.md` | Keep `/search reindex --wiki` aligned with index-only wiki semantics |
| `skills/augur-core/commands/ask.md` | Clarify that `/ask` is the strongest second-brain compounding surface without directly writing wiki pages |
| `skills/ingest/commands/wiki-rebuild.md` | Reframe rebuild as bootstrap-or-repair of the compiled wiki |
| `skills/ingest/commands/wiki-update.md` | Reframe update as focused repair/hardening on top of the existing wiki |
| `skills/ingest/commands/wiki-seed.md` | Mark skeleton seeding as internal metadata bootstrap, not the user-facing wiki `New` flow |
| `skills/rag/SKILL.md` | Update wiki command descriptions to match new semantics |
| `skills/ingest/SKILL.md` | Update wiki command/action descriptions and keep wiki-builder usage aligned |
| `skills/ingest/agents/wiki-builder.md` | Align builder workflow language with bootstrap, steady-state compounding, and focused repair |
| `docs/agent-topics/agent-rules.md` | Update global wiki-compounding instructions and regenerate derived agent files |
| `AGENTS.md` | Regenerated from `docs/agent-topics/agent-rules.md` |
| `skills/rag/scripts/mcp/rag_tools.py` | Make `wiki-reindex` and wiki-category reindexing index-only |
| `skills/rag/augur/tests/test_rag_tools.py` | Add regression coverage for index-only wiki reindex behavior |
| `skills/knowledge/scripts/mcp/tools_reflect.py` | Prefer compiled wiki context before raw vault fallback |
| `skills/knowledge/scripts/mcp/tests/test_reflect_context.py` | Cover wiki-first prioritization and raw fallback behavior |
| `apps/dashboard/components/shared/BrowseCategoryActions.tsx` | Add wiki-specific `New` prompt semantics in Browse |
| `apps/dashboard/features/pages/brain/knowledge/memory/components/WikiMaintenancePanel.tsx` | Add an explicit `Update Wiki` action for focused hardening |

---

### Task 1: Re-align Wiki Contracts And Agent Instructions

**Files:**
- Create: `skills/ingest/augur/tests/test_wiki_command_contracts.py`
- Modify: `skills/rag/commands/wiki.md`
- Modify: `skills/augur-core/commands/search.md`
- Modify: `skills/augur-core/commands/ask.md`
- Modify: `skills/ingest/commands/wiki-rebuild.md`
- Modify: `skills/ingest/commands/wiki-update.md`
- Modify: `skills/ingest/commands/wiki-seed.md`
- Modify: `skills/rag/SKILL.md`
- Modify: `skills/ingest/SKILL.md`
- Modify: `skills/ingest/agents/wiki-builder.md`
- Modify: `docs/agent-topics/agent-rules.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Write the failing contract tests**

Create `skills/ingest/augur/tests/test_wiki_command_contracts.py`:

```python
from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").lower()


def test_wiki_reindex_contract_is_index_only():
    wiki_cmd = _read("skills/rag/commands/wiki.md")
    search_cmd = _read("skills/augur-core/commands/search.md")
    rag_skill = _read("skills/rag/SKILL.md")

    assert "refresh the wiki browse/search index" in wiki_cmd
    assert "refresh wiki browse/search artifacts" in search_cmd
    assert "refresh browse/search indexing" in rag_skill
    assert "rebuild wiki skeleton" not in wiki_cmd


def test_wiki_compounding_contracts_match_bootstrap_and_repair_model():
    rebuild_cmd = _read("skills/ingest/commands/wiki-rebuild.md")
    update_cmd = _read("skills/ingest/commands/wiki-update.md")
    seed_cmd = _read("skills/ingest/commands/wiki-seed.md")
    ask_cmd = _read("skills/augur-core/commands/ask.md")
    rules = _read("docs/agent-topics/agent-rules.md")
    builder = _read("skills/ingest/agents/wiki-builder.md")

    assert "bootstrap or repair the compiled wiki" in rebuild_cmd
    assert "focused repair and hardening" in update_cmd
    assert "internal metadata seed" in seed_cmd
    assert "strongest second-brain compounding surface" in ask_cmd
    assert "second-brain interactions may strengthen the wiki" in rules
    assert "bootstrap, steady-state compounding, and focused repair" in builder
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_command_contracts.py -q
```

Expected:

```text
FAILED
```

- [ ] **Step 3: Update the command docs and agent instructions**

Replace the relevant sections with these exact semantics:

`skills/rag/commands/wiki.md`

```markdown
2. Actions available:
   - `status` — return page counts plus current lint state
   - `reindex` — refresh the wiki browse/search index for existing wiki pages only
   - `lint` — detect missing required pages, broken internal wiki links, and orphan pages
5. If the user wants wiki content created, repaired, or hardened, direct them to wiki `New` / `/wiki rebuild` or wiki `Update` / `/wiki update` instead of `reindex`.
```

`skills/augur-core/commands/search.md`

```markdown
2. Actions available:
   - `reindex --wiki`: Refresh wiki browse/search artifacts without rebuilding wiki content
3. Parse the action and call the matching MCP tool:
   - `reindex --wiki` -> `wiki-reindex`
```

`skills/augur-core/commands/ask.md`

```markdown
7. Keep retention silent by default.
8. `/ask` is the strongest second-brain compounding surface: answer first, retain durable outcomes, and let wiki hardening consume that signal later without turning the reply into a wiki-write UI.
```

`skills/ingest/commands/wiki-rebuild.md`

```markdown
description: Bootstrap or repair the compiled wiki from current Augur knowledge sources

Scan all knowledge sources and establish a usable compiled wiki. If the wiki already exists, repair and harden it instead of blindly replacing it.
```

`skills/ingest/commands/wiki-update.md`

```markdown
description: Focused repair and hardening pass over the existing wiki

Review the existing wiki, recent retained `/ask` outcomes, and current source coverage to repair thin pages, strengthen links, and add missing pages where the compiled brain is obviously incomplete.
```

`skills/ingest/commands/wiki-seed.md`

```markdown
description: Internal metadata seed for wiki inventory bootstrap

- This is an internal metadata seed, not the user-facing wiki `New` flow.
- Use wiki `New` / `/wiki rebuild` when the goal is to establish a usable compiled wiki.
```

`skills/rag/SKILL.md`

```markdown
- `/wiki reindex` — refresh browse/search indexing for existing wiki pages
```

`skills/ingest/SKILL.md`

```markdown
| `/wiki seed` | Internal metadata seed for inventory/bootstrap helpers |
| `/wiki update` | Focused wiki repair and hardening from current knowledge |
| `/wiki rebuild` | Bootstrap or repair the compiled wiki from sources |
```

`skills/ingest/agents/wiki-builder.md`

```markdown
## Workflow Model

1. Bootstrap: establish the first usable wiki or repair a broken one
2. Steady-state compounding: strengthen the wiki during second-brain interactions
3. Focused repair: perform explicit hardening when the user asks for deeper wiki work
```

`docs/agent-topics/agent-rules.md`

```markdown
## Wiki Compounding

- Shared long-term knowledge lives in `get_wiki_dir()` (`Au-vault/wiki/`).
- `wiki-reindex` only refreshes wiki browse/search artifacts for existing wiki pages.
- Use wiki `New` / `/wiki rebuild` to bootstrap or repair the compiled wiki.
- Use wiki `Update` / `/wiki update` for focused repair and hardening work.
- Second-brain interactions may strengthen the wiki, and `/ask` is the strongest second-brain compounding surface.
```

Then regenerate derived agent files:

```bash
python3 -m skills.ai.scripts.sync_agents sync all
```

- [ ] **Step 4: Run the tests to verify the contract passes**

Run:

```bash
pytest skills/ingest/augur/tests/test_wiki_command_contracts.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit**

```bash
git add \
  skills/ingest/augur/tests/test_wiki_command_contracts.py \
  skills/rag/commands/wiki.md \
  skills/augur-core/commands/search.md \
  skills/augur-core/commands/ask.md \
  skills/ingest/commands/wiki-rebuild.md \
  skills/ingest/commands/wiki-update.md \
  skills/ingest/commands/wiki-seed.md \
  skills/rag/SKILL.md \
  skills/ingest/SKILL.md \
  skills/ingest/agents/wiki-builder.md \
  docs/agent-topics/agent-rules.md \
  AGENTS.md
git commit -m "docs(wiki): align compounding and reindex semantics"
```

### Task 2: Make `wiki-reindex` Index-Only

**Files:**
- Modify: `skills/rag/scripts/mcp/rag_tools.py`
- Modify: `skills/rag/augur/tests/test_rag_tools.py`

- [ ] **Step 1: Write the failing regression test**

Append to `skills/rag/augur/tests/test_rag_tools.py`:

```python
import asyncio
import json
from pathlib import Path


class _FakeMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, name: str, annotations=None):  # noqa: ANN001
        def decorator(fn):
            self.tools[name] = fn
            return fn
        return decorator


class _FakeMetrics:
    def track_tool(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


def _identity(fn):
    return fn


def test_wiki_reindex_indexes_existing_pages_without_seeding(monkeypatch, tmp_path):
    from skills.rag.scripts.mcp import rag_tools

    wiki_dir = tmp_path / "vault" / "wiki"
    rag_dir = tmp_path / "rag"
    wiki_dir.mkdir(parents=True)
    rag_dir.mkdir(parents=True)
    (wiki_dir / "career").mkdir()
    (wiki_dir / "career" / "overview.md").write_text(
        "---\ntitle: Career Overview\ntype: wiki-page\nhub: career\n---\n# Career Overview\n\nCompiled wiki body.\n",
        encoding="utf-8",
    )

    fake_mcp = _FakeMCP()
    rag_tools.register_tools(fake_mcp, _identity, _FakeMetrics())

    monkeypatch.setattr(rag_tools, "get_wiki_dir", lambda: wiki_dir)
    monkeypatch.setattr(rag_tools, "get_rag_dir", lambda: rag_dir)
    monkeypatch.setattr(
        "skills.ingest.scripts.wiki_maintenance.seed_wiki",
        lambda **_: (_ for _ in ()).throw(AssertionError("seed_wiki should not run")),
    )

    payload = json.loads(asyncio.run(fake_mcp.tools["wiki-reindex"]()))

    assert payload["status"] == "ok"
    assert payload["mode"] == "index-only"
    assert payload["indexed"] == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest skills/rag/augur/tests/test_rag_tools.py -q
```

Expected:

```text
FAILED ... AssertionError: seed_wiki should not run
```

- [ ] **Step 3: Implement index-only wiki reindexing**

Update `skills/rag/scripts/mcp/rag_tools.py`:

```python
elif category == "wiki":
    count = scanner(get_wiki_dir(), rag_dir)
    return json.dumps(
        {
            "status": "ok",
            "category": category,
            "count": count,
            "mode": "index-only",
        }
    )
```

and replace the `wiki_reindex()` tool body with:

```python
@mcp.tool(name="wiki-reindex")
@mcp_tool_interceptor
async def wiki_reindex() -> str:
    """Refresh browse/search artifacts for existing wiki pages."""
    from .._scanners_knowledge import index_wiki

    count = index_wiki(get_wiki_dir(), get_rag_dir())
    return json.dumps(
        {
            "status": "ok",
            "indexed": count,
            "mode": "index-only",
            "wiki_dir": str(get_wiki_dir()),
        }
    )
```

- [ ] **Step 4: Run the tests to verify the tool is fixed**

Run:

```bash
pytest skills/rag/augur/tests/test_rag_tools.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

```bash
git add skills/rag/scripts/mcp/rag_tools.py skills/rag/augur/tests/test_rag_tools.py
git commit -m "feat(rag): make wiki reindex index-only"
```

### Task 3: Make `/ask` Prefer The Compiled Brain

**Files:**
- Modify: `skills/knowledge/scripts/mcp/tools_reflect.py`
- Modify: `skills/knowledge/scripts/mcp/tests/test_reflect_context.py`

- [ ] **Step 1: Write the failing prioritization tests**

Append to `skills/knowledge/scripts/mcp/tests/test_reflect_context.py`:

```python
def test_prioritize_compiled_hits_places_wiki_before_raw_vault():
    from skills.knowledge.scripts.mcp.tools_reflect import _prioritize_compiled_hits

    wiki_dir = Path("/vault/wiki")
    hits = [
        {"file": "/vault/projects/leadership.md", "content": "Raw note"},
        {"file": "/vault/wiki/brain/leadership.md", "content": "Compiled wiki page"},
    ]

    prioritized = _prioritize_compiled_hits(hits, wiki_dir=wiki_dir)

    assert prioritized[0]["content"] == "Compiled wiki page"
    assert prioritized[1]["content"] == "Raw note"


def test_prioritize_compiled_hits_keeps_raw_when_no_wiki_hits():
    from skills.knowledge.scripts.mcp.tools_reflect import _prioritize_compiled_hits

    wiki_dir = Path("/vault/wiki")
    hits = [{"file": "/vault/projects/leadership.md", "content": "Raw note"}]

    prioritized = _prioritize_compiled_hits(hits, wiki_dir=wiki_dir)

    assert prioritized == hits
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
pytest skills/knowledge/scripts/mcp/tests/test_reflect_context.py -q
```

Expected:

```text
FAILED ... cannot import name '_prioritize_compiled_hits'
```

- [ ] **Step 3: Implement wiki-first prioritization in `reflect-context`**

Update `skills/knowledge/scripts/mcp/tools_reflect.py`:

```python
from src.config.paths import get_memory_dir, get_vault_dir, get_wiki_dir


def _flatten_hit_groups(raw_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for group in raw_results:
        if isinstance(group, dict) and "hits" in group:
            hits.extend(hit for hit in group["hits"] if isinstance(hit, dict))
        elif isinstance(group, dict) and "file" in group:
            hits.append(group)
    return hits


def _prioritize_compiled_hits(hits: list[dict[str, Any]], wiki_dir: Path) -> list[dict[str, Any]]:
    compiled: list[dict[str, Any]] = []
    raw: list[dict[str, Any]] = []
    for hit in hits:
        file_path = Path(str(hit.get("file", "")))
        try:
            file_path.relative_to(wiki_dir)
            compiled.append(hit)
        except ValueError:
            raw.append(hit)
    return compiled + raw
```

Then replace the vault-search block with:

```python
        combined_hits: list[dict[str, Any]] = []
        wiki_dir = get_wiki_dir()

        if wiki_dir.exists():
            combined_hits.extend(
                _flatten_hit_groups(_raw_iterative_search(search_query, [wiki_dir], [], []))
            )

        if vault_dir.exists():
            raw_hits = _flatten_hit_groups(_raw_iterative_search(search_query, [vault_dir], [], []))
            raw_hits = [
                hit
                for hit in raw_hits
                if not str(hit.get("file", "")).startswith(str(wiki_dir))
            ]
            combined_hits.extend(raw_hits)

        vault_hits = _prioritize_compiled_hits(combined_hits, wiki_dir=wiki_dir)
```

- [ ] **Step 4: Run the tests to verify compiled-brain prioritization passes**

Run:

```bash
pytest skills/knowledge/scripts/mcp/tests/test_reflect_context.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 5: Commit**

```bash
git add \
  skills/knowledge/scripts/mcp/tools_reflect.py \
  skills/knowledge/scripts/mcp/tests/test_reflect_context.py
git commit -m "feat(ask): prefer compiled wiki context before raw vault"
```

### Task 4: Surface Wiki `New` And `Update` In The Dashboard

**Files:**
- Create: `apps/dashboard/components/shared/__tests__/BrowseCategoryActions.test.tsx`
- Create: `apps/dashboard/features/pages/brain/knowledge/memory/components/__tests__/WikiMaintenancePanel.test.tsx`
- Modify: `apps/dashboard/components/shared/BrowseCategoryActions.tsx`
- Modify: `apps/dashboard/features/pages/brain/knowledge/memory/components/WikiMaintenancePanel.tsx`

- [ ] **Step 1: Write the failing dashboard tests**

Create `apps/dashboard/components/shared/__tests__/BrowseCategoryActions.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowseCategoryActions } from "@/components/shared/BrowseCategoryActions";

const runAction = jest.fn();

jest.mock("@/hooks/useActionRunner", () => ({
  useActionRunner: () => ({ runAction }),
}));

describe("BrowseCategoryActions wiki new flow", () => {
  beforeEach(() => runAction.mockClear());

  it("dispatches wiki bootstrap-or-repair instructions for the wiki category", async () => {
    const user = userEvent.setup();
    render(
      <BrowseCategoryActions
        category="wiki"
        activeCategory={{ id: "wiki", label: "Wiki", singularLabel: "Wiki Page", group: "brain" }}
        itemCount={0}
        onRefetch={() => {}}
      />
    );

    await user.click(screen.getByRole("button", { name: /new wiki page/i }));

    expect(runAction).toHaveBeenCalledWith(
      expect.objectContaining({
        id: "new-wiki",
        dispatch: "ide",
        prompt: expect.stringContaining("If no wiki exists, build it"),
      })
    );
  });
});
```

Create `apps/dashboard/features/pages/brain/knowledge/memory/components/__tests__/WikiMaintenancePanel.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WikiMaintenancePanel } from "../WikiMaintenancePanel";

const runAction = jest.fn();

jest.mock("@/hooks/useActionRunner", () => ({
  useActionRunner: () => ({ runAction, isExecuting: false }),
}));

describe("WikiMaintenancePanel update action", () => {
  beforeEach(() => runAction.mockClear());

  it("dispatches focused wiki hardening work", async () => {
    const user = userEvent.setup();
    render(
      <WikiMaintenancePanel
        summary={null}
        candidates={[]}
        totalCandidates={0}
        isLoading={false}
        error={null}
        onRefresh={() => {}}
      />
    );

    await user.click(screen.getByRole("button", { name: /update wiki/i }));

    expect(runAction).toHaveBeenCalledWith(
      expect.objectContaining({
        dispatch: "ide",
        prompt: expect.stringContaining("focused repair and hardening"),
      })
    );
  });
});
```

- [ ] **Step 2: Run the dashboard tests to verify they fail**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath \
  apps/dashboard/components/shared/__tests__/BrowseCategoryActions.test.tsx \
  apps/dashboard/features/pages/brain/knowledge/memory/components/__tests__/WikiMaintenancePanel.test.tsx
```

Expected:

```text
FAIL
```

- [ ] **Step 3: Implement the wiki-specific actions**

Update `apps/dashboard/components/shared/BrowseCategoryActions.tsx`:

```tsx
const NEW_ACTION_PROMPTS: Partial<Record<ViewMode, string>> = {
  // ...
  wiki: "Bootstrap or repair the Augur wiki from current knowledge sources. If no wiki exists, build it. If a wiki already exists, repair and harden it instead of treating this as a blank creation flow.",
};
```

Update `apps/dashboard/features/pages/brain/knowledge/memory/components/WikiMaintenancePanel.tsx`:

```tsx
import { useActionRunner } from "@/hooks/useActionRunner";

export function WikiMaintenancePanel(...) {
  const { runAction, isExecuting } = useActionRunner();

  const handleUpdateWiki = () => {
    runAction({
      id: "wiki-update-focused",
      label: "Update Wiki",
      description: "Focused wiki repair and hardening",
      dispatch: "ide",
      page: "/brain/knowledge/memory",
      prompt: "Do focused repair and hardening on top of the existing wiki. Review current wiki coverage, retained /ask outcomes, and obvious gaps, then strengthen or add pages where the compiled brain is thin.",
    });
  };
```

and add the button beside `Refresh`:

```tsx
<button
  onClick={handleUpdateWiki}
  disabled={isLoading || isExecuting}
  className="inline-flex items-center gap-2 rounded-lg border border-cyan-500/30 px-3 min-h-[44px] text-sm text-cyan-300 transition-colors hover:bg-cyan-500/10 disabled:opacity-50 cursor-pointer shrink-0"
>
  <Sparkles className="h-4 w-4" aria-hidden="true" />
  Update Wiki
</button>
```

- [ ] **Step 4: Run the dashboard tests to verify the UI behavior**

Run:

```bash
pnpm --filter dashboard test -- --runTestsByPath \
  apps/dashboard/components/shared/__tests__/BrowseCategoryActions.test.tsx \
  apps/dashboard/features/pages/brain/knowledge/memory/components/__tests__/WikiMaintenancePanel.test.tsx
```

Expected:

```text
PASS
```

- [ ] **Step 5: Verify the dashboard in the browser**

Run the required dashboard verification flow:

```bash
/dev-build
```

Then open the real pages in Chrome and confirm:

```text
- `/browse` with the `wiki` tab selected shows the same `Reindex` button plus a wiki-specific `New Wiki Page` flow
- `/brain/knowledge/memory` shows the new `Update Wiki` button in the Wiki Maintenance panel
```

If Chrome verification is unavailable, stop and ask the user to check before merging.

- [ ] **Step 6: Commit**

```bash
git add \
  apps/dashboard/components/shared/BrowseCategoryActions.tsx \
  apps/dashboard/components/shared/__tests__/BrowseCategoryActions.test.tsx \
  apps/dashboard/features/pages/brain/knowledge/memory/components/WikiMaintenancePanel.tsx \
  apps/dashboard/features/pages/brain/knowledge/memory/components/__tests__/WikiMaintenancePanel.test.tsx
git commit -m "feat(dashboard): expose wiki new and update actions"
```
