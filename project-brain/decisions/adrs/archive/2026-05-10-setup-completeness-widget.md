# Setup Completeness Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a sidebar Setup widget that auto-detects 11 setup milestones across three phases (Foundation, Knowledge, Personalization), renders progressive-disclosure states (full card → compact bar → chip → alert), and lives in one PR with four verified checkpoints.

**Architecture:** Onboard skill owns probes, items registry, and an aggregator MCP tool (`get-setup-status`). Dashboard widget under `apps/dashboard/features/setup/` consumes the MCP tool via `POST /api/mcp/tool` and renders the state machine. Widget mounts above Settings in the sidebar and at the top of the Settings page.

**Tech Stack:** Python 3.11 (probes, MCP tool, pytest), TypeScript / React / Next.js (widget), Tailwind + CSS variables, MCP server (Claude API tool registration via `@mcp.tool` decorator), YAML (items registry).

**Spec:** `docs/superpowers/specs/2026-05-10-setup-completeness-widget-design.md` (commit `234999c81`).

---

## File Structure

### Created (new files)

**Onboard skill (Python, Augur):**
- `shared-vault/skills/onboard/config/setup-items.yaml` — declarative registry of 11 items
- `shared-vault/skills/onboard/scripts/setup/__init__.py`
- `shared-vault/skills/onboard/scripts/setup/types.py` — `ProbeResult`, `ItemStatus`, `PhaseStatus`, `SetupStatus` dataclasses
- `shared-vault/skills/onboard/scripts/setup/registry.py` — load + validate `setup-items.yaml`
- `shared-vault/skills/onboard/scripts/setup/state.py` — read/write `setup.skipped` and `setup.ever_completed` from preferences.yaml
- `shared-vault/skills/onboard/scripts/setup/probes/__init__.py`
- `shared-vault/skills/onboard/scripts/setup/probes/helpers.py` — `vault_has`, `safe_call_mcp`, timeout wrapper
- `shared-vault/skills/onboard/scripts/setup/probes/foundation.py` — `index_machine`, `vault`, `human_profile`
- `shared-vault/skills/onboard/scripts/setup/probes/knowledge.py` — `inbox_folders`, `source_folders`, `wiki_queries`, `wiki_pages_5`
- `shared-vault/skills/onboard/scripts/setup/probes/personalization.py` — `private_skill`, `saved_prompt`, `first_ask`, `integration`
- `shared-vault/skills/onboard/scripts/setup/aggregator.py` — orchestrate probes, compute state, apply 5 min cache
- `shared-vault/skills/onboard/scripts/setup/cli.py` — `python -m setup.cli --json` for verification
- `shared-vault/skills/onboard/scripts/mcp/setup_status_tools.py` — registers `get-setup-status` MCP tool
- `shared-vault/skills/onboard/templates/vault-prompts-readme.md` — copied to `<vault>/prompts/README.md` during `/onboard --migrate`
- `shared-vault/skills/onboard/augur/tests/test_setup_helpers.py`
- `shared-vault/skills/onboard/augur/tests/test_setup_registry.py`
- `shared-vault/skills/onboard/augur/tests/test_setup_state.py`
- `shared-vault/skills/onboard/augur/tests/test_setup_probes_foundation.py`
- `shared-vault/skills/onboard/augur/tests/test_setup_probes_knowledge.py`
- `shared-vault/skills/onboard/augur/tests/test_setup_probes_personalization.py`
- `shared-vault/skills/onboard/augur/tests/test_setup_aggregator.py`
- `shared-vault/skills/onboard/augur/tests/conftest.py` — `fixture_vault` and `fake_mcp_call` fixtures

**Dashboard (TypeScript / React):**
- `apps/dashboard/features/setup/types.ts` — TS mirror of `SetupStatus`
- `apps/dashboard/features/setup/hooks.ts` — `useSetupStatus` (60 s client cache + manual refresh)
- `apps/dashboard/features/setup/SetupWidget/index.tsx` — state-machine root
- `apps/dashboard/features/setup/SetupWidget/FullCard.tsx`
- `apps/dashboard/features/setup/SetupWidget/CompactBar.tsx`
- `apps/dashboard/features/setup/SetupWidget/Chip.tsx`
- `apps/dashboard/features/setup/SetupWidget/PhaseSection.tsx`
- `apps/dashboard/features/setup/SetupWidget/ItemRow.tsx` — handles inline expand + action button
- `apps/dashboard/features/setup/SetupWidget/__tests__/SetupWidget.test.tsx`
- `apps/dashboard/features/setup/SetupWidget/__tests__/ItemRow.test.tsx`

### Modified (existing files)

- `config/system/capability_exposure.yaml` — add `mcp:onboard:get-setup-status` entry
- `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py` — extend `build_wiki_status()` to expose `compounding.queries`
- `shared-vault/skills/knowledge/scripts/mcp/tools_reflect.py` — append one JSONL line on success
- `shared-vault/skills/onboard/SKILL.md` — register the setup_status MCP tool surface
- `shared-vault/skills/augur-core/commands/onboard.md` — `/onboard --migrate` copies `vault-prompts-readme.md` to `<vault>/prompts/README.md`
- `apps/dashboard/components/SidebarNav.tsx` — mount `<SetupWidget variant="sidebar"/>` above the FOOTER_ITEMS block
- `apps/dashboard/app/settings/page.tsx` — mount `<SetupWidget variant="settings"/>` at the top of the returned div

### Deleted (conditional, C4)

- `apps/dashboard/app/api/agents/onboarding/validate/[step]/route.ts` — only if grep confirms zero callers (rule 22)

---

## Phase 0: ADR adoption (do this first)

### Task 0: Adopt the spec as a numbered ADR

**Files:**
- Read: `docs/superpowers/specs/2026-05-10-setup-completeness-widget-design.md`
- Create: `<get_adr_dir()>/ADR-NNN-setup-completeness-widget.md` (NNN auto-assigned)

- [ ] **Step 1: Run `/adr write`**

```
/adr write Adopt the Setup Completeness Widget design committed at 234999c81 (docs/superpowers/specs/2026-05-10-setup-completeness-widget-design.md). Status: Accepted. Carry the spec content into the ADR body verbatim; in the spec, replace "Governance" section's items 1-3 with a backreference to the new ADR number.
```

- [ ] **Step 2: Capture the assigned ADR number**

The `/adr write` command prints the new file path. Note the ADR number (e.g., `ADR-635`). Use it in commit messages from here on (`refs ADR-635`).

- [ ] **Step 3: Verify the ADR file exists**

```bash
ls -la "$(python3 -c 'from src.config.paths import get_adr_dir; print(get_adr_dir())')" | grep -i setup-completeness
```

Expected: one matching ADR file.

- [ ] **Step 4: Commit**

The `/adr write` workflow commits the ADR itself. Verify:

```bash
git log -1 --oneline
```

Expected: latest commit references the new ADR.

---

## Checkpoint C1: Prerequisites

Five small, additive changes that ship with the widget — not before, not after.

### Task C1.1: Vault prompts README template

**Files:**
- Create: `shared-vault/skills/onboard/templates/vault-prompts-readme.md`

- [ ] **Step 1: Write the template**

```markdown
# Saved Prompts

This folder holds **your saved prompts** — reusable instructions you've
written or collected and want available across AI sessions.

## Convention

- One prompt per `.md` file.
- Frontmatter at the top with at least: `title`, `created`, `tags`, optional `source`.
- Body: free-form markdown. Wrap actual prompt text in fenced code blocks
  (` ```text `) so it's easy to copy.

## Detection

The Setup Completeness widget detects this folder. Adding **any** `.md` file
here counts as completing the "Save first prompt" milestone.

## Examples

See `voice-profile-almaya.md` (if you ran the import) for a two-step
voice-profile workflow.
```

- [ ] **Step 2: Commit**

```bash
git add shared-vault/skills/onboard/templates/vault-prompts-readme.md
git commit -m "feat(onboard): add vault-prompts README template (refs ADR-NNN)"
```

---

### Task C1.2: `/onboard --migrate` copies the prompts README into the vault

**Files:**
- Modify: `shared-vault/skills/augur-core/commands/onboard.md`

- [ ] **Step 1: Read the current onboard command file**

```bash
cat shared-vault/skills/augur-core/commands/onboard.md | head -60
```

Locate the `--migrate` workflow section.

- [ ] **Step 2: Add a step instructing the agent to seed `<vault>/prompts/`**

Append to the `--migrate` workflow (or extend an existing "scaffold vault subdirs" step):

```markdown
- Ensure `<vault>/prompts/` exists. If absent, create it and copy
  `shared-vault/skills/onboard/templates/vault-prompts-readme.md` to
  `<vault>/prompts/README.md` (do NOT overwrite if README.md already exists).
```

- [ ] **Step 3: Commit**

```bash
git add shared-vault/skills/augur-core/commands/onboard.md
git commit -m "feat(onboard): /onboard --migrate seeds <vault>/prompts/README.md (refs ADR-NNN)"
```

---

### Task C1.3: `reflect-context` appends to `ask-history.jsonl`

**Files:**
- Modify: `shared-vault/skills/knowledge/scripts/mcp/tools_reflect.py`
- Test: `shared-vault/skills/knowledge/scripts/mcp/tests/test_reflect_context_history.py`

- [ ] **Step 1: Inspect the current `reflect_context` success path**

```bash
sed -n '1,80p' shared-vault/skills/knowledge/scripts/mcp/tools_reflect.py
```

Find the function that handles a successful reflect-context call. Identify the return point.

- [ ] **Step 2: Write the failing test**

Create `shared-vault/skills/knowledge/scripts/mcp/tests/test_reflect_context_history.py`:

```python
import json
from pathlib import Path

import pytest

from shared_vault.skills.knowledge.scripts.mcp.tools_reflect import _append_ask_history  # to-be-created


