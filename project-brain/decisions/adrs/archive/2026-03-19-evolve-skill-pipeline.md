# Evolve Skill Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `/evolve` — a thin orchestrator skill in augur-ops that guides users from problem description to verified, working skill via an 8-step pipeline.

**Architecture:** Claude Code-mastered skill at `.claude/skills/evolve/`. Pipeline orchestration lives in SKILL.md instructions (Claude Code follows them conversationally). MCP tools provide state persistence (so dashboard can display pipeline progress) and a classify-problem tool (semantic matching). All other pipeline steps delegate to existing skills' MCP tools (import, skillstore, mcp-app-factory, discovery).

**Tech Stack:** Python (MCP tools, state persistence), YAML (pipeline state, ADR-450 templates), Markdown (SKILL.md instructions)

**Spec:** `docs/superpowers/specs/2026-03-19-evolve-skill-pipeline-design.md`

**Prerequisites (assumed done):**
- ADR-454 `get_project_name()` / `get_state_dir()` implemented in `src/config/paths.py`
- ADR-450 template resolver implemented in `plugins/ui/`
- mcp-app-factory scaffold emits SKILL.md frontmatter (not augur.yaml)

---

## File Structure

```
.claude/skills/evolve/
├── SKILL.md                              # Frontmatter + orchestration instructions
├── scripts/
│   └── mcp/
│       └── __init__.py                   # MCP tool registrations (state CRUD + classify)
├── augur/
│   ├── lib/
│   │   ├── __init__.py
│   │   ├── pipeline_state.py             # Pipeline data model + YAML persistence
│   │   └── classifier.py                 # Semantic skill matching logic
│   └── tests/
│       ├── conftest.py                   # Shared fixtures
│       ├── test_pipeline_state.py        # State model + persistence tests
│       └── test_classifier.py            # Classification logic tests
└── assets/
    └── seeds/
        └── _seed.yaml                    # Empty seed manifest
```

**Existing files modified:**
- None. This is a new skill. Existing skills (import, skillstore, mcp-app-factory, discovery) are called via MCP tools — no code changes needed in them.

---

### Task 1: Pipeline State Model

Core data model for pipeline state — the foundation everything else builds on.

**Files:**
- Create: `.claude/skills/evolve/augur/lib/__init__.py`
- Create: `.claude/skills/evolve/augur/lib/pipeline_state.py`
- Create: `.claude/skills/evolve/augur/tests/conftest.py`
- Create: `.claude/skills/evolve/augur/tests/test_pipeline_state.py`

- [ ] **Step 1: Write the failing tests for pipeline data model**

