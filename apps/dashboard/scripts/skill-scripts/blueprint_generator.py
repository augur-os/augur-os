"""Blueprint generator: convert FlowAnalysis + user overrides into blueprint.yaml (ADR-086 Stage 2).

Input:  FlowAnalysis (from flow_analyzer.py) + optional user answers
Output: blueprint.yaml dict suitable for YAML serialization.

The blueprint is the complete specification consumed by import_codegen.py
to generate all plugin files (SKILL.md, dashboard.yaml, pages, tabs, API routes).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

try:
    from .flow_analyzer import FlowAnalysis
except ImportError:
    from flow_analyzer import FlowAnalysis


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class UserOverrides:
    """User overrides applied on top of FlowAnalysis suggestions.

    Collected during the Questions phase of the import workflow.
    """

    hub_title: str | None = None
    hub_icon: str | None = None
    # Track 3b: hub_bundle is the plugin BUNDLE name (lifestyle/ai/dev/...),
    # not a hub id from config/system/hubs.yaml. Renaming to bundle would
    # be exhaustive across the workflow; the "hub_" prefix is historical.
    hub_bundle: str = "lifestyle"
    hub_category: str = "personal"
    hub_subtitle: str | None = None
    # Tab overrides: list of {id, action} where action is "keep", "remove", or "rename"
    tab_overrides: list[dict[str, str]] = field(default_factory=list)
    # Additional tabs the user wants to add
    extra_tabs: list[dict[str, str]] = field(default_factory=list)
    # Files to force-ignore
    ignore_files: list[str] = field(default_factory=list)
    # Files to force-render as table
    render_files: list[str] = field(default_factory=list)

    @classmethod
    def from_answers(cls, answers: dict[str, Any]) -> UserOverrides:
        """Create from user answers dict (as returned by workflow questions)."""
        return cls(
            hub_title=answers.get("hub_title"),
            hub_icon=answers.get("hub_icon"),
            hub_bundle=answers.get("hub_bundle", "lifestyle"),
            hub_category=answers.get("hub_category", "personal"),
            hub_subtitle=answers.get("hub_subtitle"),
            tab_overrides=answers.get("tab_overrides", []),
            extra_tabs=answers.get("extra_tabs", []),
            ignore_files=answers.get("ignore_files", []),
            render_files=answers.get("render_files", []),
        )


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class BlueprintGenerator:
    """Generate a complete hub blueprint from FlowAnalysis and user overrides.

    Args:
        flow: FlowAnalysis from the flow analyzer.
        overrides: Optional user overrides from the questions phase.
    """

    def __init__(
        self,
        flow: FlowAnalysis,
        overrides: UserOverrides | None = None,
    ) -> None:
        self.flow = flow
        self.overrides = overrides or UserOverrides()

    def generate(self) -> dict[str, Any]:
        """Generate the complete blueprint dict.

        Returns:
            Dict matching the blueprint.schema.yaml format.
        """
        hub_id = self.flow.hub
        title = self.overrides.hub_title or _titleize(hub_id)
        icon = self.overrides.hub_icon or self._infer_icon()
        subtitle = self.overrides.hub_subtitle or f"Dashboard for {title}"

        # Build tabs list, applying user overrides
        tabs = self._build_tabs()

        # Build file strategies, applying user overrides
        strategies = self._build_file_strategies()

        # Classify files into rendered vs external-only
        rendered_files: list[str] = []
        external_only: list[str] = []
        for s in strategies:
            if s["mode"] in ("render-table", "rendered-content", "stat-card"):
                if s["path"] not in rendered_files:
                    rendered_files.append(s["path"])
            elif s["mode"] == "open-external":
                if s["path"] not in external_only:
                    external_only.append(s["path"])

        blueprint: dict[str, Any] = {
            "version": 1,
            "hub": {
                "id": hub_id,
                "title": title,
                "subtitle": subtitle,
                "icon": icon,
                "bundle": self.overrides.hub_bundle,
                "category": self.overrides.hub_category,
            },
            "source": {
                "type": "folder",
                "path": self.flow.source_path,
            },
            "tabs": tabs,
            "stat_cards": [c.__dict__ for c in self.flow.stat_cards],
            "actions": [
                {
                    "id": a.id,
                    "label": a.label,
                    "icon": a.icon,
                    "dispatch": a.dispatch,
                    "source_file": a.source_file,
                    "description": a.description,
                }
                for a in self.flow.actions
            ],
            "file_strategies": strategies,
            "external_only": external_only,
            "rendered_files": rendered_files,
        }

        return blueprint

    # ------------------------------------------------------------------
    # Tab building
    # ------------------------------------------------------------------

    def _build_tabs(self) -> list[dict[str, Any]]:
        """Build tabs list from flow analysis and user overrides."""
        tabs: list[dict[str, Any]] = []

        # Index overrides by tab id
        override_map: dict[str, dict[str, str]] = {}
        for ovr in self.overrides.tab_overrides:
            if "id" in ovr:
                override_map[ovr["id"]] = ovr

        for suggested in self.flow.suggested_tabs:
            ovr = override_map.get(suggested.id, {})
            action = ovr.get("action", "keep")

            if action == "remove":
                continue

            tab: dict[str, Any] = {
                "id": suggested.id,
                "label": ovr.get("label", suggested.label),
                "icon": suggested.icon,
                "description": suggested.description,
                "tab_type": suggested.tab_type,
                "source_files": suggested.source_files,
                "default": suggested.id == "overview",
            }
            tabs.append(tab)

        # Add user-requested extra tabs
        for extra in self.overrides.extra_tabs:
            if extra.get("id") and extra.get("label"):
                tabs.append(
                    {
                        "id": extra["id"],
                        "label": extra["label"],
                        "icon": extra.get("icon", "LayoutDashboard"),
                        "description": extra.get("description", ""),
                        "tab_type": extra.get("tab_type", "table"),
                        "source_files": [],
                        "default": False,
                    }
                )

        return tabs

    # ------------------------------------------------------------------
    # File strategy building
    # ------------------------------------------------------------------

    def _build_file_strategies(self) -> list[dict[str, Any]]:
        """Build file strategies with user overrides applied."""
        strategies: list[dict[str, Any]] = []

        for fs in self.flow.file_strategies:
            path = fs.path

            # User forced ignore
            if path in self.overrides.ignore_files:
                strategies.append(
                    {
                        "path": path,
                        "mode": "ignore",
                        "tab": None,
                        "reason": "User override: ignored",
                    }
                )
                continue

            # User forced render
            if path in self.overrides.render_files:
                strategies.append(
                    {
                        "path": path,
                        "mode": "render-table",
                        "tab": fs.tab,
                        "reason": "User override: forced render-table",
                    }
                )
                continue

            # Default: keep original strategy
            strategies.append(
                {
                    "path": path,
                    "mode": fs.mode,
                    "tab": fs.tab,
                    "reason": fs.reason,
                }
            )

        return strategies

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _infer_icon(self) -> str:
        """Infer a Lucide icon based on hub name or file types."""
        hub = self.flow.hub.lower()

        icon_hints: dict[str, str] = {
            "finance": "DollarSign",
            "budget": "PiggyBank",
            "health": "Heart",
            "career": "Briefcase",
            "lifestyle": "Coffee",
            "home": "Home",
            "content": "PenTool",
            "enterprise": "Building2",
            "project": "FolderKanban",
            "recipes": "ChefHat",
            "travel": "Plane",
            "education": "GraduationCap",
            "music": "Music",
            "photos": "Camera",
        }

        for keyword, icon in icon_hints.items():
            if keyword in hub:
                return icon

        return "LayoutDashboard"


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _titleize(text: str) -> str:
    """Convert slug to Title Case."""
    return re.sub(r"[-_]+", " ", text).strip().title()
