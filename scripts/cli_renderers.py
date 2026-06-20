"""
Output renderers for the Augur CLI.

Each format_* function takes parsed data from an MCP tool response and returns
a formatted string for terminal display.
"""

from __future__ import annotations

import re

from scripts.cli_formatting import Colors, Formatter, Symbols


def format_skills_list(data: dict) -> str:
    """Format skills list output."""
    lines = []
    lines.append(Formatter.header(f"{Symbols.BRAIN} Augur Skills ({data['count']} available)"))

    # Legend
    lines.append(f"  {Colors.DIM}Legend: {Colors.GREEN}M{Colors.DIM}=Modules {Colors.BLUE}S{Colors.DIM}=Scripts {Colors.YELLOW}R{Colors.DIM}=References{Colors.RESET}\n")

    # Group by category (simple heuristic based on name patterns)
    categories = {
        "Career & Professional": [],
        "Content & Media": [],
        "Development & Ops": [],
        "Data & Analytics": [],
        "Other": []
    }

    for skill in data["skills"]:
        name = skill["name"].lower()
        if any(x in name for x in ["career", "interview", "job"]):
            categories["Career & Professional"].append(skill)
        elif any(x in name for x in ["marketing", "social", "voice", "recipe", "ideas", "collections"]):
            categories["Content & Media"].append(skill)
        elif any(x in name for x in ["developer", "platform-admin", "architect", "validator", "security", "frontend", "webapp"]):
            categories["Development & Ops"].append(skill)
        elif any(x in name for x in ["data", "memory", "knowledge", "inbox"]):
            categories["Data & Analytics"].append(skill)
        else:
            categories["Other"].append(skill)

    for category, skills in categories.items():
        if skills:
            lines.append(Formatter.subheader(category))
            for skill in sorted(skills, key=lambda x: x["name"]):
                lines.append(Formatter.skill_card(skill))
                lines.append("")

    # Footer
    lines.append(f"\n{Colors.DIM}\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500{Colors.RESET}")
    lines.append(f"  {Symbols.LIGHT} Use {Colors.CYAN}augur get <skill>{Colors.RESET} for details")
    lines.append(f"  {Symbols.LIGHT} Use {Colors.CYAN}augur get <skill> -m{Colors.RESET} to see modules")

    return "\n".join(lines)


def format_skill_detail(content: str, skill_name: str) -> str:
    """Format skill detail output with syntax highlighting."""
    lines = []
    lines.append(Formatter.header(f"{Symbols.SKILL} Skill: {skill_name}"))

    # Process markdown content
    in_code_block = False
    in_table = False

    for line in content.split('\n'):
        # Skip YAML frontmatter
        if line.strip() == '---':
            continue
        if line.startswith('name:') or line.startswith('version:') or line.startswith('description:'):
            continue

        # Code blocks
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            if in_code_block:
                lines.append(f"  {Colors.DIM}\u250c{'\u2500' * 50}{Colors.RESET}")
            else:
                lines.append(f"  {Colors.DIM}\u2514{'\u2500' * 50}{Colors.RESET}")
            continue

        if in_code_block:
            lines.append(f"  {Colors.DIM}\u2502{Colors.RESET} {Colors.GREEN}{line}{Colors.RESET}")
            continue

        # Headers
        if line.startswith('# '):
            lines.append(f"\n{Colors.BOLD}{Colors.CYAN}{line[2:]}{Colors.RESET}")
            continue
        if line.startswith('## '):
            lines.append(Formatter.subheader(line[3:]))
            continue
        if line.startswith('### '):
            lines.append(f"\n  {Colors.YELLOW}{Colors.BOLD}{line[4:]}{Colors.RESET}")
            continue

        # Tables
        if '|' in line and line.strip().startswith('|'):
            if '---' in line:
                continue
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if not in_table:
                in_table = True
                # Header row
                lines.append(f"  {Colors.BOLD}{Colors.WHITE}{'  '.join(cells)}{Colors.RESET}")
                lines.append(f"  {Colors.DIM}{'\u2500' * 50}{Colors.RESET}")
            else:
                lines.append(f"  {Colors.DIM}{'  '.join(cells)}{Colors.RESET}")
            continue
        else:
            in_table = False

        # List items
        if line.strip().startswith('- '):
            lines.append(f"  {Colors.CYAN}{Symbols.BULLET}{Colors.RESET} {line.strip()[2:]}")
            continue
        if line.strip().startswith('* '):
            lines.append(f"  {Colors.CYAN}{Symbols.BULLET}{Colors.RESET} {line.strip()[2:]}")
            continue

        # Bold text
        if '**' in line:
            line = re.sub(r'\*\*([^*]+)\*\*', f'{Colors.BOLD}\\1{Colors.RESET}', line)

        # Regular text
        if line.strip():
            lines.append(f"  {line}")

    return "\n".join(lines)


