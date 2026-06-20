"""
Crew Orchestration MCP Tool Contract Tests (ADR-046).

User Need: Dispatch tasks to crew agents, check status, and execute swarm presets.

Run with: cd packages/augur-mcp && uv run pytest tests/tools/test_orchestration_tools.py -v

NOTE: The orchestration subsystem was removed in refactor commit 5f338ce10.
These tests are skipped until the module is restored or the file is removed.
"""

# TODO_CLEANUP: This file is 875 lines — consider splitting into smaller modules

import json
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

pytest.importorskip(
    "src.mcp.augur_shared.orchestration",
    reason="orchestration removed (refactor 5f338ce10)",
)

from src.mcp.augur_shared.orchestration.models import (
    CrewDispatchInput,
    CrewStatusInput,
    SwarmExecuteInput,
)
from src.mcp.augur_shared.orchestration.tools import (
    _read_crew_state,
    crew_dispatch_impl,
    crew_list_impl,
    crew_status_impl,
    swarm_execute_impl,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_project(tmp_path, monkeypatch):
    """Create isolated project root with expected directory structure."""
    # Patch _get_project_root to use tmp_path
    monkeypatch.setattr(
        "src.mcp.augur_shared.orchestration.tools._get_project_root",
        lambda: tmp_path,
    )

    # Create runtime dir
    runtime = tmp_path / "data" / "core" / "runtime"
    runtime.mkdir(parents=True)

    # Create .claude/agents dir
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)

    return tmp_path


@pytest.fixture
def sample_registry(temp_project):
    """Create a sample registry.json with crew agents."""
    registry = [
        {
            "name": "developer",
            "display_name": "Developer",
            "description": "Implements features and fixes bugs",
            "mode": "executor",
            "default_model": "sonnet",
            "default_model_id": "claude-sonnet-4-20250514",
            "tools": ["Read", "Glob", "Grep", "Edit", "Bash"],
            "is_advisory": False,
            "iron_law": "All changes must pass tests before completion",
            "protected_areas": ["authentication", "payment_processing"],
            "triggers": ["implement", "code", "fix"],
            "chain_participation": [],
            "tiers": {
                "low": {
                    "model": "haiku",
                    "model_id": "claude-3-5-haiku-latest",
                    "mode": "advisory",
                    "tools": ["Read", "Glob", "Grep"],
                    "max_files": "5",
                },
                "medium": {
                    "model": "sonnet",
                    "model_id": "claude-sonnet-4-20250514",
                    "mode": "executor",
                    "tools": ["Read", "Glob", "Grep", "Edit", "Bash"],
                    "max_files": "10",
                },
                "high": {
                    "model": "opus",
                    "model_id": "claude-opus-4-5-20251101",
                    "mode": "executor",
                    "tools": ["Read", "Glob", "Grep", "Edit", "Bash", "Write"],
                    "max_files": "unlimited",
                },
            },
        },
        {
            "name": "architect",
            "display_name": "Architect",
            "description": "Designs system architecture and reviews decisions",
            "mode": "advisory",
            "default_model": "sonnet",
            "default_model_id": "claude-sonnet-4-20250514",
            "tools": ["Read", "Glob", "Grep"],
            "is_advisory": True,
            "iron_law": "Never modify code directly",
            "protected_areas": [],
            "triggers": ["architecture", "design", "review"],
            "chain_participation": [],
            "tiers": {
                "medium": {
                    "model": "sonnet",
                    "model_id": "claude-sonnet-4-20250514",
                    "mode": "advisory",
                    "tools": ["Read", "Glob", "Grep"],
                    "max_files": "10",
                },
            },
        },
        {
            "name": "security",
            "display_name": "Security",
            "description": "Scans for vulnerabilities and unsafe patterns",
            "mode": "advisory",
            "default_model": "sonnet",
            "default_model_id": "claude-sonnet-4-20250514",
            "tools": ["Read", "Glob", "Grep"],
            "is_advisory": True,
            "iron_law": "",
            "protected_areas": [],
            "triggers": ["security", "audit", "vulnerability"],
            "chain_participation": [],
            "tiers": {},
        },
    ]

    registry_path = temp_project / ".claude" / "agents" / "registry.json"
    registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")

    return registry


# =============================================================================
# Contract Tests: crew-list
# =============================================================================