def test_append_ask_history_writes_one_jsonl_line(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("AUGUR_STATE_DIR", str(state))

    _append_ask_history(query="What is X?", model="claude-opus-4-7")
    _append_ask_history(query="And Y?", model="claude-opus-4-7")

    log = state / "ask-history.jsonl"
    assert log.exists()
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 2
    rec = json.loads(lines[0])
    assert set(rec.keys()) >= {"ts", "query_hash", "model"}
    assert rec["query_hash"] != "What is X?"  # hashed, not raw


def test_append_failure_is_silent(tmp_path, monkeypatch):
    """A broken state dir must NOT raise — reflect-context must keep working."""
    monkeypatch.setenv("AUGUR_STATE_DIR", "/no/such/path/that/exists")
    _append_ask_history(query="x", model="m")  # no exception
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest shared-vault/skills/knowledge/scripts/mcp/tests/test_reflect_context_history.py -v
```

Expected: ImportError — `_append_ask_history` does not exist.

- [ ] **Step 4: Implement `_append_ask_history` in `tools_reflect.py`**

Add at the top of the file (after imports):

```python
import hashlib
import json
import os
import time
from pathlib import Path

from src.config.paths import get_runtime_dir


def _append_ask_history(*, query: str, model: str, latency_ms: int | None = None) -> None:
    """Best-effort append of one JSONL line to <state>/ask-history.jsonl.

    Never raises — a broken history log must not block reflect-context.
    """
    try:
        state_dir = Path(os.environ.get("AUGUR_STATE_DIR") or get_runtime_dir())
        log = state_dir / "ask-history.jsonl"
        rec = {
            "ts": time.time(),
            "query_hash": hashlib.sha256(query.encode("utf-8")).hexdigest()[:16],
            "model": model,
        }
        if latency_ms is not None:
            rec["latency_ms"] = latency_ms
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass
```

- [ ] **Step 5: Wire the call into `reflect_context`'s success path**

In the existing `reflect_context` MCP tool implementation, after a successful return path (find the `return json.dumps(...)` for the success case), insert a call:

```python
_append_ask_history(query=question, model=os.environ.get("ANTHROPIC_MODEL", "unknown"))
```

(Substitute the actual variable names already in scope — `question` may be `query`, `prompt`, or similar; check the existing signature.)

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest shared-vault/skills/knowledge/scripts/mcp/tests/test_reflect_context_history.py -v
```

Expected: 2 passed.

- [ ] **Step 7: Run the existing reflect-context tests to verify no regression**

```bash
uv run pytest shared-vault/skills/knowledge/scripts/mcp/tests/test_reflect_context.py -v
```

Expected: all existing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add shared-vault/skills/knowledge/scripts/mcp/tools_reflect.py \
        shared-vault/skills/knowledge/scripts/mcp/tests/test_reflect_context_history.py
git commit -m "feat(knowledge): append ask-history.jsonl on reflect-context success (refs ADR-NNN)"
```

---

### Task C1.4: Extend `wiki-status` to expose `compounding.queries`

**Files:**
- Modify: `shared-vault/skills/ingest/scripts/mcp/wiki_tools.py`
- Test: `shared-vault/skills/ingest/scripts/mcp/tests/test_wiki_status_compounding.py` (create if dir exists; else create dir)

- [ ] **Step 1: Inspect `build_wiki_status`**

```bash
grep -n "def build_wiki_status" shared-vault/skills/ingest/scripts/mcp/wiki_tools.py
```

Open that function and identify the dict it returns.

- [ ] **Step 2: Write the failing test**

```python
# shared-vault/skills/ingest/scripts/mcp/tests/test_wiki_status_compounding.py
from shared_vault.skills.ingest.scripts.mcp.wiki_tools import build_wiki_status


def test_wiki_status_includes_compounding_queries(tmp_path, monkeypatch):
    """build_wiki_status must expose compounding.queries (list of strings)."""
    # Stub out wiki config to a known set of queries — implementation may load
    # from <vault>/wiki/config.yaml or similar. Adjust monkeypatch to match.
    result = build_wiki_status()
    assert "compounding" in result, "wiki-status must include 'compounding' key"
    assert "queries" in result["compounding"], "compounding must include 'queries'"
    assert isinstance(result["compounding"]["queries"], list)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest shared-vault/skills/ingest/scripts/mcp/tests/test_wiki_status_compounding.py -v
```

Expected: AssertionError — `compounding` key missing.

- [ ] **Step 4: Implement the extension**

In `build_wiki_status` (passthrough — read whatever config holds the queries; cite `wiki-config` or vault wiki settings):

```python
def _load_compounding_queries() -> list[str]:
    try:
        from src.config.paths import get_vault_dir
        cfg = get_vault_dir() / "wiki" / "config.yaml"
        if not cfg.exists():
            return []
        import yaml
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
        return list(data.get("compounding", {}).get("queries", []))
    except Exception:
        return []


def build_wiki_status() -> dict:
    # ... existing logic ...
    status["compounding"] = {"queries": _load_compounding_queries()}
    return status
```

(If wiki queries live somewhere else — e.g., a different config file or DB — adjust `_load_compounding_queries` to read the real source. Discovery: `grep -rn "compounding" shared-vault/skills/ingest/ shared-vault/skills/rag/`.)

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest shared-vault/skills/ingest/scripts/mcp/tests/test_wiki_status_compounding.py -v
```

Expected: PASS.

- [ ] **Step 6: Run full ingest test suite**

```bash
uv run pytest shared-vault/skills/ingest/scripts/mcp/tests/ -v
```

Expected: no regressions.

- [ ] **Step 7: Commit**

```bash
git add shared-vault/skills/ingest/scripts/mcp/wiki_tools.py \
        shared-vault/skills/ingest/scripts/mcp/tests/test_wiki_status_compounding.py
git commit -m "feat(ingest): wiki-status exposes compounding.queries (refs ADR-NNN)"
```

---

### Task C1.5: Capability exposure entry for `get-setup-status`

**Files:**
- Modify: `config/system/capability_exposure.yaml`

- [ ] **Step 1: Inspect existing entries**

```bash
grep -A 7 "mcp:augur-core:" config/system/capability_exposure.yaml | head -16
```

Pick the closest sibling entry (a tool with `primary_surface: mcp` and `preferred_client: dashboard`) as the template.

- [ ] **Step 2: Add the new entry**

Append (alphabetical / per-skill order — match existing style):

```yaml
  mcp:onboard:get-setup-status:
    classification_status: approved
    export_to: [mcp]
    management: declared
    owner_kind: skill
    owner_skill: onboard
    preferred_client: dashboard
    primary_surface: mcp
    scope: project
    description: Aggregate status of the 11 setup-completeness items.
```

- [ ] **Step 3: Validate the YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('config/system/capability_exposure.yaml').read()); print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Run any capability-exposure validators**

```bash
grep -l "capability_exposure" src/ scripts/ 2>/dev/null | head
# If a validator exists (likely under src/config/ or scripts/), run it.
# Else: skip — yaml.safe_load above is the smoke test.
```

- [ ] **Step 5: Commit**

```bash
git add config/system/capability_exposure.yaml
git commit -m "feat(config): expose get-setup-status MCP tool to dashboard (refs ADR-NNN)"
```

**Checkpoint C1 verification:**

```bash
git log --oneline | head -6
```

Expected: 5 commits referencing ADR-NNN, all additive, all green tests.

---

## Checkpoint C2: Backend (Python)

The aggregator + 11 probes + items registry. End state: `python shared-vault/skills/onboard/scripts/setup/cli.py --json` returns valid `SetupStatus` against a fixture vault.

### Task C2.1: Items registry YAML

**Files:**
- Create: `shared-vault/skills/onboard/config/setup-items.yaml`

- [ ] **Step 1: Write the registry**

```yaml
version: 1
phases:
  - id: foundation
    label: Foundation
    items:
      - id: index-machine
        label: Index your machine
        description: Discover skills and AI clients across your harness.
        probe: foundation.index_machine
        action:
          type: command
          command: "/discover"
          label: "Run /discover"
      - id: vault
        label: Create or clone vault
        description: A vault is where your knowledge, prompts, and private skills live.
        probe: foundation.vault
        action:
          type: command
          command: "/onboard --migrate"
          label: "Set up vault"
      - id: human-profile
        label: Build human profile
        description: A short profile of you so the system can answer in your voice.
        probe: foundation.human_profile
        action:
          type: mcp
          mcp_tool: "memory-profile-regenerate"
          label: "Generate profile"
  - id: knowledge
    label: Knowledge
    items:
      - id: inbox-folders
        label: Configure inbox folders
        description: Folders the system watches for new documents.
        probe: knowledge.inbox_folders
        action:
          type: route
          route: "/brain/inbox"
          label: "Configure"
      - id: source-folders
        label: Add document source folders
        description: Folders containing knowledge documents you want indexed.
        probe: knowledge.source_folders
        action:
          type: route
          route: "/knowledge/sources"
          label: "Add sources"
      - id: wiki-queries
        label: Set wiki compounding queries
        description: Questions your wiki should answer; drives compounding.
        probe: knowledge.wiki_queries
        action:
          type: route
          route: "/brain/wiki"
          label: "Set queries"
      - id: wiki-pages-5
        label: Wiki has ≥5 compounded pages
        description: Your wiki has produced at least five durable pages.
        probe: knowledge.wiki_pages_5
        action:
          type: route
          route: "/brain/wiki"
          label: "Open wiki"
  - id: personalization
    label: Personalization
    items:
      - id: private-skill
        label: Create a private skill
        description: A skill of your own under <vault>/skills/.
        probe: personalization.private_skill
        action:
          type: command
          command: "/skill-create"
          label: "Create skill"
      - id: saved-prompt
        label: Save first prompt
        description: A reusable prompt under <vault>/prompts/.
        probe: personalization.saved_prompt
        action:
          type: route
          route: "/prompts"
          label: "Open prompts"
      - id: first-ask
        label: First /ask answered
        description: At least one successful /ask query.
        probe: personalization.first_ask
        action:
          type: command
          command: "/ask"
          label: "Try /ask"
      - id: integration
        label: Connect first integration
        description: At least one active integration (mail, calendar, drive, ...).
        probe: personalization.integration
        action:
          type: route
          route: "/settings/integrations"
          label: "Open integrations"
```

- [ ] **Step 2: Validate the YAML**

```bash
python3 -c "import yaml; data = yaml.safe_load(open('shared-vault/skills/onboard/config/setup-items.yaml').read()); assert data['version'] == 1; assert len(data['phases']) == 3; total = sum(len(p['items']) for p in data['phases']); assert total == 11, f'expected 11 items, got {total}'; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add shared-vault/skills/onboard/config/setup-items.yaml
git commit -m "feat(onboard): add 11-item setup registry (refs ADR-NNN)"
```

---

### Task C2.2: Types module

**Files:**
- Create: `shared-vault/skills/onboard/scripts/setup/__init__.py`
- Create: `shared-vault/skills/onboard/scripts/setup/types.py`
- Create: `shared-vault/skills/onboard/scripts/setup/probes/__init__.py`

- [ ] **Step 1: Create empty packages**

```bash
mkdir -p shared-vault/skills/onboard/scripts/setup/probes
touch shared-vault/skills/onboard/scripts/setup/__init__.py
touch shared-vault/skills/onboard/scripts/setup/probes/__init__.py
```

- [ ] **Step 2: Write `types.py`**

```python
"""Dataclasses for the setup-completeness aggregator."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal, Optional

ItemStatusValue = Literal["done", "pending", "skipped", "regressed"]
PhaseId = Literal["foundation", "knowledge", "personalization"]
WidgetState = Literal["card", "bar", "chip", "alert"]
ActionType = Literal["command", "route", "mcp"]


@dataclass
class ProbeResult:
    """Return value of every probe function. Never raises."""
    status: Literal["done", "pending"]
    details: Optional[str] = None


@dataclass
class ItemAction:
    type: ActionType
    label: str
    command: Optional[str] = None
    route: Optional[str] = None
    mcp_tool: Optional[str] = None


@dataclass
class ItemStatus:
    id: str
    label: str
    description: str
    status: ItemStatusValue
    action: ItemAction
    last_checked: str  # ISO timestamp
    details: Optional[str] = None


@dataclass
class PhaseStatus:
    id: PhaseId
    label: str
    total: int
    completed: int
    pct: int
    items: list[ItemStatus] = field(default_factory=list)


@dataclass
class SetupStatus:
    version: int  # always 1
    computed_at: str  # ISO
    total: int
    completed: int
    pct: int
    state: WidgetState
    ever_completed: bool
    phases: list[PhaseStatus] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
```

- [ ] **Step 3: Smoke test the import**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts python3 -c "from setup.types import SetupStatus, ItemAction; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add shared-vault/skills/onboard/scripts/setup/
git commit -m "feat(onboard): scaffold setup package + types (refs ADR-NNN)"
```

---

### Task C2.3: Registry loader (TDD)

**Files:**
- Create: `shared-vault/skills/onboard/scripts/setup/registry.py`
- Create: `shared-vault/skills/onboard/augur/tests/test_setup_registry.py`
- Create: `shared-vault/skills/onboard/augur/tests/conftest.py`

- [ ] **Step 1: Write `conftest.py` with shared fixtures**

```python
# shared-vault/skills/onboard/augur/tests/conftest.py
from pathlib import Path
import shutil
import pytest

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "config" / "setup-items.yaml"


@pytest.fixture
def fixture_vault(tmp_path, monkeypatch):
    """A temp vault with helpers to populate skills/, prompts/, profile, etc."""
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setenv("AUGUR_VAULT_DIR", str(vault))
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("AUGUR_STATE_DIR", str(state))

    class V:
        path = vault
        state_path = state
        def add_skill(self, name="my-skill"):
            d = vault / "skills" / name
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text("---\ntitle: x\n---\n")
        def add_prompt(self, name="prompt-one.md"):
            (vault / "prompts").mkdir(exist_ok=True)
            (vault / "prompts" / name).write_text("# x")
        def write_profile(self, content="A" * 300):
            (vault / "memory").mkdir(exist_ok=True)
            (vault / "memory" / "profile.md").write_text(content)
        def append_ask_history(self, n=1):
            (state / "ask-history.jsonl").write_text("\n".join('{"ts":1}' for _ in range(n)) + "\n")

    return V()


@pytest.fixture
def registry_path():
    return REGISTRY_PATH
```

- [ ] **Step 2: Write the failing test**

```python
# shared-vault/skills/onboard/augur/tests/test_setup_registry.py
import pytest
from setup.registry import load_registry, RegistryError


def test_load_registry_finds_11_items_in_3_phases(registry_path):
    reg = load_registry(registry_path)
    assert reg.version == 1
    assert len(reg.phases) == 3
    assert sum(len(p.items) for p in reg.phases) == 11


