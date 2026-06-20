# ADR-460 Agent Tier Operationalization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete ADR-460 — give agents full tier declarations (fast/standard/deep), safety constraints, escalation rules, a performance ledger, and static tier routing.

**Architecture:** Extend existing `x-augur-agent` minimal blocks in 14 SKILL.md files with full tier/safety/escalation data. Update the sync_agents generator to parse and embed these in agent prompts and registry. Create a performance ledger module. Wire tier routing into useActionRunner.

**Tech Stack:** Python 3.11+, TypeScript/Next.js 16, JSON Schema (jsonschema), Zustand

**ADR:** `get_vault_dir()/dev/adrs/ADR-460-agent-tier-operationalization.md`

**What's already done (~40%):**
- 14 SKILL.md files have minimal `x-augur-agent` (role, default-model, tools)
- `crew_parser.py` parses role/model/tools
- `subagent_profile.py` has `ROLE_TO_CLAUDE_MODE`, generates agent .md with correct mode/model
- `registry.json` is schema 2.0 with role/defaultModel/tools (but `tiers: {}`)
- Generated agents have correct mode (auto/plan) and tools

**What remains (~60%):**
- Full tier/safety/escalation declarations in SKILL.md
- JSON schema validation
- Safety constraints + escalation rules in generated agent prompts
- Registry populated with tier/safety/escalation/performance data
- Performance ledger (record, aggregate, compact)
- Static tier routing in useActionRunner
- Drift detection for agent files
- Tests

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/config/schemas/agent-profile.schema.json` | JSON schema for x-augur-agent validation |
| Modify | 14x `.claude/skills/*/SKILL.md` | Add tiers/safety/escalation blocks |
| Modify | `.claude/skills/ai_bridge/augur/lib/subagent_profile.py` | Extended SafetyConfig, EscalationConfig, tier embedding in prompts |
| Modify | `.claude/skills/ai_bridge/augur/lib/crew_parser.py` | Parse tiers/safety/escalation, schema validation |
| Modify | `.claude/skills/ai_bridge/scripts/sync_agents/adapters/claude_code.py` | Full registry output |
| Create | `src/agents/performance_ledger.py` | Record, aggregate, compact |
| Modify | `apps/dashboard/lib/actions/types.ts` | Add `tier` field to ActionDef |
| Modify | `apps/dashboard/hooks/useActionRunner.ts` | Tier resolution + ledger write |
| Modify | `.claude/skills/advisor/scripts/mcp/__init__.py` | Telemetry reads from ledger |
| Modify | `.claude/skills/daemon/scripts/nightly_maintainer.py` | Add compaction step |
| Create | `tests/plugins/test_agent_tiers.py` | Unit tests for parser, generator, ledger |

---

## Task 1: Create JSON Schema for x-augur-agent

**Files:**
- Create: `src/config/schemas/agent-profile.schema.json`

- [ ] **Step 1: Create the schema file**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "x-augur-agent",
  "description": "Agent capability profile declared in SKILL.md frontmatter",
  "type": "object",
  "required": ["role"],
  "properties": {
    "role": { "enum": ["executor", "advisor", "orchestrator"] },
    "specialization": { "type": "string" },
    "default-model": { "enum": ["haiku", "sonnet", "opus"], "default": "sonnet" },
    "tools": {
      "type": "array",
      "items": { "enum": ["Read", "Edit", "Write", "Glob", "Grep", "Bash", "Agent", "Notebook"] }
    },
    "tiers": {
      "type": "object",
      "properties": {
        "fast": { "$ref": "#/$defs/tier" },
        "standard": { "$ref": "#/$defs/tier" },
        "deep": { "$ref": "#/$defs/tier" }
      },
      "additionalProperties": false
    },
    "safety": {
      "type": "object",
      "properties": {
        "max-file-edits-per-run": { "type": "integer", "minimum": 1 },
        "max-file-creates-per-run": { "type": "integer", "minimum": 0 },
        "max-bash-commands-per-run": { "type": "integer", "minimum": 1 },
        "banned-paths": { "type": "array", "items": { "type": "string" } },
        "require-confirmation": { "type": "array", "items": { "type": "string" } },
        "banned-operations": { "type": "array", "items": { "type": "string" } }
      }
    },
    "escalation": {
      "type": "object",
      "properties": {
        "auto-escalate-on": { "type": "array", "items": { "type": "string" } },
        "escalation-path": { "type": "string" },
        "max-escalations-per-task": { "type": "integer", "minimum": 0 },
        "cooldown": { "type": "integer", "minimum": 0 }
      }
    }
  },
  "$defs": {
    "tier": {
      "type": "object",
      "required": ["model"],
      "properties": {
        "model": { "enum": ["haiku", "sonnet", "opus"] },
        "tools": { "type": "array", "items": { "type": "string" } },
        "context-budget": { "type": "integer", "minimum": 1000 },
        "cost-multiplier": { "type": "number", "minimum": 0 },
        "appropriate-for": { "type": "array", "items": { "type": "string" } },
        "inappropriate-for": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
```

- [ ] **Step 2: Verify schema is valid JSON**

```bash
python -c "import json; json.load(open('src/config/schemas/agent-profile.schema.json'))"
```

- [ ] **Step 3: Commit**

```bash
git add src/config/schemas/agent-profile.schema.json
git commit -m "feat(agents): add JSON schema for x-augur-agent validation (ADR-460)"
```

---

## Task 2: Enrich 14 SKILL.md files with full tier/safety/escalation

**Files:**
- Modify: 14x `.claude/skills/*/SKILL.md`

- [ ] **Step 1: Define the tier templates**

**Executor template** (developer, devops, dev-build, dev-merge, dev-rollback, dev-test, dev-adr, frontend, mcp-app-factory, test-client):
```yaml
x-augur-agent:
  role: executor
  specialization: "<per-agent>"
  default-model: sonnet
  tools: [Read, Edit, Write, Glob, Grep, Bash]
  tiers:
    fast:
      model: haiku
      tools: [Read, Glob, Grep]
      context-budget: 32000
      cost-multiplier: 0.1
      appropriate-for: [simple lookups, file checks, pattern searches]
    standard:
      model: sonnet
      tools: [Read, Edit, Write, Glob, Grep, Bash]
      context-budget: 128000
      cost-multiplier: 1.0
      appropriate-for: [implementation, bug fixes, test writing]
    deep:
      model: opus
      tools: [Read, Edit, Write, Glob, Grep, Bash]
      context-budget: 200000
      cost-multiplier: 5.0
      appropriate-for: [architecture, complex debugging, cross-system refactoring]
  safety:
    max-file-edits-per-run: 20
    max-file-creates-per-run: 5
    max-bash-commands-per-run: 30
    banned-paths: ["**/.env*", "**/credentials*", "**/secrets*"]
    require-confirmation: ["config/**", "CLAUDE.md"]
    banned-operations: ["git push --force", "rm -rf /"]
  escalation:
    auto-escalate-on: ["3 consecutive failures", "context budget exceeded"]
    escalation-path: fast -> standard -> deep -> parent
    max-escalations-per-task: 2
    cooldown: 300
