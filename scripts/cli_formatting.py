"""
Terminal formatting primitives for the Augur CLI.

Provides Colors (ANSI codes), Symbols (Unicode glyphs), and Formatter
(structured output helpers like headers, tables, progress bars, skill cards).
"""

from __future__ import annotations

import sys


# ============================================================================
# Terminal Colors & Formatting
# ============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    # Basic colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Bright colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'

    # Reset
    RESET = '\033[0m'

    @classmethod
    def disable(cls):
        """Disable colors for non-TTY output."""
        for attr in dir(cls):
            if attr.isupper() and not attr.startswith('_'):
                setattr(cls, attr, '')


# Disable colors if not TTY
if not sys.stdout.isatty():
    Colors.disable()


class Symbols:
    """Unicode symbols for visual output."""
    CHECK = '\u2713'
    CROSS = '\u2717'
    ARROW = '\u2192'
    BULLET = '\u2022'
    STAR = '\u2605'
    CIRCLE = '\u25cf'
    DIAMOND = '\u25c6'
    FOLDER = '\U0001f4c1'
    FILE = '\U0001f4c4'
    GEAR = '\u2699\ufe0f'
    BRAIN = '\U0001f9e0'
    ROCKET = '\U0001f680'
    SEARCH = '\U0001f50d'
    CHART = '\U0001f4ca'
    TOOL = '\U0001f527'
    LIGHT = '\U0001f4a1'
    WARNING = '\u26a0\ufe0f'
    ERROR = '\u274c'
    INFO = '\u2139\ufe0f'
    SKILL = '\U0001f3af'
    MODULE = '\U0001f4e6'
    TIME = '\u23f1\ufe0f'


class Formatter:
    """Format output for beautiful terminal display."""

    @staticmethod
    def header(text: str, char: str = "\u2550") -> str:
        """Create a header with decorative border."""
        width = min(60, len(text) + 4)
        border = char * width
        return f"\n{Colors.CYAN}{border}{Colors.RESET}\n{Colors.BOLD}{Colors.WHITE}  {text}{Colors.RESET}\n{Colors.CYAN}{border}{Colors.RESET}\n"

    @staticmethod
    def subheader(text: str) -> str:
        """Create a subheader."""
        return f"\n{Colors.YELLOW}{Colors.BOLD}{text}{Colors.RESET}\n{Colors.DIM}{'\u2500' * 40}{Colors.RESET}"

    @staticmethod
    def success(text: str) -> str:
        """Format success message."""
        return f"{Colors.GREEN}{Symbols.CHECK} {text}{Colors.RESET}"

    @staticmethod
    def error(text: str) -> str:
        """Format error message."""
        return f"{Colors.RED}{Symbols.ERROR} {text}{Colors.RESET}"

    @staticmethod
    def warning(text: str) -> str:
        """Format warning message."""
        return f"{Colors.YELLOW}{Symbols.WARNING} {text}{Colors.RESET}"

    @staticmethod
    def info(text: str) -> str:
        """Format info message."""
        return f"{Colors.CYAN}{Symbols.INFO} {text}{Colors.RESET}"

    @staticmethod
    def dim(text: str) -> str:
        """Dim text."""
        return f"{Colors.DIM}{text}{Colors.RESET}"

    @staticmethod
    def highlight(text: str) -> str:
        """Highlight text."""
        return f"{Colors.BRIGHT_CYAN}{text}{Colors.RESET}"

    @staticmethod
    def key_value(key: str, value: str, key_width: int = 15) -> str:
        """Format key-value pair."""
        return f"  {Colors.DIM}{key:<{key_width}}{Colors.RESET} {Colors.WHITE}{value}{Colors.RESET}"

    @staticmethod
    def table_row(cols: list, widths: list, colors: list = None) -> str:
        """Format a table row."""
        parts = []
        for i, (col, width) in enumerate(zip(cols, widths)):
            color = colors[i] if colors and i < len(colors) else Colors.WHITE
            parts.append(f"{color}{str(col):<{width}}{Colors.RESET}")
        return "  " + "  ".join(parts)

    @staticmethod
    def progress_bar(value: int, max_value: int, width: int = 20) -> str:
        """Create a simple progress bar."""
        filled = int(width * value / max_value) if max_value > 0 else 0
        bar = "\u2588" * filled + "\u2591" * (width - filled)
        percent = (value / max_value * 100) if max_value > 0 else 0
        return f"{Colors.GREEN}{bar}{Colors.RESET} {percent:.0f}%"

    @staticmethod
    def skill_card(skill: dict) -> str:
        """Format a skill as a card."""
        lines = []
        name = skill.get("name", "Unknown")
        desc = skill.get("description", "")[:60]
        tokens = skill.get("token_estimate", 0)
        triggers = skill.get("triggers", [])[:3]

        # Status indicators
        indicators = []
        if skill.get("has_modules"):
            indicators.append(f"{Colors.GREEN}M{Colors.RESET}")
        if skill.get("has_scripts"):
            indicators.append(f"{Colors.BLUE}S{Colors.RESET}")
        if skill.get("has_references"):
            indicators.append(f"{Colors.YELLOW}R{Colors.RESET}")
        indicator_str = " ".join(indicators) if indicators else ""

        lines.append(f"  {Colors.BOLD}{Colors.CYAN}{Symbols.SKILL} {name}{Colors.RESET}  {indicator_str}")
        lines.append(f"     {Colors.DIM}{desc}{'...' if len(skill.get('description', '')) > 60 else ''}{Colors.RESET}")

        if triggers:
            trigger_str = ", ".join(f'"{t}"' for t in triggers)
            lines.append(f"     {Colors.MAGENTA}Triggers:{Colors.RESET} {Colors.DIM}{trigger_str}{Colors.RESET}")

        lines.append(f"     {Colors.DIM}~{tokens} tokens{Colors.RESET}")

        return "\n".join(lines)