def test_load_registry_raises_on_unknown_action_type(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("""
version: 1
phases:
  - id: foundation
    label: Foundation
    items:
      - id: x
        label: X
        description: x
        probe: foundation.vault
        action: { type: bogus, label: "x" }
""")
    with pytest.raises(RegistryError):
        load_registry(bad)


def test_load_registry_raises_on_duplicate_item_id(tmp_path):
    bad = tmp_path / "dup.yaml"
    bad.write_text("""
version: 1
phases:
  - id: foundation
    label: Foundation
    items:
      - id: dup
        label: A
        description: a
        probe: foundation.vault
        action: { type: route, route: "/", label: "go" }
      - id: dup
        label: B
        description: b
        probe: foundation.vault
        action: { type: route, route: "/", label: "go" }
""")
    with pytest.raises(RegistryError):
        load_registry(bad)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run pytest shared-vault/skills/onboard/augur/tests/test_setup_registry.py -v
```

Expected: ImportError — `setup.registry` does not exist.

- [ ] **Step 4: Implement `registry.py`**

```python
"""Load and validate setup-items.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

from setup.types import ItemAction, PhaseId


class RegistryError(ValueError):
    """Raised when setup-items.yaml is invalid."""


@dataclass
class RegistryItem:
    id: str
    label: str
    description: str
    probe: str  # "foundation.vault"
    action: ItemAction


@dataclass
class RegistryPhase:
    id: PhaseId
    label: str
    items: list[RegistryItem] = field(default_factory=list)


@dataclass
class Registry:
    version: int
    phases: list[RegistryPhase]

    def all_items(self) -> Iterable[RegistryItem]:
        for p in self.phases:
            yield from p.items


_VALID_ACTION_TYPES = {"command", "route", "mcp"}
_VALID_PHASE_IDS = {"foundation", "knowledge", "personalization"}


def load_registry(path: Path) -> Registry:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    version = raw.get("version")
    if version != 1:
        raise RegistryError(f"Unsupported registry version: {version}")

    seen_ids: set[str] = set()
    phases: list[RegistryPhase] = []
    for p in raw.get("phases", []):
        pid = p.get("id")
        if pid not in _VALID_PHASE_IDS:
            raise RegistryError(f"Unknown phase id: {pid}")
        items: list[RegistryItem] = []
        for it in p.get("items", []):
            iid = it.get("id")
            if not iid:
                raise RegistryError("Item missing id")
            if iid in seen_ids:
                raise RegistryError(f"Duplicate item id: {iid}")
            seen_ids.add(iid)
            act = it.get("action") or {}
            atype = act.get("type")
            if atype not in _VALID_ACTION_TYPES:
                raise RegistryError(f"Unknown action.type for {iid}: {atype}")
            items.append(
                RegistryItem(
                    id=iid,
                    label=it["label"],
                    description=it.get("description", ""),
                    probe=it["probe"],
                    action=ItemAction(
                        type=atype,
                        label=act.get("label", ""),
                        command=act.get("command"),
                        route=act.get("route"),
                        mcp_tool=act.get("mcp_tool"),
                    ),
                )
            )
        phases.append(RegistryPhase(id=pid, label=p["label"], items=items))
    return Registry(version=version, phases=phases)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run pytest shared-vault/skills/onboard/augur/tests/test_setup_registry.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add shared-vault/skills/onboard/scripts/setup/registry.py \
        shared-vault/skills/onboard/augur/tests/test_setup_registry.py \
        shared-vault/skills/onboard/augur/tests/conftest.py
git commit -m "feat(onboard): registry loader for setup-items.yaml (refs ADR-NNN)"
```

---

### Task C2.4: Probe helpers (`vault_has`, `safe_call_mcp`, timeout)

**Files:**
- Create: `shared-vault/skills/onboard/scripts/setup/probes/helpers.py`
- Create: `shared-vault/skills/onboard/augur/tests/test_setup_helpers.py`

- [ ] **Step 1: Write the failing test**

```python
# test_setup_helpers.py
import pytest
from setup.probes.helpers import vault_has, safe_call_mcp, with_timeout
from setup.types import ProbeResult


def test_vault_has_returns_pending_when_dir_empty(fixture_vault):
    res = vault_has("skills", "*/SKILL.md")
    assert res.status == "pending"


def test_vault_has_returns_done_when_one_match(fixture_vault):
    fixture_vault.add_skill()
    res = vault_has("skills", "*/SKILL.md")
    assert res.status == "done"
    assert "1" in (res.details or "")


def test_vault_has_threshold_5(fixture_vault):
    for i in range(5):
        fixture_vault.add_prompt(f"p{i}.md")
    res = vault_has("prompts", "*.md", min_count=5)
    assert res.status == "done"
    fixture_vault.add_prompt("p5.md")
    assert vault_has("prompts", "*.md", min_count=10).status == "pending"


def test_safe_call_mcp_returns_pending_on_exception():
    def raises(**kw): raise RuntimeError("boom")
    res = safe_call_mcp(raises, tool_name="x")
    assert res.status == "pending"
    assert "Could not verify" in (res.details or "")


def test_with_timeout_returns_pending_on_slow_call():
    import time
    def slow(): time.sleep(3); return ProbeResult(status="done")
    res = with_timeout(slow, seconds=0.5)
    assert res.status == "pending"
    assert "timed out" in (res.details or "").lower()
```

- [ ] **Step 2: Run test — verify failure**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run pytest shared-vault/skills/onboard/augur/tests/test_setup_helpers.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement helpers**

```python
# shared-vault/skills/onboard/scripts/setup/probes/helpers.py
"""Shared helpers for probe functions. None mutate state."""
from __future__ import annotations

import os
import signal
from pathlib import Path
from typing import Callable

from setup.types import ProbeResult


def _vault_dir() -> Path:
    """Lookup vault dir, honoring AUGUR_VAULT_DIR env override (used by tests)."""
    env = os.environ.get("AUGUR_VAULT_DIR")
    if env:
        return Path(env)
    from src.config.paths import get_vault_dir
    return get_vault_dir()


def _state_dir() -> Path:
    env = os.environ.get("AUGUR_STATE_DIR")
    if env:
        return Path(env)
    from src.config.paths import get_runtime_dir
    return get_runtime_dir()


def vault_has(subdir: str, glob: str = "*", min_count: int = 1) -> ProbeResult:
    """Check whether <vault>/<subdir>/<glob> matches at least min_count entries."""
    base = _vault_dir() / subdir
    if not base.exists():
        return ProbeResult(status="pending", details=None)
    paths = list(base.glob(glob))
    if len(paths) >= min_count:
        return ProbeResult(status="done", details=f"{len(paths)} in {subdir}/")
    return ProbeResult(
        status="pending",
        details=f"{len(paths)}/{min_count} in {subdir}/" if paths else None,
    )


def state_jsonl_lines(filename: str, min_count: int = 1) -> ProbeResult:
    """Count lines in <state>/<filename>."""
    log = _state_dir() / filename
    if not log.exists():
        return ProbeResult(status="pending", details=None)
    try:
        n = sum(1 for _ in log.open("r", encoding="utf-8"))
    except OSError as e:
        return ProbeResult(status="pending", details=f"Could not read: {e}")
    if n >= min_count:
        return ProbeResult(status="done", details=f"{n} entries")
    return ProbeResult(status="pending", details=f"{n}/{min_count}")


def safe_call_mcp(fn: Callable, *, tool_name: str, **kwargs) -> ProbeResult:
    """Run an MCP-calling probe function. On any exception → pending+warn."""
    try:
        return fn(**kwargs)
    except Exception as e:
        return ProbeResult(
            status="pending",
            details=f"Could not verify ({tool_name}): {e.__class__.__name__}",
        )


class _TimeoutError(Exception):
    pass


def with_timeout(fn: Callable, seconds: float = 2.0) -> ProbeResult:
    """Run fn() with a soft timeout. Cross-platform fallback uses thread."""
    if hasattr(signal, "SIGALRM") and seconds >= 1:
        def handler(signum, frame): raise _TimeoutError()
        old = signal.signal(signal.SIGALRM, handler)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        try:
            return fn()
        except _TimeoutError:
            return ProbeResult(status="pending", details="timed out, click retry")
        except Exception as e:
            return ProbeResult(status="pending", details=f"Could not verify: {e}")
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)
    # fallback: thread-based timeout (Windows)
    import threading
    result: list[ProbeResult] = []
    err: list[Exception] = []
    def target():
        try:
            result.append(fn())
        except Exception as e:
            err.append(e)
    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        return ProbeResult(status="pending", details="timed out, click retry")
    if err:
        return ProbeResult(status="pending", details=f"Could not verify: {err[0]}")
    return result[0] if result else ProbeResult(status="pending", details="no result")
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run pytest shared-vault/skills/onboard/augur/tests/test_setup_helpers.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/onboard/scripts/setup/probes/helpers.py \
        shared-vault/skills/onboard/augur/tests/test_setup_helpers.py
git commit -m "feat(onboard): probe helpers — vault_has, safe_call_mcp, with_timeout (refs ADR-NNN)"
```

---

### Task C2.5: State persistence (preferences.yaml)

**Files:**
- Create: `shared-vault/skills/onboard/scripts/setup/state.py`
- Create: `shared-vault/skills/onboard/augur/tests/test_setup_state.py`

- [ ] **Step 1: Write the failing test**

```python
# test_setup_state.py
from setup.state import (
    load_persisted_state,
    save_skipped,
    save_ever_completed,
    PersistedState,
)


def test_default_state_when_no_preferences(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_PREFERENCES_PATH", str(tmp_path / "prefs.yaml"))
    s = load_persisted_state()
    assert s.skipped == []
    assert s.ever_completed is False


def test_save_and_reload_skipped(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_PREFERENCES_PATH", str(tmp_path / "prefs.yaml"))
    save_skipped(["wiki-pages-5", "integration"])
    s = load_persisted_state()
    assert s.skipped == ["wiki-pages-5", "integration"]


def test_ever_completed_never_flips_back(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_PREFERENCES_PATH", str(tmp_path / "prefs.yaml"))
    save_ever_completed(True)
    s = load_persisted_state()
    assert s.ever_completed is True
    # Attempting to set False is a no-op (the spec invariant)
    save_ever_completed(False)
    s = load_persisted_state()
    assert s.ever_completed is True
```

- [ ] **Step 2: Run test — verify failure**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run pytest shared-vault/skills/onboard/augur/tests/test_setup_state.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `state.py`**

```python
# shared-vault/skills/onboard/scripts/setup/state.py
"""Read/write the two persisted preferences.yaml keys."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PersistedState:
    skipped: list[str] = field(default_factory=list)
    ever_completed: bool = False


def _prefs_path() -> Path:
    env = os.environ.get("AUGUR_PREFERENCES_PATH")
    if env:
        return Path(env)
    from src.config.paths import get_runtime_dir
    return get_runtime_dir() / "preferences.yaml"


def _load_raw() -> dict[str, Any]:
    p = _prefs_path()
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _save_raw(data: dict[str, Any]) -> None:
    p = _prefs_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def load_persisted_state() -> PersistedState:
    raw = _load_raw()
    setup = raw.get("setup") or {}
    return PersistedState(
        skipped=list(setup.get("skipped") or []),
        ever_completed=bool(setup.get("ever_completed") or False),
    )


def save_skipped(skipped: list[str]) -> None:
    raw = _load_raw()
    raw.setdefault("setup", {})["skipped"] = list(skipped)
    _save_raw(raw)


def save_ever_completed(value: bool) -> None:
    """One-way latch: True can be set; False is a no-op once True."""
    raw = _load_raw()
    setup = raw.setdefault("setup", {})
    if setup.get("ever_completed") and value is False:
        return  # invariant: never flip back
    setup["ever_completed"] = bool(value)
    _save_raw(raw)
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run pytest shared-vault/skills/onboard/augur/tests/test_setup_state.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/onboard/scripts/setup/state.py \
        shared-vault/skills/onboard/augur/tests/test_setup_state.py
git commit -m "feat(onboard): persisted setup state (skipped + ever_completed) (refs ADR-NNN)"
```

---

### Task C2.6: Foundation probes (TDD)

**Files:**
- Create: `shared-vault/skills/onboard/scripts/setup/probes/foundation.py`
- Create: `shared-vault/skills/onboard/augur/tests/test_setup_probes_foundation.py`

- [ ] **Step 1: Write the failing tests**

```python
# test_setup_probes_foundation.py
import pytest
from setup.probes import foundation
from setup.types import ProbeResult


def test_index_machine_pending_when_registry_empty(monkeypatch, fixture_vault):
    def fake_call(tool, **kw):
        if tool == "agent-registry":
            return {"clients": [], "skills": []}
        raise AssertionError(tool)
    monkeypatch.setattr(foundation, "_mcp_call", fake_call)
    assert foundation.index_machine().status == "pending"


def test_index_machine_done_when_clients_and_skills(monkeypatch, fixture_vault):
    def fake_call(tool, **kw):
        return {"clients": ["claude-code"], "skills": ["onboard"]}
    monkeypatch.setattr(foundation, "_mcp_call", fake_call)
    res = foundation.index_machine()
    assert res.status == "done"


def test_vault_done_when_path_exists(fixture_vault):
    assert foundation.vault().status == "done"


def test_vault_pending_when_path_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("AUGUR_VAULT_DIR", str(tmp_path / "no" / "such"))
    assert foundation.vault().status == "pending"


def test_human_profile_pending_when_file_missing(fixture_vault):
    assert foundation.human_profile().status == "pending"


def test_human_profile_done_when_file_above_256_bytes(fixture_vault):
    fixture_vault.write_profile("X" * 300)
    assert foundation.human_profile().status == "done"


def test_human_profile_pending_when_file_too_small(fixture_vault):
    fixture_vault.write_profile("X")
    assert foundation.human_profile().status == "pending"
```

- [ ] **Step 2: Run — verify failure**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run pytest shared-vault/skills/onboard/augur/tests/test_setup_probes_foundation.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `foundation.py`**

```python
# shared-vault/skills/onboard/scripts/setup/probes/foundation.py
"""Foundation phase probes: index-machine, vault, human-profile."""
from __future__ import annotations

from setup.probes.helpers import _vault_dir, safe_call_mcp
from setup.types import ProbeResult


# Indirected so tests can monkeypatch this single symbol
def _mcp_call(tool: str, **kwargs):
    """Call an MCP tool. Wrapped here so tests can stub it."""
    from src.mcp_client import call_tool  # adjust to actual client API
    return call_tool(tool, **kwargs)


def index_machine() -> ProbeResult:
    def _do():
        result = _mcp_call("agent-registry")
        clients = result.get("clients") or []
        skills = result.get("skills") or []
        if clients and skills:
            return ProbeResult(
                status="done",
                details=f"{len(clients)} client(s), {len(skills)} skill(s)",
            )
        return ProbeResult(status="pending", details="No clients or skills indexed")
    return safe_call_mcp(_do, tool_name="agent-registry")


def vault() -> ProbeResult:
    path = _vault_dir()
    if path.exists() and path.is_dir():
        return ProbeResult(status="done", details=f"Vault at {path}")
    return ProbeResult(status="pending", details=f"Vault path not found: {path}")


_PROFILE_MIN_BYTES = 256


def human_profile() -> ProbeResult:
    """Profile lives at <vault>/memory/profile.md per the existing memory skill."""
    candidates = [
        _vault_dir() / "memory" / "profile.md",
        _vault_dir() / "profile.md",
    ]
    for p in candidates:
        if p.exists() and p.is_file() and p.stat().st_size >= _PROFILE_MIN_BYTES:
            return ProbeResult(status="done", details=f"{p.stat().st_size} bytes")
    return ProbeResult(status="pending", details="Profile missing or too small")
```

> **Discovery note:** `src.mcp_client.call_tool` is a placeholder. Find the actual in-process MCP-tool invocation API by reading `src/mcp/augur_core/` and other tools that call MCP from Python (e.g., grep `from src.mcp` in skill scripts). Adjust the import accordingly.

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run pytest shared-vault/skills/onboard/augur/tests/test_setup_probes_foundation.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/onboard/scripts/setup/probes/foundation.py \
        shared-vault/skills/onboard/augur/tests/test_setup_probes_foundation.py
git commit -m "feat(onboard): foundation probes — index, vault, profile (refs ADR-NNN)"
```

---

### Task C2.7: Knowledge probes (TDD)

**Files:**
- Create: `shared-vault/skills/onboard/scripts/setup/probes/knowledge.py`
- Create: `shared-vault/skills/onboard/augur/tests/test_setup_probes_knowledge.py`

- [ ] **Step 1: Write the failing tests**

```python
# test_setup_probes_knowledge.py
import pytest
from setup.probes import knowledge


def test_inbox_folders_done_when_one_configured(monkeypatch, fixture_vault):
    monkeypatch.setattr(knowledge, "_mcp_call", lambda tool, **kw: {"folders": [{"path": "/x"}]})
    assert knowledge.inbox_folders().status == "done"


def test_inbox_folders_pending_when_none(monkeypatch, fixture_vault):
    monkeypatch.setattr(knowledge, "_mcp_call", lambda tool, **kw: {"folders": []})
    assert knowledge.inbox_folders().status == "pending"


def test_source_folders_done_when_either_present(monkeypatch, fixture_vault):
    def fake(tool, **kw):
        if tool == "knowledge-sources": return {"sources": [{"path": "/x"}]}
        if tool == "knowledge-linked-folders": return {"folders": []}
        raise AssertionError(tool)
    monkeypatch.setattr(knowledge, "_mcp_call", fake)
    assert knowledge.source_folders().status == "done"


def test_wiki_queries_done_when_one_present(monkeypatch, fixture_vault):
    def fake(tool, **kw):
        return {"compounding": {"queries": ["how do I X?"]}}
    monkeypatch.setattr(knowledge, "_mcp_call", fake)
    assert knowledge.wiki_queries().status == "done"


def test_wiki_queries_pending_when_empty(monkeypatch, fixture_vault):
    monkeypatch.setattr(knowledge, "_mcp_call", lambda tool, **kw: {"compounding": {"queries": []}})
    assert knowledge.wiki_queries().status == "pending"


def test_wiki_pages_5_done_when_5_or_more(monkeypatch, fixture_vault):
    monkeypatch.setattr(knowledge, "_mcp_call", lambda tool, **kw: {"count": 5})
    assert knowledge.wiki_pages_5().status == "done"


def test_wiki_pages_5_pending_when_under_5(monkeypatch, fixture_vault):
    monkeypatch.setattr(knowledge, "_mcp_call", lambda tool, **kw: {"count": 4})
    assert knowledge.wiki_pages_5().status == "pending"
```

- [ ] **Step 2: Run — verify failure**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run pytest shared-vault/skills/onboard/augur/tests/test_setup_probes_knowledge.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `knowledge.py`**

```python
# shared-vault/skills/onboard/scripts/setup/probes/knowledge.py
"""Knowledge phase probes."""
from __future__ import annotations

from setup.probes.helpers import safe_call_mcp
from setup.types import ProbeResult


def _mcp_call(tool: str, **kwargs):
    from src.mcp_client import call_tool
    return call_tool(tool, **kwargs)


def inbox_folders() -> ProbeResult:
    def _do():
        r = _mcp_call("inbox-folders")
        folders = r.get("folders") or []
        if folders:
            return ProbeResult(status="done", details=f"{len(folders)} folder(s)")
        return ProbeResult(status="pending", details="No inbox folders configured")
    return safe_call_mcp(_do, tool_name="inbox-folders")


def source_folders() -> ProbeResult:
    def _do():
        srcs = (_mcp_call("knowledge-sources") or {}).get("sources") or []
        linked = (_mcp_call("knowledge-linked-folders") or {}).get("folders") or []
        n = len(srcs) + len(linked)
        if n:
            return ProbeResult(status="done", details=f"{n} source(s) configured")
        return ProbeResult(status="pending", details="No source/linked folders")
    return safe_call_mcp(_do, tool_name="knowledge-sources")


def wiki_queries() -> ProbeResult:
    def _do():
        r = _mcp_call("wiki-status")
        qs = ((r.get("compounding") or {}).get("queries")) or []
        if qs:
            return ProbeResult(status="done", details=f"{len(qs)} query/queries")
        return ProbeResult(status="pending", details="No compounding queries")
    return safe_call_mcp(_do, tool_name="wiki-status")


def wiki_pages_5() -> ProbeResult:
    def _do():
        r = _mcp_call("wiki-list", count=True)
        n = int(r.get("count") or 0)
        if n >= 5:
            return ProbeResult(status="done", details=f"{n} pages")
        return ProbeResult(status="pending", details=f"{n}/5 pages")
    return safe_call_mcp(_do, tool_name="wiki-list")
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run pytest shared-vault/skills/onboard/augur/tests/test_setup_probes_knowledge.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/onboard/scripts/setup/probes/knowledge.py \
        shared-vault/skills/onboard/augur/tests/test_setup_probes_knowledge.py
git commit -m "feat(onboard): knowledge probes — inbox, sources, wiki (refs ADR-NNN)"
```

---

### Task C2.8: Personalization probes (TDD)

**Files:**
- Create: `shared-vault/skills/onboard/scripts/setup/probes/personalization.py`
- Create: `shared-vault/skills/onboard/augur/tests/test_setup_probes_personalization.py`

- [ ] **Step 1: Write the failing tests**

```python
# test_setup_probes_personalization.py
import pytest
from setup.probes import personalization


def test_private_skill_pending_when_vault_skills_empty(fixture_vault):
    assert personalization.private_skill().status == "pending"


def test_private_skill_done_when_one_skill_in_vault(fixture_vault):
    fixture_vault.add_skill()
    assert personalization.private_skill().status == "done"


def test_saved_prompt_pending_when_dir_empty(fixture_vault):
    assert personalization.saved_prompt().status == "pending"


def test_saved_prompt_done_when_one_md_in_vault_prompts(fixture_vault):
    fixture_vault.add_prompt()
    assert personalization.saved_prompt().status == "done"


def test_first_ask_pending_when_log_missing(fixture_vault):
    assert personalization.first_ask().status == "pending"


def test_first_ask_done_when_one_line_present(fixture_vault):
    fixture_vault.append_ask_history(1)
    assert personalization.first_ask().status == "done"


def test_integration_done_when_one_active(monkeypatch, fixture_vault):
    monkeypatch.setattr(
        personalization, "_mcp_call",
        lambda tool, **kw: {"integrations": [{"id": "gmail", "active": True}]},
    )
    assert personalization.integration().status == "done"


def test_integration_pending_when_none_active(monkeypatch, fixture_vault):
    monkeypatch.setattr(
        personalization, "_mcp_call",
        lambda tool, **kw: {"integrations": [{"id": "gmail", "active": False}]},
    )
    assert personalization.integration().status == "pending"
```

- [ ] **Step 2: Run — verify failure**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run pytest shared-vault/skills/onboard/augur/tests/test_setup_probes_personalization.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `personalization.py`**

```python
# shared-vault/skills/onboard/scripts/setup/probes/personalization.py
"""Personalization phase probes."""
from __future__ import annotations

from setup.probes.helpers import vault_has, state_jsonl_lines, safe_call_mcp
from setup.types import ProbeResult


def _mcp_call(tool: str, **kwargs):
    from src.mcp_client import call_tool
    return call_tool(tool, **kwargs)


def private_skill() -> ProbeResult:
    """<vault>/skills/ is the private skills location by definition (ADR-601)."""
    return vault_has("skills", "*/SKILL.md")


def saved_prompt() -> ProbeResult:
    return vault_has("prompts", "*.md")


def first_ask() -> ProbeResult:
    return state_jsonl_lines("ask-history.jsonl", min_count=1)


def integration() -> ProbeResult:
    def _do():
        r = _mcp_call("list-integrations")
        active = [i for i in (r.get("integrations") or []) if i.get("active")]
        if active:
            return ProbeResult(status="done", details=f"{len(active)} active")
        return ProbeResult(status="pending", details="No active integrations")
    return safe_call_mcp(_do, tool_name="list-integrations")
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run pytest shared-vault/skills/onboard/augur/tests/test_setup_probes_personalization.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/onboard/scripts/setup/probes/personalization.py \
        shared-vault/skills/onboard/augur/tests/test_setup_probes_personalization.py
git commit -m "feat(onboard): personalization probes — skill, prompt, ask, integration (refs ADR-NNN)"
```

---

### Task C2.9: Aggregator (state machine + cache)

**Files:**
- Create: `shared-vault/skills/onboard/scripts/setup/aggregator.py`
- Create: `shared-vault/skills/onboard/augur/tests/test_setup_aggregator.py`

- [ ] **Step 1: Write the failing tests**

```python
# test_setup_aggregator.py
import pytest
from setup.aggregator import compute_setup_status, _derive_widget_state, clear_cache
from setup.types import ItemStatus, PhaseStatus


# --- pure state-machine tests (no probes) ---

def test_state_card_below_60pct():
    assert _derive_widget_state(pct=0, ever_completed=False, has_pending=True) == "card"
    assert _derive_widget_state(pct=59, ever_completed=False, has_pending=True) == "card"


def test_state_bar_60_to_99pct():
    assert _derive_widget_state(pct=60, ever_completed=False, has_pending=True) == "bar"
    assert _derive_widget_state(pct=99, ever_completed=False, has_pending=True) == "bar"


def test_state_chip_at_100pct_no_history():
    assert _derive_widget_state(pct=100, ever_completed=True, has_pending=False) == "chip"


def test_state_alert_at_regression():
    """ever_completed and now has pending → alert."""
    assert _derive_widget_state(pct=90, ever_completed=True, has_pending=True) == "alert"


# --- end-to-end with stubbed probes ---

def test_compute_setup_status_all_pending(monkeypatch, fixture_vault):
    clear_cache()
    # Fresh vault, no MCP stubs → all probes return pending
    status = compute_setup_status(skip_cache=True, mcp_caller=lambda tool, **kw: {})
    assert status.completed == 0
    assert status.total == 11
    assert status.state == "card"


def test_compute_setup_status_marks_skipped(monkeypatch, fixture_vault):
    clear_cache()
    monkeypatch.setattr(
        "setup.state.load_persisted_state",
        lambda: __import__("setup.state", fromlist=["PersistedState"]).PersistedState(
            skipped=["wiki-pages-5", "integration"], ever_completed=False
        ),
    )
    status = compute_setup_status(skip_cache=True, mcp_caller=lambda tool, **kw: {})
    skipped_items = [it for p in status.phases for it in p.items if it.status == "skipped"]
    assert len(skipped_items) == 2
    assert status.total == 9  # 11 - 2 skipped


def test_compute_setup_status_regressed_after_ever_completed(fixture_vault, monkeypatch):
    clear_cache()
    monkeypatch.setattr(
        "setup.state.load_persisted_state",
        lambda: __import__("setup.state", fromlist=["PersistedState"]).PersistedState(
            skipped=[], ever_completed=True
        ),
    )
    status = compute_setup_status(skip_cache=True, mcp_caller=lambda tool, **kw: {})
    assert status.state == "alert"
    regressed = [it for p in status.phases for it in p.items if it.status == "regressed"]
    assert len(regressed) > 0
```

- [ ] **Step 2: Run — verify failure**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run pytest shared-vault/skills/onboard/augur/tests/test_setup_aggregator.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `aggregator.py`**

```python
# shared-vault/skills/onboard/scripts/setup/aggregator.py
"""Run all probes, apply skipped/ever_completed, derive widget state."""
from __future__ import annotations

import importlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from setup.registry import load_registry, RegistryItem
from setup.state import load_persisted_state, save_ever_completed
from setup.types import (
    ItemAction,
    ItemStatus,
    PhaseStatus,
    ProbeResult,
    SetupStatus,
)


_REGISTRY_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "setup-items.yaml"
_CACHE_TTL_SECONDS = 5 * 60
_cache: dict = {"ts": 0.0, "value": None}


def clear_cache() -> None:
    _cache["ts"] = 0.0
    _cache["value"] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_probe(probe_path: str) -> Callable[[], ProbeResult]:
    """Resolve "foundation.vault" → setup.probes.foundation.vault."""
    module_name, func_name = probe_path.rsplit(".", 1)
    mod = importlib.import_module(f"setup.probes.{module_name}")
    return getattr(mod, func_name)


def _derive_widget_state(*, pct: int, ever_completed: bool, has_pending: bool) -> str:
    if ever_completed and has_pending:
        return "alert"
    if pct >= 100:
        return "chip"
    if pct >= 60:
        return "bar"
    return "card"


def compute_setup_status(
    *,
    skip_cache: bool = False,
    mcp_caller: Optional[Callable] = None,  # for tests; production uses default
) -> SetupStatus:
    now = time.time()
    if not skip_cache and _cache["value"] and (now - _cache["ts"]) < _CACHE_TTL_SECONDS:
        return _cache["value"]

    persisted = load_persisted_state()
    skipped_set = set(persisted.skipped)
    registry = load_registry(_REGISTRY_PATH)

    # If a custom mcp_caller is supplied (tests), patch all probe modules' _mcp_call
    if mcp_caller is not None:
        for name in ("foundation", "knowledge", "personalization"):
            mod = importlib.import_module(f"setup.probes.{name}")
            if hasattr(mod, "_mcp_call"):
                mod._mcp_call = mcp_caller  # type: ignore[attr-defined]

    phases_out: list[PhaseStatus] = []
    total_completed = 0
    total_count = 0
    has_pending = False

    for phase in registry.phases:
        items_out: list[ItemStatus] = []
        phase_completed = 0
        phase_total = 0
        for it in phase.items:
            action = ItemAction(
                type=it.action.type,
                label=it.action.label,
                command=it.action.command,
                route=it.action.route,
                mcp_tool=it.action.mcp_tool,
            )
            if it.id in skipped_set:
                items_out.append(
                    ItemStatus(
                        id=it.id, label=it.label, description=it.description,
                        status="skipped", action=action, last_checked=_now_iso(),
                    )
                )
                continue

            phase_total += 1
            total_count += 1
            try:
                fn = _load_probe(it.probe)
                result = fn()
            except Exception as e:  # last-line guard, probes already swallow most errors
                result = ProbeResult(status="pending", details=f"probe load error: {e}")

            if result.status == "done":
                status = "done"
                phase_completed += 1
                total_completed += 1
            else:
                has_pending = True
                status = "regressed" if persisted.ever_completed else "pending"
            items_out.append(
                ItemStatus(
                    id=it.id, label=it.label, description=it.description,
                    status=status, action=action, last_checked=_now_iso(),
                    details=result.details,
                )
            )

        ph_pct = int(round(100 * phase_completed / phase_total)) if phase_total else 0
        phases_out.append(
            PhaseStatus(
                id=phase.id, label=phase.label, total=phase_total,
                completed=phase_completed, pct=ph_pct, items=items_out,
            )
        )

    denom = max(total_count, 1)  # all-skipped floor
    pct = int(round(100 * total_completed / denom))

    # Latch ever_completed
    if pct >= 100 and not persisted.ever_completed:
        save_ever_completed(True)
        persisted = load_persisted_state()  # re-read

    state = _derive_widget_state(
        pct=pct, ever_completed=persisted.ever_completed, has_pending=has_pending,
    )

    out = SetupStatus(
        version=1, computed_at=_now_iso(), total=total_count, completed=total_completed,
        pct=pct, state=state, ever_completed=persisted.ever_completed, phases=phases_out,
    )
    _cache["ts"] = now
    _cache["value"] = out
    return out
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run pytest shared-vault/skills/onboard/augur/tests/test_setup_aggregator.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add shared-vault/skills/onboard/scripts/setup/aggregator.py \
        shared-vault/skills/onboard/augur/tests/test_setup_aggregator.py
git commit -m "feat(onboard): setup-status aggregator with state machine + cache (refs ADR-NNN)"
```

---

### Task C2.10: CLI for verification

**Files:**
- Create: `shared-vault/skills/onboard/scripts/setup/cli.py`

- [ ] **Step 1: Write CLI**

```python
# shared-vault/skills/onboard/scripts/setup/cli.py
"""python shared-vault/skills/onboard/scripts/setup/cli.py --json"""
from __future__ import annotations

import argparse
import json
import sys

from setup.aggregator import compute_setup_status, clear_cache


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--json", action="store_true", help="emit JSON")
    p.add_argument("--no-cache", action="store_true", help="bypass aggregator cache")
    args = p.parse_args()
    if args.no_cache:
        clear_cache()
    status = compute_setup_status(skip_cache=args.no_cache)
    if args.json:
        json.dump(status.to_dict(), sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return 0
    # plain output
    print(f"Setup: {status.completed}/{status.total} ({status.pct}%) — {status.state}")
    for ph in status.phases:
        print(f"  {ph.label}: {ph.completed}/{ph.total}")
        for it in ph.items:
            mark = {"done": "✓", "pending": "○", "skipped": "—", "regressed": "!"}[it.status]
            print(f"    {mark} {it.label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke test against the real environment**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run python shared-vault/skills/onboard/scripts/setup/cli.py --json --no-cache
```

Expected: valid JSON conforming to the `SetupStatus` schema. The state will reflect your actual machine.

- [ ] **Step 3: Commit**

```bash
git add shared-vault/skills/onboard/scripts/setup/cli.py
git commit -m "feat(onboard): setup-status CLI for verification (refs ADR-NNN)"
```

---

### Task C2.11: MCP tool registration `get-setup-status`

**Files:**
- Create: `shared-vault/skills/onboard/scripts/mcp/setup_status_tools.py`
- Modify: `shared-vault/skills/onboard/SKILL.md`

- [ ] **Step 1: Inspect a sibling tool registration to match the pattern**

```bash
sed -n '1,60p' shared-vault/skills/rag/scripts/mcp/rag_tools.py
sed -n '100,140p' shared-vault/skills/rag/scripts/mcp/rag_tools.py
```

Identify exactly where `register_tools(mcp, mcp_tool_interceptor, metrics)` is called from. The same hook path will register our new tool.

- [ ] **Step 2: Write `setup_status_tools.py`**

```python
# shared-vault/skills/onboard/scripts/mcp/setup_status_tools.py
"""Register the `get-setup-status` MCP tool."""
from __future__ import annotations

import json


def register_tools(mcp, mcp_tool_interceptor, metrics):
    @mcp.tool(name="get-setup-status")
    @mcp_tool_interceptor
    async def get_setup_status(skip_cache: bool = False) -> str:
        """Return the SetupStatus payload for the dashboard widget."""
        metrics.track_tool("get_setup_status", skill="onboard")
        try:
            from setup.aggregator import compute_setup_status, clear_cache
            if skip_cache:
                clear_cache()
            status = compute_setup_status(skip_cache=skip_cache)
            return json.dumps(status.to_dict(), default=str)
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})

    @mcp.tool(name="set-setup-skipped")
    @mcp_tool_interceptor
    async def set_setup_skipped(item_id: str, skipped: bool = True) -> str:
        """Mark / un-mark an item as skipped. Used by the widget's Skip/Unskip button."""
        metrics.track_tool("set_setup_skipped", skill="onboard")
        try:
            from setup.state import load_persisted_state, save_skipped
            current = load_persisted_state().skipped
            if skipped and item_id not in current:
                current.append(item_id)
            elif not skipped and item_id in current:
                current.remove(item_id)
            save_skipped(current)
            return json.dumps({"success": True, "skipped": current})
        except Exception as exc:
            return json.dumps({"success": False, "error": str(exc)})
```

- [ ] **Step 3: Wire the registration into the onboard skill's tool-loader**

Inspect how the onboard skill currently registers its MCP tools:

```bash
grep -rn "register_tools" shared-vault/skills/onboard/ src/mcp/
```

Add a call to `setup_status_tools.register_tools(mcp, mcp_tool_interceptor, metrics)` in whichever loader the onboard skill uses (likely `src/mcp/augur_core/...` per-skill discovery, or a `__init__.py` under `scripts/mcp/`).

- [ ] **Step 4: Update `SKILL.md`**

Append a `## MCP tools exposed` section (or add to it):

```markdown
## MCP tools exposed

- `get-setup-status` — aggregate status for the Setup widget (read-only).
- `set-setup-skipped` — mark/unmark an onboarding item as skipped (writes preferences.yaml).
```

- [ ] **Step 5: Smoke test the tool from the dashboard MCP route**

```bash
# Start the MCP server (per project convention) and call:
curl -sSL "http://localhost:3000/api/mcp/tool?tool=get-setup-status" | python3 -m json.tool | head -30
```

Expected: a JSON object with `version`, `total`, `completed`, `state`, `phases`. (If dashboard isn't running, run `/dev-build` first per rule 29.)

- [ ] **Step 6: Run all onboard tests**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run pytest shared-vault/skills/onboard/augur/tests/ -v
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add shared-vault/skills/onboard/scripts/mcp/setup_status_tools.py \
        shared-vault/skills/onboard/SKILL.md
git commit -m "feat(onboard): get-setup-status + set-setup-skipped MCP tools (refs ADR-NNN)"
```

**Checkpoint C2 verification:**

```bash
PYTHONPATH=shared-vault/skills/onboard/scripts uv run python shared-vault/skills/onboard/scripts/setup/cli.py --json --no-cache | python3 -c "import sys,json; d=json.load(sys.stdin); print('total:', d['total'], 'state:', d['state'])"
```

Expected: prints two lines with valid values. Backend is shippable independent of any UI change.

---

## Checkpoint C3: Sidebar UI

The widget consumes `get-setup-status` and renders the four states. **Per rule 28: real-browser load is required, curl-200 is not sufficient.**

### Task C3.1: TypeScript types mirror

**Files:**
- Create: `apps/dashboard/features/setup/types.ts`

- [ ] **Step 1: Write the types**

```typescript
// apps/dashboard/features/setup/types.ts
export type ItemStatusValue = "done" | "pending" | "skipped" | "regressed";
export type PhaseId = "foundation" | "knowledge" | "personalization";
export type WidgetState = "card" | "bar" | "chip" | "alert";
export type ActionType = "command" | "route" | "mcp";

export interface ItemAction {
  type: ActionType;
  label: string;
  command?: string;
  route?: string;
  mcp_tool?: string;
}

export interface ItemStatus {
  id: string;
  label: string;
  description: string;
  status: ItemStatusValue;
  action: ItemAction;
  last_checked: string;
  details?: string;
}

export interface PhaseStatus {
  id: PhaseId;
  label: string;
  total: number;
  completed: number;
  pct: number;
  items: ItemStatus[];
}

export interface SetupStatus {
  version: 1;
  computed_at: string;
  total: number;
  completed: number;
  pct: number;
  state: WidgetState;
  ever_completed: boolean;
  phases: PhaseStatus[];
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/dashboard/features/setup/types.ts
git commit -m "feat(dashboard): SetupStatus TS types (refs ADR-NNN)"
```

---

### Task C3.2: `useSetupStatus` hook (TDD with RTL)

**Files:**
- Create: `apps/dashboard/features/setup/hooks.ts`
- Create: `apps/dashboard/features/setup/__tests__/hooks.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// apps/dashboard/features/setup/__tests__/hooks.test.tsx
import { renderHook, act, waitFor } from "@testing-library/react";
import { useSetupStatus } from "../hooks";

const mockStatus = {
  version: 1, computed_at: "2026-05-10T00:00:00Z", total: 11, completed: 4,
  pct: 36, state: "card", ever_completed: false, phases: [],
};

beforeEach(() => {
  global.fetch = jest.fn();
});

test("fetches setup status and exposes data + loading", async () => {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: true, json: async () => mockStatus,
  });
  const { result } = renderHook(() => useSetupStatus());
  expect(result.current.loading).toBe(true);
  await waitFor(() => expect(result.current.loading).toBe(false));
  expect(result.current.data?.pct).toBe(36);
});

test("refresh() bypasses cache", async () => {
  (global.fetch as jest.Mock).mockResolvedValue({
    ok: true, json: async () => mockStatus,
  });
  const { result } = renderHook(() => useSetupStatus());
  await waitFor(() => expect(result.current.loading).toBe(false));
  await act(async () => { await result.current.refresh(); });
  expect((global.fetch as jest.Mock)).toHaveBeenCalledWith(
    expect.stringContaining("skip_cache=true"),
    expect.any(Object),
  );
});

test("error state surfaces fetch failure", async () => {
  (global.fetch as jest.Mock).mockRejectedValueOnce(new Error("offline"));
  const { result } = renderHook(() => useSetupStatus());
  await waitFor(() => expect(result.current.error).toBeTruthy());
  expect(result.current.data).toBeNull();
});
```

- [ ] **Step 2: Run — verify failure**

```bash
pnpm --filter @augur/dashboard test apps/dashboard/features/setup/__tests__/hooks.test.tsx
```

Expected: import error / module not found.

- [ ] **Step 3: Implement the hook**

```typescript
// apps/dashboard/features/setup/hooks.ts
"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { SetupStatus } from "./types";

const ENDPOINT = "/api/mcp/tool?tool=get-setup-status";
const CLIENT_TTL_MS = 60 * 1000;

let _cache: { ts: number; value: SetupStatus } | null = null;

interface UseSetupStatusResult {
  data: SetupStatus | null;
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

export function useSetupStatus(): UseSetupStatusResult {
  const [data, setData] = useState<SetupStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const mounted = useRef(true);

  const fetchStatus = useCallback(async (skipCache: boolean) => {
    if (!skipCache && _cache && Date.now() - _cache.ts < CLIENT_TTL_MS) {
      setData(_cache.value);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const url = skipCache ? `${ENDPOINT}&skip_cache=true` : ENDPOINT;
      const res = await fetch(url, { method: "GET" });
      if (!res.ok) throw new Error(`MCP returned ${res.status}`);
      const json: SetupStatus = await res.json();
      if (!mounted.current) return;
      _cache = { ts: Date.now(), value: json };
      setData(json);
      setError(null);
    } catch (e) {
      if (!mounted.current) return;
      setError(e instanceof Error ? e : new Error(String(e)));
      setData(null);
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    fetchStatus(false);
    return () => { mounted.current = false; };
  }, [fetchStatus]);

  const refresh = useCallback(() => fetchStatus(true), [fetchStatus]);
  return { data, loading, error, refresh };
}
```

- [ ] **Step 4: Run tests — verify pass**

```bash
pnpm --filter @augur/dashboard test apps/dashboard/features/setup/__tests__/hooks.test.tsx
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/features/setup/hooks.ts \
        apps/dashboard/features/setup/__tests__/hooks.test.tsx
git commit -m "feat(dashboard): useSetupStatus hook with 60s client cache (refs ADR-NNN)"
```

---

### Task C3.3: `<Chip>` component (the simplest leaf)

**Files:**
- Create: `apps/dashboard/features/setup/SetupWidget/Chip.tsx`
- Create: `apps/dashboard/features/setup/__tests__/Chip.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
// __tests__/Chip.test.tsx
import { render, screen } from "@testing-library/react";
import { Chip } from "../SetupWidget/Chip";

test("renders 'Setup complete' for chip state", () => {
  render(<Chip state="chip" alertHint={null} onClick={() => {}} />);
  expect(screen.getByText(/Setup complete/i)).toBeInTheDocument();
});

test("renders alert hint for alert state", () => {
  render(<Chip state="alert" alertHint="Sources empty" onClick={() => {}} />);
  expect(screen.getByText(/Sources empty/)).toBeInTheDocument();
});

test("alert state has amber styling class", () => {
  const { container } = render(<Chip state="alert" alertHint="x" onClick={() => {}} />);
  expect(container.firstChild).toHaveClass(/alert/i);
});
```

- [ ] **Step 2: Run — verify failure**

```bash
pnpm --filter @augur/dashboard test apps/dashboard/features/setup/__tests__/Chip.test.tsx
```

Expected: module not found.

- [ ] **Step 3: Implement Chip**

```tsx
// apps/dashboard/features/setup/SetupWidget/Chip.tsx
"use client";
import type { WidgetState } from "../types";

interface Props {
  state: "chip" | "alert";
  alertHint: string | null;
  onClick: () => void;
}

export function Chip({ state, alertHint, onClick }: Props) {
  const isAlert = state === "alert";
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "flex items-center gap-2 rounded-full border px-3 py-1.5",
        "text-xs font-medium transition-colors",
        isAlert
          ? "border-[var(--accent-warning)] text-[var(--accent-warning)] bg-[var(--accent-warning)]/10 alert"
          : "border-[var(--accent-success)] text-[var(--accent-success)] bg-[var(--accent-success)]/10",
      ].join(" ")}
    >
      <span
        className={[
          "h-1.5 w-1.5 rounded-full",
          isAlert ? "bg-[var(--accent-warning)]" : "bg-[var(--accent-success)]",
        ].join(" ")}
      />
      {isAlert ? (alertHint ?? "Setup needs attention") : "Setup complete"}
    </button>
  );
}
```

- [ ] **Step 4: Run — verify pass**

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/features/setup/SetupWidget/Chip.tsx \
        apps/dashboard/features/setup/__tests__/Chip.test.tsx
git commit -m "feat(dashboard): SetupWidget Chip component (refs ADR-NNN)"
```

