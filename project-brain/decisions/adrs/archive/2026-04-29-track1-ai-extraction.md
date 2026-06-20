# Track 1 / Library 5: ai → src/lib/ai/ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Worktree required:** Before starting, use `superpowers:using-git-worktrees` to create a worktree off `main` with branch name `track1-ai`.

**Goal:** Move ai's library code (22 files in `skills/ai/augur/lib/`) to `src/lib/ai/` using rename-via-overlap. Migrate 8 external import sites + ai's own tests. Retire 3 of 4 architecture-test allowlist entries (`onboard`, `platform-admin`, `file-manager`). The fourth entry `("ingest", "ai")` stays — ingest's coupling is to `skills/ai/scripts/sync_agents/`, which is out of scope for narrow Library 5.

**Architecture:** Six sequential PRs. PR 1 is purely additive (22 files copied; both old and new paths work). PRs 2–5 migrate one consumer group at a time. PR 6 deletes the 22 skill-side library files and retires 3 allowlist entries. The `skills/ai/augur/adapters/`, `skills/ai/augur/actions/`, `skills/ai/augur/config/`, and `skills/ai/scripts/` subdirectories all stay in place — only `lib/` moves.

**Tech Stack:** Python 3.11+, pytest, uv. No new dependencies.

**Related specs:**
- Layer 1: `docs/superpowers/specs/2026-04-28-cross-client-bundle-architecture-design.md`
- Layer 4 migration: `docs/superpowers/specs/2026-04-28-cross-client-bundle-migration-design.md`
- Library 1-4 plans: `2026-04-29-track1-{doc-extractor,knowledge-memory,daemon-runtime,rag-index}-extraction.md`

## Scope decision

The Layer 4 spec named "ai → src/lib/ai/" with "the LLM bridge, model routing — broadest reach". Audit found `skills/ai/scripts/` is mostly CLI tools / sync engines / ops scripts (75 .py files) — not a library. The actual library is `skills/ai/augur/lib/` (22 files), matching the 4 allowlist entries' expectations. This narrow scope:

- Moves the canonical LLM library (config, client, profiles, IDE integrations, prompt registry, usage tracking).
- Retires 3 of 4 allowlist entries (`("ingest", "ai")` stays because ingest imports `sync_agents.skill_sync`, not `augur/lib`).
- Leaves `sync_agents/`, `adaptive/`, `ops/` in `skills/ai/scripts/` as bundle-internal CLI/ops code.

## File Structure

### New files (created in PR 1)

| File | Purpose |
|---|---|
| `src/lib/ai/__init__.py` | Re-exports public API: `LLMClient`, `LLMConfig`, `LLMProfile`, `create_llm_client`, `get_llm_client`, `load_llm_config`, `resolve_llm_profile` |
| `src/lib/ai/agent_capabilities.py` | Verbatim copy |
| `src/lib/ai/cli_detect.py` | Verbatim copy |
| `src/lib/ai/client.py` | Verbatim copy |
| `src/lib/ai/cloud_execution.py` | Verbatim copy |
| `src/lib/ai/config.py` | Verbatim copy |
| `src/lib/ai/crew_parser.py` | Verbatim copy |
| `src/lib/ai/discovery.py` | Verbatim copy |
| `src/lib/ai/ide_backlog.py` | Verbatim copy |
| `src/lib/ai/ide_commands.py` | Verbatim copy |
| `src/lib/ai/ide_detector.py` | Verbatim copy |
| `src/lib/ai/ide_health.py` | Verbatim copy (keeps `from skills.ai.augur.adapters.registry import get_registry` since adapters/ stays) |
| `src/lib/ai/ide_integrations.py` | Verbatim copy |
| `src/lib/ai/ide_intent.py` | Verbatim copy |
| `src/lib/ai/ide_pillars.py` | Verbatim copy |
| `src/lib/ai/instruction_generator.py` | Verbatim copy |
| `src/lib/ai/mcp_config_controller.py` | Verbatim copy |
| `src/lib/ai/prompt_registry.py` | Verbatim copy |
| `src/lib/ai/schema.py` | Verbatim copy |
| `src/lib/ai/subagent_profile.py` | Verbatim copy |
| `src/lib/ai/token_estimator.py` | Verbatim copy |
| `src/lib/ai/usage_tracker.py` | Verbatim copy |
| `tests/lib/ai/__init__.py` | Empty package marker |
| `tests/lib/ai/test_ai_imports.py` | Smoke tests |