```python
# .claude/skills/evolve/augur/tests/test_pipeline_state.py
"""Tests for pipeline state model and persistence."""
import pytest
from pathlib import Path

from pipeline_state import (
    PipelineState,
    StepName,
    StepStatus,
    create_pipeline,
    load_pipeline,
    save_pipeline,
    list_pipelines,
)


class TestPipelineState:
    """Tests for the PipelineState dataclass."""

    def test_create_pipeline_from_chat(self):
        p = create_pipeline(
            entry_point="chat",
            problem_statement="Track home renovation projects",
        )
        assert p.entry_point == "chat"
        assert p.problem_statement == "Track home renovation projects"
        assert p.current_step == StepName.INTAKE
        assert p.steps[StepName.INTAKE].status == StepStatus.PENDING
        assert p.id.startswith("evolve-")

    def test_create_pipeline_from_collateral(self):
        p = create_pipeline(
            entry_point="collateral",
            problem_statement="Meal planning",
            collateral=[{"path": "/tmp/meals.pdf", "type": "pdf"}],
        )
        assert p.collateral[0]["path"] == "/tmp/meals.pdf"

    def test_create_pipeline_from_skill(self):
        p = create_pipeline(
            entry_point="skill",
            problem_statement="Custom skill",
            provided_skill="/tmp/SKILL.md",
        )
        assert p.provided_skill == "/tmp/SKILL.md"

    def test_advance_step(self):
        p = create_pipeline(entry_point="chat", problem_statement="test")
        p.complete_step(StepName.INTAKE, output={"summary": "test problem"})
        assert p.steps[StepName.INTAKE].status == StepStatus.COMPLETED
        assert p.current_step == StepName.CLASSIFY

    def test_complete_wrong_step_raises(self):
        p = create_pipeline(entry_point="chat", problem_statement="test")
        # current_step is INTAKE, trying to complete VERIFY should raise
        with pytest.raises(ValueError, match="Cannot complete step"):
            p.complete_step(StepName.VERIFY, output={})

    def test_skip_step(self):
        p = create_pipeline(entry_point="skill", problem_statement="test")
        p.skip_step(StepName.SEARCH, reason="SKILL.md provided")
        assert p.steps[StepName.SEARCH].status == StepStatus.SKIPPED

    def test_fail_step(self):
        p = create_pipeline(entry_point="chat", problem_statement="test")
        p.fail_step(StepName.INTAKE, error="MCP tool health check failed")
        assert p.steps[StepName.INTAKE].status == StepStatus.FAILED
        assert p.steps[StepName.INTAKE].error == "MCP tool health check failed"


class TestPipelinePersistence:
    """Tests for YAML state file read/write."""

    def test_save_and_load_roundtrip(self, tmp_path):
        p = create_pipeline(entry_point="chat", problem_statement="test project")
        p.complete_step(StepName.INTAKE, output={"summary": "test"})
        save_pipeline(p, state_dir=tmp_path)

        loaded = load_pipeline(p.id, state_dir=tmp_path)
        assert loaded.id == p.id
        assert loaded.problem_statement == "test project"
        assert loaded.current_step == StepName.CLASSIFY
        assert loaded.steps[StepName.INTAKE].status == StepStatus.COMPLETED

    def test_list_pipelines(self, tmp_path):
        p1 = create_pipeline(entry_point="chat", problem_statement="first")
        p2 = create_pipeline(entry_point="chat", problem_statement="second")
        save_pipeline(p1, state_dir=tmp_path)
        save_pipeline(p2, state_dir=tmp_path)

        pipelines = list_pipelines(state_dir=tmp_path)
        assert len(pipelines) == 2

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_pipeline("nonexistent-id", state_dir=tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd .claude/skills/evolve && python -m pytest augur/tests/test_pipeline_state.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline_state'`

- [ ] **Step 3: Implement pipeline state model**

```python
# .claude/skills/evolve/augur/lib/__init__.py
# (empty — marks as package)
```