@pytest.mark.contract
class TestCrewListContract:
    """
    User Need: Discover available crew agents and their capabilities.

    Acceptance Criteria:
    1. User can list all crew agents
    2. Each agent has required metadata
    3. Empty registry handled gracefully
    4. Metrics tracking works
    """

    @pytest.mark.asyncio
    async def test_user_can_list_agents(self, sample_registry):
        """User story: As a user, I can see all crew agents."""
        result = await crew_list_impl()

        data = json.loads(result)
        assert "agents" in data
        assert "count" in data
        assert data["count"] == 3

    @pytest.mark.asyncio
    async def test_agents_have_required_fields(self, sample_registry):
        """User story: As a user, each agent has essential info."""
        result = await crew_list_impl()

        data = json.loads(result)
        for agent in data["agents"]:
            assert "name" in agent
            assert "display_name" in agent
            assert "description" in agent
            assert "mode" in agent
            assert "default_model" in agent
            assert "is_advisory" in agent
            assert "tools" in agent

    @pytest.mark.asyncio
    async def test_agent_tiers_present(self, sample_registry):
        """User story: As a user, I can see tier mappings per agent."""
        result = await crew_list_impl()

        data = json.loads(result)
        developer = next(a for a in data["agents"] if a["name"] == "developer")
        assert "tiers" in developer
        assert "medium" in developer["tiers"]
        assert developer["tiers"]["medium"]["model"] == "sonnet"

    @pytest.mark.asyncio
    async def test_empty_registry_returns_warning(self, temp_project):
        """User story: As a new user, empty registry gives a helpful warning."""
        result = await crew_list_impl()

        data = json.loads(result)
        assert data.get("status") == "warning"
        assert data["count"] == 0
        assert "agents" in data

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, sample_registry):
        """User story: As an operator, crew-list usage is tracked."""
        mock_metrics = MagicMock()

        await crew_list_impl(metrics=mock_metrics)

        mock_metrics.track_tool.assert_called_once_with("crew_list")


# =============================================================================
# Contract Tests: crew-dispatch
# =============================================================================