### Files modified (across PRs)

| File | PR | Change |
|---|---|---|
| `skills/file-manager/scripts/autoloop.py:42` | 2 | `from skills.ai.augur.lib import get_llm_client` → `from src.lib.ai import get_llm_client` |
| `skills/onboard/scripts/cloud_status.py:16` | 2 | `from skills.ai.augur.lib.cloud_execution import (` → `from src.lib.ai.cloud_execution import (` |
| `skills/platform-admin/scripts/run_prompt.py:24` | 2 | `from skills.ai.augur.lib.prompt_registry import registry` → `from src.lib.ai.prompt_registry import registry` |
| `.github/scripts/validate_command_parity.py:15` | 3 | `from skills.ai.augur.lib.discovery import validate_commands` → `from src.lib.ai.discovery import validate_commands` |
| `.github/scripts/verify_schema.py:10` | 3 | `from skills.ai.augur.lib.usage_tracker import UsageTracker` → `from src.lib.ai.usage_tracker import UsageTracker` |
| `src/lib/extraction/ollama_client.py:9` | 4 | `from skills.ai.augur.lib import get_llm_client` → `from src.lib.ai import get_llm_client` |
| `src/lib/llm_retry.py:299` | 4 | `from skills.ai.augur.lib import load_llm_config, resolve_llm_profile` → `from src.lib.ai import load_llm_config, resolve_llm_profile` |
| `tests/test_llm_retry_config.py:22-43` | 4 | All `skills.ai.augur.lib` patch targets → `src.lib.ai` |
| `skills/ai/augur/tests/*.py` | 5 | Bulk substitute `skills.ai.augur.lib` → `src.lib.ai` (42 references) |
| `tests/architecture/test_no_cross_skill_imports.py` | 6 | Remove 3 allowlist entries: `onboard`, `platform-admin`, `file-manager` |
| `skills/ai/augur/lib/*.py` | 6 | Delete 22 files (the entire `lib/` directory) |

---

## Task 1: PR 1 — Add src/lib/ai/ alongside skills/ai/augur/lib/

**Files:**
- Create: `src/lib/ai/*.py` (22 files including `__init__.py`)
- Create: `tests/lib/ai/__init__.py`, `tests/lib/ai/test_ai_imports.py`

- [ ] **Step 1.1: Verify branch**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && git branch --show-current
```
Expected: `track1-ai`. STOP if not.

- [ ] **Step 1.2: Verify `src/lib/__init__.py` exists**

```bash
ls ~/Projects/Augur/.worktrees/track1-ai/src/lib/__init__.py
```
Expected: file exists.

- [ ] **Step 1.3: Copy 21 .py files verbatim (not __init__.py — write that ourselves)**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  mkdir -p src/lib/ai && \
  for f in agent_capabilities cli_detect client cloud_execution config crew_parser discovery ide_backlog ide_commands ide_detector ide_health ide_integrations ide_intent ide_pillars instruction_generator mcp_config_controller prompt_registry schema subagent_profile token_estimator usage_tracker; do \
    cp "skills/ai/augur/lib/$f.py" "src/lib/ai/$f.py"; \
  done && \
  ls src/lib/ai/ | wc -l
```
Expected: 21 .py files (no __init__.py yet).