```python
# .claude/skills/evolve/augur/lib/pipeline_state.py
"""Pipeline state model and YAML persistence for /evolve."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml


class StepName(str, Enum):
    INTAKE = "intake"
    CLASSIFY = "classify"
    SEARCH = "search"
    SCAFFOLD = "scaffold"
    ENRICH = "enrich"
    WIRE = "wire"
    VERIFY = "verify"
    PAGE = "page"


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


# Ordered sequence — determines next step after completion
STEP_ORDER = list(StepName)


@dataclass
class StepState:
    status: StepStatus = StepStatus.PENDING
    output: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class PipelineState:
    id: str
    entry_point: str  # "chat" | "collateral" | "skill"
    problem_statement: str
    current_step: StepName
    steps: dict[StepName, StepState]
    collateral: list[dict[str, Any]] = field(default_factory=list)
    provided_skill: Optional[str] = None
    classification: Optional[dict[str, Any]] = None
    created_at: str = ""
    completed_at: Optional[str] = None

    def complete_step(self, step: StepName, output: dict[str, Any] | None = None) -> None:
        if step != self.current_step:
            raise ValueError(
                f"Cannot complete step '{step.value}' — current step is '{self.current_step.value}'"
            )
        self.steps[step].status = StepStatus.COMPLETED
        self.steps[step].output = output or {}
        self.steps[step].completed_at = _now()
        self._advance()

    def skip_step(self, step: StepName, reason: str = "") -> None:
        self.steps[step].status = StepStatus.SKIPPED
        self.steps[step].output = {"reason": reason}
        if step == self.current_step:
            self._advance()

    def fail_step(self, step: StepName, error: str) -> None:
        self.steps[step].status = StepStatus.FAILED
        self.steps[step].error = error

    def _advance(self) -> None:
        idx = STEP_ORDER.index(self.current_step)
        for next_step in STEP_ORDER[idx + 1:]:
            if self.steps[next_step].status == StepStatus.PENDING:
                self.current_step = next_step
                return
        self.completed_at = _now()


def create_pipeline(
    entry_point: str,
    problem_statement: str,
    collateral: list[dict[str, Any]] | None = None,
    provided_skill: str | None = None,
) -> PipelineState:
    return PipelineState(
        id=f"evolve-{uuid.uuid4().hex[:8]}",
        entry_point=entry_point,
        problem_statement=problem_statement,
        current_step=StepName.INTAKE,
        steps={step: StepState() for step in StepName},
        collateral=collateral or [],
        provided_skill=provided_skill,
        created_at=_now(),
    )


def save_pipeline(pipeline: PipelineState, state_dir: Path) -> Path:
    evolve_dir = state_dir / "evolve"
    evolve_dir.mkdir(parents=True, exist_ok=True)
    path = evolve_dir / f"{pipeline.id}.yaml"
    path.write_text(yaml.dump(_to_dict(pipeline), default_flow_style=False), encoding="utf-8")
    return path


def load_pipeline(pipeline_id: str, state_dir: Path) -> PipelineState:
    path = state_dir / "evolve" / f"{pipeline_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Pipeline not found: {pipeline_id}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _from_dict(data)


def list_pipelines(state_dir: Path) -> list[PipelineState]:
    evolve_dir = state_dir / "evolve"
    if not evolve_dir.exists():
        return []
    pipelines = []
    for path in sorted(evolve_dir.glob("evolve-*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        pipelines.append(_from_dict(data))
    return pipelines


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_dict(p: PipelineState) -> dict:
    return {
        "id": p.id,
        "entry_point": p.entry_point,
        "problem_statement": p.problem_statement,
        "current_step": p.current_step.value,
        "steps": {
            step.value: {
                "status": state.status.value,
                "output": state.output,
                "error": state.error,
                "started_at": state.started_at,
                "completed_at": state.completed_at,
            }
            for step, state in p.steps.items()
        },
        "collateral": p.collateral,
        "provided_skill": p.provided_skill,
        "classification": p.classification,
        "created_at": p.created_at,
        "completed_at": p.completed_at,
    }


def _from_dict(data: dict) -> PipelineState:
    steps = {}
    for step_name in StepName:
        step_data = data.get("steps", {}).get(step_name.value, {})
        steps[step_name] = StepState(
            status=StepStatus(step_data.get("status", "pending")),
            output=step_data.get("output", {}),
            error=step_data.get("error"),
            started_at=step_data.get("started_at"),
            completed_at=step_data.get("completed_at"),
        )
    return PipelineState(
        id=data["id"],
        entry_point=data["entry_point"],
        problem_statement=data["problem_statement"],
        current_step=StepName(data["current_step"]),
        steps=steps,
        collateral=data.get("collateral", []),
        provided_skill=data.get("provided_skill"),
        classification=data.get("classification"),
        created_at=data.get("created_at", ""),
        completed_at=data.get("completed_at"),
    )
```

- [ ] **Step 4: Create conftest with sys.path setup**

```python
# .claude/skills/evolve/augur/tests/conftest.py
"""Pytest configuration for evolve skill tests."""
import sys
from pathlib import Path

# Add lib directory to path so tests can import modules directly
_lib_dir = str(Path(__file__).resolve().parent.parent / "lib")
if _lib_dir not in sys.path:
    sys.path.insert(0, _lib_dir)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd .claude/skills/evolve && python -m pytest augur/tests/test_pipeline_state.py -v
```

Expected: all 9 tests PASS

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/evolve/augur/
git commit -m "feat(evolve): pipeline state model with YAML persistence"
```

---

### Task 2: Classifier — Semantic Skill Matching

The classify step needs to score installed skills against a problem statement using the skill registry.

**Files:**
- Create: `.claude/skills/evolve/augur/lib/classifier.py`
- Create: `.claude/skills/evolve/augur/tests/test_classifier.py`

- [ ] **Step 1: Write failing tests for classifier**

```python
# .claude/skills/evolve/augur/tests/test_classifier.py
"""Tests for semantic skill classification."""
import pytest

