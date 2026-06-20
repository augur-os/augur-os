"""
Subagent Profile Dataclass.

Defines the structure for a Claude Code subagent profile generated from
crew SKILL.md frontmatter. Used by sync_agents.py to generate
.claude/agents/{skill}.md files.

Part of ADR-046: Claude Code Crew Orchestration Bridge.
ADR-460 Phase 5: Agent tier operationalization via x-augur-agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Maps crew tier capability names to Claude Code model preferences
CAPABILITY_TO_MODEL = {
    "fast": "haiku",
    "balanced": "sonnet",
    "reasoning": "opus",
}

# Maps crew tier capability names to Claude Code model IDs (from tier_selector.py)
CAPABILITY_TO_MODEL_ID = {
    "fast": "claude-3-5-haiku-latest",
    "balanced": "claude-sonnet-4-20250514",
    "reasoning": "claude-opus-4-5-20251101",
}

# ADR-460: Map x-augur-agent role to Claude Code mode
ROLE_TO_CLAUDE_MODE = {
    "executor": "auto",
    "advisor": "plan",
    # Claude Code has no distinct orchestrator mode; maps to auto like executor.
    # Orchestrator distinction is in the Agent tool availability, not the mode.
    "orchestrator": "auto",
}


@dataclass
class TierProfile:
    """A single tier configuration for a crew subagent."""

    capability: str  # "fast" | "balanced" | "reasoning"
    mode: str  # "advisory" | "executor"
    tools: list[str] = field(default_factory=list)
    max_files: str = "5"  # str to handle "unlimited"
    use_cases: list[str] = field(default_factory=list)
    escalate_when: list[str] = field(default_factory=list)
    cost_multiplier: float = 1.0  # ADR-460: cost weight for tier routing

    @property
    def model_name(self) -> str:
        """Map capability to Claude model name (haiku/sonnet/opus)."""
        return CAPABILITY_TO_MODEL.get(self.capability, "sonnet")

    @property
    def model_id(self) -> str:
        """Map capability to Claude model ID."""
        return CAPABILITY_TO_MODEL_ID.get(self.capability, "claude-sonnet-4-20250514")

    @property
    def is_advisory(self) -> bool:
        return self.mode == "advisory"


@dataclass
class SafetyConfig:
    """Safety configuration parsed from SKILL.md frontmatter."""

    # ADR-460: New granular safety fields from x-augur-agent
    max_file_edits: int = 20
    max_file_creates: int = 5
    max_bash_commands: int = 30
    banned_paths: tuple[str, ...] = ()
    require_confirmation: tuple[str, ...] = ()
    banned_operations: tuple[str, ...] = ()
    # Legacy fields (kept for backward compat with older SKILL.md format)
    read_only: bool = True
    iron_law: str = ""
    circuit_breaker_max_failures: int = 3
    circuit_breaker_action: str = "escalate_to_human"
    verification_required: list[str] = field(default_factory=list)
    protected_areas: list[str] = field(default_factory=list)


@dataclass
class EscalationConfig:
    """Escalation configuration parsed from SKILL.md x-augur-agent (ADR-460)."""

    auto_escalate_on: tuple[str, ...] = ()
    escalation_path: str = "fast -> standard -> deep -> parent"
    max_escalations: int = 2
    cooldown_seconds: int = 300


@dataclass
class SubagentProfile:
    """
    Claude Code subagent profile generated from a crew SKILL.md.

    Contains everything needed to generate a .claude/agents/{name}.md file
    that Claude Code can use when spawning this agent via the Task tool.
    """

    # Identity
    name: str
    display_name: str
    description: str
    version: str = "0.1.0"

    # Tiers (fast/standard/deep)
    tiers: dict[str, TierProfile] = field(default_factory=dict)

    # Safety
    safety: SafetyConfig = field(default_factory=SafetyConfig)

    # Escalation (ADR-460)
    escalation: EscalationConfig | None = None

    # Content (from SKILL.md body)
    capabilities: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    commands: list[dict[str, str]] = field(default_factory=list)

    # Chain integration
    chain_participation: list[str] = field(default_factory=list)

    # Triggers (for routing)
    triggers: list[str] = field(default_factory=list)

    # ADR-460: Agent tier configuration from x-augur-agent
    agent_role: str = ""  # "executor" | "advisor" | "orchestrator"
    agent_default_model: str = ""  # "sonnet" | "opus" | "haiku"
    agent_tools: list[str] = field(default_factory=list)

    # Enrichment (ADR-145)
    skills: list[str] = field(default_factory=list)
    memory: str = ""  # "project" | "user" | ""
    max_turns: int = 0  # 0 = no limit
    mcp_servers: list[str] = field(default_factory=list)
    agent_hooks: dict[str, list[dict]] = field(default_factory=dict)  # per-agent hooks
    isolation: str = ""  # "worktree" | "" — whether agent gets isolated worktree

    # ADR-464: Master client declaration
    master_client: str = "claude-code"  # Which client owns this agent

    @property
    def default_tier(self) -> TierProfile:
        """Return the standard tier as default, falling back to x-augur-agent or advisory default."""
        if self.tiers:
            # Prefer "standard" tier, fall back to first available
            return self.tiers.get("standard", next(iter(self.tiers.values())))

        # ADR-460: Use x-augur-agent data when no explicit tiers defined
        if self.agent_role:
            # Map role to capability for model lookup
            capability = {"haiku": "fast", "sonnet": "balanced", "opus": "reasoning"}.get(
                self.agent_default_model, "balanced"
            )
            claude_mode = ROLE_TO_CLAUDE_MODE.get(self.agent_role, "plan")
            return TierProfile(
                capability=capability,
                mode=claude_mode,
                tools=self.agent_tools or ["Read", "Glob", "Grep"],
                max_files="unlimited" if self.agent_role != "advisor" else "10",
            )

        # Fallback: default advisory profile
        return TierProfile(
            capability="balanced",
            mode="advisory",
            tools=["Read", "Glob", "Grep"],
            max_files="10",
        )

    @property
    def is_advisory(self) -> bool:
        """True if the agent is advisory at its default (standard) tier."""
        return self.default_tier.is_advisory

    def to_agent_markdown(
        self,
        tier: str = "standard",
        project_context: str | None = None,
    ) -> str:
        """
        Generate Claude Code agent markdown for .claude/agents/{name}.md.

        Args:
            tier: Which tier to generate for ("fast", "standard", "deep")
            project_context: Optional project-specific context to inject

        Returns:
            Markdown string suitable for .claude/agents/{name}.md
        """
        tp = self.tiers.get(tier, self.default_tier)

        lines: list[str] = []

        # ADR-460: Always emit YAML frontmatter with mode/model for Claude Code
        fm_lines = ["---"]
        # Map mode to Claude Code mode names
        claude_mode = tp.mode
        if self.agent_role:
            claude_mode = ROLE_TO_CLAUDE_MODE.get(self.agent_role, "plan")
        elif tp.mode == "advisory":
            claude_mode = "plan"
        elif tp.mode in ("executor", "auto"):
            claude_mode = "auto"
        fm_lines.append(f"mode: {claude_mode}")
        fm_lines.append(f"model: {tp.model_name}")
        # ADR-145: Include enrichment fields when present
        if self.skills:
            fm_lines.append("skills:")
            for s in self.skills:
                fm_lines.append(f"  - {s}")
        if self.memory:
            fm_lines.append(f"memory: {self.memory}")
        if self.max_turns:
            fm_lines.append(f"maxTurns: {self.max_turns}")
        if self.mcp_servers:
            fm_lines.append("mcpServers:")
            for srv in self.mcp_servers:
                fm_lines.append(f"  - {srv}")
        if self.isolation:
            fm_lines.append(f"isolation: {self.isolation}")
        if self.agent_hooks:
            fm_lines.append("hooks:")
            for event, matchers in self.agent_hooks.items():
                fm_lines.append(f"  {event}:")
                for matcher_entry in matchers:
                    fm_lines.append(f"    - matcher: \"{matcher_entry.get('matcher', '')}\"")
                    fm_lines.append("      hooks:")
                    for hook in matcher_entry.get("hooks", []):
                        fm_lines.append(f"        - type: {hook.get('type', 'command')}")
                        fm_lines.append(f"          command: \"{hook.get('command', '')}\"")
        fm_lines.append("---")
        lines.extend(fm_lines)
        lines.append("")

        # Determine display role
        role_display = self.agent_role or ("advisor" if tp.is_advisory else "executor")

        lines.extend(
            [
                f"# {self.display_name}",
                "",
                f"> {self.description}",
                "",
                f"**Model**: {tp.model_name} | **Mode**: {claude_mode} | **Role**: {role_display}",
                "",
            ]
        )

        # Available tiers (for cost-aware routing)
        if self.tiers:
            lines.append("## Available Tiers")
            lines.append("")
            lines.append("When spawning this agent via Task tool, select the model " "matching the task complexity:")
            lines.append("")
            for tier_name, tier_profile in sorted(self.tiers.items()):
                marker = " ← default" if tier_name == tier else ""
                lines.append(f"- **{tier_name}**: `{tier_profile.model_name}` " f"({tier_profile.mode}){marker}")
            lines.append("")

        # System instructions
        lines.append("## Instructions")
        lines.append("")

        if role_display == "advisor":
            lines.append(
                "You are in **advisory mode**. You MUST NOT modify files. " "Only analyze, recommend, and report."
            )
        elif role_display == "orchestrator":
            lines.append(
                "You are in **orchestrator mode**. You may modify files and "
                "delegate to sub-agents via the Agent tool."
            )
        else:
            lines.append(
                "You are in **executor mode**. You may modify files, " "but must follow all safety constraints below."
            )
        lines.append("")

        # Iron law
        if self.safety.iron_law:
            lines.append(f"**Iron Law**: {self.safety.iron_law}")
            lines.append("")

        # Project context
        if project_context:
            lines.append("## Project Context")
            lines.append("")
            lines.append(project_context)
            lines.append("")

        # Tools
        lines.append("## Allowed Tools")
        lines.append("")
        for tool in tp.tools:
            lines.append(f"- {tool}")
        lines.append("")

        # Capabilities
        if self.capabilities:
            lines.append("## Capabilities")
            lines.append("")
            for cap in self.capabilities:
                lines.append(f"- {cap}")
            lines.append("")

        # Constraints
        if self.constraints:
            lines.append("## Constraints")
            lines.append("")
            for con in self.constraints:
                lines.append(f"- {con}")
            lines.append("")

        # Protected areas
        if self.safety.protected_areas:
            lines.append("## Protected Areas (Require Human Approval)")
            lines.append("")
            for area in self.safety.protected_areas:
                lines.append(f"- {area}")
            lines.append("")

        # ADR-460: Safety constraints from x-augur-agent
        if self.safety and (self.safety.banned_paths or self.safety.banned_operations):
            lines.append("## Safety Constraints")
            lines.append("")
            lines.append(f"- Maximum {self.safety.max_file_edits} file edits per run")
            lines.append(f"- Maximum {self.safety.max_file_creates} file creates per run")
            if self.safety.banned_paths:
                lines.append("- NEVER modify files matching: " + ", ".join(f"`{p}`" for p in self.safety.banned_paths))
            if self.safety.require_confirmation:
                lines.append("- ASK before modifying: " + ", ".join(f"`{p}`" for p in self.safety.require_confirmation))
            if self.safety.banned_operations:
                lines.append("- NEVER execute: " + ", ".join(f"`{c}`" for c in self.safety.banned_operations))
            lines.append("")

        # ADR-460: Escalation rules from x-augur-agent
        if self.escalation and self.escalation.auto_escalate_on:
            lines.append("## Escalation Rules")
            lines.append("")
            lines.append(f"- Path: {self.escalation.escalation_path}")
            lines.append(f"- Auto-escalate when: {', '.join(self.escalation.auto_escalate_on)}")
            lines.append(f"- Maximum {self.escalation.max_escalations} escalations per task")
            lines.append("")

        # Circuit breaker
        lines.append("## Circuit Breaker")
        lines.append("")
        lines.append(
            f"After {self.safety.circuit_breaker_max_failures} consecutive failures: "
            f"`{self.safety.circuit_breaker_action}`"
        )
        lines.append("")

        # Escalation
        if tp.escalate_when:
            lines.append("## Escalation Triggers")
            lines.append("")
            for trigger in tp.escalate_when:
                lines.append(f"- {trigger}")
            lines.append("")

        # Max files
        lines.append(f"**Max files**: {tp.max_files}")
        lines.append("")

        return "\n".join(lines)

    def to_registry_entry(self) -> dict:
        """Generate a JSON-serializable registry entry for registry.json (schema 2.0)."""
        default = self.default_tier
        role = self.agent_role or ("advisor" if default.is_advisory else "executor")

        # ADR-460: Populate tiers with actual tier data
        tiers_dict = {}
        if self.tiers:
            for name, tp in self.tiers.items():
                tier_entry: dict = {
                    "model": tp.model_name,
                    "tools": tp.tools,
                    "contextBudget": int(tp.max_files) if tp.max_files.isdigit() else 128000,
                    "costMultiplier": tp.cost_multiplier,
                }
                if tp.use_cases:
                    tier_entry["appropriateFor"] = tp.use_cases
                tiers_dict[name] = tier_entry

        # ADR-460: Safety section
        safety_dict = {}
        if self.safety and self.safety.banned_paths:
            safety_dict = {
                "maxFileEdits": self.safety.max_file_edits,
                "bannedPaths": list(self.safety.banned_paths),
                "bannedOperations": list(self.safety.banned_operations),
            }

        # ADR-460: Escalation section
        escalation_dict = {}
        if self.escalation and self.escalation.auto_escalate_on:
            escalation_dict = {
                "path": self.escalation.escalation_path,
                "maxEscalations": self.escalation.max_escalations,
            }

        entry = {
            "role": role,
            "defaultModel": default.model_name,
            "tools": default.tools,
            "master_client": self.master_client,
            "tiers": tiers_dict,
            "safety": safety_dict,
            "escalation": escalation_dict,
        }
        # ADR-145: Include enrichment fields when present
        if self.skills:
            entry["skills"] = self.skills
        if self.memory:
            entry["memory"] = self.memory
        if self.max_turns:
            entry["max_turns"] = self.max_turns
        if self.mcp_servers:
            entry["mcp_servers"] = self.mcp_servers
        if self.agent_hooks:
            entry["hooks"] = self.agent_hooks
        if self.isolation:
            entry["isolation"] = self.isolation
        return entry