- [ ] **Step 1.4: Verify all 21 parse**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  for f in src/lib/ai/*.py; do uv run python -c "import ast; ast.parse(open('$f').read())" && echo "$f OK" || echo "$f FAIL"; done
```
Expected: 21 lines, all "OK".

- [ ] **Step 1.5: Create `src/lib/ai/__init__.py`**

Write this exact content:

```python
"""Shared LLM utilities (provider-agnostic, local-first).

Migrated from skills/ai/augur/lib/ in Track 1 of the cross-client bundle
architecture migration. The ai bundle's adapter surface
(skills/ai/augur/adapters/) and CLI tools (skills/ai/scripts/) remain in
the bundle — this library hosts the provider-agnostic LLM client + IDE
integration code.

The core contract is: Augur calls an OpenAI-compatible HTTP API (or a local
command) using profiles configured under the user data repo.

Public API:
    LLMConfig, LLMProfile, load_llm_config, resolve_llm_profile
        Profile/config types and loaders.

    LLMClient, create_llm_client
        Provider-agnostic client.

    get_llm_client(task, context=None)
        Convenience: resolve a profile by task name and return a ready client.
"""
from __future__ import annotations

from src.lib.ai.client import LLMClient, create_llm_client
from src.lib.ai.config import (
    LLMConfig,
    LLMProfile,
    load_llm_config,
    resolve_llm_profile,
)


def get_llm_client(task: str, *, context: str | None = None) -> LLMClient:
    """Convenience: resolve a profile by task name and return a ready client."""
    config = load_llm_config()
    profile = resolve_llm_profile(config, task=task, context=context)
    return create_llm_client(profile)


__all__ = [
    "LLMClient",
    "LLMConfig",
    "LLMProfile",
    "create_llm_client",
    "get_llm_client",
    "load_llm_config",
    "resolve_llm_profile",
]
```

- [ ] **Step 1.6: Verify the public API imports cleanly**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  uv run python -c "
from src.lib.ai import (
    LLMClient, LLMConfig, LLMProfile,
    create_llm_client, get_llm_client,
    load_llm_config, resolve_llm_profile,
)
print('OK', LLMClient.__module__)
"
```
Expected: `OK src.lib.ai.client`

If imports fail, check for absolute references inside the copied files:
```bash
grep -n "^from skills\.ai\.augur\.lib\|^[[:space:]]*from skills\.ai\.augur\.lib" src/lib/ai/*.py
```
If matches: edit each to relative form (`from .X` for siblings) — but at planning time `lib/ide_health.py` is the only one using `skills.ai.augur.lib.X` form, and it should be converted to relative `from .ide_integrations` and `from .ide_pillars`.

- [ ] **Step 1.7: Convert `ide_health.py`'s self-package absolute imports to relative**

Read `src/lib/ai/ide_health.py` and find the two imports:
```python
from skills.ai.augur.lib.ide_integrations import (
    ...
)
from skills.ai.augur.lib.ide_pillars import get_pillar_status
```

Replace with relative form:
```python
from .ide_integrations import (
    ...
)
from .ide_pillars import get_pillar_status
```

(Preserve the imported symbol set in the multi-line import.)

The third import in `ide_health.py` — `from skills.ai.augur.adapters.registry import get_registry` — STAYS as absolute. The `adapters/` directory is not moving.

- [ ] **Step 1.8: Re-verify imports after the relative-form fix**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  uv run python -c "from src.lib.ai import ide_health; print('OK', ide_health.__name__)"
```
Expected: `OK src.lib.ai.ide_health`

- [ ] **Step 1.9: Create test scaffolding**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  mkdir -p tests/lib/ai && \
  touch tests/lib/ai/__init__.py
```

- [ ] **Step 1.10: Write smoke tests**

Save to `tests/lib/ai/test_ai_imports.py`:

```python
"""Smoke tests for the src.lib.ai public API."""
from __future__ import annotations


def test_public_api_importable():
    """All 7 documented public symbols importable from src.lib.ai."""
    from src.lib.ai import (  # noqa: F401
        LLMClient,
        LLMConfig,
        LLMProfile,
        create_llm_client,
        get_llm_client,
        load_llm_config,
        resolve_llm_profile,
    )


def test_public_api_origins():
    """Symbols originate in the right submodules."""
    from src.lib.ai import (
        LLMClient,
        LLMConfig,
        LLMProfile,
        create_llm_client,
        load_llm_config,
        resolve_llm_profile,
    )

    assert LLMClient.__module__ == "src.lib.ai.client"
    assert create_llm_client.__module__ == "src.lib.ai.client"
    assert LLMConfig.__module__ == "src.lib.ai.config"
    assert LLMProfile.__module__ == "src.lib.ai.config"
    assert load_llm_config.__module__ == "src.lib.ai.config"
    assert resolve_llm_profile.__module__ == "src.lib.ai.config"


def test_submodule_paths_reachable():
    """Submodule access works for callers that bypass __init__ re-exports."""
    from src.lib.ai import (  # noqa: F401
        cli_detect,
        discovery,
        ide_health,
        prompt_registry,
        schema,
        usage_tracker,
    )
```

- [ ] **Step 1.11: Run lib smoke tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  uv run pytest tests/lib/ai/ -v 2>&1 | tail -10
```
Expected: 3 passed.

- [ ] **Step 1.12: Confirm ai's existing tests still pass (old path)**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  uv run pytest skills/ai/augur/tests/ 2>&1 | tail -3
```
Expected: existing test count passes (additive PR — old path unchanged).

- [ ] **Step 1.13: Worktree pollution check + commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  git status --short
```
Expected: only new files under `src/lib/ai/` and `tests/lib/ai/`. STOP and report if anything else.

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  git add src/lib/ai/ tests/lib/ai/ && \
  git commit -m "$(cat <<'EOF'
feat(lib): add src/lib/ai/ alongside ai (additive)

Track 1 / Library 5 of the cross-client bundle architecture migration.
Libraries 1-4 already landed. This PR moves ai's 22 library .py files
from skills/ai/augur/lib/ to their canonical home at src/lib/ai/.

This PR is additive only:
- src/lib/ai/ contains verbatim copies of all 21 .py files in
  skills/ai/augur/lib/ (plus a new __init__.py exposing the same
  public API as the original).
- ide_health.py's self-package absolute imports converted to relative
  form (from .ide_integrations, from .ide_pillars). The cross-package
  reach into adapters/ (from skills.ai.augur.adapters.registry) stays
  because adapters/ is not moving.
- New smoke tests at tests/lib/ai/test_ai_imports.py verify the public
  API origins and submodule reachability.

Public API: LLMClient, LLMConfig, LLMProfile, create_llm_client,
get_llm_client, load_llm_config, resolve_llm_profile.

The 22 .py files in skills/ai/augur/lib/ stay in place; consumers
continue to import via the legacy path until PRs 2-5 migrate each
consumer group. PR 6 deletes the skill-side files and retires 3
architecture-test allowlist entries (onboard, platform-admin,
file-manager). The ("ingest", "ai") entry stays — ingest's coupling
is to skills/ai/scripts/sync_agents/, out of narrow scope for
Library 5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If pre-commit hooks reject, STOP and report.

---

## Task 2: PR 2 — Migrate 3 skills (file-manager, onboard, platform-admin)

**Files:**
- Modify: `skills/file-manager/scripts/autoloop.py:42`
- Modify: `skills/onboard/scripts/cloud_status.py:16` (multi-line import block)
- Modify: `skills/platform-admin/scripts/run_prompt.py:24`

3 import sites in 3 files. Same substitution rule: replace `skills.ai.augur.lib` with `src.lib.ai`.

- [ ] **Step 2.1: Read each site**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  sed -n '40,45p' skills/file-manager/scripts/autoloop.py && \
  echo "---" && \
  sed -n '14,22p' skills/onboard/scripts/cloud_status.py && \
  echo "---" && \
  sed -n '22,28p' skills/platform-admin/scripts/run_prompt.py
```

- [ ] **Step 2.2: Update `autoloop.py`**

Replace `from skills.ai.augur.lib import get_llm_client` with `from src.lib.ai import get_llm_client`.

- [ ] **Step 2.3: Update `cloud_status.py`**

Replace `from skills.ai.augur.lib.cloud_execution import (` with `from src.lib.ai.cloud_execution import (`. Preserve the symbol list and closing parenthesis. The `# noqa: E402` comment may be on the first line; preserve it.

- [ ] **Step 2.4: Update `run_prompt.py`**

Replace `from skills.ai.augur.lib.prompt_registry import registry` with `from src.lib.ai.prompt_registry import registry`. Preserve any `# noqa` comment.

- [ ] **Step 2.5: Verify no remaining references in these 3 files**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  grep -n "skills\.ai\.augur\.lib" skills/file-manager/scripts/autoloop.py skills/onboard/scripts/cloud_status.py skills/platform-admin/scripts/run_prompt.py
```
Expected: zero matches.

- [ ] **Step 2.6: Run their tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  uv run pytest skills/file-manager/augur/tests/ skills/onboard/augur/tests/ skills/platform-admin/augur/tests/ 2>&1 | tail -5
```
Expected: existing test counts pass.

- [ ] **Step 2.7: Worktree pollution check + commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  git status --short
```
Expected: ONLY 3 files modified. STOP if anything else.

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  git add skills/file-manager/scripts/autoloop.py skills/onboard/scripts/cloud_status.py skills/platform-admin/scripts/run_prompt.py && \
  git commit -m "$(cat <<'EOF'
refactor(file-manager,onboard,platform-admin): consume src.lib.ai

Track 1 / Library 5 PR 2: migrate 3 skill consumers of ai's library
to import from src.lib.ai (added in PR 1).

Files updated:
- file-manager/scripts/autoloop.py: get_llm_client
- onboard/scripts/cloud_status.py: cloud_execution module
- platform-admin/scripts/run_prompt.py: prompt_registry.registry

The skill-side skills/ai/augur/lib/ files still exist; PR 6 deletes
them after the rest of the consumers (.github/scripts, src/lib/
internal, ai's own tests) migrate. PR 6 also retires 3 architecture-
test allowlist entries (onboard, platform-admin, file-manager).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: PR 3 — Migrate `.github/scripts/`

**Files:**
- Modify: `.github/scripts/validate_command_parity.py:15`
- Modify: `.github/scripts/verify_schema.py:10`

2 import sites. Same substitution rule.

- [ ] **Step 3.1: Read each site**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  sed -n '13,17p' .github/scripts/validate_command_parity.py && \
  echo "---" && \
  sed -n '8,12p' .github/scripts/verify_schema.py
```

- [ ] **Step 3.2: Update `validate_command_parity.py`**

Replace `from skills.ai.augur.lib.discovery import validate_commands` with `from src.lib.ai.discovery import validate_commands`.

- [ ] **Step 3.3: Update `verify_schema.py`**

Replace `from skills.ai.augur.lib.usage_tracker import UsageTracker  # noqa: E402` with `from src.lib.ai.usage_tracker import UsageTracker  # noqa: E402`. Preserve the `# noqa` comment.

- [ ] **Step 3.4: Verify no remaining references**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  grep -n "skills\.ai\.augur\.lib" .github/scripts/validate_command_parity.py .github/scripts/verify_schema.py
```
Expected: zero matches.

- [ ] **Step 3.5: Smoke test the scripts (compile-only)**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  uv run python -c "import ast; ast.parse(open('.github/scripts/validate_command_parity.py').read()); ast.parse(open('.github/scripts/verify_schema.py').read()); print('OK')"
```
Expected: OK. (Full execution requires CI context; AST parse is sufficient.)

- [ ] **Step 3.6: Worktree pollution check + commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  git status --short
```
Expected: ONLY 2 files modified.

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  git add .github/scripts/validate_command_parity.py .github/scripts/verify_schema.py && \
  git commit -m "$(cat <<'EOF'
ci: consume src.lib.ai in .github/scripts/

Track 1 / Library 5 PR 3: migrate 2 CI scripts to import from
src.lib.ai (added in PR 1).

Files updated:
- validate_command_parity.py: discovery.validate_commands
- verify_schema.py: usage_tracker.UsageTracker

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: PR 4 — Migrate src/lib/ internal consumers + tests/test_llm_retry_config.py

**Files:**
- Modify: `src/lib/extraction/ollama_client.py:9` (lazy import)
- Modify: `src/lib/llm_retry.py:299` (function-internal import)
- Modify: `tests/test_llm_retry_config.py:22-43` (multiple patch targets)

3 sites in 3 files.

- [ ] **Step 4.1: Read each site**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  sed -n '5,15p' src/lib/extraction/ollama_client.py && \
  echo "---" && \
  sed -n '295,305p' src/lib/llm_retry.py && \
  echo "---" && \
  sed -n '18,46p' tests/test_llm_retry_config.py
```

- [ ] **Step 4.2: Update `src/lib/extraction/ollama_client.py:9`**

Find `from skills.ai.augur.lib import get_llm_client` (likely indented inside try/except — preserve indentation) and replace with `from src.lib.ai import get_llm_client`.

- [ ] **Step 4.3: Update `src/lib/llm_retry.py:299`**

Find `from skills.ai.augur.lib import load_llm_config, resolve_llm_profile` (function-internal import — preserve indentation) and replace with `from src.lib.ai import load_llm_config, resolve_llm_profile`.

- [ ] **Step 4.4: Update `tests/test_llm_retry_config.py` (multiple sites at lines 22, 23, 34, 35, 42, 43)**

Bulk substitute `skills.ai.augur.lib` → `src.lib.ai` across the file. Use sed:

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  sed -i '' -E 's/skills\.ai\.augur\.lib/src.lib.ai/g' tests/test_llm_retry_config.py
```

This catches all 6 references (4 patch strings, 1 sys.modules dict key, 1 docstring/comment).

- [ ] **Step 4.5: Verify no remaining references**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  grep -n "skills\.ai\.augur\.lib" src/lib/extraction/ollama_client.py src/lib/llm_retry.py tests/test_llm_retry_config.py
```
Expected: zero matches.

- [ ] **Step 4.6: Run affected tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  uv run pytest tests/test_llm_retry_config.py tests/lib/extraction/ tests/lib/ai/ -v 2>&1 | tail -10
```
Expected: all pass.

- [ ] **Step 4.7: Worktree pollution check + commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  git status --short
```
Expected: ONLY 3 files modified.

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  git add src/lib/extraction/ollama_client.py src/lib/llm_retry.py tests/test_llm_retry_config.py && \
  git commit -m "$(cat <<'EOF'
refactor(src/lib): consume src.lib.ai (no more skills.ai.augur.lib)

Track 1 / Library 5 PR 4: migrate src/lib/ internal consumers and
tests/test_llm_retry_config.py to import from src.lib.ai.

Files updated:
- src/lib/extraction/ollama_client.py: lazy get_llm_client import
- src/lib/llm_retry.py: function-internal load_llm_config + resolve_llm_profile
- tests/test_llm_retry_config.py: 6 patch targets / sys.modules keys

After this PR, no module under src/lib/ imports skills.ai.augur.lib.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: PR 5 — Migrate ai's own tests

**Files:**
- Modify: `skills/ai/augur/tests/*.py` (all test files that import `skills.ai.augur.lib`)

Bulk substitution. Per audit: 42 references across multiple test files.

- [ ] **Step 5.1: Find all references**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  grep -rn "skills\.ai\.augur\.lib" skills/ai/augur/tests/ 2>&1 | grep -v "Binary\|__pycache__" | wc -l
```
Note the count for the commit message (expect ~42).

- [ ] **Step 5.2: Apply bulk substitution**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  sed -i '' -E 's/skills\.ai\.augur\.lib/src.lib.ai/g' skills/ai/augur/tests/*.py
```

This replaces all `skills.ai.augur.lib.X` → `src.lib.ai.X` references — imports, patch targets, importlib calls, and string literals alike.

- [ ] **Step 5.3: Verify zero remaining references**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  grep -rn "skills\.ai\.augur\.lib" skills/ai/augur/tests/ 2>&1 | grep -v "Binary\|__pycache__"
```
Expected: zero matches.

- [ ] **Step 5.4: Run ai's tests**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  uv run pytest skills/ai/augur/tests/ 2>&1 | tail -5
```
Expected: existing test count passes (same as PR 1's baseline).

If a test fails because a mock patch target like `skills.ai.augur.lib.config.SOME_CONSTANT` was migrated and now doesn't resolve, double-check the substitution preserved everything after the module name.

- [ ] **Step 5.5: Worktree pollution check + commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  git status --short
```
Expected: only `M skills/ai/augur/tests/*.py` files.

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  git add skills/ai/augur/tests/ && \
  git commit -m "$(cat <<'EOF'
refactor(ai): tests consume src.lib.ai

Track 1 / Library 5 PR 5: migrate ai's own tests from
\`skills.ai.augur.lib.X\` references (imports, patch targets,
importlib calls, string literals) to \`src.lib.ai.X\`.

Bulk substitution applied across all test files in
skills/ai/augur/tests/ via sed.

After this PR, skills/ai/ has no remaining production code or test
imports of skills.ai.augur.lib.X. PR 6 deletes the 22 library files
from the skill bundle and retires 3 architecture-test allowlist
entries.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: PR 6 — Delete skill-side library files; retire 3 allowlist entries; final verification

**Files:**
- Delete: 22 .py files in `skills/ai/augur/lib/`
- Modify: `tests/architecture/test_no_cross_skill_imports.py` (remove 3 allowlist entries)

Rename-via-overlap completes here.

- [ ] **Step 6.1: Final pre-deletion sanity check**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  grep -rn "skills\.ai\.augur\.lib" skills/ src/ apps/ tests/ scripts/ .github/ 2>/dev/null \
    | grep -v "__pycache__\|\.pyc\|skills/ai/augur/lib/" \
    | head -50
```
Expected: zero or only doc/comment references. STOP and report if any real consumer remains.

Also check file-path string forms:
```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  grep -rn "skills/ai/augur/lib/" skills/ src/ apps/ tests/ scripts/ .github/ 2>/dev/null \
    | grep -v "__pycache__\|skills/ai/augur/lib/" \
    | head -20
```
Expected: zero or only allowlist/doc references.

- [ ] **Step 6.2: Delete the 22 .py files**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  rm -r skills/ai/augur/lib/ && \
  ls skills/ai/augur/
```
Expected: `lib/` is gone. `adapters/`, `actions/`, `config/`, `tests/` remain.

- [ ] **Step 6.3: Retire 3 allowlist entries in `tests/architecture/test_no_cross_skill_imports.py`**

Read the file:
```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  grep -n "ai\")\|, \"ai\")" tests/architecture/test_no_cross_skill_imports.py
```

Use Edit tool to remove these 3 entries with their preceding comments:
- `("onboard", "ai"),`
- `("platform-admin", "ai"),`
- `("file-manager", "ai"),`

Each is preceded by a `# Retired by Track 1 when ai becomes src/lib/ai/.` comment — remove the comment too.

KEEP `("ingest", "ai"),` — its retirement reason is different (sync_agents coupling, out of scope).

- [ ] **Step 6.4: Run the architecture test**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  uv run pytest tests/architecture/ 2>&1 | tail -5
```
Expected: 2 passed. If the test now fails because a real cross-skill `ai` import was missed, that import needs to be migrated before continuing.

- [ ] **Step 6.5: Run the full test cascade**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  uv run pytest tests/lib/ai/ tests/lib/extraction/ tests/lib/index/ tests/lib/knowledge/ tests/lib/runtime/ 2>&1 | tail -3
```
Expected: ~19 passed (3 new ai smoke + previous library smokes).

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  uv run pytest skills/ai/augur/tests/ 2>&1 | tail -3
```
Expected: ai's full test suite passes (matches PR 1 baseline).

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  uv run pytest skills/file-manager/augur/tests/ skills/onboard/augur/tests/ skills/platform-admin/augur/tests/ 2>&1 | tail -3
```
Expected: existing test counts pass.

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  uv run pytest tests/test_llm_retry_config.py 2>&1 | tail -3
```
Expected: passes.

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  uv run pytest skills/document-extractor/augur/tests/ skills/knowledge/augur/tests/ skills/rag/augur/tests/ skills/augur-core/augur/tests/ 2>&1 | tail -5
```
Expected: ~548 passed (Libraries 1-4 + augur-core baselines).

- [ ] **Step 6.6: Build the dashboard**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai/apps/dashboard && \
  ls node_modules >/dev/null 2>&1 || (cd ~/Projects/Augur/.worktrees/track1-ai && pnpm install)
```

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  pnpm --filter dashboard build 2>&1 | tail -15
```
Expected: build succeeds.

- [ ] **Step 6.7: Worktree pollution check + commit**

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  git status --short
```

Expected: 22 deletions under `skills/ai/augur/lib/` + 1 modification (`tests/architecture/test_no_cross_skill_imports.py`). If dashboard regenerated `apps/dashboard/lib/plugin-runtime/assembled-hubs.json` or `apps/dashboard/lib/tabs/generated-registry.ts`, restore them with `git checkout HEAD --` — do NOT stage them.

```bash
cd ~/Projects/Augur/.worktrees/track1-ai && \
  git add -A skills/ai/augur/lib/ tests/architecture/test_no_cross_skill_imports.py && \
  git commit -m "$(cat <<'EOF'
refactor(ai): remove 22 skill-side library files; canonical at src/lib/ai

Track 1 / Library 5 PR 6 — final step of ai's library extraction.
Deletes the 22 .py files in skills/ai/augur/lib/. The canonical
location is now src/lib/ai/.

Retires 3 of 4 architecture-test allowlist entries in
tests/architecture/test_no_cross_skill_imports.py:
- ("onboard", "ai")          # was: cloud_status.py → augur.lib.cloud_execution
- ("platform-admin", "ai")   # was: run_prompt.py   → augur.lib.prompt_registry
- ("file-manager", "ai")     # was: autoloop.py     → augur.lib.get_llm_client

The fourth entry, ("ingest", "ai"), STAYS — ingest's coupling
(skills/ingest/augur/tests/test_wiki_command_contracts.py →
skills.ai.scripts.sync_agents.skill_sync) is out of narrow Library 5
scope. sync_agents lives in skills/ai/scripts/, not skills/ai/augur/lib/.

The ai bundle keeps:
- SKILL.md, config (metadata)
- augur/adapters/  (adapter shims for Claude/Codex/Gemini/etc.)
- augur/actions/   (slash command handlers)
- augur/config/    (config wiring)
- augur/tests/     (with all imports migrated to src.lib.ai)
- scripts/         (CLI tools, sync_agents, adaptive loop, ops scripts)

Verified after deletion:
- tests/lib/ai/ + extraction/ + index/ + knowledge/ + runtime/ — 19 passed
- skills/ai/augur/tests/ — full suite passes
- skills/file-manager/ + onboard/ + platform-admin/ — existing counts pass
- tests/architecture/ — 2 passed (now with 1 fewer ai allowlist entry)
- tests/test_llm_retry_config.py — passes
- skills/document-extractor/ + knowledge/ + rag/ + augur-core/ — existing counts pass
- pnpm --filter dashboard build — succeeded

Track 1 (library extraction) is now complete: 5/5 libraries migrated.
Document-extractor → src/lib/extraction/, knowledge memory →
src/lib/knowledge/, daemon → src/lib/runtime/, rag → src/lib/index/,
ai → src/lib/ai/.

Next per Layer 4 spec: Track 2 (vault server split — 5 bundles).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Done criteria

Track 1 / Library 5 is complete when:

1. ✅ `src/lib/ai/` exists with 22 .py files and a public-API `__init__.py`.
2. ✅ All consumers (3 skills + 2 .github scripts + 2 src/lib internals + 1 unit test + ai's own tests) import from `src.lib.ai`.
3. ✅ `skills/ai/augur/lib/` is deleted.
4. ✅ 3 architecture-test allowlist entries retired (`onboard`, `platform-admin`, `file-manager`).
5. ✅ `("ingest", "ai")` entry retained with comment noting sync_agents scope deferral.
6. ✅ All test suites pass (lib smoke, ai, file-manager, onboard, platform-admin, architecture, llm_retry, doc-extractor, knowledge, rag, augur-core).
7. ✅ Dashboard builds.
8. ✅ All 6 commits merged to `main`.

## Track 1 complete after Library 5

Once Library 5 ships, Track 1 of the cross-client bundle architecture migration is done:
- Library 1: document-extractor → src/lib/extraction/ ✅
- Library 2: knowledge memory → src/lib/knowledge/ ✅
- Library 3: daemon runtime → src/lib/runtime/ ✅
- Library 4: rag → src/lib/index/ ✅
- Library 5: ai → src/lib/ai/ ← this plan

Next track per Layer 4 spec ordering: Track 2 (vault server split — 5 bundles, simplest first).