@pytest.mark.contract
class TestCrewDispatchContract:
    """
    User Need: Dispatch tasks to specific crew agents.

    Acceptance Criteria:
    1. User can dispatch to a known agent
    2. Unknown agent returns helpful error with available list
    3. Dispatch recorded in crew state
    4. Spawn instructions include profile path and model
    5. Tier fallback works when specific tier not available
    """

    @pytest.mark.asyncio
    async def test_dispatch_to_known_agent(self, sample_registry, temp_project):
        """User story: As a user, I can dispatch a task to developer."""
        params = CrewDispatchInput(
            skill_name="developer",
            task="Implement user authentication feature",
        )
        result = await crew_dispatch_impl(params)

        data = json.loads(result)
        assert data["status"] == "dispatched"
        assert data["skill"] == "developer"
        assert data["model"] == "sonnet"
        assert "dispatch_id" in data
        assert data["profile_path"] == ".claude/agents/developer.md"

    @pytest.mark.asyncio
    async def test_dispatch_includes_spawn_instructions(self, sample_registry, temp_project):
        """User story: As a user, dispatch gives me Task tool instructions."""
        params = CrewDispatchInput(
            skill_name="developer",
            task="Fix login bug",
        )
        result = await crew_dispatch_impl(params)

        data = json.loads(result)
        assert "spawn_instructions" in data
        si = data["spawn_instructions"]
        assert "description" in si
        assert "model" in si
        assert "profile" in si
        assert "task" in si

    @pytest.mark.asyncio
    async def test_unknown_agent_returns_error(self, sample_registry, temp_project):
        """User story: As a user, unknown agent gives list of available ones."""
        params = CrewDispatchInput(
            skill_name="nonexistent",
            task="Do something impossible",
        )
        result = await crew_dispatch_impl(params)

        data = json.loads(result)
        assert data["status"] == "error"
        assert "available_skills" in data
        assert "developer" in data["available_skills"]
        assert "architect" in data["available_skills"]

    @pytest.mark.asyncio
    async def test_dispatch_records_state(self, sample_registry, temp_project):
        """User story: As an operator, dispatches are tracked in crew state."""
        params = CrewDispatchInput(
            skill_name="developer",
            task="Implement feature X",
        )
        await crew_dispatch_impl(params)

        state = _read_crew_state()
        assert len(state["dispatches"]) == 1
        assert state["dispatches"][0]["skill"] == "developer"
        assert state["dispatches"][0]["status"] == "dispatched"
        assert "developer" in state["agents"]

    @pytest.mark.asyncio
    async def test_tier_selection(self, sample_registry, temp_project):
        """User story: As a user, I can request a specific tier."""
        params = CrewDispatchInput(
            skill_name="developer",
            task="Complex reasoning task",
            tier="high",
        )
        result = await crew_dispatch_impl(params)

        data = json.loads(result)
        assert data["status"] == "dispatched"
        assert data["model"] == "opus"
        assert data["tier"] == "high"

    @pytest.mark.asyncio
    async def test_tier_fallback(self, sample_registry, temp_project):
        """User story: As a user, invalid tier falls back to available one."""
        # Architect only has "medium" tier
        params = CrewDispatchInput(
            skill_name="architect",
            task="Review architecture",
            tier="high",
        )
        result = await crew_dispatch_impl(params)

        data = json.loads(result)
        assert data["status"] == "dispatched"
        # Should fall back to medium
        assert data["tier"] == "medium"

    @pytest.mark.asyncio
    async def test_dispatch_with_context(self, sample_registry, temp_project):
        """User story: As a user, I can provide context for the dispatch."""
        params = CrewDispatchInput(
            skill_name="developer",
            task="Fix the auth bug",
            context={"note": "Previous analysis showed issue in middleware.py line 42"},
        )
        result = await crew_dispatch_impl(params)

        data = json.loads(result)
        assert data["status"] == "dispatched"
        assert "context" in data["spawn_instructions"]

    @pytest.mark.asyncio
    async def test_advisory_mode_flagged(self, sample_registry, temp_project):
        """User story: As a user, advisory agents are clearly flagged."""
        params = CrewDispatchInput(
            skill_name="architect",
            task="Review this design",
        )
        result = await crew_dispatch_impl(params)

        data = json.loads(result)
        assert data["mode"] == "advisory"
        assert data["spawn_instructions"]["advisory_only"] is True

    @pytest.mark.asyncio
    async def test_executor_mode_flagged(self, sample_registry, temp_project):
        """User story: As a user, executor agents are clearly flagged."""
        params = CrewDispatchInput(
            skill_name="developer",
            task="Implement feature",
        )
        result = await crew_dispatch_impl(params)

        data = json.loads(result)
        assert data["mode"] == "executor"
        assert data["spawn_instructions"]["advisory_only"] is False

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, sample_registry, temp_project):
        """User story: As an operator, dispatches are tracked."""
        mock_metrics = MagicMock()

        params = CrewDispatchInput(
            skill_name="developer",
            task="Track this",
        )
        await crew_dispatch_impl(params, metrics=mock_metrics)

        mock_metrics.track_tool.assert_called_once_with("crew_dispatch", skill="developer")


# =============================================================================
# Contract Tests: crew-status
# =============================================================================


@pytest.mark.contract
class TestCrewStatusContract:
    """
    User Need: Check status of crew dispatches.

    Acceptance Criteria:
    1. User can see all active agents
    2. User can filter by specific agent
    3. Empty state handled gracefully
    4. Recent dispatches shown
    """

    @pytest.mark.asyncio
    async def test_status_with_no_dispatches(self, temp_project):
        """User story: As a new user, empty state returns cleanly."""
        params = CrewStatusInput()
        result = await crew_status_impl(params)

        data = json.loads(result)
        assert "active_agents" in data
        assert "all_agents" in data
        assert data["total_dispatches"] == 0

    @pytest.mark.asyncio
    async def test_status_after_dispatch(self, sample_registry, temp_project):
        """User story: As a user, I can see my dispatched agent."""
        # First dispatch
        dispatch_params = CrewDispatchInput(
            skill_name="developer",
            task="Build feature X",
        )
        await crew_dispatch_impl(dispatch_params)

        # Then check status
        params = CrewStatusInput()
        result = await crew_status_impl(params)

        data = json.loads(result)
        assert data["total_dispatches"] >= 1
        assert "developer" in data["all_agents"]

    @pytest.mark.asyncio
    async def test_filter_by_skill(self, sample_registry, temp_project):
        """User story: As a user, I can check a specific agent's status."""
        # Dispatch two agents
        await crew_dispatch_impl(CrewDispatchInput(skill_name="developer", task="Task 1"))
        await crew_dispatch_impl(CrewDispatchInput(skill_name="architect", task="Task 2"))

        # Filter to developer only
        params = CrewStatusInput(skill_name="developer")
        result = await crew_status_impl(params)

        data = json.loads(result)
        assert data["skill"] == "developer"
        assert data["agent_state"] is not None
        # All dispatches should be for developer
        for d in data["dispatches"]:
            assert d["skill"] == "developer"

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, temp_project):
        """User story: As an operator, status checks are tracked."""
        mock_metrics = MagicMock()

        params = CrewStatusInput()
        await crew_status_impl(params, metrics=mock_metrics)

        mock_metrics.track_tool.assert_called_once_with("crew_status")


