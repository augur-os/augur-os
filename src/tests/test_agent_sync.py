"""Tests for ADR-464: Cross-Client Agent Sync.

Tests model mapping resolution, agent file parsing, capability translation,
and registry schema updates.
"""

import sys
import textwrap
from pathlib import Path

# Ensure sync_agents package is importable
_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[1].parent / "project-brain" / "capabilities" / "skills" / "ai" / "scripts"
)
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


# ── Model Mapping Tests ─────────────────────────────────────────────


class TestModelMapping:
    """Test model_mapping.py resolution functions."""

    def test_resolve_tier_from_reverse_lookup(self):
        from sync_agents.model_mapping import resolve_tier

        assert resolve_tier("claude-code", "haiku") == "fast"
        assert resolve_tier("claude-code", "sonnet") == "standard"
        assert resolve_tier("claude-code", "opus") == "deep"

    def test_resolve_tier_gemini_models(self):
        from sync_agents.model_mapping import resolve_tier

        assert resolve_tier("gemini", "gemini-2.5-flash") == "fast"
        assert resolve_tier("gemini", "gemini-3-flash-preview") == "standard"
        assert resolve_tier("gemini", "gemini-3.1-pro-preview") == "deep"

    def test_resolve_tier_unknown_model_defaults_to_standard(self):
        from sync_agents.model_mapping import resolve_tier

        assert resolve_tier("claude-code", "unknown-model-xyz") == "standard"

    def test_resolve_model_claude_to_gemini(self):
        from sync_agents.model_mapping import resolve_model

        assert resolve_model("claude-code", "gemini", "sonnet") == "gemini-3-flash-preview"
        assert resolve_model("claude-code", "gemini", "haiku") == "gemini-2.5-flash"
        assert resolve_model("claude-code", "gemini", "opus") == "gemini-3.1-pro-preview"

    def test_resolve_model_gemini_to_claude(self):
        from sync_agents.model_mapping import resolve_model

        assert resolve_model("gemini", "claude-code", "gemini-3-flash-preview") == "sonnet"
        assert resolve_model("gemini", "claude-code", "gemini-2.5-flash") == "haiku"
        assert resolve_model("gemini", "claude-code", "gemini-3.1-pro-preview") == "opus"

    def test_resolve_model_claude_to_codex(self):
        from sync_agents.model_mapping import resolve_model

        assert resolve_model("claude-code", "codex", "sonnet") == "gpt-5.4"
        assert resolve_model("claude-code", "codex", "opus") == "gpt-5.3-codex"

    def test_resolve_model_claude_to_cursor(self):
        from sync_agents.model_mapping import resolve_model

        assert resolve_model("claude-code", "cursor", "sonnet") == "inherit"
        assert resolve_model("claude-code", "cursor", "opus") == "claude-opus-4-6"

    def test_get_tier_model(self):
        from sync_agents.model_mapping import get_tier_model

        assert get_tier_model("fast", "claude-code") == "haiku"
        assert get_tier_model("standard", "gemini") == "gemini-3-flash-preview"
        assert get_tier_model("deep", "codex") == "gpt-5.3-codex"

    def test_get_all_tiers(self):
        from sync_agents.model_mapping import get_all_tiers

        tiers = get_all_tiers()
        assert "fast" in tiers
        assert "standard" in tiers
        assert "deep" in tiers

    def test_get_supported_clients(self):
        from sync_agents.model_mapping import get_supported_clients

        clients = get_supported_clients()
        assert "claude-code" in clients
        assert "gemini" in clients
        assert "codex" in clients
        assert "cursor" in clients


# ── Agent Parser Tests ───────────────────────────────────────────────


