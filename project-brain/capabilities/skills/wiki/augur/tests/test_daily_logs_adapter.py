from datetime import date, timedelta

import pytest

from src.config.paths import invalidate_project_cache
from skills.wiki.scripts.wiki_query_sources import DailyLogsAdapter


@pytest.fixture(autouse=True)
def _clear_path_cache():
    invalidate_project_cache()
    yield
    invalidate_project_cache()


def _seed_daily_logs(vault, days: list[int]) -> None:
    daily = vault / "memory" / "daily"
    daily.mkdir(parents=True, exist_ok=True)
    today = date.today()
    for day_offset in days:
        log_date = today - timedelta(days=day_offset)
        (daily / f"{log_date.isoformat()}.md").write_text(
            f"# {log_date}\n## 10:00 - Decision\n- decided X on day -{day_offset}\n",
            encoding="utf-8",
        )


def test_adapter_kind():
    assert DailyLogsAdapter().kind == "daily_logs"


def test_resolve_default_recent_days_30(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    _seed_daily_logs(tmp_path, [0, 5, 35])

    result = DailyLogsAdapter().resolve({"kind": "daily_logs"}, budget_tokens=10_000)

    assert "day -0" in result.text
    assert "day -5" in result.text
    assert "day -35" not in result.text


def test_resolve_explicit_recent_days(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    _seed_daily_logs(tmp_path, [0, 10])

    result = DailyLogsAdapter().resolve({"kind": "daily_logs", "recent_days": 7}, budget_tokens=10_000)

    assert "day -0" in result.text
    assert "day -10" not in result.text


def test_resolve_empty_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    result = DailyLogsAdapter().resolve({"kind": "daily_logs"}, budget_tokens=10_000)
    assert result.text == ""
    assert result.citations == []


def test_resolve_citations_list_each_file(tmp_path, monkeypatch):
    monkeypatch.setenv("AUGUR_VAULT", str(tmp_path))
    _seed_daily_logs(tmp_path, [0, 1, 2])

    result = DailyLogsAdapter().resolve({"kind": "daily_logs"}, budget_tokens=10_000)

    assert len(result.citations) == 3
