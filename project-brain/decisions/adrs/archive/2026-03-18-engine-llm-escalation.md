# Engine-Level LLM Escalation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LLM escalation as a first-class engine capability so any adaptive loop can opt in to LLM-powered fixes when file-level operations plateau, with automatic session detection and CLI-agnostic dispatch.

**Architecture:** Add `SessionContext` dataclass to `ops_protocol.py`, detect runtime environment in `engine.py` init, wire LLM escalation into `engine_fix_phase.py` after `fix()` returns empty, dispatch via `build_headless_cmd()` from `llm_retry.py`. Individual loops opt in by adding `llm_fix()` function.

**Tech Stack:** Python (ops_protocol, adaptive engine), existing `build_headless_cmd()` + `resolve_cli()` from `src/lib/llm_retry.py`

**Spec:** `docs/superpowers/specs/2026-03-18-engine-llm-escalation-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/lib/ops_protocol.py` | Modify (lines 68-78) | Add `SessionContext`, add `session` field to `OpsContext` |
| `dist/.../adaptive/engine.py` | Modify (lines 85-111) | Add `_detect_session()`, populate in `__init__`, store on engine |
| `dist/.../adaptive/engine_fix_phase.py` | Modify (lines 60-62) | Add LLM escalation after `fix()` returns empty |
| `config/system/adaptive_loops.yaml` | Modify | Add `engine.llm_escalation` config block |
| `.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py` | Modify | Add `llm_fix()` as first adopter |

---

## Task 1: Add SessionContext to ops_protocol.py

**Files:**
- Modify: `src/lib/ops_protocol.py` (lines 68-79)

- [ ] **Step 1: Add SessionContext dataclass before OpsContext**

Insert after line 66 (after the `FixType` line) and before the `OpsContext` class:

```python
@dataclass
class SessionContext:
    """Runtime environment capabilities — detected by engine at startup."""

    has_tool_access: bool = False  # True = running in agent session (Claude Code, Codex, Gemini)
    has_llm: bool = False          # True = an LLM CLI is available on PATH
    cli_path: str = ""             # Resolved CLI path (empty if none found)
    cli_name: str = ""             # CLI identity: "claude", "gemini", "codex", etc.
    max_turns: int = 20            # From engine config
    timeout: int = 600             # From engine config (seconds)
```

- [ ] **Step 2: Add session field to OpsContext**

In the `OpsContext` dataclass, add after line 78 (`shared_snapshot`):

```python
    session: SessionContext = field(default_factory=SessionContext)  # Runtime LLM capabilities
```

- [ ] **Step 3: Update the module's exports**

Find the `__all__` or verify `SessionContext` is importable. Check if there's an `__all__` list — if so, add `"SessionContext"`. If not, the import will work by default.

- [ ] **Step 4: Verify syntax**

Run: `cd ~/Projects/Augur && python -c "from src.lib.ops_protocol import OpsContext, SessionContext; ctx = OpsContext(); print(f'session.has_llm={ctx.session.has_llm}'); print('OK')"`
Expected: `session.has_llm=False` then `OK`

- [ ] **Step 5: Commit**

```bash
git add src/lib/ops_protocol.py
git commit -m "feat(engine): add SessionContext to OpsContext for LLM escalation"
```

---

## Task 2: Add Session Detection to Engine

**Files:**
- Modify: `dist/plugins/augur-system/skills/daemon/scripts/adaptive/engine.py` (lines 85-111)

- [ ] **Step 1: Add _detect_session method and call it in __init__**

Read the file first. Then add the import at the top (after existing imports):

```python
import os
import shutil
```

Add a new method after `__init__`:

