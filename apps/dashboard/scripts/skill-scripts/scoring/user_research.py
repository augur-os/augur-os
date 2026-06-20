"""
User Journey Research.

Uses WebFetch/WebSearch to understand user expectations for this type of plugin.
Builds a "user expectation model" based on:
- What actions users typically want
- What data accumulates over time
- What needs fast review/access
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class UserExpectationModel:
    """Model of user expectations for a plugin category."""

    category: str
    typical_actions: List[str]
    data_accumulation_patterns: List[str]
    fast_access_needs: List[str]
    common_workflows: List[str]
    pain_points: List[str]
    sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage."""
        return {
            "category": self.category,
            "typical_actions": self.typical_actions,
            "data_accumulation_patterns": self.data_accumulation_patterns,
            "fast_access_needs": self.fast_access_needs,
            "common_workflows": self.common_workflows,
            "pain_points": self.pain_points,
            "sources": self.sources,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserExpectationModel":
        """Deserialize from storage."""
        return cls(
            category=data.get("category", ""),
            typical_actions=data.get("typical_actions", []),
            data_accumulation_patterns=data.get("data_accumulation_patterns", []),
            fast_access_needs=data.get("fast_access_needs", []),
            common_workflows=data.get("common_workflows", []),
            pain_points=data.get("pain_points", []),
            sources=data.get("sources", []),
        )


def extract_keywords(text: str) -> List[str]:
    """Extract important keywords from text."""
    stopwords = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "for",
        "with",
        "to",
        "of",
        "in",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "you",
        "your",
        "i",
        "my",
    }
    words = re.findall(r"\b[a-z]+\b", text.lower())
    return [w for w in words if w not in stopwords and len(w) > 3]


def build_search_queries(plugin_name: str, problem_statement: str) -> List[str]:
    """Build search queries to research user expectations.

    Args:
        plugin_name: Name of the plugin/bundle (e.g., "lifestyle", "career")
            -- this is a plugin BUNDLE id, not a hub id from
            config/system/hubs.yaml.
        problem_statement: Extracted problem statement

    Returns:
        List of search queries to execute
    """
    # Extract key terms from problem statement
    keywords = extract_keywords(problem_statement)
    keyword_str = " ".join(keywords[:3]) if keywords else plugin_name

    queries = [
        f"{plugin_name} app features users want 2026",
        f"best {plugin_name} software UX patterns",
        f"{keyword_str} user workflow automation",
        f"personal {plugin_name} data management best practices",
    ]
    return queries


def parse_search_results(results: List[Dict[str, Any]]) -> UserExpectationModel:
    """Parse search results to build user expectation model.

    Args:
        results: List of search result dicts with 'snippet', 'url', 'title' keys

    Returns:
        UserExpectationModel built from the results
    """
    typical_actions: List[str] = []
    data_patterns: List[str] = []
    fast_access: List[str] = []
    workflows: List[str] = []
    pain_points: List[str] = []
    sources: List[str] = []

    for result in results:
        if result.get("url"):
            sources.append(result["url"])

        content = " ".join(
            [
                result.get("snippet", ""),
                result.get("title", ""),
            ]
        ).lower()

        # Extract action patterns (verbs + nouns)
        action_patterns = re.findall(
            r"(add|create|track|manage|search|filter|export|import|share|"
            r"view|edit|delete|organize|save|archive|tag|sort|find)\s+(\w+)",
            content,
        )
        for verb, noun in action_patterns:
            action = f"{verb} {noun}"
            if action not in typical_actions:
                typical_actions.append(action)

        # Extract data patterns
        data_patterns_found = re.findall(
            r"(store|save|track|log|record|collect|accumulate)\s+(\w+(?:\s+\w+)?)",
            content,
        )
        for _, pattern in data_patterns_found:
            if pattern not in data_patterns:
                data_patterns.append(pattern)

        # Fast access patterns
        fast_patterns = re.findall(
            r"(quick|fast|instant|one-click|easy|rapid)\s+(\w+(?:\s+\w+)?)",
            content,
        )
        for _, pattern in fast_patterns:
            if pattern not in fast_access:
                fast_access.append(pattern)

        # Workflow patterns
        workflow_patterns = re.findall(
            r"(workflow|process|routine|habit|daily|weekly)\s+(\w+(?:\s+\w+)?)",
            content,
        )
        for _, pattern in workflow_patterns:
            if pattern not in workflows:
                workflows.append(pattern)

        # Pain points (negative patterns)
        pain_patterns = re.findall(
            r"(difficult|hard|annoying|frustrating|slow|tedious|complex)\s+(\w+(?:\s+\w+)?)",
            content,
        )
        for _, pattern in pain_patterns:
            if pattern not in pain_points:
                pain_points.append(pattern)

    return UserExpectationModel(
        category="",
        typical_actions=typical_actions[:10],
        data_accumulation_patterns=data_patterns[:10],
        fast_access_needs=fast_access[:5],
        common_workflows=workflows[:5],
        pain_points=pain_points[:5],
        sources=list(set(sources))[:5],
    )