---

### Task C3.4: `<CompactBar>` component

**Files:**
- Create: `apps/dashboard/features/setup/SetupWidget/CompactBar.tsx`
- Create: `apps/dashboard/features/setup/__tests__/CompactBar.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { CompactBar } from "../SetupWidget/CompactBar";

test("renders fraction and percentage", () => {
  render(<CompactBar completed={8} total={11} pct={73} onClick={() => {}} />);
  expect(screen.getByText(/8\s*\/\s*11/)).toBeInTheDocument();
});

test("click triggers callback", () => {
  const onClick = jest.fn();
  render(<CompactBar completed={8} total={11} pct={73} onClick={onClick} />);
  fireEvent.click(screen.getByRole("button"));
  expect(onClick).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run — verify failure**

- [ ] **Step 3: Implement CompactBar**

```tsx
// apps/dashboard/features/setup/SetupWidget/CompactBar.tsx
"use client";
import { ChevronRight, Zap } from "lucide-react";

interface Props {
  completed: number;
  total: number;
  pct: number;
  onClick: () => void;
}

export function CompactBar({ completed, total, pct, onClick }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        "w-full flex items-center gap-2 rounded-lg border px-3 py-2",
        "border-[var(--border-color)] bg-[var(--bg-card)]",
        "hover:border-[var(--border-strong)] transition-colors text-xs font-medium",
      ].join(" ")}
    >
      <Zap className="w-4 h-4 text-[var(--text-secondary)]" />
      <div className="flex-1 h-1 rounded-full bg-[var(--bg-muted)] overflow-hidden">
        <div
          className="h-full bg-[var(--accent-success)]"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[var(--text-secondary)] tabular-nums">
        {completed} / {total}
      </span>
      <ChevronRight className="w-3 h-3 text-[var(--text-muted)]" />
    </button>
  );
}
```

- [ ] **Step 4: Run — verify pass.** (2 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/features/setup/SetupWidget/CompactBar.tsx \
        apps/dashboard/features/setup/__tests__/CompactBar.test.tsx
git commit -m "feat(dashboard): SetupWidget CompactBar component (refs ADR-NNN)"
```