```python
    @staticmethod
    def _detect_session(config: dict[str, Any]) -> "SessionContext":
        """Detect runtime environment capabilities."""
        from src.lib.ops_protocol import SessionContext

        ctx = SessionContext()

        # 1. Check if running inside an agent session with tool access
        agent_env_vars = [
            "CLAUDE_CODE_ENTRY_POINT",
            "CODEX_SESSION",
            "GEMINI_SESSION",
            "AUGUR_AGENT_SESSION",
        ]
        ctx.has_tool_access = any(os.environ.get(v) for v in agent_env_vars)

        # 2. Resolve CLI for headless dispatch
        try:
            from src.lib.llm_retry import resolve_cli
            cli_path = resolve_cli()
            if cli_path:
                ctx.has_llm = True
                ctx.cli_path = cli_path
                ctx.cli_name = Path(cli_path).stem
        except Exception:
            pass

        # 3. If in-session, LLM is always available
        if ctx.has_tool_access:
            ctx.has_llm = True

        # 4. Load config overrides
        llm_cfg = config.get("engine", {}).get("llm_escalation", {})
        ctx.max_turns = llm_cfg.get("max_turns", 20)
        ctx.timeout = llm_cfg.get("timeout_s", 600)

        return ctx
```

Then in `__init__`, add after line 111 (`self._shared_snapshot_enabled = ...`):

```python
        self._session = self._detect_session(config)
        self._llm_escalation_enabled = bool(
            config.get("engine", {}).get("llm_escalation", {}).get("enabled", False)
        )
        self._llm_min_trust = config.get("engine", {}).get("llm_escalation", {}).get("min_trust", 0.5)
        self._llm_budget_multiplier = config.get("engine", {}).get("llm_escalation", {}).get("budget_multiplier", 3)
```

- [ ] **Step 2: Verify syntax**

Run: `cd ~/Projects/Augur && python -c "import ast; ast.parse(open('dist/plugins/augur-system/skills/daemon/scripts/adaptive/engine.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add dist/plugins/augur-system/skills/daemon/scripts/adaptive/engine.py
git commit -m "feat(engine): detect session capabilities at startup for LLM escalation"
```

---

## Task 3: Wire LLM Escalation into Fix Phase

**Files:**
- Modify: `dist/plugins/augur-system/skills/daemon/scripts/adaptive/engine_fix_phase.py` (around line 60-100)

- [ ] **Step 1: Read the full file to understand the fix flow**

Read `engine_fix_phase.py` completely. The key line is:
```python
fix_result = entry.module.fix(ctx, issues)  # line 62
```

- [ ] **Step 2: Add LLM escalation after fix() returns**

Replace the single `fix_result = entry.module.fix(ctx, issues)` line (around line 62) with:

```python
    try:
        fix_result = entry.module.fix(ctx, issues)
    except Exception as exc:
        # ... existing exception handling stays ...
```

Then after the fix succeeds and `changes` is computed (around line 96), add the LLM escalation check. Insert after line 98 (`fix_actions = getattr(fix_result, "actions", [])`) and before the commit verification:

```python
    # LLM escalation: if fix() returned no changes and module has llm_fix()
    if (
        not changes
        and not fix_actions
        and hasattr(entry.module, "llm_fix")
        and getattr(engine, "_llm_escalation_enabled", False)
        and ctx.session.has_llm
        and ctx.difficulty >= entry_config.get("llm_min_difficulty", 3)
    ):
        cat_state = loop_state.categories.get(entry.name)
        cat_trust = cat_state.trust if cat_state else 0.0
        min_trust = getattr(engine, "_llm_min_trust", 0.5)

        if cat_trust >= min_trust:
            logger.info("LLM escalation for %s (trust=%.2f, d=%d)", entry.name, cat_trust, ctx.difficulty)
            try:
                llm_prompt = entry.module.llm_fix(ctx, issues)
                if llm_prompt:
                    llm_result = _dispatch_llm_fix(engine, ctx, llm_prompt)
                    if llm_result.get("success"):
                        # Override fix_result with LLM result
                        fix_result = type(fix_result)(
                            success=True,
                            changes=llm_result.get("changes", ["llm-fix"]),
                            summary=f"LLM: {llm_result.get('summary', 'applied')}",
                            fix_type="code-fix",
                        )
                        changes = fix_result.changes
                        fix_summary = fix_result.summary
                        fix_actions = getattr(fix_result, "actions", [])
                    else:
                        logger.warning("LLM fix failed for %s: %s", entry.name, llm_result.get("error", "unknown"))
            except Exception as llm_exc:
                logger.warning("LLM escalation error for %s: %s", entry.name, llm_exc)
```

- [ ] **Step 3: Add _dispatch_llm_fix helper function**

Add at the top of the file, after the imports:

