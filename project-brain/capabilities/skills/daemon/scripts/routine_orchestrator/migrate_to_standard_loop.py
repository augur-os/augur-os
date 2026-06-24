"""Finalize canonical x-augur-loop blocks: set runner and remove legacy routine frontmatter."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md has no frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("unterminated frontmatter")
    fm = yaml.safe_load(text[4:end]) or {}
    body = text[end + 5:]
    return fm, body


def finalize_skill(skill_md: Path, *, runner: str = "auto") -> dict[str, Any]:
    """Set every canonical loop block's runner and remove legacy routine frontmatter."""
    skill_md = Path(skill_md)
    text = skill_md.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)

    changed = 0
    single = fm.get("x-augur-loop")
    if isinstance(single, dict):
        single.setdefault("automation", {})["runner"] = runner
        changed += 1
    plural = fm.get("x-augur-loops")
    if isinstance(plural, list):
        for item in plural:
            if isinstance(item, dict):
                item.setdefault("automation", {})["runner"] = runner
                changed += 1
    if changed == 0:
        raise ValueError(f"no x-augur-loop(s) found in {skill_md}")

    fm.pop("x-augur-routine", None)
    fm.pop("x-augur-routines", None)

    new_fm = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, width=4096).rstrip("\n")
    skill_md.write_text(f"---\n{new_fm}\n---\n{body}", encoding="utf-8")
    return {"skill": str(fm.get("name") or skill_md.parent.name), "loops": changed, "runner": runner}
