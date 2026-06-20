"""
Tests for Knowledge skill - Memory Store, Search, Curator, and Daily Logger.

Tests the two-layer memory architecture:
- Layer 1: DailyLogger (raw session events)
- Layer 2: MemoryStore (curated MEMORY.md)
- MemorySearcher (search across both layers)
- MemoryCurator (distills daily logs into curated memory)
"""
# TODO_CLEANUP: This file is 835 lines — consider splitting into smaller modules

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import yaml

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary data directory structure for memory tests."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True)
    daily_dir = memory_dir / "daily"
    daily_dir.mkdir()
    return tmp_path


@pytest.fixture
def mock_data_base(tmp_data_dir):
    """Patch get_memory_dir and get_runtime_dir in all knowledge submodules."""
    memory_dir = tmp_data_dir / "memory"
    runtime_dir = tmp_data_dir / "runtime"
    (runtime_dir / "memory" / "daily").mkdir(parents=True, exist_ok=True)
    mem_targets = [
        "src.lib.knowledge.memory_store.get_memory_dir",
        "src.lib.knowledge.search.get_memory_dir",
        "src.lib.knowledge.curator.get_memory_dir",
        "src.lib.knowledge.daily_logger.get_memory_dir",
    ]
    rt_targets = [
        "src.lib.knowledge.search.get_runtime_dir",
        "src.lib.knowledge.curator.get_runtime_dir",
        "src.lib.knowledge.daily_logger.get_runtime_dir",
    ]
    patches = [patch(t, return_value=memory_dir) for t in mem_targets]
    patches += [patch(t, return_value=runtime_dir) for t in rt_targets]
    patches.append(
        patch(
            "src.lib.knowledge.memory_store.resolve_active_stack",
            side_effect=RuntimeError("disabled for legacy MemoryStore file tests"),
        )
    )
    for p in patches:
        p.start()
    yield memory_dir
    for p in patches:
        p.stop()


# ---------------------------------------------------------------------------
# MemoryEntry (dataclass) tests
# ---------------------------------------------------------------------------


class TestMemoryEntry:
    """Tests for the MemoryEntry dataclass in memory_store module."""

    def test_to_markdown_item_basic(self):
        from src.lib.knowledge.memory_store import MemoryEntry

        entry = MemoryEntry(
            category="decisions",
            subcategory="Health",
            key="Vitamin D",
            value="Take 2000 IU daily",
            date=datetime(2026, 1, 15),
        )
        md = entry.to_markdown_item()
        assert "**Vitamin D**" in md
        assert "Take 2000 IU daily" in md
        assert "(2026-01-15)" in md

    def test_to_markdown_item_with_source(self):
        from src.lib.knowledge.memory_store import MemoryEntry

        entry = MemoryEntry(
            category="decisions",
            subcategory="Health",
            key="Exercise",
            value="30 min daily",
            date=datetime(2026, 1, 15),
            source="doctor recommendation",
        )
        md = entry.to_markdown_item()
        assert "Source: doctor recommendation" in md

    def test_to_markdown_item_with_confidence(self):
        from src.lib.knowledge.memory_store import MemoryEntry

        entry = MemoryEntry(
            category="decisions",
            subcategory="Career",
            key="Focus area",
            value="ML engineering",
            date=datetime(2026, 1, 15),
            confidence="high",
        )
        md = entry.to_markdown_item()
        assert "Confidence: High" in md

    def test_to_markdown_item_default_confidence_omitted(self):
        from src.lib.knowledge.memory_store import MemoryEntry

        entry = MemoryEntry(
            category="decisions",
            subcategory="General",
            key="Test",
            value="Value",
            date=datetime(2026, 1, 15),
            confidence="medium",
        )
        md = entry.to_markdown_item()
        # Default confidence ("medium") should NOT appear
        assert "Confidence" not in md


# ---------------------------------------------------------------------------
# MemoryStore tests
# ---------------------------------------------------------------------------