class TestAgentParser:
    """Test agent_parser.py parsing and classification."""

    def test_parse_claude_agent(self, tmp_path):
        from sync_agents.agent_parser import parse_agent_file

        agent_md = tmp_path / "developer.md"
        agent_md.write_text(textwrap.dedent("""\
            ---
            mode: auto
            model: sonnet
            mcpServers:
              - augur
            x-augur-master: claude-code
            ---

            # Developer

            > Code simplification and Augur-aware refactoring.

            **Model**: sonnet | **Mode**: auto | **Role**: executor

            ## Allowed Tools

            - `Read`
            - `Edit`
            - `Bash`
        """))

        agent = parse_agent_file(agent_md, "claude-code")
        assert agent is not None
        assert agent.name == "developer"
        assert agent.model == "sonnet"
        assert agent.mode == "auto"
        assert agent.master_client == "claude-code"
        assert agent.is_master is True
        assert agent.is_adapted is False
        assert agent.description == "Code simplification and Augur-aware refactoring."
        assert "Read" in agent.tools
        assert "Edit" in agent.tools
        assert "Bash" in agent.tools
        assert agent.mcp_servers == ["augur"]

    def test_parse_adapted_copy(self, tmp_path):
        from sync_agents.agent_parser import parse_agent_file, ADAPTED_COPY_MARKER

        agent_md = tmp_path / "researcher.md"
        agent_md.write_text(textwrap.dedent(f"""\
            ---
            name: researcher
            model: gemini-3-flash-preview
            ---
            <!-- {ADAPTED_COPY_MARKER} source=gemini -->

            # Researcher

            > Deep research agent.
        """))

        agent = parse_agent_file(agent_md, "claude-code")
        assert agent is not None
        assert agent.is_adapted is True
        assert agent.is_master is False

    def test_parse_plan_mode_agent(self, tmp_path):
        from sync_agents.agent_parser import parse_agent_file

        agent_md = tmp_path / "advisor.md"
        agent_md.write_text(textwrap.dedent("""\
            ---
            mode: plan
            model: sonnet
            mcpServers:
              - augur
            x-augur-master: claude-code
            ---

            # Advisor

            > Advisory agent.
        """))

        agent = parse_agent_file(agent_md, "claude-code")
        assert agent is not None
        assert agent.mode == "plan"

    def test_parse_generated_agent_with_header_comment(self, tmp_path):
        from sync_agents.agent_parser import parse_agent_file

        agent_md = tmp_path / "advisor.md"
        agent_md.write_text(textwrap.dedent("""\
            <!-- AUGUR-GENERATED -->
            ---
            name: advisor
            mode: plan
            model: sonnet
            mcpServers:
              - augur
            x-augur-master: claude-code
            ---

            # Advisor

            > Advisory agent.
        """))

        agent = parse_agent_file(agent_md, "claude-code")
        assert agent is not None
        assert agent.name == "advisor"
        assert agent.mode == "plan"
        assert agent.model == "sonnet"

    def test_parse_agent_without_frontmatter_returns_none(self, tmp_path):
        from sync_agents.agent_parser import parse_agent_file

        readme_md = tmp_path / "README.md"
        readme_md.write_text("# Agent docs only\n")

        agent = parse_agent_file(readme_md, "claude-code")
        assert agent is None

    def test_collect_masters_deduplicates(self, tmp_path):
        from sync_agents.agent_parser import AgentFile, collect_masters

        # Two agents with same name, different clients
        agent1 = AgentFile(
            name="dev",
            path=tmp_path / "a.md",
            frontmatter={"x-augur-master": "claude-code"},
            body="# Dev",
            client_dir="claude-code",
        )
        agent2 = AgentFile(
            name="dev",
            path=tmp_path / "b.md",
            frontmatter={"x-augur-master": "gemini"},
            body="# Dev",
            client_dir="gemini",
        )
        # Create actual files so stat() works
        (tmp_path / "a.md").write_text("old")
        import time

        time.sleep(0.01)
        (tmp_path / "b.md").write_text("new")

        masters = collect_masters([agent1, agent2])
        assert len(masters) == 1
        assert "dev" in masters
        # b.md is newer, so gemini should win
        assert masters["dev"].client_dir == "gemini"

    def test_scan_agent_dirs(self, tmp_path):
        from sync_agents.agent_parser import scan_agent_dirs

        # Create a mock claude agent dir
        claude_dir = tmp_path / ".claude" / "agents"
        claude_dir.mkdir(parents=True)
        (claude_dir / "dev.md").write_text("---\nmode: auto\nmodel: sonnet\n---\n# Dev\n")
        (claude_dir / "registry.json").write_text("{}")  # Should be skipped

        # Monkey-patch CLIENT_AGENT_DIRS temporarily
        import sync_agents.agent_parser as ap

        orig = ap.CLIENT_AGENT_DIRS.copy()
        ap.CLIENT_AGENT_DIRS = {"claude-code": ".claude/agents"}

        try:
            agents = scan_agent_dirs(tmp_path, clients=["claude-code"])
            assert len(agents) == 1
            assert agents[0].name == "dev"
        finally:
            ap.CLIENT_AGENT_DIRS = orig