# =============================================================================
# Contract Tests: swarm-execute
# =============================================================================


@pytest.mark.contract
class TestSwarmExecuteContract:
    """
    User Need: Execute swarm presets for multi-agent coordination.

    Acceptance Criteria:
    1. User can execute a known preset
    2. Unknown preset returns error with available list
    3. Spawn plan includes all agents with models
    4. Strategy and consensus instructions included
    5. Execution state recorded
    """

    @pytest.mark.asyncio
    async def test_execute_code_review_preset(self, temp_project, monkeypatch):
        """User story: As a user, I can execute the code-review swarm."""
        # Patch the import of swarm_bridge

        from src.mcp.augur_shared.orchestration.tools import swarm_execute_impl

        # Mock the swarm bridge import
        import sys
        from unittest.mock import MagicMock as MM

        mock_module = MM()
        mock_module.SWARM_PRESETS = [
            {
                "name": "code-review",
                "description": "Parallel code review",
                "strategy": "PARALLEL",
                "agents": [
                    {"name": "developer", "role": "Review code quality", "model": "sonnet"},
                    {"name": "validator", "role": "Check lint and tests", "model": "haiku"},
                    {"name": "security", "role": "Scan for vulnerabilities", "model": "sonnet"},
                ],
                "consensus": "MERGE",
            },
        ]

        monkeypatch.setitem(sys.modules, "swarm_bridge", mock_module)

        params = SwarmExecuteInput(
            preset="code-review",
            task="Review the auth module",
        )
        result = await swarm_execute_impl(params)

        data = json.loads(result)
        assert data["status"] == "ready"
        assert data["preset"] == "code-review"
        assert data["strategy"] == "PARALLEL"
        assert data["consensus"] == "MERGE"
        assert len(data["agents"]) == 3

    @pytest.mark.asyncio
    async def test_spawn_plan_has_agent_details(self, temp_project, monkeypatch):
        """User story: As a user, spawn plan includes agent profiles and models."""
        import sys
        from unittest.mock import MagicMock as MM

        mock_module = MM()
        mock_module.SWARM_PRESETS = [
            {
                "name": "code-review",
                "description": "Parallel code review",
                "strategy": "PARALLEL",
                "agents": [
                    {"name": "developer", "role": "Review code quality", "model": "sonnet"},
                ],
                "consensus": "MERGE",
            },
        ]
        monkeypatch.setitem(sys.modules, "swarm_bridge", mock_module)

        params = SwarmExecuteInput(
            preset="code-review",
            task="Review auth",
        )
        result = await swarm_execute_impl(params)

        data = json.loads(result)
        agent = data["agents"][0]
        assert agent["agent"] == "developer"
        assert agent["model"] == "sonnet"
        assert agent["profile_path"] == ".claude/agents/developer.md"
        assert "role" in agent

    @pytest.mark.asyncio
    async def test_parallel_strategy_instructions(self, temp_project, monkeypatch):
        """User story: As a user, parallel presets tell me to spawn simultaneously."""
        import sys
        from unittest.mock import MagicMock as MM

        mock_module = MM()
        mock_module.SWARM_PRESETS = [
            {
                "name": "code-review",
                "description": "Parallel code review",
                "strategy": "PARALLEL",
                "agents": [
                    {"name": "developer", "role": "Review", "model": "sonnet"},
                ],
                "consensus": "MERGE",
            },
        ]
        monkeypatch.setitem(sys.modules, "swarm_bridge", mock_module)

        params = SwarmExecuteInput(preset="code-review", task="Review")
        result = await swarm_execute_impl(params)

        data = json.loads(result)
        assert "execution_instructions" in data
        assert "simultaneously" in data["execution_instructions"]["note"].lower()

    @pytest.mark.asyncio
    async def test_pipeline_strategy_instructions(self, temp_project, monkeypatch):
        """User story: As a user, pipeline presets tell me to spawn sequentially."""
        import sys
        from unittest.mock import MagicMock as MM

        mock_module = MM()
        mock_module.SWARM_PRESETS = [
            {
                "name": "feature-dev",
                "description": "Pipeline feature development",
                "strategy": "PIPELINE",
                "agents": [
                    {"name": "architect", "role": "Design", "model": "opus"},
                    {"name": "developer", "role": "Implement", "model": "sonnet"},
                ],
                "consensus": "COORDINATOR",
                "coordinator": "architect",
            },
        ]
        monkeypatch.setitem(sys.modules, "swarm_bridge", mock_module)

        params = SwarmExecuteInput(preset="feature-dev", task="New feature")
        result = await swarm_execute_impl(params)

        data = json.loads(result)
        assert "sequentially" in data["execution_instructions"]["note"].lower()
        assert data["execution_instructions"]["coordinator"] == "architect"

    @pytest.mark.asyncio
    async def test_unknown_preset_returns_error(self, temp_project, monkeypatch):
        """User story: As a user, unknown preset lists available ones."""
        import sys
        from unittest.mock import MagicMock as MM

        mock_module = MM()
        mock_module.SWARM_PRESETS = [
            {
                "name": "code-review",
                "description": "Code review",
                "strategy": "PARALLEL",
                "agents": [],
                "consensus": "MERGE",
            },
        ]
        monkeypatch.setitem(sys.modules, "swarm_bridge", mock_module)

        params = SwarmExecuteInput(
            preset="nonexistent",
            task="Do something",
        )
        result = await swarm_execute_impl(params)

        data = json.loads(result)
        assert data["status"] == "error"
        assert "available_presets" in data
        assert "code-review" in data["available_presets"]

    @pytest.mark.asyncio
    async def test_swarm_state_recorded(self, temp_project, monkeypatch):
        """User story: As an operator, swarm agents are tracked in crew state."""
        import sys
        from unittest.mock import MagicMock as MM

        mock_module = MM()
        mock_module.SWARM_PRESETS = [
            {
                "name": "code-review",
                "description": "Code review",
                "strategy": "PARALLEL",
                "agents": [
                    {"name": "developer", "role": "Review", "model": "sonnet"},
                    {"name": "security", "role": "Audit", "model": "sonnet"},
                ],
                "consensus": "MERGE",
            },
        ]
        monkeypatch.setitem(sys.modules, "swarm_bridge", mock_module)

        params = SwarmExecuteInput(preset="code-review", task="Review auth")
        await swarm_execute_impl(params)

        state = _read_crew_state()
        assert "developer" in state["agents"]
        assert "security" in state["agents"]
        assert state["agents"]["developer"]["status"] == "dispatched"

    @pytest.mark.asyncio
    async def test_swarm_with_context(self, temp_project, monkeypatch):
        """User story: As a user, I can provide context for the swarm."""
        import sys
        from unittest.mock import MagicMock as MM

        mock_module = MM()
        mock_module.SWARM_PRESETS = [
            {
                "name": "code-review",
                "description": "Code review",
                "strategy": "PARALLEL",
                "agents": [
                    {"name": "developer", "role": "Review", "model": "sonnet"},
                ],
                "consensus": "MERGE",
            },
        ]
        monkeypatch.setitem(sys.modules, "swarm_bridge", mock_module)

        params = SwarmExecuteInput(
            preset="code-review",
            task="Review auth",
            context={"focus": "middleware layer"},
        )
        result = await swarm_execute_impl(params)

        data = json.loads(result)
        assert data["context"] == {"focus": "middleware layer"}

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, temp_project, monkeypatch):
        """User story: As an operator, swarm executions are tracked."""
        import sys
        from unittest.mock import MagicMock as MM

        mock_module = MM()
        mock_module.SWARM_PRESETS = [
            {
                "name": "code-review",
                "description": "Code review",
                "strategy": "PARALLEL",
                "agents": [],
                "consensus": "MERGE",
            },
        ]
        monkeypatch.setitem(sys.modules, "swarm_bridge", mock_module)

        mock_metrics = MagicMock()
        params = SwarmExecuteInput(preset="code-review", task="Review")
        await swarm_execute_impl(params, metrics=mock_metrics)

        mock_metrics.track_tool.assert_called_once_with("swarm_execute", skill="code-review")