from classifier import classify_problem, SkillMatch


class TestClassifyProblem:
    """Tests for the classify_problem function."""

    def test_returns_list_of_skill_matches(self):
        # Uses actual skill registry — integration test
        results = classify_problem("track my daily habits and routines")
        assert isinstance(results, list)
        for match in results:
            assert isinstance(match, SkillMatch)
            assert 0.0 <= match.confidence <= 1.0
            assert match.skill_id
            assert match.description

    def test_results_sorted_by_confidence_descending(self):
        results = classify_problem("manage job applications and interviews")
        if len(results) >= 2:
            for i in range(len(results) - 1):
                assert results[i].confidence >= results[i + 1].confidence

    def test_empty_problem_returns_empty(self):
        results = classify_problem("")
        assert results == []

    def test_skill_match_has_gap_analysis(self):
        results = classify_problem("track expenses and budget for home renovation")
        if results:
            # Gap analysis is optional but should be a string when present
            assert isinstance(results[0].gap, str)

    def test_matching_with_injected_skills(self):
        """Verify matching logic with known data — not dependent on installed skills."""
        from dataclasses import dataclass

        @dataclass
        class FakeSkill:
            id: str = "test-habit-tracker"
            display_name: str = "Habit Tracker"
            description: str = "track daily habits and exercise routines"
            triggers: tuple = ("habits", "exercise", "tracking")
            path: object = None

        fake_skills = [FakeSkill()]
        results = classify_problem("track my daily habits", skills=fake_skills)
        assert len(results) >= 1
        assert results[0].skill_id == "test-habit-tracker"
        assert results[0].confidence > 0.0

    def test_no_match_with_unrelated_skills(self):
        """Verify low-relevance skills are filtered out."""
        from dataclasses import dataclass

        @dataclass
        class FakeSkill:
            id: str = "astronomy"
            display_name: str = "Astronomy"
            description: str = "observe planets and track celestial events"
            triggers: tuple = ("planets", "telescope", "stars")
            path: object = None

        results = classify_problem("manage job applications", skills=[FakeSkill()])
        assert len(results) == 0  # No token overlap
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd .claude/skills/evolve && python -m pytest augur/tests/test_classifier.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'classifier'`

- [ ] **Step 3: Implement classifier**

```python
# .claude/skills/evolve/augur/lib/classifier.py
"""Semantic skill matching — scores installed skills against a problem statement.

Uses keyword overlap and description similarity as a lightweight classifier.
Does NOT call an LLM — the IDE agent handles natural-language reasoning.
This provides structured data for the agent to present to the user.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class SkillMatch:
    skill_id: str
    display_name: str
    description: str
    confidence: float
    gap: str  # What the problem asks for that the skill doesn't cover
    path: Optional[str] = None


def classify_problem(problem: str, skills: list | None = None) -> list[SkillMatch]:
    """Score all installed skills against a problem statement.

    Args:
        problem: Natural language problem description.
        skills: Optional list of SkillMetadata objects. If None, loads from registry.

    Returns matches sorted by confidence (descending), filtered to >0.1.
    """
    if not problem.strip():
        return []

    if skills is None:
        try:
            from src.plugins.skill_registry import list_skills
            skills = list_skills()
        except ImportError:
            return []

    problem_tokens = _tokenize(problem)
    if not problem_tokens:
        return []

    matches = []
    for skill in skills:
        desc_tokens = _tokenize(skill.description)
        trigger_tokens = set()
        for t in skill.triggers:
            trigger_tokens.update(_tokenize(t))
        all_skill_tokens = desc_tokens | trigger_tokens

        overlap = problem_tokens & all_skill_tokens
        if not overlap:
            continue

        confidence = len(overlap) / max(len(problem_tokens), 1)
        confidence = min(confidence, 1.0)

        if confidence < 0.1:
            continue

        missing = problem_tokens - all_skill_tokens
        gap = f"Not covered: {', '.join(sorted(missing))}" if missing else ""

        matches.append(SkillMatch(
            skill_id=skill.id,
            display_name=skill.display_name,
            description=skill.description,
            confidence=round(confidence, 2),
            gap=gap,
            path=str(skill.path) if skill.path else None,
        ))

    matches.sort(key=lambda m: m.confidence, reverse=True)
    return matches


# Stopwords to exclude from matching
_STOPWORDS = frozenset(
    "a an the and or but in on at to for of is it my i we you with from by"
    " this that be have do will can would should".split()
)


def _tokenize(text: str) -> set[str]:
    """Extract lowercase word tokens, excluding stopwords."""
    words = set(re.findall(r"[a-z]+", text.lower()))
    return words - _STOPWORDS
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd .claude/skills/evolve && python -m pytest augur/tests/test_classifier.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/evolve/augur/lib/classifier.py .claude/skills/evolve/augur/tests/test_classifier.py
git commit -m "feat(evolve): keyword-based skill classifier with gap analysis"
```

---

### Task 3: MCP Tool Registrations

Register 4 MCP tools: `get-evolve-pipelines`, `get-evolve-pipeline-detail`, `evolve-step-action` (supports create/complete/skip/fail/resume actions), `classify-problem`.

**Files:**
- Create: `.claude/skills/evolve/scripts/mcp/__init__.py`

- [ ] **Step 1: Implement MCP tool registrations**

```python
# .claude/skills/evolve/scripts/mcp/__init__.py
"""Evolve — Pipeline orchestration MCP tools.