```

**Advisor template** (advisor, test-ui):
```yaml
  tiers:
    fast:
      model: haiku
      tools: [Read, Glob, Grep]
      context-budget: 16000
      cost-multiplier: 0.1
    standard:
      model: sonnet
      tools: [Read, Glob, Grep]
      context-budget: 64000
      cost-multiplier: 1.0
  safety:
    max-file-edits-per-run: 0
    banned-paths: ["**/.env*"]
  escalation:
    auto-escalate-on: ["context budget exceeded"]
    escalation-path: fast -> standard -> parent
    max-escalations-per-task: 1
```

**Validator template** (deep by default):
```yaml
  tiers:
    standard:
      model: sonnet
      tools: [Read, Glob, Grep]
      context-budget: 64000
      cost-multiplier: 1.0
    deep:
      model: opus
      tools: [Read, Glob, Grep]
      context-budget: 200000
      cost-multiplier: 5.0
      appropriate-for: [security audits, architecture review, vulnerability analysis]
```

**Orchestrator template** (dev-debug):
```yaml
  tools: [Read, Edit, Write, Glob, Grep, Bash, Agent]
  tiers:
    standard:
      model: sonnet
      tools: [Read, Edit, Write, Glob, Grep, Bash, Agent]
      context-budget: 128000
    deep:
      model: opus
      tools: [Read, Edit, Write, Glob, Grep, Bash, Agent]
      context-budget: 200000