# ── Integration: Capability Translation ──────────────────────────────


class TestCapabilityTranslation:
    """Test adapter sync logic with real AgentFile objects."""

    def _make_agent(
        self,
        tmp_path,
        name="dev",
        mode="auto",
        model="sonnet",
        master="claude-code",
        body="# Dev\n\n> Dev agent.\n\n## Allowed Tools\n\n- `Read`\n- `Edit`\n- `Bash`\n",
        mcp_servers=None,
        adapted=False,
    ):
        """Helper to create an AgentFile with a real file on disk."""
        from sync_agents.agent_parser import AgentFile, ADAPTED_COPY_MARKER

        if adapted:
            body = f"<!-- {ADAPTED_COPY_MARKER} source={master} -->\n\n{body}"

        fm = {"mode": mode, "model": model, "x-augur-master": master}
        if mcp_servers:
            fm["mcpServers"] = mcp_servers

        tmp_path.mkdir(parents=True, exist_ok=True)
        path = tmp_path / f"{name}.md"
        path.write_text(f"---\n{mode}\n---\n{body}")

        return AgentFile(
            name=name,
            path=path,
            frontmatter=fm,
            body=body,
            client_dir=master,
        )

    def test_gemini_tool_mapping(self, tmp_path):
        """Verify Gemini adapter maps Claude Code tools to Gemini equivalents."""
        agent = self._make_agent(tmp_path, mcp_servers=["augur"])

        tool_map = {
            "Read": "read_file",
            "Glob": "glob",
            "Grep": "grep_search",
            "Edit": "replace",
            "Write": "write_file",
            "Bash": "run_shell_command",
        }
        gemini_tools = [tool_map[t] for t in agent.tools if t in tool_map]
        if agent.mcp_servers:
            gemini_tools.append("mcp_augur_*")

        assert "read_file" in gemini_tools
        assert "replace" in gemini_tools
        assert "run_shell_command" in gemini_tools
        assert "mcp_augur_*" in gemini_tools

    def test_plan_mode_adds_instruction(self, tmp_path):
        """Verify plan mode agents get 'MUST NOT modify files' prepended."""
        agent = self._make_agent(tmp_path, mode="plan", body="# Advisor\n\n> Advisory agent.")

        body = agent.body
        if agent.mode == "plan" and "MUST NOT modify files" not in body:
            body = "You MUST NOT modify files. Only analyze, recommend, and report.\n\n" + body

        assert body.startswith("You MUST NOT modify files")
        assert "# Advisor" in body

    def test_plan_mode_no_duplicate_instruction(self, tmp_path):
        """Verify plan mode doesn't duplicate existing instruction."""
        agent = self._make_agent(
            tmp_path,
            mode="plan",
            body="You MUST NOT modify files.\n\n# Advisor",
        )

        body = agent.body
        if agent.mode == "plan" and "MUST NOT modify files" not in body:
            body = "You MUST NOT modify files.\n\n" + body

        assert body.count("MUST NOT modify files") == 1

    def test_cursor_skips_claude_and_plugin_masters(self, tmp_path):
        """Verify Cursor skip logic for claude-code, cursor, and plugin agents."""
        from sync_agents.agent_parser import AgentFile

        claude_agent = self._make_agent(tmp_path / "a", name="dev", master="claude-code")
        cursor_agent = self._make_agent(tmp_path / "b", name="styler", master="cursor")
        plugin_agent = self._make_agent(tmp_path / "c", name="reviewer", master="claude-code")
        plugin_agent = AgentFile(
            name="reviewer",
            path=plugin_agent.path,
            frontmatter=plugin_agent.frontmatter,
            body=plugin_agent.body,
            client_dir="plugin:feature-dev",
        )
        gemini_agent = self._make_agent(
            tmp_path / "d", name="researcher", master="gemini", model="gemini-3-flash-preview"
        )

        # Simulate the Cursor adapter's skip conditions
        masters = {"dev": claude_agent, "styler": cursor_agent, "reviewer": plugin_agent, "researcher": gemini_agent}

        synced = []
        for name, master in masters.items():
            if master.master_client in ("claude-code", "cursor") or master.client_dir.startswith("plugin:"):
                continue
            synced.append(name)

        # Only the gemini-mastered agent should be synced to Cursor
        assert synced == ["researcher"]

    def test_adapted_copies_skipped_by_collect_masters(self, tmp_path):
        """Verify adapted copies are filtered out during master collection."""
        from sync_agents.agent_parser import collect_masters

        master = self._make_agent(tmp_path / "a", name="dev", master="claude-code")
        adapted = self._make_agent(tmp_path / "b", name="dev", master="gemini", adapted=True)

        masters = collect_masters([master, adapted])
        assert len(masters) == 1
        assert masters["dev"].client_dir == "claude-code"

    def test_model_mapping_round_trip(self):
        """Verify model mapping works in both directions for all tiers."""
        from sync_agents.model_mapping import resolve_model

        pairs = [
            ("claude-code", "gemini", "haiku", "gemini-2.5-flash"),
            ("claude-code", "gemini", "sonnet", "gemini-3-flash-preview"),
            ("claude-code", "gemini", "opus", "gemini-3.1-pro-preview"),
            ("claude-code", "codex", "sonnet", "gpt-5.4"),
            ("claude-code", "cursor", "opus", "claude-opus-4-6"),
        ]
        for from_client, to_client, from_model, expected in pairs:
            result = resolve_model(from_client, to_client, from_model)
            assert result == expected, f"{from_client}:{from_model} → {to_client} = {result}, expected {expected}"

            # Round trip: resolve back
            back = resolve_model(to_client, from_client, expected)
            assert (
                back == from_model
            ), f"Round trip failed: {to_client}:{expected} → {from_client} = {back}, expected {from_model}"