def format_module_content(content: str, module_name: str) -> str:
    """Format module content."""
    return format_skill_detail(content, f"Module: {module_name}")


def format_action_result(data: dict) -> str:
    """Format action result."""
    lines = []
    lines.append(Formatter.header(f"{Symbols.ROCKET} Action: {data.get('action', 'Unknown')}"))

    lines.append(Formatter.key_value("Skill", data.get("skill", "N/A")))
    lines.append(Formatter.key_value("Script", f"{Colors.GREEN}Available{Colors.RESET}" if data.get("script_available") else f"{Colors.DIM}Not found{Colors.RESET}"))

    if data.get("params"):
        lines.append(Formatter.subheader("Parameters"))
        for k, v in data["params"].items():
            lines.append(Formatter.key_value(k, str(v)))

    if data.get("suggested_modules"):
        lines.append(Formatter.subheader("Suggested Modules"))
        for mod in data["suggested_modules"]:
            lines.append(f"  {Colors.CYAN}{Symbols.MODULE}{Colors.RESET} {mod}")

    if data.get("guidance"):
        lines.append(Formatter.subheader("Guidance"))
        lines.append(f"  {Colors.DIM}{data['guidance']}{Colors.RESET}")

    return "\n".join(lines)


def format_find_result(data: dict) -> str:
    """Format find/search result."""
    lines = []
    lines.append(Formatter.header(f"{Symbols.SEARCH} Search: \"{data.get('query', '')}\""))

    matches = data.get("matches", [])
    if not matches:
        lines.append(f"\n  {Colors.YELLOW}No matching skills found.{Colors.RESET}")
        lines.append(f"  {Colors.DIM}Try broader terms or check 'augur list' for available skills.{Colors.RESET}")
    else:
        lines.append(f"\n  Found {Colors.GREEN}{len(matches)}{Colors.RESET} matching skill(s):\n")
        for i, match in enumerate(matches, 1):
            score = match.get("score", 0)
            score_color = Colors.GREEN if score > 5 else Colors.YELLOW if score > 2 else Colors.DIM
            lines.append(f"  {Colors.BOLD}{i}.{Colors.RESET} {Colors.CYAN}{match.get('skill', 'Unknown')}{Colors.RESET}")
            lines.append(f"     Score: {score_color}{score:.1f}{Colors.RESET}")
            if match.get("description"):
                lines.append(f"     {Colors.DIM}{match['description'][:60]}...{Colors.RESET}")
            lines.append("")

    return "\n".join(lines)