```python
import subprocess
import os
from pathlib import Path


def _dispatch_llm_fix(engine: Any, ctx: Any, prompt: str) -> dict:
    """Dispatch an LLM fix via CLI subprocess.

    Uses build_headless_cmd() with the CLI resolved at engine startup.
    Returns {"success": bool, "summary": str, "changes": list, "error": str}.
    """
    session = ctx.session
    if not session.cli_path:
        return {"success": False, "error": "No CLI available for LLM dispatch"}

    try:
        from src.lib.llm_retry import build_headless_cmd

        cmd = build_headless_cmd(
            cli_path=session.cli_path,
            prompt=prompt,
            max_turns=session.max_turns,
            allowed_tools="Read,Edit,Bash,Grep,Glob,Write",
            bypass_approvals=True,
            no_session=True,
        )

        # Clear session env vars to prevent nesting issues
        env = {**os.environ, "CLAUDECODE": "", "CLAUDE_CODE": ""}

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=session.timeout,
            cwd=str(ctx.project_root),
            env=env,
        )

        if result.returncode == 0:
            # Check git for new commits since the LLM may have committed
            git_result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1"],
                capture_output=True, text=True,
                cwd=str(ctx.project_root),
            )
            changed_files = [f for f in git_result.stdout.strip().split("\n") if f]
            return {
                "success": True,
                "summary": f"LLM applied changes to {len(changed_files)} files",
                "changes": changed_files,
            }
        else:
            return {"success": False, "error": result.stderr[:500] if result.stderr else "non-zero exit"}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"LLM timed out after {session.timeout}s"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
```

- [ ] **Step 4: Verify syntax**

Run: `cd ~/Projects/Augur && python -c "import ast; ast.parse(open('dist/plugins/augur-system/skills/daemon/scripts/adaptive/engine_fix_phase.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add dist/plugins/augur-system/skills/daemon/scripts/adaptive/engine_fix_phase.py
git commit -m "feat(engine): wire LLM escalation into fix phase with headless dispatch"
```

---

## Task 4: Add LLM Escalation Config

**Files:**
- Modify: `config/system/adaptive_loops.yaml`

- [ ] **Step 1: Read the file to find the engine section**

