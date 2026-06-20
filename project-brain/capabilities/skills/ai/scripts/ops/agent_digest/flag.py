# skills/auto-agent-digest/scripts/flag.py
"""Executor for the /flag slash command.

Parses user input, resolves directive mapping, and appends a boosted
event to the agent-digest journal.

Usage: /flag "<description>" [--rule <rule_id>] [--adr <ADR-NNN>]
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from collect_session_signals import infer_directive


def parse_flag_args(args_str: str) -> dict:
    """Parse /flag command arguments."""
    desc_match = re.search(r'"([^"]+)"', args_str)
    description = desc_match.group(1) if desc_match else args_str.strip().strip('"')

    rule_match = re.search(r"--rule\s+(\S+)", args_str)
    rule = rule_match.group(1) if rule_match else None

    adr_match = re.search(r"--adr\s+(\S+)", args_str)
    adr = adr_match.group(1) if adr_match else None

    return {"description": description, "rule": rule, "adr": adr}


def build_event(
    description: str,
    rule: str | None = None,
    adr: str | None = None,
    directive_map: dict[str, dict] | None = None,
) -> dict:
    """Build a journal event from /flag input."""
    if rule:
        resolved_rule = rule
    elif adr:
        resolved_rule = adr
    elif directive_map:
        inferred = infer_directive(description, directive_map)
        resolved_rule = inferred if inferred else f"manual:{description}"
    else:
        resolved_rule = f"manual:{description}"

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "manual",
        "type": "flag",
        "rule": resolved_rule,
        "note": description,
        "priority": "boost",
    }