Provides state persistence for the /evolve pipeline and a classify-problem
tool for semantic skill matching. Loaded dynamically by the Augur MCP server.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

try:
    from augur_mcp.logging import get_entity_logger
    from augur_mcp.annotations import tool_annotations
    from augur_mcp.config import get_project_root
except ImportError:
    import importlib

    def get_entity_logger(name: str):
        return importlib.import_module("logging").getLogger(name)

    def tool_annotations(annotations: dict) -> dict:
        return annotations

    def get_project_root() -> Path:
        data_dir = os.environ.get("AUGUR_ROOT")
        if data_dir:
            return Path(data_dir)
        inferred = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
        if (inferred / "src").exists():
            return inferred
        raise FileNotFoundError("Project root not found. Set AUGUR_ROOT.")


logger = get_entity_logger("mcp.evolve")

_SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
_LIB_DIR = str(_SKILL_ROOT / "augur" / "lib")


def _ensure_lib_path() -> None:
    if _LIB_DIR not in sys.path:
        sys.path.insert(0, _LIB_DIR)


def _get_state_dir() -> Path:
    try:
        from src.config.paths import get_state_dir
        return get_state_dir()
    except ImportError:
        # Fallback for development/testing
        return Path.home() / "Library" / "Application Support" / "Augur" / "state"