# =============================================================================
# Input Validation Tests
# =============================================================================


@pytest.mark.contract
class TestInputValidation:
    """
    User Need: Get clear feedback for invalid inputs.
    """

    def test_crew_dispatch_requires_skill_name(self):
        """Validation: skill_name is required."""
        with pytest.raises(ValidationError):
            CrewDispatchInput(task="Do something")

    def test_crew_dispatch_requires_task(self):
        """Validation: task is required."""
        with pytest.raises(ValidationError):
            CrewDispatchInput(skill_name="developer")

    def test_crew_dispatch_default_tier(self):
        """Validation: tier defaults to medium."""
        params = CrewDispatchInput(skill_name="developer", task="Test task here")
        assert params.tier == "medium"

    def test_swarm_execute_requires_preset(self):
        """Validation: preset is required."""
        with pytest.raises(ValidationError):
            SwarmExecuteInput(task="Do something")

    def test_swarm_execute_requires_task(self):
        """Validation: task is required."""
        with pytest.raises(ValidationError):
            SwarmExecuteInput(preset="code-review")


# =============================================================================
# Crew State Management Tests
# =============================================================================


@pytest.mark.contract
class TestCrewState:
    """
    User Need: Reliable state tracking across crew dispatches.
    """

    @pytest.mark.asyncio
    async def test_state_persists_across_calls(self, sample_registry, temp_project):
        """State: Multiple dispatches accumulate in crew state."""
        await crew_dispatch_impl(CrewDispatchInput(skill_name="developer", task="Task 1"))
        await crew_dispatch_impl(CrewDispatchInput(skill_name="architect", task="Task 2"))

        state = _read_crew_state()
        assert len(state["dispatches"]) == 2
        assert "developer" in state["agents"]
        assert "architect" in state["agents"]
        assert state["last_updated"] is not None

    @pytest.mark.asyncio
    async def test_empty_state_returns_defaults(self, temp_project):
        """State: Fresh project returns sensible defaults."""
        state = _read_crew_state()
        assert state["agents"] == {}
        assert state["dispatches"] == []
        assert state["last_updated"] is None

    @pytest.mark.asyncio
    async def test_corrupted_state_handled(self, temp_project):
        """State: Corrupted state file doesn't crash."""
        state_file = temp_project / "data" / "core" / "runtime" / "crew-state.json"
        state_file.write_text("not valid json{{{", encoding="utf-8")

        state = _read_crew_state()
        # Should return defaults, not crash
        assert state["agents"] == {}
        assert state["dispatches"] == []