```

- [ ] **Step 2: Apply templates to all 14 SKILL.md files**

Read each SKILL.md, find existing `x-augur-agent` block, replace with the full template. Set `specialization` per agent:
- developer: "code generation, refactoring, and migration"
- devops: "CI/CD, environment setup, releases"
- dev-build: "build pipeline and cache management"
- dev-merge: "git workflow and merge operations"
- dev-debug: "multi-phase debugging and root cause analysis"
- dev-rollback: "safe rollback and recovery"
- dev-test: "test execution and coverage"
- dev-adr: "architecture decision record lifecycle"
- frontend: "React/Next.js/Tailwind UI implementation"
- mcp-app-factory: "plugin scaffolding and MCP wiring"
- test-client: "client test suite execution"
- advisor: "prompt quality and codebase analysis"
- test-ui: "browser-based UI observation and QA"
- validator: "security audits and compliance verification"

- [ ] **Step 3: Validate all 14 against schema**

```bash
python -c "
import json, yaml, jsonschema
from pathlib import Path
schema = json.load(open('src/config/schemas/agent-profile.schema.json'))
for p in sorted(Path('.claude/skills').glob('*/SKILL.md')):
    text = p.read_text()
    if 'x-augur-agent:' not in text: continue
    _, fm, _ = text.split('---', 2)
    data = yaml.safe_load(fm)
    agent = data.get('x-augur-agent')
    if agent:
        try:
            jsonschema.validate(agent, schema)
            print(f'  OK: {p.parent.name}')
        except jsonschema.ValidationError as e:
            print(f'FAIL: {p.parent.name}: {e.message}')
