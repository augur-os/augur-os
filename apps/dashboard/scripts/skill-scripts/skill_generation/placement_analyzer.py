#!/usr/bin/env python3
"""
Skill Placement Analyzer

Analyzes existing skills and recommends where to place a new dashboard:
- Which layer (factory, horizontal, vertical)
- Which plugin bundle
- Whether to create new skill or add module to existing
- Related skills for cross-referencing
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.config.paths import get_project_root
from src.logging import get_entity_logger


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


logger = get_entity_logger("placement_analyzer")


@dataclass
class PlacementRecommendation:
    """Recommendation for skill placement."""

    recommendation: str  # 'new_skill' | 'add_module' | 'enhance_existing'
    target_bundle: str  # e.g., 'career', 'services', 'dev'
    target_skill: Optional[str]  # Existing skill to add module to
    confidence: float  # 0.0 - 1.0
    reasoning: str
    related_skills: list[str] = field(default_factory=list)
    layer: str = "vertical"  # factory | horizontal | vertical

    def to_dict(self) -> dict:
        return {
            "recommendation": self.recommendation,
            "target_bundle": self.target_bundle,
            "target_skill": self.target_skill,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "related_skills": self.related_skills,
            "layer": self.layer,
        }


@dataclass
class SkillInfo:
    """Information about an existing skill."""

    name: str
    path: Path
    layer: str
    bundle: str
    patterns: list[str]
    description: str
    domain: Optional[str] = None


class SkillPlacementAnalyzer:
    """Analyzes codebase and recommends skill placement."""

    # Plugin bundle mappings by placement layer.
    # Includes legacy names for backward compatibility.
    BUNDLES = {
        "factory": ["dev", "orchestration", "ai", "observability", "admin", "core", "crew"],
        "horizontal": ["services", "integrations"],
        "vertical": [
            "career",
            "health",
            "finance",
            "lifestyle",
            "home",
            "productivity",
            "consulting",
            "professional",
            "enterprise",
            "growth",
            "venture",
            "creative",
            "apps",
        ],
    }

    # Bundle descriptions for matching
    BUNDLE_DOMAINS = {
        "dev": ["architecture", "system", "infrastructure", "core", "devops", "developer", "tooling"],
        "orchestration": ["project", "backlog", "sprint", "workflow", "executor", "routing"],
        "ai": ["agent", "llm", "prompt", "model", "knowledge", "automation"],
        "observability": ["health", "monitor", "monitoring", "log", "telemetry", "metrics", "alerts"],
        "admin": ["settings", "config", "security", "permissions", "governance", "compliance"],
        "crew": ["architecture", "system", "infrastructure", "core", "devops", "developer", "agent"],
        "orchestrator": ["project", "backlog", "sprint", "workflow", "executor", "routing"],
        "services": ["memory", "calendar", "voice", "ocr", "notification", "integration", "shared", "common"],
        "integrations": ["integration", "api", "connector", "sync", "external"],
        "career": ["career", "job", "resume", "interview", "portfolio", "content"],
        "health": ["health", "fitness", "wellness", "nutrition", "sleep"],
        "finance": ["finance", "budget", "expense", "investment", "tax", "wealth"],
        "lifestyle": ["lifestyle", "personal", "habit", "travel", "recipe"],
        "home": ["home", "household", "family"],
        "productivity": ["productivity", "task", "focus", "planning", "automation"],
        "consulting": ["consulting", "client", "engagement", "delivery"],
        "professional": ["business", "venture", "sales", "marketing", "investor", "startup"],
        "enterprise": ["enterprise", "organization", "team", "operations", "policy", "compliance"],
        "apps": ["health", "fitness", "lifestyle", "personal", "career", "job", "business", "venture"],
    }

    # Pattern keywords for matching
    PATTERN_KEYWORDS = {
        "inbox": ["process", "incoming", "queue", "triage", "email", "notification"],
        "database": ["store", "data", "records", "crud", "persistence", "tracking"],
        "dashboard": ["view", "display", "ui", "interface", "visualization"],
        "api": ["endpoint", "rest", "graphql", "service", "integration"],
        "scheduler": ["cron", "schedule", "automation", "recurring", "timer"],
        "rag": ["search", "documents", "knowledge", "retrieval", "context"],
    }

    def __init__(self):
        self.project_root = get_project_root()
        self.skills_cache: list[SkillInfo] = []
        self._load_existing_skills()

    def _load_existing_skills(self) -> None:
        """Load all existing skills from the codebase."""
        plugins_dir = self.project_root / "plugins"

        if not plugins_dir.exists():
            logger.warning(f"Plugins directory not found: {plugins_dir}")
            return

        for bundle_dir in plugins_dir.iterdir():
            if not bundle_dir.is_dir() or bundle_dir.name.startswith("."):
                continue

            skills_dir = bundle_dir / "skills"
            if not skills_dir.exists():
                continue

            # Determine placement layer from bundle.
            if bundle_dir.name in set(self.BUNDLES.get("factory", [])):
                layer = "factory"
            elif bundle_dir.name in set(self.BUNDLES.get("horizontal", [])):
                layer = "horizontal"
            else:
                layer = "vertical"

            for skill_dir in skills_dir.iterdir():
                if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                    continue

                skill_info = self._parse_skill(skill_dir, layer, bundle_dir.name)
                if skill_info:
                    self.skills_cache.append(skill_info)

        logger.info(f"Loaded {len(self.skills_cache)} existing skills")

    def _parse_skill(self, skill_dir: Path, layer: str, bundle: str) -> Optional[SkillInfo]:
        """Parse skill information from SKILL.md."""
        skill_md_paths = [
            skill_dir / "skill-package" / "SKILL.md",
            skill_dir / "SKILL.md",
        ]

        skill_md = None
        for path in skill_md_paths:
            if path.exists():
                skill_md = path
                break

        if not skill_md:
            return None

        try:
            content = skill_md.read_text(encoding="utf-8")

            # Extract patterns
            patterns = []
            if "## Patterns" in content:
                patterns_section = content.split("## Patterns")[1].split("##")[0]
                for line in patterns_section.split("\n"):
                    line = line.strip()
                    if line.startswith("- ") or line.startswith("* "):
                        pattern = line[2:].strip().lower()
                        # Extract pattern name (before any description)
                        if ":" in pattern:
                            pattern = pattern.split(":")[0].strip()
                        if pattern in ["inbox", "database", "dashboard", "api", "scheduler", "rag"]:
                            patterns.append(pattern)

            # Extract description
            description = ""
            if "## Overview" in content:
                overview = content.split("## Overview")[1].split("##")[0].strip()
                description = overview[:500]  # First 500 chars
            elif content.startswith("#"):
                # Use first paragraph after title
                lines = content.split("\n")[1:]
                for line in lines:
                    if line.strip() and not line.startswith("#"):
                        description = line.strip()[:500]
                        break

            return SkillInfo(
                name=skill_dir.name,
                path=skill_dir,
                layer=layer,
                bundle=bundle,
                patterns=patterns,
                description=description,
            )

        except Exception as e:
            logger.warning(f"Failed to parse skill {skill_dir.name}: {e}")
            return None

    def analyze_placement(
        self,
        skill_name: str,
        description: str,
        patterns: list[str],
    ) -> PlacementRecommendation:
        """
        Analyze where to place a new skill.

        Args:
            skill_name: Name of the new skill
            description: Description of what the skill does
            patterns: List of patterns the skill will use

        Returns:
            PlacementRecommendation with placement details
        """
        # Step 1: Determine best layer based on description
        layer = self._determine_layer(description, patterns)

        # Step 2: Find most similar existing skills
        similar_skills = self._find_similar_skills(description, patterns)

        # Step 3: Determine if we should add to existing skill or create new
        recommendation, target_skill, confidence, reasoning = self._determine_recommendation(
            skill_name, description, patterns, similar_skills, layer
        )

        # Step 4: Determine target bundle
        target_bundle = self._determine_bundle(layer, description, similar_skills)

        # Step 5: Get related skills for cross-referencing
        related_skills = [s.name for s in similar_skills[:5]]

        return PlacementRecommendation(
            recommendation=recommendation,
            target_bundle=target_bundle,
            target_skill=target_skill,
            confidence=confidence,
            reasoning=reasoning,
            related_skills=related_skills,
            layer=layer,
        )

    def _determine_layer(self, description: str, patterns: list[str]) -> str:
        """Determine which layer the skill belongs to."""
        desc_lower = description.lower()

        # Factory layer indicators
        factory_keywords = [
            "architecture",
            "infrastructure",
            "developer",
            "devops",
            "agent",
            "system",
            "platform",
            "core",
            "management",
            "sprint",
            "backlog",
            "frontend",
            "design system",
        ]
        factory_score = sum(1 for kw in factory_keywords if kw in desc_lower)

        # Horizontal layer indicators
        horizontal_keywords = [
            "memory",
            "calendar",
            "notification",
            "voice",
            "ocr",
            "cross-cutting",
            "src/lib",
            "common",
            "utility",
        ]
        horizontal_score = sum(1 for kw in horizontal_keywords if kw in desc_lower)

        # Vertical layer indicators (domain-specific)
        vertical_keywords = [
            "health",
            "fitness",
            "career",
            "job",
            "business",
            "venture",
            "lifestyle",
            "personal",
            "recipe",
            "finance",
            "travel",
        ]
        vertical_score = sum(1 for kw in vertical_keywords if kw in desc_lower)

        # Default to vertical if no clear match
        if factory_score > horizontal_score and factory_score > vertical_score:
            return "factory"
        elif horizontal_score > factory_score and horizontal_score > vertical_score:
            return "horizontal"
        else:
            return "vertical"

    def _find_similar_skills(self, description: str, patterns: list[str]) -> list[SkillInfo]:
        """Find skills similar to the new one."""
        desc_lower = description.lower()
        desc_words = set(desc_lower.split())

        scores: list[tuple[float, SkillInfo]] = []

        for skill in self.skills_cache:
            score = 0.0

            # Pattern overlap score (0-0.5)
            if skill.patterns and patterns:
                pattern_overlap = len(set(skill.patterns) & set(patterns))
                score += (pattern_overlap / max(len(skill.patterns), len(patterns))) * 0.5

            # Description word overlap score (0-0.5)
            skill_desc_words = set(skill.description.lower().split())
            if skill_desc_words and desc_words:
                word_overlap = len(skill_desc_words & desc_words)
                score += (word_overlap / max(len(skill_desc_words), len(desc_words))) * 0.5

            scores.append((score, skill))

        # Sort by score descending
        scores.sort(key=lambda x: x[0], reverse=True)

        return [skill for _, skill in scores if _ > 0.1]  # Filter low scores

    def _determine_recommendation(
        self,
        skill_name: str,
        description: str,
        patterns: list[str],
        similar_skills: list[SkillInfo],
        layer: str,
    ) -> tuple[str, Optional[str], float, str]:
        """Determine if new skill, add module, or enhance existing."""

        if not similar_skills:
            return (
                "new_skill",
                None,
                0.9,
                f"No similar skills found. Creating new skill in {layer} layer.",
            )

        top_skill = similar_skills[0]

        # Calculate similarity more precisely
        pattern_overlap = 0.0
        if top_skill.patterns and patterns:
            pattern_overlap = len(set(top_skill.patterns) & set(patterns)) / max(len(top_skill.patterns), len(patterns))

        # Very high similarity (>0.8) - suggest adding as module
        if pattern_overlap > 0.8:
            return (
                "add_module",
                top_skill.name,
                0.85,
                f"High pattern overlap ({pattern_overlap:.0%}) with '{top_skill.name}'. "
                f"Consider adding as a module to existing skill.",
            )

        # Medium similarity (0.5-0.8) - suggest new skill in same bundle
        if pattern_overlap > 0.5:
            return (
                "new_skill",
                None,
                0.75,
                f"Moderate pattern overlap ({pattern_overlap:.0%}) with '{top_skill.name}'. "
                f"Creating new skill in same bundle for potential cross-referencing.",
            )

        # Low similarity - definitely new skill
        return (
            "new_skill",
            None,
            0.9,
            f"Low similarity to existing skills. Creating new skill in {layer} layer.",
        )

    def _determine_bundle(self, layer: str, description: str, similar_skills: list[SkillInfo]) -> str:
        """Determine which plugin bundle to use."""
        desc_lower = description.lower()

        # If we have similar skills in the same layer, use their bundle
        for skill in similar_skills:
            if skill.layer == layer:
                return skill.bundle

        # Otherwise, determine based on description keywords
        bundles = self.BUNDLES.get(layer, [])
        if not bundles:
            return f"{layer}-core"

        # Score each bundle
        best_bundle = bundles[0]
        best_score = 0

        for bundle in bundles:
            domain_keywords = self.BUNDLE_DOMAINS.get(bundle, [])
            score = sum(1 for kw in domain_keywords if kw in desc_lower)
            if score > best_score:
                best_score = score
                best_bundle = bundle

        return best_bundle

    def get_existing_skills_summary(self) -> list[dict]:
        """Get summary of all existing skills for reference."""
        return [
            {
                "name": skill.name,
                "layer": skill.layer,
                "bundle": skill.bundle,
                "patterns": skill.patterns,
            }
            for skill in self.skills_cache
        ]


# Convenience function
def analyze_skill_placement(
    skill_name: str,
    description: str,
    patterns: list[str],
) -> dict:
    """
    Analyze where to place a new skill.

    Args:
        skill_name: Name of the new skill
        description: Description of what the skill does
        patterns: List of patterns the skill will use

    Returns:
        Dictionary with placement recommendation
    """
    analyzer = SkillPlacementAnalyzer()
    recommendation = analyzer.analyze_placement(skill_name, description, patterns)
    return recommendation.to_dict()


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 2 and sys.argv[1] == "--list":
        analyzer = SkillPlacementAnalyzer()
        skills = analyzer.get_existing_skills_summary()
        _out(json.dumps({"skills": skills}, indent=2))
        sys.exit(0)

    if len(sys.argv) < 4:
        _out("Usage: python placement_analyzer.py <skill_name> <description> <patterns>")
        _out("  patterns: comma-separated list (e.g., inbox,database,dashboard)")
        _out("  or: python placement_analyzer.py --list")
        sys.exit(1)

    skill_name = sys.argv[1]
    description = sys.argv[2]
    patterns = sys.argv[3].split(",")

    result = analyze_skill_placement(skill_name, description, patterns)
    _out(json.dumps(result, indent=2))