async def research_user_expectations(
    plugin_name: str,
    problem_statement: str,
    web_search_func: Optional[Callable] = None,
) -> UserExpectationModel:
    """Research user expectations using web search.

    This function is async to allow parallel web requests.
    The web_search_func is injected to allow testing and to use
    the MCP tools when available.

    Args:
        plugin_name: Name of the plugin
        problem_statement: Extracted problem statement
        web_search_func: Optional function to execute web searches

    Returns:
        UserExpectationModel with researched expectations
    """
    queries = build_search_queries(plugin_name, problem_statement)

    # If no search function provided, return defaults based on plugin name
    if web_search_func is None:
        return get_default_expectations(plugin_name)

    # Execute searches
    search_results: List[Dict[str, Any]] = []
    for query in queries:
        try:
            result = await web_search_func(query)
            if result and isinstance(result, dict):
                results = result.get("results", [])
                search_results.extend(results[:3])
        except Exception as error:
            logger.warning("User research search failed for query %r: %s", query, error)

    if not search_results:
        return get_default_expectations(plugin_name)

    model = parse_search_results(search_results)
    model.category = plugin_name
    return model


def get_default_expectations(plugin_name: str) -> UserExpectationModel:
    """Get default user expectations based on plugin category.

    Used when web search is not available or fails.
    """
    # Common expectations for different plugin categories
    category_defaults: Dict[str, Dict[str, List[str]]] = {
        "lifestyle": {
            "typical_actions": [
                "add recipe",
                "track reading",
                "save place",
                "create list",
                "search items",
                "organize collections",
            ],
            "data_accumulation": [
                "recipes",
                "reading lists",
                "favorite places",
                "movie watchlist",
                "travel plans",
            ],
            "fast_access": ["recent items", "favorites", "search"],
            "workflows": ["meal planning", "reading tracking", "trip planning"],
            "pain_points": ["finding items", "organizing data", "duplicate entries"],
        },
        "career": {
            "typical_actions": [
                "add job",
                "track application",
                "update status",
                "add contact",
                "schedule interview",
                "export resume",
            ],
            "data_accumulation": [
                "job applications",
                "contacts",
                "interview notes",
                "company research",
                "skills",
            ],
            "fast_access": ["active applications", "upcoming interviews", "contacts"],
            "workflows": ["job search", "application tracking", "interview prep"],
            "pain_points": ["status tracking", "follow-up reminders", "comparison"],
        },
        "health": {
            "typical_actions": [
                "log weight",
                "track exercise",
                "add meal",
                "record symptom",
                "schedule appointment",
            ],
            "data_accumulation": [
                "weight history",
                "exercise logs",
                "meals",
                "symptoms",
                "appointments",
            ],
            "fast_access": ["today's log", "recent trends", "upcoming appointments"],
            "workflows": ["daily logging", "weekly review", "goal tracking"],
            "pain_points": ["consistency", "data entry", "trend analysis"],
        },
        "finance": {
            "typical_actions": [
                "add transaction",
                "categorize expense",
                "set budget",
                "track investment",
                "generate report",
            ],
            "data_accumulation": [
                "transactions",
                "budgets",
                "investments",
                "recurring expenses",
                "income",
            ],
            "fast_access": ["recent transactions", "budget status", "balances"],
            "workflows": ["expense tracking", "budget review", "tax preparation"],
            "pain_points": ["categorization", "reconciliation", "forecasting"],
        },
    }

    # Get category-specific defaults or use generic defaults
    defaults = category_defaults.get(
        plugin_name.lower(),
        {
            "typical_actions": [
                "add item",
                "search items",
                "edit item",
                "delete item",
                "export data",
                "organize",
            ],
            "data_accumulation": ["items", "categories", "history"],
            "fast_access": ["recent", "favorites", "search"],
            "workflows": ["add and organize", "search and review", "export and share"],
            "pain_points": ["finding things", "organization", "data entry"],
        },
    )

    return UserExpectationModel(
        category=plugin_name,
        typical_actions=defaults.get("typical_actions", []),
        data_accumulation_patterns=defaults.get("data_accumulation", []),
        fast_access_needs=defaults.get("fast_access", []),
        common_workflows=defaults.get("workflows", []),
        pain_points=defaults.get("pain_points", []),
        sources=["default_expectations"],
    )