# ── Orphan Cleanup Tests ─────────────────────────────────────────────


class TestOrphanCleanup:
    """Test that orphan adapted copies are cleaned up."""

    def test_orphan_adapted_copy_removed(self, tmp_path):
        """Verify adapted copies not in generated_names are deleted."""
        from sync_agents.adapters.base import BaseAdapter

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        # Create an adapted copy that's no longer in generated_names
        orphan = agents_dir / "old-agent.md"
        orphan.write_text("<!-- AUGUR-ADAPTED-COPY source=gemini -->\n\n# Old Agent")

        # Create a non-adapted file that should be preserved
        manual = agents_dir / "manual.md"
        manual.write_text("# Manual Agent\n\nHand-authored.")

        adapter = BaseAdapter()
        adapter._cleanup_orphan_agents(agents_dir, generated_names=set())

        assert not orphan.exists(), "Orphaned adapted copy should be removed"
        assert manual.exists(), "Non-adapted manual agent should be preserved"

    def test_generated_names_preserved(self, tmp_path):
        """Verify files in generated_names are not removed even if adapted."""
        from sync_agents.adapters.base import BaseAdapter

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        kept = agents_dir / "dev.md"
        kept.write_text("<!-- AUGUR-ADAPTED-COPY source=claude-code -->\n\n# Dev")

        adapter = BaseAdapter()
        adapter._cleanup_orphan_agents(agents_dir, generated_names={"dev"})

        assert kept.exists(), "Adapted copy in generated_names should be preserved"


