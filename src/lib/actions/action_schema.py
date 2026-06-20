from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml

VALID_KINDS = {"ai", "mcp"}
VALID_DISPATCH = {"fire", "oneshot", "ide", "chat", "modal"}
VALID_SURFACES = {"card", "page", "html"}


class ActionSchemaError(ValueError):
    pass


@dataclass
class Action:
    id: str
    label: str
    kind: str
    dispatch: str = "ide"
    surfaces: list[str] = field(default_factory=lambda: ["card"])
    mcp_tool: str | None = None
    template: str | None = None
    icon: str | None = None
    categories: list[str] = field(default_factory=list)
    args: dict = field(default_factory=dict)
    when: dict = field(default_factory=dict)
    confirm: str | None = None
    modal: str | None = None
    schedule: dict | None = None


def load_actions_yaml(path: Path) -> list[Action]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    items = raw.get("actions") or []
    out: list[Action] = []
    seen: set[str] = set()
    for i, it in enumerate(items):
        aid = it.get("id")
        if not aid:
            raise ActionSchemaError(f"{path}: action #{i} missing id")
        if aid in seen:
            raise ActionSchemaError(f"{path}: duplicate action id '{aid}'")
        seen.add(aid)
        kind = it.get("kind")
        if kind not in VALID_KINDS:
            raise ActionSchemaError(f"{path}:{aid}: kind must be one of {VALID_KINDS}")
        dispatch = it.get("dispatch", "ide")
        if dispatch not in VALID_DISPATCH:
            raise ActionSchemaError(f"{path}:{aid}: dispatch must be one of {VALID_DISPATCH}")
        surfaces = it.get("surfaces", ["card"])
        if not surfaces or any(s not in VALID_SURFACES for s in surfaces):
            raise ActionSchemaError(f"{path}:{aid}: surfaces must be subset of {VALID_SURFACES}")
        if dispatch == "fire" and not (kind == "mcp" and it.get("mcp_tool")):
            raise ActionSchemaError(f"{path}:{aid}: dispatch 'fire' requires kind 'mcp' + mcp_tool")
        if kind == "ai" and not it.get("template"):
            raise ActionSchemaError(f"{path}:{aid}: kind 'ai' requires template")
        if "card" in surfaces and not it.get("categories"):
            raise ActionSchemaError(f"{path}:{aid}: surfaces[card] requires categories")
        if it.get("schedule") and not (dispatch == "fire" and kind == "mcp" and it.get("mcp_tool")):
            raise ActionSchemaError(f"{path}:{aid}: schedule requires dispatch 'fire' + kind 'mcp' + mcp_tool")
        out.append(
            Action(
                id=aid,
                label=it.get("label", aid),
                kind=kind,
                dispatch=dispatch,
                surfaces=surfaces,
                mcp_tool=it.get("mcp_tool"),
                template=it.get("template"),
                icon=it.get("icon"),
                categories=it.get("categories", []),
                args=it.get("args", {}),
                when=it.get("when", {}),
                confirm=it.get("confirm"),
                modal=it.get("modal"),
                schedule=it.get("schedule"),
            )
        )
    return out