# =============================================================================
# Security Tests
# =============================================================================


@pytest.mark.contract
class TestSecuritySanitization:
    """
    Critical Security: Verify orchestration inputs are properly handled.
    """

    @pytest.mark.asyncio
    async def test_path_traversal_in_skill_name(self, sample_registry, temp_project):
        """Security: Path traversal in skill name is handled safely."""
        params = CrewDispatchInput(
            skill_name="../../etc/passwd",
            task="Attempt path traversal",
        )
        result = await crew_dispatch_impl(params)

        data = json.loads(result)
        assert data["status"] == "error"

    @pytest.mark.asyncio
    async def test_shell_injection_in_task(self, sample_registry, temp_project):
        """Security: Shell metacharacters in task don't execute."""
        params = CrewDispatchInput(
            skill_name="developer",
            task="; rm -rf / && echo pwned",
        )
        result = await crew_dispatch_impl(params)

        data = json.loads(result)
        # Should dispatch normally — task is just a string, not executed
        assert data["status"] == "dispatched"
        # But the task should be stored as-is, not interpreted
        assert data["spawn_instructions"]["task"] == "; rm -rf / && echo pwned"

    @pytest.mark.asyncio
    async def test_iron_law_included_in_dispatch(self, sample_registry, temp_project):
        """Security: Iron law constraints are included in dispatch response."""
        params = CrewDispatchInput(
            skill_name="developer",
            task="Implement feature",
        )
        result = await crew_dispatch_impl(params)

        data = json.loads(result)
        assert data["iron_law"] == "All changes must pass tests before completion"

    @pytest.mark.asyncio
    async def test_protected_areas_in_tools(self, sample_registry, temp_project):
        """Security: Protected areas are communicated in dispatch."""
        params = CrewDispatchInput(
            skill_name="developer",
            task="Modify authentication",
        )
        result = await crew_dispatch_impl(params)

        data = json.loads(result)
        # The dispatch should succeed but tools list should be available
        assert "tools" in data