class TestMemoryStore:
    """Tests for the MemoryStore class."""

    def test_creates_memory_file_on_init(self, mock_data_base):
        from src.lib.knowledge.memory_store import MemoryStore

        store = MemoryStore()
        assert store._memory_file.exists()
        content = store.get_memory_content()
        assert "# Augur Memory" in content
        assert "## Decisions" in content

    def test_lazy_init_reads_template_without_creating_memory_file(self, mock_data_base):
        from src.lib.knowledge.memory_store import MemoryStore

        store = MemoryStore(ensure_file=False)

        assert not store._memory_file.exists()
        content = store.get_memory_content()

        assert "# Augur Memory" in content
        assert "## Decisions" in content
        assert not store._memory_file.exists()

    def test_lazy_init_creates_memory_file_on_write(self, mock_data_base):
        from src.lib.knowledge.memory_store import MemoryStore

        store = MemoryStore(ensure_file=False)
        store.add_preference("Communication", "Response style", "Concise")

        assert store._memory_file.exists()
        assert "Response style" in store.get_memory_content()

    def test_get_section(self, mock_data_base):
        from src.lib.knowledge.memory_store import MemoryStore

        store = MemoryStore()
        section = store.get_section("Decisions")
        assert section is not None
        assert "### Health" in section

    def test_get_section_not_found(self, mock_data_base):
        from src.lib.knowledge.memory_store import MemoryStore

        store = MemoryStore()
        section = store.get_section("Nonexistent Section")
        assert section is None

    def test_get_subsection(self, mock_data_base):
        from src.lib.knowledge.memory_store import MemoryStore

        store = MemoryStore()
        subsection = store.get_subsection("Decisions", "Health")
        # Subsection exists but is empty
        assert subsection is not None or subsection == ""

    def test_add_decision(self, mock_data_base):
        from src.lib.knowledge.memory_store import MemoryStore

        store = MemoryStore()
        store.add_decision(
            topic="Vitamin D",
            decision="Take 2000 IU daily",
            category="Health",
            source="doctor recommendation",
            confidence="high",
        )
        content = store.get_memory_content()
        assert "**Vitamin D**" in content
        assert "Take 2000 IU daily" in content

    def test_add_pattern(self, mock_data_base):
        from src.lib.knowledge.memory_store import MemoryStore

        store = MemoryStore()
        store.add_pattern(
            pattern_type="Workflow Patterns",
            description="Most productive in morning hours",
            frequency="daily",
        )
        content = store.get_memory_content()
        assert "Most productive in morning hours" in content
        assert "Frequency: daily" in content

    def test_add_preference(self, mock_data_base):
        from src.lib.knowledge.memory_store import MemoryStore

        store = MemoryStore()
        store.add_preference(
            preference_type="Communication",
            key="Response style",
            value="Concise and technical",
            source="stated preference",
        )
        content = store.get_memory_content()
        assert "**Response style**" in content
        assert "Concise and technical" in content

    def test_search_decisions(self, mock_data_base):
        from src.lib.knowledge.memory_store import MemoryStore

        store = MemoryStore()
        store.add_decision(topic="Vitamin D", decision="Take 2000 IU", category="Health")
        store.add_decision(topic="Exercise", decision="Run daily", category="Health")

        results = store.search_decisions("vitamin")
        assert len(results) >= 1
        assert any("Vitamin" in r for r in results)

    def test_search_all(self, mock_data_base):
        from src.lib.knowledge.memory_store import MemoryStore

        store = MemoryStore()
        store.add_decision(topic="Focus area", decision="ML engineering", category="Career")
        store.add_preference(
            preference_type="Communication",
            key="Style",
            value="Focus on ML topics",
        )

        results = store.search_all("ML")
        # Should find in at least Decisions section
        assert len(results) >= 1

    def test_get_recent_decisions(self, mock_data_base):
        from src.lib.knowledge.memory_store import MemoryStore

        store = MemoryStore()
        store.add_decision(topic="Recent decision", decision="Test value", category="General")
        results = store.get_recent_decisions(days=1)
        assert len(results) >= 1

    def test_update_curation_date(self, mock_data_base):
        from src.lib.knowledge.memory_store import MemoryStore

        store = MemoryStore()
        store.update_curation_date()
        content = store.get_memory_content()
        today = datetime.now().strftime("%Y-%m-%d")
        assert f"*Last curated: {today}*" in content

    def test_add_to_nonexistent_section_warns(self, mock_data_base):
        from src.lib.knowledge.memory_store import MemoryStore

        store = MemoryStore()
        # Remove all content to test section-not-found path
        store._memory_file.write_text("# Empty\n")
        store._add_to_subsection("NonexistentSection", "Sub", "- item")
        # Should not crash, content should be unchanged
        content = store.get_memory_content()
        assert "# Empty" in content