def register_tools(
    mcp: "FastMCP",
    mcp_tool_interceptor: Callable[..., Any],
    metrics: Any,
) -> None:
    """Register evolve MCP tools with the server."""
    logger.info("Registering evolve MCP tools...")

    @mcp.tool(
        name="get-evolve-pipelines",
        annotations=tool_annotations({
            "title": "List Evolve Pipelines",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def get_evolve_pipelines() -> str:
        """List all evolve pipelines (active and completed).

        Returns:
            JSON array of pipeline summaries with id, problem_statement,
            current_step, entry_point, created_at, completed_at.
        """
        metrics.track_tool("get_evolve_pipelines", skill="evolve")
        _ensure_lib_path()
        from pipeline_state import list_pipelines

        state_dir = _get_state_dir()
        pipelines = list_pipelines(state_dir)
        return json.dumps([
            {
                "id": p.id,
                "problem_statement": p.problem_statement,
                "entry_point": p.entry_point,
                "current_step": p.current_step.value,
                "created_at": p.created_at,
                "completed_at": p.completed_at,
            }
            for p in pipelines
        ], indent=2)

    @mcp.tool(
        name="get-evolve-pipeline-detail",
        annotations=tool_annotations({
            "title": "Get Evolve Pipeline Detail",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def get_evolve_pipeline_detail(pipeline_id: str) -> str:
        """Get full detail for a single evolve pipeline.

        Args:
            pipeline_id: The pipeline ID (e.g., 'evolve-a1b2c3d4')

        Returns:
            JSON with full pipeline state including all step details.
        """
        metrics.track_tool("get_evolve_pipeline_detail", skill="evolve")
        _ensure_lib_path()
        from pipeline_state import load_pipeline, _to_dict

        state_dir = _get_state_dir()
        pipeline = load_pipeline(pipeline_id, state_dir)
        return json.dumps(_to_dict(pipeline), indent=2)

    @mcp.tool(
        name="evolve-step-action",
        annotations=tool_annotations({
            "title": "Evolve Step Action",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def evolve_step_action(
        action: str,
        pipeline_id: str = "",
        step: str = "",
        entry_point: str = "",
        problem_statement: str = "",
        collateral_json: str = "",
        provided_skill: str = "",
        output_json: str = "",
        error: str = "",
    ) -> str:
        """Create a pipeline or submit a step action for an evolve pipeline.

        Args:
            action: One of 'create', 'complete', 'skip', 'fail', 'resume'
            pipeline_id: Pipeline ID (required for all actions except 'create')
            step: Step name (e.g., 'intake', 'classify'). Required for complete/skip/fail.
            entry_point: One of 'chat', 'collateral', 'skill' (for 'create')
            problem_statement: Problem description (for 'create')
            collateral_json: JSON array of collateral items (for 'create')
            provided_skill: Path to SKILL.md (for 'create')
            output_json: JSON string with step output data (for 'complete')
            error: Error message (for 'fail')

        Returns:
            JSON with pipeline state summary.
        """
        metrics.track_tool("evolve_step_action", skill="evolve")
        _ensure_lib_path()
        from pipeline_state import (
            create_pipeline, load_pipeline, save_pipeline, StepName,
        )

        state_dir = _get_state_dir()

        if action == "create":
            collateral = json.loads(collateral_json) if collateral_json else []
            pipeline = create_pipeline(
                entry_point=entry_point,
                problem_statement=problem_statement,
                collateral=collateral,
                provided_skill=provided_skill or None,
            )
            save_pipeline(pipeline, state_dir)
            return json.dumps({
                "id": pipeline.id,
                "current_step": pipeline.current_step.value,
                "created_at": pipeline.created_at,
            })

        pipeline = load_pipeline(pipeline_id, state_dir)
        step_name = StepName(step) if step else pipeline.current_step

        if action == "complete":
            output = json.loads(output_json) if output_json else {}
            pipeline.complete_step(step_name, output=output)
        elif action == "skip":
            pipeline.skip_step(step_name, reason=output_json or "skipped by user")
        elif action == "fail":
            pipeline.fail_step(step_name, error=error)
        elif action == "resume":
            pass  # Load + re-save; dashboard reads current state
        else:
            return json.dumps({"error": f"Unknown action: {action}"})

        save_pipeline(pipeline, state_dir)
        return json.dumps({
            "id": pipeline.id,
            "current_step": pipeline.current_step.value,
            "completed_at": pipeline.completed_at,
        })

    @mcp.tool(
        name="classify-problem",
        annotations=tool_annotations({
            "title": "Classify Problem Against Skills",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }),
    )
    @mcp_tool_interceptor
    async def classify_problem_tool(problem: str) -> str:
        """Score installed skills against a problem statement.

        Returns ranked matches with confidence scores and gap analysis.
        Used by the /evolve classify step.

        Args:
            problem: Natural language description of the problem to solve

        Returns:
            JSON array of skill matches sorted by confidence (descending).
        """
        metrics.track_tool("classify_problem", skill="evolve")
        _ensure_lib_path()
        from classifier import classify_problem

        matches = classify_problem(problem)  # loads from registry internally
        return json.dumps([
            {
                "skill_id": m.skill_id,
                "display_name": m.display_name,
                "description": m.description,
                "confidence": m.confidence,
                "gap": m.gap,
                "path": m.path,
            }
            for m in matches
        ], indent=2)
```

- [ ] **Step 2: Verify MCP module loads and has register_tools**

```bash
cd ~/Projects/Augur && python -c "
import importlib.util
from pathlib import Path
spec_path = Path('.claude/skills/evolve/scripts/mcp/__init__.py')
assert spec_path.exists(), 'MCP module file not found'
spec = importlib.util.spec_from_file_location('evolve_mcp', spec_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
assert hasattr(mod, 'register_tools'), 'register_tools function not found'
print('MCP module loads with register_tools')
"
```

Expected: `MCP module loads with register_tools`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/evolve/scripts/
git commit -m "feat(evolve): MCP tools — state CRUD + classify-problem"
```

---

### Task 4: SKILL.md — Orchestration Instructions

The SKILL.md is the heart of the skill — it contains the conversational instructions that Claude Code follows to run the pipeline. This is where all 8 steps are orchestrated.

**Files:**
- Create: `.claude/skills/evolve/SKILL.md`
- Create: `.claude/skills/evolve/assets/seeds/_seed.yaml`

- [ ] **Step 1: Write the SKILL.md with frontmatter and orchestration logic**

Write `.claude/skills/evolve/SKILL.md` with:

**Frontmatter:**
```yaml
---
name: evolve
description: Unified user journey for growing your Augur project — from problem description
  to verified, working skill with optional dashboard page. Orchestrates intake, classification,
  search, scaffolding, enrichment, wiring, verification, and page composition.
x-augur-hub: command
x-augur-tab: system
x-augur-visibility: app
x-augur-license: MIT
x-augur-metadata:
  version: 1.0.0
  author: Augur
  mcp-server: augur
x-augur-master: claude-code
x-augur-plugin: augur-ops
x-augur-requires-platform: true
x-augur-mcp-tools:
  - get-evolve-pipelines
  - get-evolve-pipeline-detail
  - evolve-step-action
  - classify-problem
x-augur-data-dir: evolve
---
```

**Body:** Write the full orchestration instructions covering:
1. Mode selection (`--from-docs`, `--from-skill`, `--status`, `--resume`, default interactive)
2. `--help` flag handling (per CLAUDE.md rule #15)
3. Step 1 INTAKE — normalize entry point, create pipeline via `evolve-step-action`
4. Step 2 CLASSIFY — call `classify-problem`, present results with confidence tiers, get user decision
5. Step 3 SEARCH — call `skills-sh-search` and `skillstore-gh-search`, present gap analysis
6. Step 4 SCAFFOLD — call `create-plugin` (mcp-app-factory) or describe extend plan
7. Step 5 ENRICH — call `import-data` for collateral processing
8. Step 6 WIRE — describe MCP tool generation, call `mount-plugins` equivalent
9. Step 7 VERIFY — run 5-check verification (MCP health, API health, wiring audit, data access, SKILL.md validation)
10. Step 8 PAGE — offer ADR-450 template composition

Each step should: call `evolve-step-action` with `action=complete/skip/fail` to persist state, present results to user, and get confirmation before advancing.

- [ ] **Step 2: Create seed manifest**

```yaml
# .claude/skills/evolve/assets/seeds/_seed.yaml
# Evolve skill has no seed data — pipeline state lives in get_state_dir()
entries: []
```

- [ ] **Step 3: Verify SKILL.md frontmatter is valid**

```bash
cd ~/Projects/Augur && python -c "
import yaml
from pathlib import Path
content = Path('.claude/skills/evolve/SKILL.md').read_text()
parts = content.split('---', 2)
fm = yaml.safe_load(parts[1])
assert fm['name'] == 'evolve'
assert fm['x-augur-master'] == 'claude-code'
assert fm['x-augur-plugin'] == 'augur-ops'
assert 'classify-problem' in fm['x-augur-mcp-tools']
assert 'get-evolve-pipelines' in fm['x-augur-mcp-tools']
print('Frontmatter valid')
"
```

Expected: `Frontmatter valid`

- [ ] **Step 4: Verify skill is discovered by skill_registry**

```bash
cd ~/Projects/Augur && python -c "
from src.plugins.skill_registry import list_skills
skills = list_skills()
evolve = [s for s in skills if s.id == 'evolve']
assert len(evolve) == 1, f'Expected 1 evolve skill, found {len(evolve)}'
assert evolve[0].master == 'claude-code'
assert evolve[0].plugin == 'augur-ops'
print(f'Skill discovered: {evolve[0].display_name} (master={evolve[0].master}, plugin={evolve[0].plugin})')
"
```

Expected: `Skill discovered: evolve (master=claude-code, plugin=augur-ops)`

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/evolve/SKILL.md .claude/skills/evolve/assets/
git commit -m "feat(evolve): SKILL.md with pipeline orchestration instructions"
```

---

### Task 5: Dashboard Template (ADR-450)

Create the YAML template for the evolve dashboard page with horizontal stepper + history table.

**Files:**
- Create: Template YAML in the ADR-450 template directory (exact path depends on ADR-450 implementation — likely `plugins/ui/templates/ops/evolve.yaml` or equivalent)

- [ ] **Step 1: Verify ADR-450 template directory exists**

```bash
ls plugins/ui/templates/ 2>/dev/null || echo "ADR-450 not yet implemented — skip this task"
```

If ADR-450 is not yet implemented, skip this task entirely — it's the optional last step and depends on ADR-450 landing first.

- [ ] **Step 2: Write the template YAML**

Create the template with two blocks:
1. A stepper block referencing `get-evolve-pipeline-detail` MCP tool
2. A data-table block referencing `get-evolve-pipelines` MCP tool

The exact YAML schema depends on ADR-450's template format. Use the patterns from existing templates in `plugins/ui/templates/`.

- [ ] **Step 3: Commit**

```bash
git add plugins/ui/templates/
git commit -m "feat(evolve): dashboard stepper template (ADR-450)"
```

---

### Task 6: Integration Verification

End-to-end smoke test — verify the skill works as a complete unit.

**Files:**
- No new files — verification only

- [ ] **Step 1: Run all unit tests**

```bash
cd .claude/skills/evolve && python -m pytest augur/tests/ -v
```

Expected: all tests PASS

- [ ] **Step 2: Verify MCP tools are registered**

```bash
cd ~/Projects/Augur && python -c "
# Verify all 4 tools are loadable
from pathlib import Path
import importlib.util

spec_path = Path('.claude/skills/evolve/scripts/mcp/__init__.py')
spec = importlib.util.spec_from_file_location('evolve_mcp', spec_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
assert hasattr(mod, 'register_tools'), 'register_tools function not found'
print('MCP module loads successfully with register_tools')
"
```

- [ ] **Step 3: Verify SKILL.md is complete and well-formed**

```bash
cd ~/Projects/Augur && python -c "
from pathlib import Path
content = Path('.claude/skills/evolve/SKILL.md').read_text()
# Check all 8 steps are documented
for step in ['intake', 'classify', 'search', 'scaffold', 'enrich', 'wire', 'verify', 'page']:
    assert step.lower() in content.lower(), f'Step {step} not found in SKILL.md'
# Check CLI flags are documented
for flag in ['--from-docs', '--from-skill', '--status', '--resume', '--help']:
    assert flag in content, f'Flag {flag} not found in SKILL.md'
print('SKILL.md covers all 8 steps and 5 CLI flags')
"
```

- [ ] **Step 4: Test the /evolve command manually**

In Claude Code, run `/evolve --help` and verify it displays usage information without executing.

Then run `/evolve` and verify it starts the interactive pipeline, asks for a problem description, and creates pipeline state.

- [ ] **Step 5: Final commit if any fixes were needed**

```bash
git add -A .claude/skills/evolve/
git commit -m "fix(evolve): integration fixes from smoke testing"
```

---

## Summary

| Task | What it builds | Estimated steps |
|------|---------------|----------------|
| 1. Pipeline State Model | Data model + YAML persistence | 6 |
| 2. Classifier | Semantic skill matching | 5 |
| 3. MCP Tools | State CRUD + classify-problem | 3 |
| 4. SKILL.md | Orchestration instructions | 5 |
| 5. Dashboard Template | ADR-450 stepper page | 3 (may skip if ADR-450 not ready) |
| 6. Integration | End-to-end verification | 5 |

**Total:** 6 tasks, ~27 steps. Tasks 1-4 are the core implementation. Task 5 depends on ADR-450. Task 6 is verification.