"
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/*/SKILL.md
git commit -m "feat(agents): add full tier/safety/escalation to 14 SKILL.md (ADR-460)"
```

---

## Task 3: Extend parser and generator for tiers/safety/escalation

**Files:**
- Modify: `.claude/skills/ai_bridge/augur/lib/subagent_profile.py`
- Modify: `.claude/skills/ai_bridge/augur/lib/crew_parser.py`

- [ ] **Step 1: Update SafetyConfig dataclass**

In `subagent_profile.py`, replace or extend `SafetyConfig`:

```python
@dataclass(frozen=True)
class SafetyConfig:
    max_file_edits: int = 20
    max_file_creates: int = 5
    max_bash_commands: int = 30
    banned_paths: tuple[str, ...] = ()
    require_confirmation: tuple[str, ...] = ()
    banned_operations: tuple[str, ...] = ()
    # Legacy fields (kept for backward compat)
    read_only: bool = False
    circuit_breaker_max_failures: int = 3
    circuit_breaker_action: str = "escalate_to_human"
```

- [ ] **Step 2: Add EscalationConfig dataclass**

```python
@dataclass(frozen=True)
class EscalationConfig:
    auto_escalate_on: tuple[str, ...] = ()
    escalation_path: str = "fast -> standard -> deep -> parent"
    max_escalations: int = 2
    cooldown_seconds: int = 300
```

- [ ] **Step 3: Update _build_profile in crew_parser.py to parse full blocks**

Parse the new sub-keys from `x-augur-agent`:

```python
agent_data = fm.get("x-augur-agent") or {}

# Tiers
tiers_raw = agent_data.get("tiers", {})
tiers = {}
for tier_name, tier_data in tiers_raw.items():
    tiers[tier_name] = TierProfile(
        capability=tier_name,
        mode=ROLE_TO_CLAUDE_MODE.get(agent_data.get("role", "advisor"), "plan"),
        tools=tier_data.get("tools", agent_tools),
        model_id=CAPABILITY_TO_MODEL_ID.get({"fast":"fast","standard":"balanced","deep":"reasoning"}.get(tier_name,"balanced"), ""),
        max_files=tier_data.get("context-budget", 128000),
        use_cases=tier_data.get("appropriate-for", []),
        escalate_when=tier_data.get("inappropriate-for", []),
    )

# Safety
safety_raw = agent_data.get("safety", {})
safety = SafetyConfig(
    max_file_edits=safety_raw.get("max-file-edits-per-run", 20),
    max_file_creates=safety_raw.get("max-file-creates-per-run", 5),
    max_bash_commands=safety_raw.get("max-bash-commands-per-run", 30),
    banned_paths=tuple(safety_raw.get("banned-paths", [])),
    require_confirmation=tuple(safety_raw.get("require-confirmation", [])),
    banned_operations=tuple(safety_raw.get("banned-operations", [])),
)

# Escalation
esc_raw = agent_data.get("escalation", {})
escalation = EscalationConfig(
    auto_escalate_on=tuple(esc_raw.get("auto-escalate-on", [])),
    escalation_path=esc_raw.get("escalation-path", "fast -> standard -> deep -> parent"),
    max_escalations=esc_raw.get("max-escalations-per-task", 2),
    cooldown_seconds=esc_raw.get("cooldown", 300),
)
```

- [ ] **Step 4: Add schema validation to _build_profile**

```python
try:
    import jsonschema
    schema_path = Path(__file__).resolve().parents[5] / "src" / "config" / "schemas" / "agent-profile.schema.json"
    if schema_path.exists():
        schema = json.loads(schema_path.read_text())
        jsonschema.validate(agent_data, schema)
except jsonschema.ValidationError as e:
    logger.warning("x-augur-agent validation failed in %s: %s", skill_name, e.message)
except ImportError:
    pass  # jsonschema not installed
```

- [ ] **Step 5: Update to_agent_markdown() to embed safety and escalation**

In the generated agent .md, after the tools section, add:

```python
# Safety constraints
if self.safety and (self.safety.banned_paths or self.safety.banned_operations):
    lines.append("\n## Safety Constraints")
    lines.append(f"- Maximum {self.safety.max_file_edits} file edits per run")
    lines.append(f"- Maximum {self.safety.max_file_creates} file creates per run")
    if self.safety.banned_paths:
        lines.append("- NEVER modify files matching: " + ", ".join(f"`{p}`" for p in self.safety.banned_paths))
    if self.safety.require_confirmation:
        lines.append("- ASK before modifying: " + ", ".join(f"`{p}`" for p in self.safety.require_confirmation))
    if self.safety.banned_operations:
        lines.append("- NEVER execute: " + ", ".join(f"`{c}`" for c in self.safety.banned_operations))

# Escalation rules
if self.escalation and self.escalation.auto_escalate_on:
    lines.append("\n## Escalation Rules")
    lines.append(f"- Path: {self.escalation.escalation_path}")
    lines.append(f"- Auto-escalate when: {', '.join(self.escalation.auto_escalate_on)}")
    lines.append(f"- Maximum {self.escalation.max_escalations} escalations per task")
```

- [ ] **Step 6: Update to_registry_entry() to include full data**

```python
def to_registry_entry(self) -> dict:
    entry = {
        "role": self.agent_role or "advisor",
        "defaultModel": self.agent_default_model or "sonnet",
        "tools": self.agent_tools or ["Read", "Glob", "Grep"],
        "tiers": {
            name: {
                "model": tp.model_id,
                "tools": tp.tools,
                "contextBudget": tp.max_files,
                "costMultiplier": getattr(tp, 'cost_multiplier', 1.0),
                "appropriateFor": tp.use_cases,
            }
            for name, tp in self.tiers.items()
        } if self.tiers else {},
        "safety": {
            "maxFileEdits": self.safety.max_file_edits,
            "bannedPaths": list(self.safety.banned_paths),
            "bannedOperations": list(self.safety.banned_operations),
        } if self.safety and self.safety.banned_paths else {},
        "escalation": {
            "path": self.escalation.escalation_path,
            "maxEscalations": self.escalation.max_escalations,
        } if self.escalation and self.escalation.auto_escalate_on else {},
    }
    return entry
```

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/ai_bridge/augur/lib/subagent_profile.py .claude/skills/ai_bridge/augur/lib/crew_parser.py
git commit -m "feat(agents): parse and generate full tier/safety/escalation (ADR-460)"
```

---

## Task 4: Create performance ledger

**Files:**
- Create: `src/agents/performance_ledger.py`

- [ ] **Step 1: Create the module**

```python
"""Performance ledger for agent task tracking (ADR-460)."""
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.config.paths import get_state_dir


def _ledger_path() -> Path:
    return get_state_dir() / "agents" / "performance.json"


@dataclass
class TaskRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent: str = ""
    tier: str = "standard"
    model: str = "sonnet"
    tokens_in: int = 0
    tokens_out: int = 0
    duration_seconds: float = 0.0
    files_edited: int = 0
    files_created: int = 0
    outcome: str = "unknown"  # success | failure | escalated | timeout
    task_signals: list[str] = field(default_factory=list)
    escalated_from: str | None = None


def record_task(record: TaskRecord) -> None:
    """Append a task record and update aggregates."""
    path = _ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = _load(path)
    data["records"].append(asdict(record))
    _update_aggregates(data, record)
    _save(path, data)


def get_aggregates() -> dict[str, Any]:
    """Return per-agent per-tier aggregates."""
    data = _load(_ledger_path())
    return data.get("aggregates", {})


def compact(max_age_days: int = 30, max_size_mb: float = 10.0) -> int:
    """Roll old records into aggregates, enforce size cap. Returns records removed."""
    path = _ledger_path()
    if not path.exists():
        return 0

    data = _load(path)
    cutoff = (datetime.now() - timedelta(days=max_age_days)).isoformat()
    before = len(data["records"])

    # Keep only recent records
    data["records"] = [r for r in data["records"] if r.get("timestamp", "") >= cutoff]

    # Size cap: evict oldest if over limit
    serialized = json.dumps(data)
    while len(serialized) > max_size_mb * 1_000_000 and data["records"]:
        data["records"].pop(0)
        serialized = json.dumps(data)

    removed = before - len(data["records"])
    if removed > 0:
        _save(path, data)
    return removed


def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"records": [], "aggregates": {}}


def _save(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str))
    tmp.rename(path)


def _update_aggregates(data: dict, record: TaskRecord) -> None:
    key = f"{record.agent}:{record.tier}"
    aggs = data.setdefault("aggregates", {})
    agg = aggs.get(key, {"total_tasks": 0, "successes": 0, "total_tokens": 0, "total_duration": 0.0})

    agg["total_tasks"] += 1
    if record.outcome == "success":
        agg["successes"] += 1
    agg["total_tokens"] += record.tokens_in + record.tokens_out
    agg["total_duration"] += record.duration_seconds
    agg["success_rate"] = round(agg["successes"] / agg["total_tasks"], 3) if agg["total_tasks"] else 0
    agg["avg_tokens"] = agg["total_tokens"] // agg["total_tasks"] if agg["total_tasks"] else 0
    agg["avg_duration"] = round(agg["total_duration"] / agg["total_tasks"], 2) if agg["total_tasks"] else 0
    agg["last_updated"] = datetime.now().isoformat()
    aggs[key] = agg
```

- [ ] **Step 2: Verify it runs**

```bash
python -c "
from src.agents.performance_ledger import TaskRecord, record_task, get_aggregates, compact
r = TaskRecord(agent='developer', tier='standard', model='sonnet', outcome='success', duration_seconds=5.0, tokens_in=1000)
record_task(r)
print(get_aggregates())
print('Compacted:', compact())
"
```

- [ ] **Step 3: Commit**

```bash
mkdir -p src/agents && git add src/agents/performance_ledger.py
git commit -m "feat(agents): create performance ledger module (ADR-460)"
```

---

## Task 5: Wire tier routing into useActionRunner

**Files:**
- Modify: `apps/dashboard/lib/actions/types.ts`
- Modify: `apps/dashboard/hooks/useActionRunner.ts`

- [ ] **Step 1: Add tier field to ActionDef**

In `types.ts`, add to the `ActionDef` interface:

```typescript
tier?: "fast" | "standard" | "deep";
```

- [ ] **Step 2: Add tier resolution function in useActionRunner**

```typescript
function resolveTier(action: ActionDef): "fast" | "standard" | "deep" {
  // Explicit tier from action config
  if (action.tier) return action.tier;

  // Keyword-based static routing
  const signals = [action.id, action.label, action.description || ""].join(" ").toLowerCase();
  if (/quick.?check|lookup|search|status/.test(signals)) return "fast";
  if (/refactor|architect|debug.?complex|security|audit/.test(signals)) return "deep";
  return "standard";
}
```

- [ ] **Step 3: Pass tier to dispatch functions**

In the `runIde()` and `runApi()` functions, include tier in the prompt context:

```typescript
const tier = resolveTier(action);
// Include in prompt: `[Tier: ${tier}]`
```

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/lib/actions/types.ts apps/dashboard/hooks/useActionRunner.ts
git commit -m "feat(agents): add tier routing to useActionRunner (ADR-460)"
```

---

## Task 6: Wire ledger collection into useActionRunner

**Files:**
- Modify: `apps/dashboard/hooks/useActionRunner.ts`

- [ ] **Step 1: Add completion callback that writes to ledger**

After each dispatch completes, POST to a ledger API:

```typescript
async function recordTaskCompletion(
  agent: string,
  tier: string,
  outcome: "success" | "failure" | "timeout",
  durationMs: number,
) {
  try {
    await fetch("/api/agents/telemetry/record", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent, tier, outcome, duration_seconds: durationMs / 1000 }),
    });
  } catch {
    // Best-effort — don't block action on ledger write
  }
}
```

- [ ] **Step 2: Call recordTaskCompletion in dispatch completion paths**

Wrap each dispatch case with timing and outcome tracking.

- [ ] **Step 3: Commit**

```bash
git add apps/dashboard/hooks/useActionRunner.ts
git commit -m "feat(agents): wire performance ledger collection (ADR-460)"
```

---

## Task 7: Update telemetry endpoint and nightly compaction

**Files:**
- Modify: `.claude/skills/advisor/scripts/mcp/__init__.py` (get-agent-telemetry tool)
- Modify: `.claude/skills/daemon/scripts/nightly_maintainer.py`

- [ ] **Step 1: Update get-agent-telemetry MCP tool to read ledger**

In the tool implementation, import and use the ledger:

```python
from src.agents.performance_ledger import get_aggregates

aggregates = get_aggregates()
# Return aggregates alongside existing telemetry data
```

- [ ] **Step 2: Add compaction to nightly maintainer**

In `nightly_maintainer.py`, add after `prune_stale_sessions()`:

```python
def compact_performance_ledger():
    """Roll old agent performance records into aggregates."""
    try:
        from src.agents.performance_ledger import compact
        removed = compact(max_age_days=30)
        logger.info("Performance ledger: compacted %d old records", removed)
    except Exception as e:
        logger.warning("Performance ledger compaction failed: %s", e)
```

Call it in `main()`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/advisor/scripts/mcp/__init__.py .claude/skills/daemon/scripts/nightly_maintainer.py
git commit -m "feat(agents): wire telemetry to ledger + nightly compaction (ADR-460)"
```

---

## Task 8: Regenerate agents and run full verification

- [ ] **Step 1: Run sync_agents**

```bash
python -m skills.ai.scripts.sync_agents sync agents all
```

- [ ] **Step 2: Verify generated agent files**

Check that `developer.md` has Safety Constraints and Escalation Rules sections:
```bash
grep -c "Safety Constraints\|Escalation Rules\|banned-paths\|max-file-edits" .claude/agents/developer.md
```
Expected: >= 3 matches.

Check that `advisor.md` does NOT have write tools:
```bash
grep "Edit\|Write\|Bash" .claude/agents/advisor.md
```
Expected: 0 matches.

Check that `registry.json` has populated tiers:
```bash
python -c "import json; r=json.load(open('.claude/agents/registry.json')); print('tiers' in r['agents']['developer'] and len(r['agents']['developer']['tiers']) > 0)"
```
Expected: `True`.

- [ ] **Step 3: Commit generated files**

```bash
git add .claude/agents/
git commit -m "chore: regenerate agents with full tier/safety/escalation (ADR-460)"
```

---

## Task 9: Tests

**Files:**
- Create: `tests/plugins/test_agent_tiers.py`

- [ ] **Step 1: Write tests for parser, generator, and ledger**

```python
"""Tests for ADR-460 agent tier operationalization."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from src.agents.performance_ledger import TaskRecord, record_task, get_aggregates, compact


class TestPerformanceLedger:
    def test_record_and_aggregate(self, tmp_path):
        with patch("src.agents.performance_ledger._ledger_path", return_value=tmp_path / "perf.json"):
            record_task(TaskRecord(agent="dev", tier="standard", outcome="success", tokens_in=1000))
            record_task(TaskRecord(agent="dev", tier="standard", outcome="success", tokens_in=2000))
            record_task(TaskRecord(agent="dev", tier="standard", outcome="failure", tokens_in=500))
            aggs = get_aggregates()
            assert "dev:standard" in aggs
            assert aggs["dev:standard"]["total_tasks"] == 3
            assert aggs["dev:standard"]["successes"] == 2

    def test_compact_removes_old(self, tmp_path):
        with patch("src.agents.performance_ledger._ledger_path", return_value=tmp_path / "perf.json"):
            record_task(TaskRecord(agent="dev", tier="fast", outcome="success"))
            removed = compact(max_age_days=0)  # Compact everything
            assert removed == 1

    def test_compact_empty_ledger(self, tmp_path):
        with patch("src.agents.performance_ledger._ledger_path", return_value=tmp_path / "perf.json"):
            assert compact() == 0


class TestSchemaValidation:
    def test_valid_executor_profile(self):
        import jsonschema
        schema = json.loads((Path("src/config/schemas/agent-profile.schema.json")).read_text())
        profile = {
            "role": "executor",
            "default-model": "sonnet",
            "tools": ["Read", "Edit", "Write"],
            "tiers": {
                "fast": {"model": "haiku", "context-budget": 32000},
                "standard": {"model": "sonnet", "context-budget": 128000},
            },
            "safety": {"max-file-edits-per-run": 20, "banned-paths": [".env*"]},
        }
        jsonschema.validate(profile, schema)  # Should not raise

    def test_invalid_role_rejected(self):
        import jsonschema
        schema = json.loads((Path("src/config/schemas/agent-profile.schema.json")).read_text())
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({"role": "invalid"}, schema)
```

- [ ] **Step 2: Run tests**

```bash
pytest tests/plugins/test_agent_tiers.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/plugins/test_agent_tiers.py
git commit -m "test(agents): add ADR-460 tier/safety/ledger tests"
```

---

## Task 10: Update ADR status to Implemented

- [ ] **Step 1: Update ADR frontmatter**

Change `status: Proposed` to `status: Implemented` in `get_vault_dir()/dev/adrs/ADR-460-agent-tier-operationalization.md`.

- [ ] **Step 2: Commit**

Not a repo file — vault only. No git commit needed.

---

## Verification Checklist

- [ ] All 14 SKILL.md have `tiers`, `safety`, `escalation` in `x-augur-agent`
- [ ] Schema validation passes for all 14
- [ ] Generated `.claude/agents/developer.md` has Safety Constraints + Escalation Rules sections
- [ ] Generated `.claude/agents/advisor.md` has read-only tools only
- [ ] `registry.json` schema 2.0 with populated tiers/safety/escalation per agent
- [ ] `performance_ledger.py` records tasks and computes aggregates
- [ ] Nightly compaction registered in daemon
- [ ] `useActionRunner` resolves tier from action metadata
- [ ] `get-agent-telemetry` returns ledger aggregates
- [ ] Tests pass: `pytest tests/plugins/test_agent_tiers.py -v`
- [ ] Backward compat: skills without `x-augur-agent` generate unchanged output