# ---------------------------------------------------------------------------
# MemorySearcher tests
# ---------------------------------------------------------------------------


class TestMemorySearcher:
    """Tests for the MemorySearcher class."""

    def test_load_config_from_skill_contract(self, mock_data_base, tmp_path):
        from src.lib.knowledge.search import MemorySearcher

        repo_root = tmp_path / "repo"
        skill_md = repo_root / "project-brain" / "capabilities" / "skills" / "knowledge" / "SKILL.md"
        skill_md.parent.mkdir(parents=True, exist_ok=True)
        skill_md.write_text(
            """---
name: knowledge
x-augur-hub: workspace
x-augur-config:
  version: "1.0"
  advanced:
    iterative_search:
      enabled: true
      max_rounds: 5
---
Body
""",
        )

        with patch(
            "src.lib.knowledge.search.get_project_root",
            return_value=repo_root,
        ):
            searcher = MemorySearcher()

        assert searcher._config["advanced"]["iterative_search"]["max_rounds"] == 5

    def test_infer_category(self, mock_data_base):
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        assert searcher._infer_category("This is a decision about X") == "decision"
        assert searcher._infer_category("User preference for Y") == "preference"
        assert searcher._infer_category("Workflow pattern observed") == "pattern"
        assert searcher._infer_category("tool: some_tool executed") == "tool_execution"
        assert searcher._infer_category("error occurred in module") == "error"
        assert searcher._infer_category("general event happened") == "event"

    def test_extract_date_from_path(self, mock_data_base):
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        assert searcher._extract_date("/daily/2026-01-15.md", "") == "2026-01-15"
        assert searcher._extract_date("no-date.md", "item (2026-03-20)") == "2026-03-20"
        assert searcher._extract_date("no-date.md", "no date here") == ""

    def test_calculate_relevance_exact_match(self, mock_data_base):
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        score = searcher._calculate_relevance("vitamin d", "Take vitamin d daily")
        assert score > 0.5

    def test_calculate_relevance_partial_match(self, mock_data_base):
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        score = searcher._calculate_relevance("vitamin exercise", "Take vitamin d daily")
        assert 0 < score <= 0.5

    def test_calculate_relevance_no_match(self, mock_data_base):
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        score = searcher._calculate_relevance("xyz123", "Take vitamin d daily")
        assert score == 0.0

    def test_extract_tags(self, mock_data_base):
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        tags = searcher._extract_tags('Decision about "daily routine" and Health')
        assert "decision" in tags or "health" in tags
        assert "daily routine" in tags

    def test_fallback_search(self, mock_data_base):
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        # Create a test file
        test_file = searcher._memory_dir / "test_search.md"
        test_file.write_text("# Test\n- Found keyword here\n- Another line\n")

        results = searcher._fallback_search("keyword", test_file)
        assert len(results) == 1
        assert results[0]["content"] == "- Found keyword here"

    def test_search_result_to_dict(self):
        from src.lib.knowledge.search import SearchResult

        result = SearchResult(
            content="test content",
            source="daily",
            category="decision",
            date="2026-01-15",
            relevance=0.8,
            file_path="/test.md",
            line_number=5,
        )
        d = result.to_dict()
        assert d["content"] == "test content"
        assert d["relevance"] == 0.8
        assert d["source"] == "daily"

    def test_memory_entry_to_dict(self):
        from src.lib.knowledge.search import MemoryEntry

        entry = MemoryEntry(
            key="test",
            content="test content",
            category="decision",
            source="daily",
            date="2026-01-15",
            file_path="/test.md",
            line_number=1,
            tags=["health"],
        )
        d = entry.to_dict()
        assert d["key"] == "test"
        assert d["tags"] == ["health"]

    def test_build_index(self, mock_data_base):
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()

        # Create a daily log
        daily_file = searcher._daily_dir / "2026-01-15.md"
        searcher._daily_dir.mkdir(parents=True, exist_ok=True)
        daily_file.write_text(
            "# Session Log: 2026-01-15\n\n"
            "## 10:00 - Decision\n"
            "**Topic**: Test decision\n"
            "**Decision**: Do the thing\n\n"
        )

        count = searcher.build_index()
        assert count >= 1
        assert searcher._index_path.exists()

    def test_parse_daily_log(self, mock_data_base):
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        content = (
            "# Session Log\n\n"
            "## 09:00 - Decision about lunch\n"
            "**Topic**: What to eat\n\n"
            "## 10:00 - Context Switch\n"
            "From: career to health\n"
        )
        entries = searcher._parse_daily_log(content, "2026-01-15", "/test.md")
        assert len(entries) == 2
        assert entries[0].category == "decision"
        assert entries[1].category == "context_switch"

    def test_parse_memory_md(self, mock_data_base):
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        content = (
            "# Augur Memory\n\n"
            "## Decisions\n\n"
            "### Health\n"
            "- **Vitamin D**: Take 2000 IU (2026-01-15)\n\n"
            "## User Preferences\n\n"
            "### Communication\n"
            "- **Style**: Concise (2026-01-10)\n"
        )
        entries = searcher._parse_memory_md(content, "/memory.md")
        assert len(entries) == 2
        assert entries[0].category == "decision"
        assert entries[1].category == "preference"

    def test_get_stats(self, mock_data_base):
        from src.lib.knowledge.search import MemorySearcher

        searcher = MemorySearcher()
        stats = searcher.get_stats()
        assert "memory_dir" in stats
        assert "daily_logs" in stats
        assert stats["daily_logs"] == 0

    def test_search_mode_enum(self):
        from src.lib.knowledge.search import SearchMode

        assert SearchMode.KEYWORD.value == "keyword"
        assert SearchMode.METADATA.value == "metadata"
        assert SearchMode.HYBRID.value == "hybrid"