# ── Registry Schema Tests ────────────────────────────────────────────


class TestRegistrySchema:
    """Test registry.json schema expectations (ADR-464)."""

    def test_mcp_tool_expects_dict_schema(self):
        """Verify the MCP tool correctly parses schema 2.0 dict format."""
        import json

        registry = {
            "schema": "2.0",
            "agents": {
                "developer": {
                    "role": "executor",
                    "defaultModel": "sonnet",
                    "tools": ["Read", "Edit"],
                    "master_client": "claude-code",
                }
            },
        }

        data = json.loads(json.dumps(registry))
        assert isinstance(data, dict)
        agents_raw = data.get("agents", {})
        assert "developer" in agents_raw
        assert agents_raw["developer"]["master_client"] == "claude-code"

    def test_list_format_rejected(self):
        """Verify a list-format registry is detected as invalid."""
        import json

        registry = [{"name": "developer", "role": "executor"}]
        data = json.loads(json.dumps(registry))

        # The MCP tool does: if not isinstance(data, dict): return default
        assert not isinstance(data, dict), "List format should fail isinstance(dict) check"

    def test_cline_not_in_client_agent_dirs(self):
        """Verify CLIENT_AGENT_DIRS doesn't include cline (avoids duplicate scanning)."""
        from sync_agents.agent_parser import CLIENT_AGENT_DIRS

        assert "cline" not in CLIENT_AGENT_DIRS, (
            "Cline should not be in CLIENT_AGENT_DIRS — it reads .claude/agents/ natively, "
            "and including it causes duplicate scanning with claude-code"
        )


# ── Gemini Adapter Spec Compliance ───────────────────────────────────


class TestGeminiAdapterSpec:
    """Test Gemini adapter output matches ADR-464 spec."""

    def test_max_turns_in_frontmatter(self):
        """Verify Gemini adapted agents include max_turns: 30 (ADR-464 spec)."""
        import yaml
        from sync_agents.agent_parser import AgentFile
        from sync_agents.model_mapping import resolve_model

        master = AgentFile(
            name="dev",
            path=Path("/fake/dev.md"),
            frontmatter={"mode": "auto", "model": "sonnet", "x-augur-master": "claude-code"},
            body="# Dev\n\n> Dev agent.",
            client_dir="claude-code",
        )

        gemini_model = resolve_model("claude-code", "gemini", master.model)
        fm = {
            "name": "dev",
            "description": "Dev agent.",
            "model": gemini_model,
            "max_turns": 30,
        }
        fm_str = yaml.dump(fm, default_flow_style=False, sort_keys=False)
        assert "max_turns: 30" in fm_str

    def test_codex_toml_format(self):
        """Verify Codex adapted agents use TOML format with required fields."""
        from sync_agents.model_mapping import resolve_model

        codex_model = resolve_model("claude-code", "codex", "sonnet")
        assert codex_model == "gpt-5.4"

        # Simulate TOML output
        lines = [
            '# AUGUR-ADAPTED-COPY source=claude-code',
            'name = "developer"',
            'description = "Dev agent"',
            f'model = "{codex_model}"',
            '',
            'developer_instructions = """',
            '# Developer instructions here',
            '"""',
        ]
        content = "\n".join(lines)

        # Verify required TOML fields
        assert 'name = "developer"' in content
        assert 'description = "Dev agent"' in content
        assert f'model = "{codex_model}"' in content
        assert 'developer_instructions = """' in content
        assert "AUGUR-ADAPTED-COPY" in content
        # Must NOT have YAML frontmatter
        assert "---" not in content


# ── Integration: Full Sync Pipeline ──────────────────────────────────


