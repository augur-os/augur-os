"""
Problem Statement and Capability Analyzer.

Extracts what problems the plugin claims to solve from:
- dashboard.yaml (hub.subtitle, action descriptions)
- SKILL.md (description, capabilities section)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class PageCapabilities:
    """Extracted capabilities for a specific page/tab."""

    page_id: str
    page_label: str
    problem_statement: str
    stated_capabilities: List[str]
    actions: List[Dict[str, Any]]
    data_entities: List[str]
    expected_user_actions: List[str]
    data_accumulation: List[str]
    quick_access_needs: List[str]
    icon: str = ""
    href: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage."""
        return {
            "page_id": self.page_id,
            "page_label": self.page_label,
            "problem_statement": self.problem_statement,
            "stated_capabilities": self.stated_capabilities,
            "actions": self.actions,
            "data_entities": self.data_entities,
            "expected_user_actions": self.expected_user_actions,
            "data_accumulation": self.data_accumulation,
            "quick_access_needs": self.quick_access_needs,
            "icon": self.icon,
            "href": self.href,
        }


@dataclass
class PluginCapabilities:
    """Extracted capabilities from plugin files."""

    problem_statement: str
    stated_capabilities: List[str]
    actions: List[Dict[str, Any]]
    data_entities: List[str]
    tabs: List[Dict[str, Any]]
    mcp_tools: List[str]
    description: str = ""
    hub_subtitle: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage."""
        return {
            "problem_statement": self.problem_statement,
            "stated_capabilities": self.stated_capabilities,
            "actions": self.actions,
            "data_entities": self.data_entities,
            "tabs": self.tabs,
            "mcp_tools": self.mcp_tools,
            "description": self.description,
            "hub_subtitle": self.hub_subtitle,
        }


def extract_problem_statement(skill_path: Path) -> PluginCapabilities:
    """Extract the problem statement and capabilities from plugin files.

    Args:
        skill_path: Path to the skill directory

    Returns:
        PluginCapabilities with extracted information
    """
    skill_md = skill_path / "SKILL.md"
    dashboard_yaml = skill_path / "dashboard.yaml"

    problem_parts: List[str] = []
    capabilities: List[str] = []
    actions: List[Dict[str, Any]] = []
    data_entities: List[str] = []
    tabs: List[Dict[str, Any]] = []
    mcp_tools: List[str] = []
    description = ""
    hub_subtitle = ""

    # Parse SKILL.md
    if skill_md.exists():
        content = skill_md.read_text(encoding="utf-8")

        # Extract description from frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 2:
                try:
                    fm = yaml.safe_load(parts[1])
                    if fm and "description" in fm:
                        description = fm["description"]
                        problem_parts.append(description)
                except yaml.YAMLError:
                    pass

        # Extract capabilities section
        cap_match = re.search(r"## Capabilities\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if cap_match:
            cap_lines = cap_match.group(1).strip().split("\n")
            for line in cap_lines:
                if line.strip().startswith("-"):
                    cap_text = line.strip()[1:].strip()
                    if cap_text:
                        capabilities.append(cap_text)

        # Extract features section (additional capabilities)
        features_match = re.search(r"## Features\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if features_match:
            features_lines = features_match.group(1).strip().split("\n")
            for line in features_lines:
                if line.strip().startswith("-"):
                    feature_text = line.strip()[1:].strip()
                    if feature_text and feature_text not in capabilities:
                        capabilities.append(feature_text)

        # Extract MCP tools
        mcp_match = re.search(r"## MCP Tools\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if mcp_match:
            for line in mcp_match.group(1).split("\n"):
                tool_match = re.match(r"-\s+`([^`]+)`", line.strip())
                if tool_match:
                    mcp_tools.append(tool_match.group(1))

        # Extract data entities from Data Structure section
        data_match = re.search(r"## Data Structure\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if data_match:
            # Look for YAML file references
            entity_matches = re.findall(r"(\w+)\.yaml", data_match.group(1))
            data_entities.extend(entity_matches)

    # Parse dashboard.yaml
    if dashboard_yaml.exists():
        try:
            with open(dashboard_yaml, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            hub = config.get("hub", {})
            if hub.get("subtitle"):
                hub_subtitle = hub["subtitle"]
                problem_parts.append(hub_subtitle)

            actions = config.get("actions", [])
            tabs = config.get("tabs", [])

            # Extract data entities from data_dir
            data_dir = config.get("data_dir")
            if data_dir:
                data_entities.append(data_dir)

            # Extract descriptions from actions for problem context
            for action in actions:
                if action.get("description"):
                    problem_parts.append(action["description"])
        except (yaml.YAMLError, OSError):
            pass

    # Build combined problem statement
    problem_statement = " | ".join(filter(None, problem_parts[:3]))

    return PluginCapabilities(
        problem_statement=problem_statement,
        stated_capabilities=capabilities,
        actions=actions,
        data_entities=list(set(data_entities)),
        tabs=tabs,
        mcp_tools=mcp_tools,
        description=description,
        hub_subtitle=hub_subtitle,
    )


def get_available_pages(skill_path: Path) -> List[Dict[str, Any]]:
    """Get list of available pages/tabs for a plugin.

    Args:
        skill_path: Path to the skill directory

    Returns:
        List of tab dicts with id, label, icon, href
    """
    dashboard_yaml = skill_path / "dashboard.yaml"
    if not dashboard_yaml.exists():
        return []

    try:
        with open(dashboard_yaml, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        return config.get("tabs", [])
    except (yaml.YAMLError, OSError):
        return []


def extract_page_capabilities(
    skill_path: Path,
    page_id: str,
) -> Optional[PageCapabilities]:
    """Extract capabilities for a specific page/tab.

    Args:
        skill_path: Path to the skill directory
        page_id: The tab/page ID (e.g., 'recipes', 'reading', 'movies')

    Returns:
        PageCapabilities for the specified page, or None if not found
    """
    skill_md = skill_path / "SKILL.md"
    dashboard_yaml = skill_path / "dashboard.yaml"

    # Find the tab info and page-specific actions
    tab_info: Optional[Dict[str, Any]] = None
    all_tabs: List[Dict[str, Any]] = []
    page_actions: List[Dict[str, Any]] = []
    all_actions: List[Dict[str, Any]] = []

    if dashboard_yaml.exists():
        try:
            with open(dashboard_yaml, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            all_tabs = config.get("tabs", [])
            all_actions = config.get("actions", [])

            # Find the tab
            for tab in all_tabs:
                if isinstance(tab, dict) and tab.get("id") == page_id:
                    tab_info = tab
                    break

            # Filter actions for this page (by scope field)
            for action in all_actions:
                if isinstance(action, dict):
                    action_scope = action.get("scope", "").lower()
                    # Match if scope equals page_id or page_label
                    if action_scope == page_id.lower() or action_scope == page_id.lower() + "s":
                        page_actions.append(action)
        except (yaml.YAMLError, OSError):
            pass

    if not tab_info:
        return None

    page_label = tab_info.get("label", page_id.title())
    icon = tab_info.get("icon", "")
    href = tab_info.get("href", "")

    # Extract page-specific capabilities from SKILL.md
    stated_capabilities: List[str] = []
    data_entities: List[str] = []

    if skill_md.exists():
        content = skill_md.read_text(encoding="utf-8")

        # Look for a section matching the page name (e.g., ### Recipes, ### Reading)
        page_section_pattern = rf"###\s+{re.escape(page_label)}\n(.*?)(?=\n###|\n##|\Z)"
        page_match = re.search(page_section_pattern, content, re.DOTALL | re.IGNORECASE)

        if page_match:
            section_content = page_match.group(1).strip()
            # Extract bullet points as capabilities
            for line in section_content.split("\n"):
                if line.strip().startswith("-"):
                    cap_text = line.strip()[1:].strip()
                    if cap_text:
                        stated_capabilities.append(cap_text)

        # Look for data entities related to this page
        data_pattern = rf"{page_id}[/-]?\w*\.yaml"
        entity_matches = re.findall(data_pattern, content, re.IGNORECASE)
        data_entities.extend(entity_matches)

        # Also check for page_id in data structure section
        data_section = re.search(r"## Data Structure\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if data_section:
            if page_id.lower() in data_section.group(1).lower():
                data_entities.append(page_id)

    # Build problem statement for this page
    problem_statement = f"Manage and organize {page_label.lower()}"
    if stated_capabilities:
        problem_statement = f"{page_label}: {stated_capabilities[0]}" if stated_capabilities else problem_statement

    # Define expected user actions based on page type
    expected_actions = _get_expected_actions_for_page(page_id, page_label)
    data_accumulation = _get_data_accumulation_for_page(page_id, page_label)
    quick_access = _get_quick_access_for_page(page_id, page_label)

    # Also check for schema files for this page
    schemas_dir = skill_path / "schemas"
    if schemas_dir.exists():
        schema_file = schemas_dir / f"{page_id}.yaml"
        if schema_file.exists():
            data_entities.append(f"{page_id}.yaml (schema)")

    return PageCapabilities(
        page_id=page_id,
        page_label=page_label,
        problem_statement=problem_statement,
        stated_capabilities=stated_capabilities,
        actions=page_actions,  # Actions filtered by scope
        data_entities=list(set(data_entities)),
        expected_user_actions=expected_actions,
        data_accumulation=data_accumulation,
        quick_access_needs=quick_access,
        icon=icon,
        href=href,
    )


def _get_expected_actions_for_page(page_id: str, page_label: str) -> List[str]:
    """Get expected user actions based on page type."""
    page_actions: Dict[str, List[str]] = {
        "recipes": [
            "add new recipe",
            "search recipes by ingredient",
            "filter by cuisine type",
            "mark recipe as favorite",
            "create meal plan",
            "generate shopping list",
            "rate recipe",
            "edit recipe",
            "share recipe",
        ],
        "reading": [
            "add book to reading list",
            "mark as currently reading",
            "mark as completed",
            "rate book",
            "add reading notes",
            "track reading progress",
            "search books",
            "filter by genre",
            "set reading goal",
        ],
        "movies": [
            "add movie to watchlist",
            "mark as watched",
            "rate movie",
            "add review/notes",
            "search movies",
            "filter by genre",
            "track watch history",
            "get recommendations",
        ],
        "shopping": [
            "create shopping list",
            "add item to list",
            "check off item",
            "organize by store/aisle",
            "share list",
            "save favorite items",
            "set quantity",
            "estimate cost",
        ],
        "places": [
            "save favorite place",
            "add visit notes",
            "rate place",
            "categorize places",
            "search places",
            "filter by type",
            "get directions",
            "share place",
        ],
        "travel": [
            "create trip plan",
            "add destination",
            "book accommodation",
            "create itinerary",
            "track expenses",
            "save documents",
            "share trip",
            "set reminders",
        ],
        "ideas": [
            "capture quick idea",
            "categorize idea",
            "develop idea",
            "link to project",
            "search ideas",
            "prioritize ideas",
            "archive idea",
            "share idea",
        ],
    }

    # Return page-specific or generic actions
    if page_id.lower() in page_actions:
        return page_actions[page_id.lower()]

    # Generic actions for unknown pages
    return [
        f"add new {page_label.lower()}",
        f"search {page_label.lower()}",
        f"edit {page_label.lower()}",
        f"delete {page_label.lower()}",
        f"filter {page_label.lower()}",
        f"export {page_label.lower()}",
    ]


def _get_data_accumulation_for_page(page_id: str, page_label: str) -> List[str]:
    """Get expected data accumulation patterns for page type."""
    page_data: Dict[str, List[str]] = {
        "recipes": ["recipe collection", "ingredients", "cooking notes", "meal plans", "ratings"],
        "reading": ["book list", "reading notes", "progress", "reviews", "quotes"],
        "movies": ["watchlist", "watch history", "ratings", "reviews"],
        "shopping": ["lists", "items", "stores", "purchase history"],
        "places": ["saved places", "visit history", "ratings", "notes"],
        "travel": ["trips", "itineraries", "bookings", "expenses", "documents"],
        "ideas": ["ideas", "categories", "connections", "development notes"],
    }

    return page_data.get(page_id.lower(), [f"{page_label.lower()} items", "notes", "history"])


def _get_quick_access_for_page(page_id: str, page_label: str) -> List[str]:
    """Get quick access needs for page type."""
    page_quick: Dict[str, List[str]] = {
        "recipes": ["recent recipes", "favorites", "quick meals", "search"],
        "reading": ["currently reading", "up next", "recently finished"],
        "movies": ["watchlist", "recently watched", "recommendations"],
        "shopping": ["active lists", "frequent items", "nearby stores"],
        "places": ["favorites", "recently visited", "nearby"],
        "travel": ["upcoming trips", "active trip", "bookings"],
        "ideas": ["recent ideas", "in development", "quick capture"],
    }

    return page_quick.get(page_id.lower(), ["recent", "favorites", "search"])


def analyze_action_coverage(
    capabilities: PluginCapabilities,
) -> Dict[str, Any]:
    """Analyze how well actions cover stated capabilities.

    Returns:
        Dict with coverage analysis including:
        - coverage_ratio: float (0-1)
        - covered_capabilities: List[str]
        - uncovered_capabilities: List[str]
        - action_count: int
    """
    action_labels = [a.get("label", "").lower() for a in capabilities.actions if isinstance(a, dict)]
    action_descriptions = [a.get("description", "").lower() for a in capabilities.actions if isinstance(a, dict)]

    covered = []
    uncovered = []

    for cap in capabilities.stated_capabilities:
        cap_lower = cap.lower()
        # Check if any action relates to this capability
        found = False
        for label, desc in zip(action_labels, action_descriptions):
            # Simple keyword matching
            cap_words = set(cap_lower.split())
            label_words = set(label.split())
            desc_words = set(desc.split())

            # If there's word overlap, consider it covered
            if cap_words & label_words or cap_words & desc_words:
                found = True
                break

        if found:
            covered.append(cap)
        else:
            uncovered.append(cap)

    total = len(capabilities.stated_capabilities) or 1
    coverage_ratio = len(covered) / total

    return {
        "coverage_ratio": coverage_ratio,
        "covered_capabilities": covered,
        "uncovered_capabilities": uncovered,
        "action_count": len(capabilities.actions),
        "capability_count": len(capabilities.stated_capabilities),
    }


def analyze_ui_structure(capabilities: PluginCapabilities) -> Dict[str, Any]:
    """Analyze UI structure from tabs.

    Returns:
        Dict with UI analysis including:
        - tab_count: int
        - has_overview: bool
        - overview_is_default: bool
        - tab_variety: float (0-1, diversity of tab types)
    """
    tabs = capabilities.tabs
    tab_count = len(tabs)

    has_overview = False
    overview_is_default = False

    for tab in tabs:
        if isinstance(tab, dict):
            tab_id = tab.get("id", "").lower()
            if tab_id == "overview":
                has_overview = True
                if tab.get("default"):
                    overview_is_default = True
                break

    # Calculate tab variety based on unique icons
    unique_icons = set()
    for tab in tabs:
        if isinstance(tab, dict) and tab.get("icon"):
            unique_icons.add(tab["icon"])

    tab_variety = len(unique_icons) / max(tab_count, 1)

    return {
        "tab_count": tab_count,
        "has_overview": has_overview,
        "overview_is_default": overview_is_default,
        "tab_variety": min(tab_variety, 1.0),
        "unique_icons": len(unique_icons),
    }


def analyze_data_structure(skill_path: Path, capabilities: PluginCapabilities) -> Dict[str, Any]:
    """Analyze data structure completeness.

    Returns:
        Dict with data analysis including:
        - has_schemas: bool
        - schema_count: int
        - has_data_dir: bool
        - entity_coverage: float
    """
    schemas_dir = skill_path / "schemas"
    has_schemas = schemas_dir.exists() and any(schemas_dir.iterdir())

    schema_count = 0
    if has_schemas:
        schema_count = len(list(schemas_dir.glob("*.yaml")))

    # Check for data directory in dashboard.yaml
    dashboard_yaml = skill_path / "dashboard.yaml"
    has_data_dir = False
    if dashboard_yaml.exists():
        try:
            with open(dashboard_yaml, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            has_data_dir = bool(config.get("data_dir"))
        except (yaml.YAMLError, OSError):
            pass

    # Calculate entity coverage (schemas vs stated data entities)
    entity_count = len(capabilities.data_entities)
    if entity_count > 0:
        entity_coverage = min(schema_count / entity_count, 1.0)
    else:
        entity_coverage = 1.0 if schema_count > 0 else 0.5

    return {
        "has_schemas": has_schemas,
        "schema_count": schema_count,
        "has_data_dir": has_data_dir,
        "entity_coverage": entity_coverage,
        "declared_entities": capabilities.data_entities,
    }