# ---------------------------------------------------------------------------
# DailyLogger tests
# ---------------------------------------------------------------------------


class TestDailyLogger:
    """Tests for the DailyLogger class."""

    def test_creates_directories_on_init(self, mock_data_base):
        from src.lib.knowledge.daily_logger import DailyLogger

        logger = DailyLogger()
        assert logger._daily_dir.exists()

    def test_get_daily_file(self, mock_data_base):
        from src.lib.knowledge.daily_logger import DailyLogger

        logger = DailyLogger()
        path = logger._get_daily_file(datetime(2026, 1, 15))
        assert path.name == "2026-01-15.md"

    def test_ensure_daily_file_creates_with_header(self, mock_data_base):
        from src.lib.knowledge.daily_logger import DailyLogger

        logger = DailyLogger()
        path = logger._ensure_daily_file(datetime(2026, 1, 15))
        assert path.exists()
        content = path.read_text()
        assert "# Session Log: 2026-01-15" in content

    def test_log_decision(self, mock_data_base):
        from src.lib.knowledge.daily_logger import DailyLogger

        logger = DailyLogger()
        logger.log_decision(
            topic="Test topic",
            decision="Test decision",
            reasoning="Because reasons",
            confidence="high",
        )
        content = logger.get_today_log()
        assert content is not None
        assert "Decision" in content
        assert "Test topic" in content

    def test_log_context_switch(self, mock_data_base):
        from src.lib.knowledge.daily_logger import DailyLogger

        logger = DailyLogger()
        logger.log_context_switch(
            from_page="career",
            to_page="health",
            tools_loaded=["tool1", "tool2"],
            duration_ms=250,
        )
        content = logger.get_today_log()
        assert content is not None
        assert "Context Switch" in content
        assert "career" in content
        assert "health" in content

    def test_log_tool_execution(self, mock_data_base):
        from src.lib.knowledge.daily_logger import DailyLogger

        logger = DailyLogger()
        logger.log_tool_execution(
            tool_name="test_tool",
            action="run",
            input_data={"key": "val"},
            result="success",
        )
        content = logger.get_today_log()
        assert "Tool Execution" in content
        assert "test_tool" in content

    def test_log_error(self, mock_data_base):
        from src.lib.knowledge.daily_logger import DailyLogger

        logger = DailyLogger()
        logger.log_error(
            error="Something broke",
            context="During test",
            recovery_action="Retry",
        )
        content = logger.get_today_log()
        assert "Error" in content
        assert "Something broke" in content

    def test_log_user_preference(self, mock_data_base):
        from src.lib.knowledge.daily_logger import DailyLogger

        logger = DailyLogger()
        logger.log_user_preference(
            preference="Theme",
            value="Dark mode",
            source="explicit request",
        )
        content = logger.get_today_log()
        assert "User Preference" in content
        assert "Dark mode" in content

    def test_get_log_for_date_none_if_missing(self, mock_data_base):
        from src.lib.knowledge.daily_logger import DailyLogger

        logger = DailyLogger()
        result = logger.get_log_for_date(datetime(2020, 1, 1))
        assert result is None

    def test_cleanup_old_logs(self, mock_data_base):
        from src.lib.knowledge.daily_logger import DailyLogger

        logger = DailyLogger(retention_days=7)
        # Create an old log file
        old_date = datetime.now() - timedelta(days=30)
        old_file = logger._daily_dir / f"{old_date.strftime('%Y-%m-%d')}.md"
        old_file.write_text("# Old log\n")

        removed = logger.cleanup_old_logs()
        assert removed >= 1
        assert not old_file.exists()

    def test_cleanup_old_logs_keeps_recent(self, mock_data_base):
        from src.lib.knowledge.daily_logger import DailyLogger

        logger = DailyLogger(retention_days=7)
        # Create a recent log file
        recent_file = logger._daily_dir / f"{datetime.now().strftime('%Y-%m-%d')}.md"
        recent_file.write_text("# Recent log\n")

        removed = logger.cleanup_old_logs()
        assert removed == 0
        assert recent_file.exists()


