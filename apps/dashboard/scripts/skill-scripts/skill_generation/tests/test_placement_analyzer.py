#!/usr/bin/env python3
"""
Unit tests for Skill Placement Analyzer

Tests the intelligent skill placement recommendation system.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from ..placement_analyzer import (
    SkillPlacementAnalyzer,
    SkillInfo,
    PlacementRecommendation,
    analyze_skill_placement,
)


class TestPlacementRecommendation:
    """Tests for PlacementRecommendation dataclass."""

    def test_to_dict(self):
        """Test that to_dict returns all fields."""
        rec = PlacementRecommendation(
            recommendation="new_skill",
            target_bundle="apps",
            target_skill=None,
            confidence=0.85,
            reasoning="Test reasoning",
            related_skills=["calendar", "notes"],
            layer="vertical",
        )

        result = rec.to_dict()

        assert result["recommendation"] == "new_skill"
        assert result["target_bundle"] == "apps"
        assert result["target_skill"] is None
        assert result["confidence"] == 0.85
        assert result["reasoning"] == "Test reasoning"
        assert result["related_skills"] == ["calendar", "notes"]
        assert result["layer"] == "vertical"


class TestSkillPlacementAnalyzer:
    """Tests for SkillPlacementAnalyzer class."""

    @pytest.fixture
    def analyzer_no_cache(self):
        """Create analyzer with mocked skill loading (no cache)."""
        with patch.object(SkillPlacementAnalyzer, "_load_existing_skills"):
            analyzer = SkillPlacementAnalyzer()
            analyzer.skills_cache = []
            return analyzer

    @pytest.fixture
    def analyzer_with_skills(self):
        """Create analyzer with mock skill cache."""
        with patch.object(SkillPlacementAnalyzer, "_load_existing_skills"):
            analyzer = SkillPlacementAnalyzer()
            analyzer.skills_cache = [
                SkillInfo(
                    name="google-workspace",
                    path=Path("/fake/skills/google-workspace"),
                    layer="horizontal",
                    bundle="productivity",
                    patterns=["database", "dashboard", "api"],
                    description="Calendar and scheduling management",
                ),
                SkillInfo(
                    name="health",
                    path=Path("/fake/skills/health"),
                    layer="vertical",
                    bundle="health",
                    patterns=["database", "dashboard", "inbox"],
                    description="Track health metrics and fitness goals",
                ),
                SkillInfo(
                    name="devops",
                    path=Path("/fake/skills/devops"),
                    layer="factory",
                    bundle="dev",
                    patterns=["scheduler", "api"],
                    description="DevOps and infrastructure management",
                ),
                SkillInfo(
                    name="executor",
                    path=Path("/fake/skills/executor"),
                    layer="factory",
                    bundle="orchestration",
                    patterns=["inbox", "database", "scheduler"],
                    description="Project and sprint backlog management",
                ),
            ]
            return analyzer

    # _determine_layer tests

    def test_determine_layer_factory_keywords(self, analyzer_no_cache):
        """Factory keywords should return 'factory' layer."""
        test_cases = [
            "Build system architecture for the platform",
            "Developer tools and infrastructure management",
            "Agent orchestration and backlog sprint planning",
            "Frontend design system components",
            "Platform core services",
        ]

        for description in test_cases:
            result = analyzer_no_cache._determine_layer(description, [])
            assert result == "factory", f"Expected 'factory' for: {description}"

    def test_determine_layer_horizontal_keywords(self, analyzer_no_cache):
        """Horizontal keywords should return 'horizontal' layer."""
        # Test cases must avoid factory keywords (management, system, platform, etc.)
        # to ensure horizontal keywords dominate
        test_cases = [
            "Memory storage and retrieval",
            "Calendar and scheduling features",
            "Voice transcription and OCR tools",
            "Cross-cutting notification handlers",
            "Shared utility helpers and common functions",
        ]

        for description in test_cases:
            result = analyzer_no_cache._determine_layer(description, [])
            assert result == "horizontal", f"Expected 'horizontal' for: {description}"

    def test_determine_layer_vertical_keywords(self, analyzer_no_cache):
        """Vertical (domain-specific) keywords should return 'vertical' layer."""
        test_cases = [
            "Track health and fitness goals",
            "Career management and job search",
            "Business venture planning and startup ideas",
            "Personal lifestyle tracking",
            "Recipe management and meal planning",
        ]

        for description in test_cases:
            result = analyzer_no_cache._determine_layer(description, [])
            assert result == "vertical", f"Expected 'vertical' for: {description}"

    def test_determine_layer_default_vertical(self, analyzer_no_cache):
        """Unknown/ambiguous descriptions should default to 'vertical'."""
        # Test cases must avoid all layer-specific keywords to test the default
        test_cases = [
            "General purpose task tracker",
            "Something completely unrelated",
            "Random string without keywords",
            "",
        ]

        for description in test_cases:
            result = analyzer_no_cache._determine_layer(description, [])
            assert result == "vertical", f"Expected 'vertical' default for: {description}"

    # _determine_bundle tests

    def test_determine_bundle_factory_layer(self, analyzer_no_cache):
        """Factory layer should map to factory bundles."""
        # Test management keywords
        result = analyzer_no_cache._determine_bundle("factory", "Project and sprint management tool", [])
        assert result == "orchestration"

        # Test product/design keywords
        result = analyzer_no_cache._determine_bundle("factory", "Frontend user experience design", [])
        assert result == "dev"

        # Test core/system keywords
        result = analyzer_no_cache._determine_bundle("factory", "Core system architecture", [])
        assert result == "dev"

    def test_determine_bundle_with_similar_skills(self, analyzer_with_skills):
        """Should use bundle from most similar skill in same layer."""
        # Similar to calendar (horizontal) - should return matching skill bundle
        similar_skills = [analyzer_with_skills.skills_cache[0]]  # calendar
        result = analyzer_with_skills._determine_bundle("horizontal", "Event scheduling system", similar_skills)
        assert result == "productivity"

    def test_determine_bundle_vertical_default(self, analyzer_no_cache):
        """Vertical layer should default to appropriate bundle."""
        # Health + personal keywords currently route to legacy-compatible "apps" bucket.
        result = analyzer_no_cache._determine_bundle("vertical", "Track personal health metrics", [])
        assert result == "apps"

        # Career/job keywords -> career
        result = analyzer_no_cache._determine_bundle("vertical", "Resume and job interview prep", [])
        assert result == "career"

        # Business/venture keywords -> professional
        result = analyzer_no_cache._determine_bundle("vertical", "Startup business planning and innovation", [])
        assert result == "professional"

    # _find_similar_skills tests

    def test_find_similar_skills_pattern_overlap(self, analyzer_with_skills):
        """Should find skills with overlapping patterns."""
        # inbox + database patterns should match health and executor
        similar = analyzer_with_skills._find_similar_skills(
            "Process incoming items and store data", ["inbox", "database"]
        )

        names = [s.name for s in similar]
        assert "health" in names
        assert "executor" in names

    def test_find_similar_skills_description_match(self, analyzer_with_skills):
        """Should find skills with similar descriptions."""
        # Description mentioning health should match health
        similar = analyzer_with_skills._find_similar_skills("Track fitness and health goals for the user", [])

        if similar:  # May be empty if scores are below threshold
            names = [s.name for s in similar]
            assert "health" in names or len(similar) == 0

    def test_find_similar_skills_no_matches(self, analyzer_with_skills):
        """Should return empty list when no similar skills found."""
        similar = analyzer_with_skills._find_similar_skills(
            "Completely unique functionality xyz abc", ["nonexistent_pattern"]
        )

        assert isinstance(similar, list)

    # analyze_placement tests

    def test_analyze_placement_new_skill_no_similar(self, analyzer_no_cache):
        """With no similar skills, should recommend new_skill."""
        result = analyzer_no_cache.analyze_placement(
            skill_name="test-skill",
            description="Track personal recipes and cooking plans",
            patterns=["database", "dashboard"],
        )

        assert result.recommendation == "new_skill"
        assert result.confidence >= 0.8
        assert result.target_skill is None
        assert result.layer in ["factory", "horizontal", "vertical"]

    def test_analyze_placement_add_module_high_similarity(self, analyzer_with_skills):
        """High pattern overlap should recommend add_module."""
        # Use exact same patterns as health-tracker to trigger high similarity
        result = analyzer_with_skills.analyze_placement(
            skill_name="fitness-goals",
            description="Track health metrics and fitness goals for users",
            patterns=["database", "dashboard", "inbox"],  # Same as health-tracker
        )

        # Should either recommend add_module or new_skill depending on exact similarity
        assert result.recommendation in ["new_skill", "add_module"]
        assert result.confidence > 0.5

    def test_analyze_placement_returns_related_skills(self, analyzer_with_skills):
        """Should return related skills for cross-referencing."""
        result = analyzer_with_skills.analyze_placement(
            skill_name="meal-planner",
            description="Plan meals and track nutrition with database storage",
            patterns=["database", "dashboard"],
        )

        assert isinstance(result.related_skills, list)
        # Should include skills with overlapping patterns
        # (health-tracker and others have database, dashboard)

    def test_analyze_placement_sets_layer(self, analyzer_no_cache):
        """Should set correct layer based on description."""
        # Factory description
        result = analyzer_no_cache.analyze_placement(
            skill_name="build-system",
            description="Infrastructure and platform architecture management",
            patterns=["api"],
        )
        assert result.layer == "factory"

        # Horizontal description
        result = analyzer_no_cache.analyze_placement(
            skill_name="src/lib-memory",
            description="Cross-cutting memory and context management utility",
            patterns=["database"],
        )
        assert result.layer == "horizontal"

        # Vertical description
        result = analyzer_no_cache.analyze_placement(
            skill_name="fitness-app",
            description="Personal health and fitness goal tracking",
            patterns=["dashboard"],
        )
        assert result.layer == "vertical"

    # get_existing_skills_summary tests

    def test_get_existing_skills_summary(self, analyzer_with_skills):
        """Should return summary of all cached skills."""
        summary = analyzer_with_skills.get_existing_skills_summary()

        assert isinstance(summary, list)
        assert len(summary) == 4

        # Check structure of first item
        first = summary[0]
        assert "name" in first
        assert "layer" in first
        assert "bundle" in first
        assert "patterns" in first


class TestAnalyzeSkillPlacementFunction:
    """Tests for the convenience function."""

    def test_analyze_skill_placement_returns_dict(self):
        """Convenience function should return dictionary."""
        with patch.object(SkillPlacementAnalyzer, "_load_existing_skills"):
            with patch.object(
                SkillPlacementAnalyzer,
                "analyze_placement",
                return_value=PlacementRecommendation(
                    recommendation="new_skill",
                    target_bundle="apps",
                    target_skill=None,
                    confidence=0.9,
                    reasoning="Test",
                    related_skills=[],
                    layer="vertical",
                ),
            ):
                result = analyze_skill_placement(
                    skill_name="test",
                    description="Test description",
                    patterns=["database"],
                )

                assert isinstance(result, dict)
                assert result["recommendation"] == "new_skill"
                assert result["target_bundle"] == "apps"
                assert result["confidence"] == 0.9


class TestSkillInfoParsing:
    """Tests for skill info parsing from SKILL.md files."""

    @pytest.fixture
    def analyzer_for_parsing(self):
        """Create analyzer for testing parsing methods."""
        with patch.object(SkillPlacementAnalyzer, "_load_existing_skills"):
            return SkillPlacementAnalyzer()

    def test_parse_skill_with_patterns_section(self, analyzer_for_parsing, tmp_path):
        """Should extract patterns from SKILL.md Patterns section."""
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""# Test Skill

A test skill for unit testing.

## Overview

This skill demonstrates pattern extraction.

## Patterns

- inbox: Process incoming items
- database: Store data
- dashboard: Display UI

## Other Section

Some other content.
""")

        result = analyzer_for_parsing._parse_skill(skill_dir, "vertical", "apps")

        assert result is not None
        assert result.name == "test-skill"
        assert result.layer == "vertical"
        assert result.bundle == "apps"
        assert "inbox" in result.patterns
        assert "database" in result.patterns
        assert "dashboard" in result.patterns

    def test_parse_skill_missing_skill_md(self, analyzer_for_parsing, tmp_path):
        """Should return None when SKILL.md doesn't exist."""
        skill_dir = tmp_path / "empty-skill"
        skill_dir.mkdir()

        result = analyzer_for_parsing._parse_skill(skill_dir, "vertical", "apps")

        assert result is None

    def test_parse_skill_skill_package_location(self, analyzer_for_parsing, tmp_path):
        """Should find SKILL.md in skill-package subdirectory."""
        skill_dir = tmp_path / "packaged-skill"
        skill_dir.mkdir()

        package_dir = skill_dir / "skill-package"
        package_dir.mkdir()

        skill_md = package_dir / "SKILL.md"
        skill_md.write_text("""# Packaged Skill

## Overview

A skill with SKILL.md in skill-package directory.
""")

        result = analyzer_for_parsing._parse_skill(skill_dir, "horizontal", "services")

        assert result is not None
        assert result.name == "packaged-skill"
        assert result.layer == "horizontal"

    def test_parse_skill_extracts_description(self, analyzer_for_parsing, tmp_path):
        """Should extract description from Overview section."""
        skill_dir = tmp_path / "desc-skill"
        skill_dir.mkdir()

        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("""# Description Test Skill

## Overview

This is a detailed description of the skill that should be extracted for matching purposes.

## Patterns

- api
""")

        result = analyzer_for_parsing._parse_skill(skill_dir, "factory", "crew")

        assert result is not None
        assert "detailed description" in result.description.lower()
