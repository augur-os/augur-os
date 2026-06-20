"""Guard: the Slash Commands roster has a single source — the computed
generator in ``templates.py`` (fed by ``discover_commands()``).

ADR-796 follow-up. The command roster rendered into CLAUDE.md / AGENTS.md /
CODEX.md is computed from the live command catalog. ``docs/agent-topics`` topic
docs must NOT hand-author a parallel ``**Core** (N): /a, /b`` roster: that
duplicate is fed by nothing, so it silently drifts from the catalog the moment a
command is added, retired, or re-grouped (exactly the dual-source drift this ADR
set out to kill). Topic docs should point to the computed roster / ``/commands``
instead of restating it.
"""

from __future__ import annotations

import re
from pathlib import Path


def _project_root() -> Path:
    root = Path(__file__).resolve()
    while not (root / "docs" / "agent-topics").is_dir():
        if root.parent == root:
            raise RuntimeError("Could not locate project root (docs/agent-topics)")
        root = root.parent
    return root


# A hand-authored command roster line: ``**Core** (11): `/adr`, ...``.
# The ``(\d+):`` count distinguishes it from prose like ``**Core** (`requirements.txt`)``.
_ROSTER_RE = re.compile(r"^\*\*(?:App|Core|Dev|Test|Ops)\*\*\s*\(\d+\):", re.MULTILINE)


def test_no_handauthored_command_roster_in_topic_docs() -> None:
    topics_dir = _project_root() / "docs" / "agent-topics"
    offenders: dict[str, list[str]] = {}
    for md in sorted(topics_dir.glob("*.md")):
        hits = _ROSTER_RE.findall(md.read_text(encoding="utf-8"))
        if hits:
            offenders[md.name] = hits
    assert not offenders, (
        "Hand-authored command roster found in topic docs; this duplicates the "
        "computed Slash Commands section (templates.py) and will drift. Replace "
        f"it with a pointer to /commands or the generated roster. Offenders: {offenders}"
    )