# ---------------------------------------------------------------------------
# MemoryEvent tests
# ---------------------------------------------------------------------------


class TestMemoryEvent:
    """Tests for MemoryEvent to_markdown formatting."""

    def test_decision_event_markdown(self):
        from src.lib.knowledge.daily_logger import (
            EventType,
            MemoryEvent,
        )

        event = MemoryEvent(
            event_type=EventType.DECISION,
            timestamp=datetime(2026, 1, 15, 10, 30),
            data={"topic": "Test", "decision": "Do it", "reasoning": "Good idea"},
            confidence="high",
        )
        md = event.to_markdown()
        assert "10:30 - Decision" in md
        assert "**Topic**: Test" in md
        assert "**Decision**: Do it" in md
        assert "**Confidence**: High" in md

    def test_error_event_markdown(self):
        from src.lib.knowledge.daily_logger import (
            EventType,
            MemoryEvent,
        )

        event = MemoryEvent(
            event_type=EventType.ERROR,
            timestamp=datetime(2026, 1, 15, 11, 0),
            data={"error": "Crash", "context": "startup", "recovery_action": "restart"},
        )
        md = event.to_markdown()
        assert "Error" in md
        assert "Crash" in md
        assert "Recovery: restart" in md

    def test_pattern_detected_event_markdown(self):
        from src.lib.knowledge.daily_logger import (
            EventType,
            MemoryEvent,
        )

        event = MemoryEvent(
            event_type=EventType.PATTERN_DETECTED,
            timestamp=datetime(2026, 1, 15, 14, 0),
            data={"pattern": "Morning productivity", "frequency": "daily", "examples": ["a", "b", "c"]},
        )
        md = event.to_markdown()
        assert "Pattern Detected" in md
        assert "Morning productivity" in md

    def test_event_type_enum_values(self):
        from src.lib.knowledge.daily_logger import EventType

        assert EventType.CONTEXT_SWITCH.value == "context_switch"
        assert EventType.DECISION.value == "decision"
        assert EventType.TOOL_EXECUTION.value == "tool_execution"
        assert EventType.ERROR.value == "error"
        assert EventType.USER_PREFERENCE.value == "user_preference"
        assert EventType.PATTERN_DETECTED.value == "pattern_detected"