---

### Task C3.5: `<ItemRow>` with inline expand + action buttons

**Files:**
- Create: `apps/dashboard/features/setup/SetupWidget/ItemRow.tsx`
- Create: `apps/dashboard/features/setup/__tests__/ItemRow.test.tsx`

- [ ] **Step 1: Write failing tests**

```tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { ItemRow } from "../SetupWidget/ItemRow";
import type { ItemStatus } from "../types";

const baseItem: ItemStatus = {
  id: "vault", label: "Create or clone vault", description: "Vault desc.",
  status: "pending", last_checked: "", action: { type: "command", command: "/onboard --migrate", label: "Set up vault" },
};

test("done item has strike-through and check icon", () => {
  render(<ItemRow item={{ ...baseItem, status: "done" }} expanded={false} onExpand={() => {}} onSkip={() => {}} onAct={() => {}} />);
  expect(screen.getByText(/Create or clone vault/)).toHaveClass(/line-through/);
});

test("clicking pending row triggers onExpand", () => {
  const onExpand = jest.fn();
  render(<ItemRow item={baseItem} expanded={false} onExpand={onExpand} onSkip={() => {}} onAct={() => {}} />);
  fireEvent.click(screen.getByRole("button", { name: /Create or clone vault/i }));
  expect(onExpand).toHaveBeenCalledWith("vault");
});

test("expanded shows description, action button, and skip", () => {
  render(<ItemRow item={baseItem} expanded={true} onExpand={() => {}} onSkip={() => {}} onAct={() => {}} />);
  expect(screen.getByText(/Vault desc\./)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Set up vault/i })).toBeInTheDocument();
  expect(screen.getByText(/Skip/)).toBeInTheDocument();
});

test("command action copies to clipboard and shows toast", async () => {
  const writeText = jest.fn().mockResolvedValue(undefined);
  Object.assign(navigator, { clipboard: { writeText } });
  const onAct = jest.fn();
  render(<ItemRow item={baseItem} expanded={true} onExpand={() => {}} onSkip={() => {}} onAct={onAct} />);
  fireEvent.click(screen.getByRole("button", { name: /Set up vault/i }));
  expect(writeText).toHaveBeenCalledWith("/onboard --migrate");
  expect(onAct).toHaveBeenCalledWith(baseItem);
});
```