def format_metrics(data: dict) -> str:
    """Format metrics output."""
    lines = []
    lines.append(Formatter.header(f"{Symbols.CHART} Augur Metrics"))

    # Sessions
    sessions = data.get("sessions", 0)
    lines.append(Formatter.subheader("Sessions"))
    lines.append(Formatter.key_value("Total Sessions", str(sessions)))
    if data.get("session_start"):
        lines.append(Formatter.key_value("Current Started", data["session_start"][:19]))

    # Tool Usage
    tool_calls = data.get("tool_calls", {})
    if tool_calls:
        lines.append(Formatter.subheader("Tool Usage"))
        total = sum(tool_calls.values())
        for tool, count in sorted(tool_calls.items(), key=lambda x: -x[1])[:10]:
            bar = Formatter.progress_bar(count, total, width=15)
            lines.append(f"  {tool:<30} {count:>4}  {bar}")

    # Skill Usage
    skill_usage = data.get("skill_usage", {})
    if skill_usage:
        lines.append(Formatter.subheader("Skill Usage"))
        for skill, count in sorted(skill_usage.items(), key=lambda x: -x[1])[:5]:
            lines.append(Formatter.key_value(skill, str(count)))

    # Cache
    cache = data.get("cache_stats", {})
    if cache:
        lines.append(Formatter.subheader("Cache"))
        lines.append(Formatter.key_value("Entries", str(cache.get("entries", 0))))

    return "\n".join(lines)


def format_patterns(data: dict) -> str:
    """Format patterns output."""
    lines = []
    lines.append(Formatter.header(f"{Symbols.LIGHT} Learned Patterns ({data.get('count', 0)}/{data.get('total', 0)})"))

    patterns = data.get("patterns", [])
    if not patterns:
        lines.append(f"\n  {Colors.DIM}No pending patterns.{Colors.RESET}")
    else:
        for p in patterns[:10]:  # Show max 10
            status = f"{Colors.GREEN}Applied{Colors.RESET}" if p.get("applied") else f"{Colors.YELLOW}Pending{Colors.RESET}"
            lines.append(f"\n  {Colors.BOLD}{p.get('id', 'N/A')}{Colors.RESET} [{status}]")
            lines.append(Formatter.key_value("Skill", p.get("skill", "N/A")))
            lines.append(Formatter.key_value("Type", p.get("type", "N/A")))
            lines.append(f"  {Colors.DIM}{p.get('description', '')[:80]}...{Colors.RESET}")

    return "\n".join(lines)


def format_buttons_list(data: dict) -> str:
    """Format action buttons list output."""
    lines = []
    count = data.get("count", 0)
    lines.append(Formatter.header(f"{Symbols.GEAR} Action Buttons ({count} available)"))

    actions = data.get("actions", [])

    # Group by page for readability
    pages: dict[str, list[dict]] = {}
    for action in actions:
        page = action.get("page", "/")
        pages.setdefault(page, []).append(action)

    for page in sorted(pages):
        lines.append(Formatter.subheader(page))
        for action in sorted(pages[page], key=lambda a: a.get("id", "")):
            action_id = action.get("id", "unknown")
            label = action.get("label", action_id)
            description = action.get("description", "")
            dispatch = action.get("dispatch", "")
            plugin = action.get("_plugin", "")

            lines.append(f"  {Colors.BOLD}{label}{Colors.RESET} {Colors.DIM}({action_id}){Colors.RESET}")
            lines.append(f"     {Colors.DIM}{description}{Colors.RESET}")
            lines.append(f"     {Colors.CYAN}Dispatch:{Colors.RESET} {dispatch}  {Colors.CYAN}Plugin:{Colors.RESET} {Colors.DIM}{plugin}{Colors.RESET}")

            agents = action.get("agents", [])
            if agents:
                agent_list = ", ".join(agents) if isinstance(agents, list) else str(agents)
                lines.append(f"     {Colors.BLUE}Agents:{Colors.RESET} {Colors.DIM}{agent_list}{Colors.RESET}")

            mcp_tools = action.get("mcp_tools", [])
            if mcp_tools:
                lines.append(f"     {Colors.GREEN}MCP:{Colors.RESET} {Colors.DIM}{', '.join(mcp_tools)}{Colors.RESET}")

            lines.append("")

    if not actions:
        lines.append(f"  {Colors.DIM}No action buttons found.{Colors.RESET}")

    return "\n".join(lines).rstrip()