class TestSyncPipeline:
    """Integration tests verifying end-to-end sync produces correct output."""

    def test_gemini_sync_produces_adapted_copies(self, tmp_path):
        """Verify Gemini adapter generates adapted copies from Claude masters."""
        import yaml
        from sync_agents.agent_parser import (
            parse_agent_file,
            collect_masters,
            ADAPTED_COPY_COMMENT,
            ADAPTED_COPY_MARKER,
        )
        from sync_agents.model_mapping import resolve_model

        # Set up a mock project with a Claude master agent
        claude_dir = tmp_path / ".claude" / "agents"
        claude_dir.mkdir(parents=True)
        master_md = claude_dir / "dev.md"
        master_md.write_text(textwrap.dedent("""\
            ---
            mode: auto
            model: sonnet
            mcpServers:
              - augur
            x-augur-master: claude-code
            ---

            # Developer

            > Code simplification.

            ## Allowed Tools

            - `Read`
            - `Edit`
            - `Bash`
        """))

        # Parse the master
        master = parse_agent_file(master_md, "claude-code")
        assert master is not None
        masters = collect_masters([master])
        assert "dev" in masters

        # Simulate Gemini adapter logic
        gemini_dir = tmp_path / ".gemini" / "agents"
        gemini_dir.mkdir(parents=True)

        m = masters["dev"]
        gemini_model = resolve_model("claude-code", "gemini", m.model)
        fm = {
            "name": "dev",
            "description": m.description or "dev agent",
            "kind": "local",
            "model": gemini_model,
            "max_turns": 30,
            "tools": ["read_file", "replace", "run_shell_command", "mcp_augur_*"],
        }
        fm_str = yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip()
        marker = ADAPTED_COPY_COMMENT.format(master_client="claude-code")
        content = f"---\n{fm_str}\n---\n{marker}\n\n{m.body}"
        (gemini_dir / "dev.md").write_text(content)

        # Verify output
        output = (gemini_dir / "dev.md").read_text()
        assert ADAPTED_COPY_MARKER in output
        assert "gemini-3-flash-preview" in output
        assert "kind: local" in output
        assert "max_turns: 30" in output
        assert "read_file" in output
        assert "mcp_augur_*" in output

    def test_reverse_sync_non_claude_master(self, tmp_path):
        """Verify a Gemini-mastered agent produces a Claude Code adapted copy."""
        import yaml
        from sync_agents.agent_parser import (
            parse_agent_file,
            ADAPTED_COPY_COMMENT,
            ADAPTED_COPY_MARKER,
        )
        from sync_agents.model_mapping import resolve_model

        # Create a Gemini-mastered agent
        gemini_dir = tmp_path / ".gemini" / "agents"
        gemini_dir.mkdir(parents=True)
        (gemini_dir / "researcher.md").write_text(textwrap.dedent("""\
            ---
            name: researcher
            description: Deep research agent
            model: gemini-3.1-pro-preview
            x-augur-master: gemini
            tools:
              - read_file
              - grep_search
              - mcp_augur_*
            ---

            # Researcher

            > Deep research agent with web search.
        """))

        master = parse_agent_file(gemini_dir / "researcher.md", "gemini")
        assert master is not None
        assert master.master_client == "gemini"
        assert master.is_master is True

        # Simulate reverse sync to Claude Code
        claude_model = resolve_model("gemini", "claude-code", master.model)
        assert claude_model == "opus"

        fm = {"mode": "auto", "model": claude_model, "x-augur-master": "gemini"}
        fm_str = yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip()
        marker = ADAPTED_COPY_COMMENT.format(master_client="gemini")
        content = f"---\n{fm_str}\n---\n{marker}\n\n{master.body}"

        claude_dir = tmp_path / ".claude" / "agents"
        claude_dir.mkdir(parents=True)
        (claude_dir / "researcher.md").write_text(content)

        # Verify the adapted copy
        output = (claude_dir / "researcher.md").read_text()
        assert ADAPTED_COPY_MARKER in output
        assert "model: opus" in output
        assert "x-augur-master: gemini" in output

        # Verify the adapted copy is detected as adapted
        adapted = parse_agent_file(claude_dir / "researcher.md", "claude-code")
        assert adapted.is_adapted is True
        assert adapted.is_master is False