- [ ] **Step 2: Run — verify failure**

- [ ] **Step 3: Implement ItemRow**

```tsx
// apps/dashboard/features/setup/SetupWidget/ItemRow.tsx
"use client";
import Link from "next/link";
import { Check, Circle, AlertTriangle } from "lucide-react";
import type { ItemStatus, ItemAction } from "../types";

interface Props {
  item: ItemStatus;
  expanded: boolean;
  onExpand: (id: string) => void;
  onSkip: (id: string) => void;
  onAct: (item: ItemStatus) => void;
}

const STATUS_ICON = {
  done: Check,
  pending: Circle,
  skipped: Circle,
  regressed: AlertTriangle,
} as const;

export function ItemRow({ item, expanded, onExpand, onSkip, onAct }: Props) {
  const Icon = STATUS_ICON[item.status];
  const isDone = item.status === "done";
  return (
    <div
      className={[
        "rounded-md transition-colors",
        expanded ? "bg-[var(--bg-muted)] -mx-2 px-2 py-2" : "",
      ].join(" ")}
    >
      <button
        type="button"
        onClick={() => !isDone && onExpand(item.id)}
        className="w-full flex items-center gap-2 py-1 text-left"
        disabled={isDone}
      >
        <Icon
          className={[
            "w-3.5 h-3.5 flex-shrink-0",
            item.status === "done" ? "text-[var(--accent-success)]" : "",
            item.status === "regressed" ? "text-[var(--accent-warning)]" : "",
          ].join(" ")}
        />
        <span
          className={[
            "text-xs flex-1",
            isDone
              ? "line-through text-[var(--text-secondary)]"
              : "text-[var(--text-primary)]",
          ].join(" ")}
        >
          {item.label}
        </span>
      </button>
      {expanded && !isDone && (
        <div className="pl-5 pr-1 mt-1 space-y-2">
          <p className="text-[11px] text-[var(--text-secondary)] leading-snug">
            {item.description}
            {item.details ? ` — ${item.details}` : null}
          </p>
          <div className="flex gap-2 items-center">
            <ActionButton action={item.action} onClick={() => handleAction(item, onAct)} />
            <button
              type="button"
              onClick={() => onSkip(item.id)}
              className="text-[11px] text-[var(--text-secondary)] underline-offset-2 hover:underline"
            >
              Skip
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ActionButton({ action, onClick }: { action: ItemAction; onClick: () => void }) {
  if (action.type === "route" && action.route) {
    return (
      <Link
        href={action.route}
        className="inline-flex items-center rounded-md bg-[var(--bg-strong)] text-white text-[11px] font-medium px-2.5 py-1 hover:opacity-90"
      >
        {action.label}
      </Link>
    );
  }
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center rounded-md bg-[var(--bg-strong)] text-white text-[11px] font-medium px-2.5 py-1 hover:opacity-90"
    >
      {action.label}
    </button>
  );
}

async function handleAction(item: ItemStatus, onAct: (i: ItemStatus) => void) {
  const a = item.action;
  if (a.type === "command" && a.command) {
    try {
      await navigator.clipboard.writeText(a.command);
      // Toast: "Paste in your AI client" — UI lib of the project; replace with actual toast call.
      window.dispatchEvent(
        new CustomEvent("augur-toast", {
          detail: { kind: "info", message: `Copied "${a.command}" — paste in your AI client` },
        }),
      );
    } catch {}
  } else if (a.type === "mcp" && a.mcp_tool) {
    try {
      await fetch(`/api/mcp/tool?tool=${encodeURIComponent(a.mcp_tool)}`, { method: "POST" });
    } catch {}
  }
  onAct(item);
}
```

