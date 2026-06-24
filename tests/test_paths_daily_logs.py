"""Regression tests for daily-logs directory isolation (QA finding B2).

The memory surface (memory-search, curator) reads Layer-1 daily logs. Before the
fix these were hard-wired to get_runtime_dir()/memory/daily, so pointing AUGUR_VAULT
at a synthetic vault still surfaced real session data — breaking test isolation.
get_daily_logs_dir() adds an AUGUR_DAILY_LOGS override (default unchanged) so the
memory surface can be isolated without touching AUGUR_STATE (which keys dev-server
instance management).
"""


def test_daily_logs_dir_defaults_to_runtime_subdir(monkeypatch):
    monkeypatch.delenv("AUGUR_DAILY_LOGS", raising=False)
    from src.config.paths import get_daily_logs_dir, get_runtime_dir

    assert get_daily_logs_dir() == get_runtime_dir() / "memory" / "daily"


def test_daily_logs_dir_honors_override(monkeypatch, tmp_path):
    override = tmp_path / "isolated-daily"
    monkeypatch.setenv("AUGUR_DAILY_LOGS", str(override))
    from src.config.paths import get_daily_logs_dir

    assert get_daily_logs_dir() == override


def test_memory_searcher_uses_override(monkeypatch, tmp_path):
    override = tmp_path / "isolated-daily"
    monkeypatch.setenv("AUGUR_DAILY_LOGS", str(override))
    from src.lib.knowledge.search import MemorySearcher

    searcher = MemorySearcher()
    assert searcher._daily_dir == override


def test_curator_uses_override(monkeypatch, tmp_path):
    override = tmp_path / "isolated-daily"
    monkeypatch.setenv("AUGUR_DAILY_LOGS", str(override))
    from src.lib.knowledge.curator import MemoryCurator

    curator = MemoryCurator()
    assert curator._daily_dir == override


def test_daily_logger_uses_override(monkeypatch, tmp_path):
    override = tmp_path / "isolated-daily"
    monkeypatch.setenv("AUGUR_DAILY_LOGS", str(override))
    from src.lib.knowledge.daily_logger import DailyLogger

    logger = DailyLogger()
    assert logger._daily_dir == override
    # explicit constructor arg still wins over the env default
    explicit = tmp_path / "explicit"
    assert DailyLogger(daily_dir=explicit)._daily_dir == explicit