Read `config/system/adaptive_loops.yaml`. Find the `engine:` section (or create it if it doesn't exist).

- [ ] **Step 2: Add llm_escalation config**

Under the `engine:` key, add:

```yaml
  llm_escalation:
    enabled: true
    min_difficulty: 3
    min_trust: 0.5
    budget_multiplier: 3
    max_turns: 20
    timeout_s: 600
    allowed_tools: "Read,Edit,Bash,Grep,Glob,Write"
```

- [ ] **Step 3: Commit**

```bash
git add config/system/adaptive_loops.yaml
git commit -m "feat(engine): add llm_escalation config to adaptive_loops.yaml"
```

---

## Task 5: Add llm_fix() to auto-skill-quality (First Adopter)

**Files:**
- Modify: `.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py`

- [ ] **Step 1: Read the current file to find the right insertion point**

Read the file. The `llm_fix()` function goes after `fix()` at the end of the module.

- [ ] **Step 2: Add llm_fix() function**

Append to the end of the file:

```python
def llm_fix(ctx: OpsContext, issues: list[dict]) -> str:
    """Return a prompt for LLM-powered skill improvement.

    Called by the engine when fix() returns no changes (plateau).
    Returns a prompt string — the engine handles dispatch and safety.
    """
    if not issues:
        return ""

    # Group issues by skill, pick the worst one
    by_skill: dict[str, list[dict]] = {}
    for issue in issues:
        sname = issue.get("skill_name", "")
        if sname:
            by_skill.setdefault(sname, []).append(issue)

    if not by_skill:
        return ""

    # Pick the skill with the lowest score
    worst_skill = min(by_skill.keys(), key=lambda s: min(
        i.get("score", 100) for i in by_skill[s]
    ))
    skill_issues = by_skill[worst_skill]
    skill_dir = ctx.project_root / ".claude" / "skills" / worst_skill

    # Read skill context
    skill_md = skill_dir / "SKILL.md"
    description = ""
    hub = "system"
    if skill_md.exists():
        try:
            fm, body = parse_frontmatter(skill_md)
            description = fm.get("description", "")
            hub = (fm.get("x-augur-config") or {}).get("hub", "system")
        except Exception:
            pass

    # Build dimension breakdown
    dim_lines = []
    for issue in skill_issues:
        dim = issue.get("dimension", "unknown")
        score = issue.get("score", 0)
        detail = issue.get("detail", "")
        dim_lines.append(f"- {dim}: {score}/100 — {detail}")

    # Determine the worst dimension for targeted instructions
    worst_dim = min(skill_issues, key=lambda i: i.get("score", 100)).get("dimension", "product")

    dim_instructions = {
        "instruction": (
            "Rewrite the SKILL.md to be genuinely useful. Read the skill's code, "
            "scripts, data, and page components to understand what it does. Write a "
            "description (20+ words) that tells a user: what problem this solves, when "
            "to use it, what they'll see on the dashboard. Add ## Overview, ## Usage, "
            "and ## Configuration sections with real content."
        ),
        "product": (
            "This skill lacks MCP tools or API routes. Create:\n"
            "1. A minimal MCP tool that returns useful data. Register it via "
            "@mcp.tool(name=...) following the pattern in existing tools under "
            "src/mcp/augur_mcp/. The tool should return JSON relevant to this skill.\n"
            "2. An API route at apps/dashboard/app/api/{skill}/route.ts that calls "
            "the MCP tool via callMCPTool() from @/lib/mcp/MCPBridge.\n"
            "3. If data/ is empty, create seed files in augur/seed/ with realistic "
            "sample data that would make the dashboard page look populated."
        ),
        "ui": (
            "Dashboard pages are missing or in mock/dev state. If page components "
            "exist in augur/dashboard/, promote their state in SKILL.md frontmatter "
            "x-augur-config.contributions.pages[].state from mock to dev (if .tsx "
            "files exist) or dev to mature (if data is populated). If no pages exist, "
            "create a minimal page.tsx in augur/dashboard/ that displays the skill's data."
        ),
        "wiring": (
            "API routes have issues. Check apps/dashboard/app/api/ for routes that "
            "reference this skill. Fix:\n"
            "- Replace any fs/spawn/exec imports with MCP tool calls via callMCPTool()\n"
            "- Update stale toolName references to match actual @mcp.tool registrations\n"
            "- Remove empty gracefulFallback objects that mask failures"
        ),
    }

    instructions = dim_instructions.get(worst_dim, dim_instructions["product"])

    prompt = f"""You are improving the "{worst_skill}" skill to reach tier A quality.

## Current Score
{chr(10).join(dim_lines)}

## Skill Context
- Hub: {hub}
- Purpose: {description or 'No description'}
- Path: .claude/skills/{worst_skill}/

## Bottleneck: {worst_dim}
{instructions}

## Rules
- Commit each meaningful change: git commit -m "auto(skill-quality): {worst_skill} — <what changed>"
- Only modify files in .claude/skills/{worst_skill}/ and apps/dashboard/app/api/
- If creating MCP tools, put them in src/mcp/augur_mcp/ following existing patterns
- Follow existing codebase patterns exactly — read examples before writing
- Do NOT break existing imports or other skills
- Keep changes minimal and focused
"""
    return prompt
```

- [ ] **Step 3: Update SKILL.md config with LLM settings**

Read `.claude/skills/auto-skill-quality/SKILL.md`. Update the `x-augur-loop.config` section to add:

```yaml
    llm_min_difficulty: 3
    llm_max_turns: 20
    llm_timeout: 600
```

- [ ] **Step 4: Verify syntax**

Run: `cd ~/Projects/Augur && python -c "import ast; ast.parse(open('.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Test llm_fix() returns a prompt**

Run:
```bash
cd ~/Projects/Augur && python -c "
from src.lib.ops_protocol import OpsContext, SessionContext
from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location('m', '.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ctx = OpsContext(project_root=Path.cwd(), difficulty=4, session=SessionContext(has_llm=True))
scan_result = mod.scan(ctx)
actionable = [i for i in scan_result.issues if i.get('kind') == 'actionable']
prompt = mod.llm_fix(ctx, actionable[:5])
print(f'Prompt length: {len(prompt)} chars')
print(prompt[:500])
"
```

Expected: Non-empty prompt targeting the worst skill with dimension-specific instructions.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/auto-skill-quality/scripts/skill_quality_ops.py .claude/skills/auto-skill-quality/SKILL.md
git commit -m "feat(auto-skill-quality): add llm_fix() as first adopter of engine LLM escalation"
```

---

## Task 6: Propagate Session to OpsContext in Entry Runner

**Files:**
- Modify: `dist/plugins/augur-system/skills/daemon/scripts/adaptive/engine_entry_runner.py` (around line 70-80)

- [ ] **Step 1: Read the file to find where OpsContext is constructed**

Read the full file. Find where `OpsContext(...)` is instantiated and passed to `scan()`.

- [ ] **Step 2: Add session to the OpsContext construction**

Wherever `OpsContext(...)` is created, add:

```python
session=getattr(engine, '_session', SessionContext()),
```

This requires importing `SessionContext`:
```python
from src.lib.ops_protocol import SessionContext
```

Add this import at the top of the file.

- [ ] **Step 3: Verify syntax**

Run: `cd ~/Projects/Augur && python -c "import ast; ast.parse(open('dist/plugins/augur-system/skills/daemon/scripts/adaptive/engine_entry_runner.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add dist/plugins/augur-system/skills/daemon/scripts/adaptive/engine_entry_runner.py
git commit -m "feat(engine): propagate SessionContext to OpsContext in entry runner"
```

---

## Task 7: Integration Test

- [ ] **Step 1: Verify SessionContext imports work**

Run:
```bash
cd ~/Projects/Augur && python -c "
from src.lib.ops_protocol import OpsContext, SessionContext

# Default: no capabilities
ctx = OpsContext()
assert ctx.session.has_llm == False
assert ctx.session.has_tool_access == False
print('Default SessionContext: OK')

# With capabilities
ctx2 = OpsContext(session=SessionContext(has_llm=True, cli_path='/usr/bin/claude', cli_name='claude'))
assert ctx2.session.has_llm == True
assert ctx2.session.cli_name == 'claude'
print('Configured SessionContext: OK')
"
```

- [ ] **Step 2: Verify engine session detection**

Run:
```bash
cd ~/Projects/Augur && python -c "
import sys, os
sys.path.insert(0, 'dist/plugins/augur-system/skills/daemon/scripts')
from adaptive.engine import AdaptiveLoopEngine
from pathlib import Path

engine = AdaptiveLoopEngine(
    config={'engine': {'llm_escalation': {'enabled': True}}},
    runtime_dir=Path('/tmp/test-engine'),
    project_root=Path.cwd(),
)
s = engine._session
print(f'has_tool_access: {s.has_tool_access}')
print(f'has_llm: {s.has_llm}')
print(f'cli_path: {s.cli_path}')
print(f'cli_name: {s.cli_name}')
print(f'llm_escalation_enabled: {engine._llm_escalation_enabled}')
"
```

Expected: `has_llm=True` (should find a CLI on PATH), `llm_escalation_enabled=True`.

- [ ] **Step 3: Verify llm_fix() prompt generation**

Run:
```bash
cd ~/Projects/Augur && python -c "
from src.lib.ops_protocol import OpsContext, SessionContext
from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location('m', '.claude/skills/auto-skill-quality/scripts/skill_quality_ops.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

assert hasattr(mod, 'llm_fix'), 'llm_fix not found'
ctx = OpsContext(project_root=Path.cwd(), difficulty=4, session=SessionContext(has_llm=True))
scan_result = mod.scan(ctx)
actionable = [i for i in scan_result.issues if i.get('kind') == 'actionable']
prompt = mod.llm_fix(ctx, actionable[:3])
assert len(prompt) > 100, f'Prompt too short: {len(prompt)}'
assert 'Bottleneck' in prompt, 'Missing bottleneck section'
print(f'Prompt OK: {len(prompt)} chars, targets {prompt.split(chr(34))[1]}')
"
```

- [ ] **Step 4: Commit any fixups**

```bash
git add -A && git commit -m "fix(engine): integration test fixups for LLM escalation"
```