> **Discovery note:** the `augur-toast` CustomEvent shape is a placeholder. Find the project's actual toast helper (search `useToast`, `toast(`, `Toaster`) and replace `window.dispatchEvent` with the real call.

- [ ] **Step 4: Run — verify pass.** (4 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/features/setup/SetupWidget/ItemRow.tsx \
        apps/dashboard/features/setup/__tests__/ItemRow.test.tsx
git commit -m "feat(dashboard): SetupWidget ItemRow with inline expand + actions (refs ADR-NNN)"
```

---

### Task C3.6: `<PhaseSection>` and `<FullCard>` components

**Files:**
- Create: `apps/dashboard/features/setup/SetupWidget/PhaseSection.tsx`
- Create: `apps/dashboard/features/setup/SetupWidget/FullCard.tsx`
- Create: `apps/dashboard/features/setup/__tests__/FullCard.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { render, screen } from "@testing-library/react";
import { FullCard } from "../SetupWidget/FullCard";
import type { SetupStatus } from "../types";

const stub: SetupStatus = {
  version: 1, computed_at: "", total: 11, completed: 4, pct: 36,
  state: "card", ever_completed: false,
  phases: [
    { id: "foundation", label: "Foundation", total: 3, completed: 3, pct: 100, items: [
      { id: "index-machine", label: "Index", description: "x", status: "done", action: { type: "command", label: "x" }, last_checked: "" },
      { id: "vault", label: "Vault", description: "x", status: "done", action: { type: "command", label: "x" }, last_checked: "" },
      { id: "human-profile", label: "Profile", description: "x", status: "done", action: { type: "mcp", label: "x" }, last_checked: "" },
    ]},
    { id: "knowledge", label: "Knowledge", total: 4, completed: 1, pct: 25, items: [
      { id: "inbox-folders", label: "Inbox", description: "x", status: "done", action: { type: "route", route: "/", label: "x" }, last_checked: "" },
      { id: "source-folders", label: "Sources", description: "x", status: "pending", action: { type: "route", route: "/", label: "x" }, last_checked: "" },
      { id: "wiki-queries", label: "Wiki Q", description: "x", status: "pending", action: { type: "route", route: "/", label: "x" }, last_checked: "" },
      { id: "wiki-pages-5", label: "Wiki 5", description: "x", status: "pending", action: { type: "route", route: "/", label: "x" }, last_checked: "" },
    ]},
    { id: "personalization", label: "Personalization", total: 4, completed: 0, pct: 0, items: [] },
  ],
};

test("renders fraction header", () => {
  render(<FullCard data={stub} expandedId={null} onExpand={() => {}} onSkip={() => {}} onAct={() => {}} onRefresh={() => {}} />);
  expect(screen.getByText(/4\s*\/\s*11/)).toBeInTheDocument();
});

test("renders three phase headers", () => {
  render(<FullCard data={stub} expandedId={null} onExpand={() => {}} onSkip={() => {}} onAct={() => {}} onRefresh={() => {}} />);
  expect(screen.getByText("Foundation")).toBeInTheDocument();
  expect(screen.getByText("Knowledge")).toBeInTheDocument();
  expect(screen.getByText("Personalization")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run — verify failure**

- [ ] **Step 3: Implement `PhaseSection.tsx`**

```tsx
// apps/dashboard/features/setup/SetupWidget/PhaseSection.tsx
"use client";
import type { PhaseStatus } from "../types";
import { ItemRow } from "./ItemRow";

interface Props {
  phase: PhaseStatus;
  expandedId: string | null;
  onExpand: (id: string) => void;
  onSkip: (id: string) => void;
  onAct: (item: any) => void;
}

export function PhaseSection({ phase, expandedId, onExpand, onSkip, onAct }: Props) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[10px] uppercase tracking-wide font-semibold text-[var(--text-secondary)]">
        <span>{phase.label}</span>
        <span className="text-[var(--text-muted)] font-medium">
          {phase.completed} / {phase.total}
        </span>
      </div>
      <div className="h-0.5 rounded-full bg-[var(--bg-muted)] overflow-hidden">
        <div className="h-full bg-[var(--accent-success)]" style={{ width: `${phase.pct}%` }} />
      </div>
      <div className="space-y-0.5 pt-1">
        {phase.items.map((it) => (
          <ItemRow
            key={it.id}
            item={it}
            expanded={expandedId === it.id}
            onExpand={onExpand}
            onSkip={onSkip}
            onAct={onAct}
          />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement `FullCard.tsx`**

```tsx
// apps/dashboard/features/setup/SetupWidget/FullCard.tsx
"use client";
import { RotateCcw } from "lucide-react";
import type { SetupStatus } from "../types";
import { PhaseSection } from "./PhaseSection";

interface Props {
  data: SetupStatus;
  expandedId: string | null;
  onExpand: (id: string) => void;
  onSkip: (id: string) => void;
  onAct: (item: any) => void;
  onRefresh: () => void;
}

export function FullCard({ data, expandedId, onExpand, onSkip, onAct, onRefresh }: Props) {
  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-3 space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold text-[var(--text-primary)]">Setup</div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-[var(--text-secondary)] tabular-nums rounded-full bg-[var(--bg-muted)] px-2 py-0.5">
            {data.completed} / {data.total}
          </span>
          <button
            type="button"
            onClick={onRefresh}
            aria-label="Refresh setup status"
            className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
          >
            <RotateCcw className="w-3 h-3" />
          </button>
        </div>
      </div>
      {data.phases.map((p) => (
        <PhaseSection
          key={p.id}
          phase={p}
          expandedId={expandedId}
          onExpand={onExpand}
          onSkip={onSkip}
          onAct={onAct}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Run tests — verify pass.** (2 tests)

- [ ] **Step 6: Commit**

```bash
git add apps/dashboard/features/setup/SetupWidget/PhaseSection.tsx \
        apps/dashboard/features/setup/SetupWidget/FullCard.tsx \
        apps/dashboard/features/setup/__tests__/FullCard.test.tsx
git commit -m "feat(dashboard): SetupWidget PhaseSection + FullCard (refs ADR-NNN)"
```

---

### Task C3.7: `<SetupWidget>` root state machine

**Files:**
- Create: `apps/dashboard/features/setup/SetupWidget/index.tsx`
- Create: `apps/dashboard/features/setup/__tests__/SetupWidget.test.tsx`

- [ ] **Step 1: Write failing test**

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { SetupWidget } from "../SetupWidget";

beforeEach(() => {
  global.fetch = jest.fn();
});

const status = (overrides: Partial<any> = {}) => ({
  version: 1, computed_at: "", total: 11, completed: 4, pct: 36,
  state: "card", ever_completed: false, phases: [
    { id: "foundation", label: "F", total: 1, completed: 1, pct: 100, items: [] },
    { id: "knowledge", label: "K", total: 1, completed: 0, pct: 0, items: [] },
    { id: "personalization", label: "P", total: 1, completed: 0, pct: 0, items: [] },
  ],
  ...overrides,
});

test("renders FullCard for state=card", async () => {
  (global.fetch as jest.Mock).mockResolvedValue({ ok: true, json: async () => status() });
  render(<SetupWidget variant="sidebar" />);
  await waitFor(() => expect(screen.getByText(/4\s*\/\s*11/)).toBeInTheDocument());
});

test("renders CompactBar for state=bar", async () => {
  (global.fetch as jest.Mock).mockResolvedValue({
    ok: true, json: async () => status({ state: "bar", completed: 8, pct: 73 }),
  });
  render(<SetupWidget variant="sidebar" />);
  await waitFor(() => expect(screen.getByText(/8\s*\/\s*11/)).toBeInTheDocument());
});

test("renders Chip for state=chip", async () => {
  (global.fetch as jest.Mock).mockResolvedValue({
    ok: true, json: async () => status({ state: "chip", completed: 11, pct: 100, ever_completed: true }),
  });
  render(<SetupWidget variant="sidebar" />);
  await waitFor(() => expect(screen.getByText(/Setup complete/i)).toBeInTheDocument());
});

test("renders alert chip for state=alert", async () => {
  (global.fetch as jest.Mock).mockResolvedValue({
    ok: true, json: async () => status({
      state: "alert", ever_completed: true,
      phases: [{ id: "foundation", label: "F", total: 1, completed: 0, pct: 0, items: [
        { id: "vault", label: "Vault", description: "x", status: "regressed", action: { type: "command", label: "x" }, last_checked: "", details: "Sources empty" },
      ]}, ...status().phases.slice(1)],
    }),
  });
  render(<SetupWidget variant="sidebar" />);
  await waitFor(() => expect(screen.getByText(/Sources empty|Setup needs attention/i)).toBeInTheDocument());
});

test("error state renders fallback", async () => {
  (global.fetch as jest.Mock).mockRejectedValue(new Error("offline"));
  render(<SetupWidget variant="sidebar" />);
  await waitFor(() => expect(screen.getByText(/Setup status unavailable/i)).toBeInTheDocument());
});
```

- [ ] **Step 2: Run — verify failure**

- [ ] **Step 3: Implement `index.tsx`**

```tsx
// apps/dashboard/features/setup/SetupWidget/index.tsx
"use client";
import { useState } from "react";
import { useSetupStatus } from "../hooks";
import { FullCard } from "./FullCard";
import { CompactBar } from "./CompactBar";
import { Chip } from "./Chip";
import type { ItemStatus } from "../types";

interface Props {
  variant: "sidebar" | "settings";
}

export function SetupWidget({ variant }: Props) {
  const { data, loading, error, refresh } = useSetupStatus();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  // sidebar: when state is bar/chip, click reveals expanded full card
  const [expandFromCompact, setExpandFromCompact] = useState(false);

  if (loading && !data) {
    return (
      <div className="text-[11px] text-[var(--text-muted)] px-2 py-2">
        Loading setup status…
      </div>
    );
  }
  if (error || !data) {
    return (
      <div className="text-[11px] text-[var(--text-muted)] px-2 py-2">
        Setup status unavailable
      </div>
    );
  }

  const showFullCard =
    data.state === "card" || expandFromCompact || variant === "settings";

  const handleSkip = async (id: string) => {
    try {
      await fetch(
        `/api/mcp/tool?tool=set-setup-skipped&item_id=${encodeURIComponent(id)}&skipped=true`,
        { method: "POST" },
      );
    } finally {
      setExpandedId(null);
      await refresh();
    }
  };

  const handleAct = async (item: ItemStatus) => {
    setExpandedId(null);
    setTimeout(() => refresh(), 250); // tiny debounce so the user sees it close
  };

  if (showFullCard) {
    return (
      <FullCard
        data={data}
        expandedId={expandedId}
        onExpand={(id) => setExpandedId((cur) => (cur === id ? null : id))}
        onSkip={handleSkip}
        onAct={handleAct}
        onRefresh={refresh}
      />
    );
  }

  if (data.state === "bar") {
    return (
      <CompactBar
        completed={data.completed}
        total={data.total}
        pct={data.pct}
        onClick={() => setExpandFromCompact(true)}
      />
    );
  }

  // state === "chip" or "alert"
  const alertHint =
    data.state === "alert"
      ? data.phases.flatMap((p) => p.items).find((it) => it.status === "regressed")?.label ?? null
      : null;
  return <Chip state={data.state} alertHint={alertHint} onClick={() => setExpandFromCompact(true)} />;
}
```

- [ ] **Step 4: Run — verify pass.** (5 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/features/setup/SetupWidget/index.tsx \
        apps/dashboard/features/setup/__tests__/SetupWidget.test.tsx
git commit -m "feat(dashboard): SetupWidget root state machine (refs ADR-NNN)"
```

---

### Task C3.8: Mount the widget in SidebarNav

**Files:**
- Modify: `apps/dashboard/components/SidebarNav.tsx`

- [ ] **Step 1: Read the footer section**

```bash
sed -n '570,610p' apps/dashboard/components/SidebarNav.tsx
```

Confirm the JSX block that renders FOOTER_ITEMS.

- [ ] **Step 2: Insert the widget above FOOTER_ITEMS**

Locate:

```tsx
{FOOTER_ITEMS.length > 0 && (
  <div className="mt-auto pt-4 border-t border-[var(--border-color)] flex flex-col gap-2">
```

Replace with:

```tsx
<div className="mt-auto pt-4 border-t border-[var(--border-color)] flex flex-col gap-2">
  <SetupWidget variant="sidebar" />
  {FOOTER_ITEMS.map((item) => {
    // ... existing FOOTER_ITEMS map ...
  })}
</div>
```

Add the import at the top of the file:

```tsx
import { SetupWidget } from "@/features/setup/SetupWidget";
```

(Adjust if the dashboard's path alias for `features` differs from `@/features` — verify with the existing imports in `SidebarNav.tsx`.)

- [ ] **Step 3: Build and verify NO chunk-load errors**

```bash
/dev-build
```

Per rule 29: never `pnpm dev` directly. Wait for the build to finish.

- [ ] **Step 4: Real-browser verification (rule 28)**

Open the dashboard in a real browser. Confirm:
- Widget renders above Settings.
- Page loads to *interactive state* (not just SSR 200).
- No `Failed to load chunk` error overlay.
- Click an incomplete item → it expands inline; click again → collapses.
- Refresh button reloads the status.

If anything looks wrong, run `/dev-debug`.

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/components/SidebarNav.tsx
git commit -m "feat(dashboard): mount SetupWidget above Settings in sidebar (refs ADR-NNN)"
```

---

### Task C3.9: Auto-test-dashboard for sidebar

**Files:**
- (none new — runs the existing loop)

- [ ] **Step 1: Run the auto-loop**

```bash
/auto-test-dashboard
```

- [ ] **Step 2: Verify no regressions**

Loop must report green. If it reports gaps, address them honestly (rule 8) — do not silence them.

**Checkpoint C3 verification:**

- Sidebar shows the widget above Settings.
- All four states render correctly (verify by toggling fixture data via `set-setup-skipped` to force `card` / `bar` / `chip` transitions; force regression by deleting a vault subdir after `ever_completed` was latched).
- No browser chunk-load errors.

---

## Checkpoint C4: Settings deep-dive + cleanup

### Task C4.1: Mount widget at the top of `/settings`

**Files:**
- Modify: `apps/dashboard/app/settings/page.tsx`

- [ ] **Step 1: Read current settings page**

```bash
sed -n '1,60p' apps/dashboard/app/settings/page.tsx
```

- [ ] **Step 2: Mount the widget**

In the returned JSX, just inside the wrapping div, before the existing description paragraph:

```tsx
import { SetupWidget } from "@/features/setup/SetupWidget";

// inside the component:
return (
  <div className="space-y-4">
    <SetupWidget variant="settings" />
    <p className="text-sm text-[var(--text-secondary)]">…</p>
    <GeneralTab />
  </div>
);
```

- [ ] **Step 3: Build and verify**

```bash
/dev-build
```

- [ ] **Step 4: Real-browser check (rule 28)**

Open `/settings`. Verify the widget renders at the top in `variant="settings"` mode (always shows full card, regardless of completion %).

- [ ] **Step 5: Commit**

```bash
git add apps/dashboard/app/settings/page.tsx
git commit -m "feat(dashboard): mount SetupWidget on settings page (refs ADR-NNN)"
```

---

### Task C4.2: Conditional cleanup of legacy onboarding-validate route

**Files:**
- Modify or Delete: `apps/dashboard/app/api/agents/onboarding/validate/[step]/route.ts`

- [ ] **Step 1: Find callers**

```bash
grep -rn "agents/onboarding/validate\|/api/agents/onboarding" apps/ src/ shared-vault/ 2>/dev/null
```

- [ ] **Step 2: Decision**

If grep returns ZERO callers (other than the route itself), delete:

```bash
rm apps/dashboard/app/api/agents/onboarding/validate/[step]/route.ts
# also remove the directory if it's empty:
rmdir apps/dashboard/app/api/agents/onboarding/validate/[step] 2>/dev/null
rmdir apps/dashboard/app/api/agents/onboarding/validate 2>/dev/null
rmdir apps/dashboard/app/api/agents/onboarding 2>/dev/null
```

If grep returns callers: leave the route in place. Do NOT add a compatibility shim (rule 14).

- [ ] **Step 3: Build to verify nothing else relied on it**

```bash
/dev-build
```

- [ ] **Step 4: Commit**

If deleted:

```bash
git add -A apps/dashboard/app/api/agents/
git commit -m "chore(dashboard): remove unused legacy onboarding-validate route (refs ADR-NNN)"
```

If kept: skip the commit; note the decision in the PR description.

---

### Task C4.3: Register `auto-test-onboarding-probes` loop

**Files:**
- Modify: the loop registry (per project convention — discover via `/dev-loops`)

- [ ] **Step 1: Inspect the loop registry**

```bash
/dev-loops
```

Find where new auto-loops are declared (likely a YAML in `config/` or under a skill).

- [ ] **Step 2: Add a loop entry**

Add an entry that runs the onboard skill's pytests against a fixture vault. Example shape (adjust to actual schema):

```yaml
- id: auto-test-onboarding-probes
  description: Run setup-completeness probes against a fixture vault
  command: >
    PYTHONPATH=shared-vault/skills/onboard/scripts
    uv run pytest shared-vault/skills/onboard/augur/tests/ -v
  expected: green
  cadence: on-commit
```

- [ ] **Step 3: Run the loop once to verify**

```bash
/dev-loops run auto-test-onboarding-probes
```

Expected: green.

- [ ] **Step 4: Commit**

```bash
git add <loop-registry-file>
git commit -m "chore(loops): register auto-test-onboarding-probes (refs ADR-NNN)"
```

---

### Task C4.4: Final verification + screenshot pass

- [ ] **Step 1: Full test sweep**

```bash
/auto-test-pytest
/auto-test-dashboard
/auto-lint
```

All three loops must return green. No coverage gaps hidden.

- [ ] **Step 2: Real-browser screenshot pass on the four states (rule 28)**

Use a screenshot-capable browser tool. Verify:
1. **Card state**: full checklist, three phase headers, one item inline-expanded.
2. **Bar state**: compact bar with `8 / 11`. Click → reveals full card.
3. **Chip state** at 100%: green pill `● Setup complete`. Click → expands.
4. **Alert chip**: amber pill with regressed-item label. Click → expands and shows regressed item at top.

To force each state for testing:
- Card: fresh vault (default).
- Bar: skip enough items via `set-setup-skipped` to land between 60–99%.
- Chip: complete or skip all 11 items.
- Alert: hit 100% (latches `ever_completed`), then delete a vault subdir or unset an integration.

- [ ] **Step 3: Final commit / push**

If everything green:

```bash
git status
git log --oneline | head -20
git push
```

- [ ] **Step 4: Open / update PR**

```bash
gh pr create --title "feat(setup-widget): sidebar + settings setup-completeness widget" --body "$(cat <<'EOF'
## Summary
- Adds a sidebar Setup widget tracking 11 onboarding milestones across three phases.
- Probes auto-detect via existing MCP tools + small additions.
- Three progressive-disclosure states (card / bar / chip) plus alert state on regression.

## Refs
- Spec: docs/superpowers/specs/2026-05-10-setup-completeness-widget-design.md
- ADR: ADR-NNN

## Test plan
- [ ] /auto-test-pytest
- [ ] /auto-test-dashboard
- [ ] /auto-lint
- [ ] Real-browser screenshot pass on all four states (card, bar, chip, alert)
- [ ] CLI smoke: `python shared-vault/skills/onboard/scripts/setup/cli.py --json --no-cache`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Plan task |
|---|---|
| Three states (card/bar/chip/alert) | C2.9 (state machine), C3.3–C3.7 (UI) |
| 11 items registry | C2.1 |
| 11 probes | C2.6, C2.7, C2.8 |
| Aggregator + caching | C2.9, C2.10 |
| MCP tool `get-setup-status` + `set-setup-skipped` | C2.11 |
| Capability exposure | C1.5 |
| State persistence (skipped, ever_completed) | C2.5 |
| `<vault>/prompts/` convention + README | C1.1, C1.2 |
| `/ask` history JSONL | C1.3 |
| `wiki-status.compounding.queries` | C1.4 |
| Sidebar mount | C3.8 |
| Settings page mount | C4.1 |
| Legacy route cleanup (conditional) | C4.2 |
| Auto-loop registration | C4.3 |
| Real-browser verification (rule 28) | C3.8 step 4, C4.4 step 2 |
| ADR governance | Phase 0 (Task 0) |

All spec sections covered.

**2. Placeholder scan:**

- "Discovery note" callouts in C1.4, C2.6 are intentional — they flag the only places where the engineer must verify a path before implementing (`compounding.queries` source location; in-process MCP-call import path; toast helper). These are honest discovery prompts, not unfilled placeholders.
- No "TODO", "TBD", or "implement later" patterns.

**3. Type consistency:**

Python `ProbeResult.status` ∈ `{"done", "pending"}` (binary). The aggregator promotes `"pending"` → `"regressed"` only at status-row construction time when `ever_completed` is true. TypeScript `ItemStatusValue` ∈ `{"done", "pending", "skipped", "regressed"}` matches the wire format. Action types `command | route | mcp` consistent across YAML, Python, TypeScript. Method names `compute_setup_status`, `clear_cache`, `useSetupStatus`, `refresh` consistent across modules.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-10-setup-completeness-widget.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