# ---------------------------------------------------------------------------
# MemoryCurator tests
# ---------------------------------------------------------------------------


class TestMemoryCurator:
    """Tests for the MemoryCurator class."""

    def test_infer_category_health(self, mock_data_base):
        from src.lib.knowledge.curator import MemoryCurator

        curator = MemoryCurator()
        assert curator._infer_category("health check", "vitamin d supplements") == "Health"

    def test_infer_category_career(self, mock_data_base):
        from src.lib.knowledge.curator import MemoryCurator

        curator = MemoryCurator()
        assert curator._infer_category("job search", "resume update") == "Career"

    def test_infer_category_workflow(self, mock_data_base):
        from src.lib.knowledge.curator import MemoryCurator

        curator = MemoryCurator()
        assert curator._infer_category("daily routine", "morning process") == "Workflow"

    def test_infer_category_general(self, mock_data_base):
        from src.lib.knowledge.curator import MemoryCurator

        curator = MemoryCurator()
        assert curator._infer_category("random", "stuff") == "General"

    def test_parse_log_for_decision(self, mock_data_base):
        from src.lib.knowledge.curator import MemoryCurator

        curator = MemoryCurator()
        content = (
            "## 10:00 - Decision\n"
            "**Topic**: Diet change\n"
            "**Decision**: Go vegetarian on weekdays\n"
            "**Confidence**: high\n"
        )
        entries = curator._parse_log_for_entries(content, "2026-01-15", "/test.md")
        assert len(entries) == 1
        assert entries[0].entry_type == "decision"
        assert entries[0].key == "Diet change"
        assert entries[0].value == "Go vegetarian on weekdays"

    def test_parse_log_for_preference(self, mock_data_base):
        from src.lib.knowledge.curator import MemoryCurator

        curator = MemoryCurator()
        content = "## 11:00 - User Preference\n" "**Preference**: Dark mode\n" "**Value**: Always on\n"
        entries = curator._parse_log_for_entries(content, "2026-01-15", "/test.md")
        assert len(entries) == 1
        assert entries[0].entry_type == "preference"

    def test_parse_log_for_pattern(self, mock_data_base):
        from src.lib.knowledge.curator import MemoryCurator

        curator = MemoryCurator()
        content = "## 12:00 - Pattern Observed\n" "**Pattern**: Peak productivity at 10am\n"
        entries = curator._parse_log_for_entries(content, "2026-01-15", "/test.md")
        assert len(entries) == 1
        assert entries[0].entry_type == "pattern"

    def test_parse_log_ignores_non_curate_worthy(self, mock_data_base):
        from src.lib.knowledge.curator import MemoryCurator

        curator = MemoryCurator()
        content = "## 09:00 - General Event\n" "Just a regular event\n"
        entries = curator._parse_log_for_entries(content, "2026-01-15", "/test.md")
        assert len(entries) == 0

    def test_consolidate_entries_deduplicates(self, mock_data_base):
        from src.lib.knowledge.curator import (
            DistilledEntry,
            MemoryCurator,
        )

        curator = MemoryCurator()
        entries = [
            DistilledEntry(
                entry_type="decision",
                key="Vitamin D",
                value="1000 IU",
                date="2026-01-10",
                source_file="/a.md",
            ),
            DistilledEntry(
                entry_type="decision",
                key="Vitamin D",
                value="2000 IU",
                date="2026-01-15",
                source_file="/b.md",
            ),
        ]
        consolidated = curator._consolidate_entries(entries)
        assert len(consolidated) == 1
        assert consolidated[0].value == "2000 IU"  # Most recent

    def test_distilled_entry_to_memory_item(self):
        from src.lib.knowledge.curator import DistilledEntry

        entry = DistilledEntry(
            entry_type="decision",
            key="Test",
            value="Test value",
            date="2026-01-15",
            source_file="/test.md",
        )
        md = entry.to_memory_item()
        assert "**Test**" in md
        assert "Test value" in md
        assert "(2026-01-15)" in md

    def test_insert_entry_into_existing_subsection(self, mock_data_base):
        from src.lib.knowledge.curator import MemoryCurator

        curator = MemoryCurator()
        content = "## Decisions\n\n### Health\n\n### Career\n"
        result = curator._insert_entry(content, "Decisions", "Health", "- **Test**: value")
        assert "- **Test**: value" in result
        # Should appear after ### Health header
        health_pos = result.index("### Health")
        item_pos = result.index("- **Test**: value")
        assert item_pos > health_pos

    def test_insert_entry_creates_subsection(self, mock_data_base):
        from src.lib.knowledge.curator import MemoryCurator

        curator = MemoryCurator()
        content = "## Decisions\n\n### Health\n"
        result = curator._insert_entry(content, "Decisions", "NewSubsection", "- **New**: item")
        assert "### NewSubsection" in result
        assert "- **New**: item" in result

    def test_insert_entry_creates_section_if_missing(self, mock_data_base):
        from src.lib.knowledge.curator import MemoryCurator

        curator = MemoryCurator()
        content = "# Empty doc\n"
        result = curator._insert_entry(content, "NewSection", "NewSub", "- **Item**: value")
        assert "## NewSection" in result
        assert "### NewSub" in result

    def test_get_recent_logs_empty(self, mock_data_base):
        from src.lib.knowledge.curator import MemoryCurator

        curator = MemoryCurator()
        logs = curator._get_recent_logs(7)
        assert logs == []

    def test_get_curation_summary(self, mock_data_base):
        from src.lib.knowledge.curator import MemoryCurator

        curator = MemoryCurator()
        summary = curator.get_curation_summary()
        assert "memory_file_exists" in summary
        assert "daily_logs_count" in summary
        assert summary["daily_logs_count"] == 0

    def test_curate_with_daily_logs(self, mock_data_base):
        from src.lib.knowledge.curator import MemoryCurator

        curator = MemoryCurator()
        # Create a daily log with a decision
        today_str = datetime.now().strftime("%Y-%m-%d")
        daily_file = curator._daily_dir / f"{today_str}.md"
        curator._daily_dir.mkdir(parents=True, exist_ok=True)
        daily_file.write_text(
            f"# Session Log: {today_str}\n\n"
            "## 10:00 - Decision\n"
            "**Topic**: Test curation\n"
            "**Decision**: Curate this entry\n"
        )

        result = curator.curate(days_back=1)
        assert result["logs_processed"] >= 1
        assert result["entries_extracted"] >= 1
