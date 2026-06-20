"""Tests for check_expirations.py -- data expiration checker."""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists() and (p / ".git").exists()), Path(__file__).resolve().parents[-1])
SCRIPTS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_expirations.py"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Stub runtime_paths before import
import types

_rp = sys.modules.get("runtime_paths")
if not _rp:
    _rp = types.ModuleType("runtime_paths")
    sys.modules["runtime_paths"] = _rp
_rp.get_notification_history_path = lambda: Path("/tmp/augur-test/history.yaml")
_rp.get_notification_pending_path = lambda: Path("/tmp/augur-test/pending.yaml")
_rp.get_notification_preferences_path = lambda: Path("/tmp/augur-test/preferences.yaml")
_rp.get_notifications_runtime_dir = lambda: Path("/tmp/augur-test/notifications")
_rp.get_insights_archive_dir = lambda: Path("/tmp/augur-test/archive")
_rp.get_insights_config_path = lambda: Path("/tmp/augur-test/config.yaml")
_rp.get_insights_path = lambda: Path("/tmp/augur-test/insights.yaml")

_spec = importlib.util.spec_from_file_location("check_expirations", SCRIPTS_PATH)
check_expirations = importlib.util.module_from_spec(_spec)
sys.modules["check_expirations"] = check_expirations
assert _spec.loader is not None
_spec.loader.exec_module(check_expirations)


class TestParseDuration:
    """Tests for parsing expiry policy strings."""

    def test_days(self):
        td = check_expirations.parse_duration("3d")
        assert td == timedelta(days=3)

    def test_weeks(self):
        td = check_expirations.parse_duration("2w")
        assert td == timedelta(days=14)

    def test_months(self):
        td = check_expirations.parse_duration("1m")
        assert td == timedelta(days=30)

    def test_never_returns_none(self):
        assert check_expirations.parse_duration("never") is None

    def test_invalid_falls_back_to_default(self):
        td = check_expirations.parse_duration("xyz")
        assert td == timedelta(days=30)


class TestIsExpired:
    """Tests for item expiration checking."""

    def test_expired_item(self):
        item = {
            "title": "Old job",
            "added": (datetime.now() - timedelta(days=60)).isoformat(),
            "expiry_policy": "1m",
        }
        assert check_expirations.is_expired(item) is True

    def test_not_expired_item(self):
        item = {
            "title": "Fresh job",
            "added": datetime.now().isoformat(),
            "expiry_policy": "1m",
        }
        assert check_expirations.is_expired(item) is False

    def test_never_policy_not_expired(self):
        item = {
            "title": "Permanent",
            "added": (datetime.now() - timedelta(days=365)).isoformat(),
            "expiry_policy": "never",
        }
        assert check_expirations.is_expired(item) is False

    def test_explicit_expires_at(self):
        item = {
            "title": "Explicit",
            "expires_at": (datetime.now() - timedelta(days=1)).isoformat(),
        }
        assert check_expirations.is_expired(item) is True

    def test_no_date_not_expired(self):
        item = {"title": "No date"}
        assert check_expirations.is_expired(item) is False


class TestExtractItemsFromFile:
    """Tests for extracting items from different YAML structures."""

    def test_root_list(self, tmp_path):
        f = tmp_path / "items.yaml"
        f.write_text(yaml.dump([{"title": "A"}, {"title": "B"}]))
        result = check_expirations.extract_items_from_file(f)
        assert len(result) == 2
        assert result[0][0]["title"] == "A"

    def test_dict_with_jobs_key(self, tmp_path):
        f = tmp_path / "jobs.yaml"
        f.write_text(yaml.dump({"jobs": [{"company": "Acme"}, {"company": "Beta"}]}))
        result = check_expirations.extract_items_from_file(f)
        assert len(result) == 2
        assert result[0][1] == "jobs"

    def test_nonexistent_file(self, tmp_path):
        result = check_expirations.extract_items_from_file(tmp_path / "nope.yaml")
        assert result == []

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("")
        result = check_expirations.extract_items_from_file(f)
        assert result == []


class TestCreateReviewItems:
    """Tests for converting expired items to review items."""

    def test_priority_based_on_days_expired(self):
        items = [
            {
                "identifier": "Very old",
                "days_expired": 45,
                "file": "/data/jobs.yaml",
                "list_key": "jobs",
                "index": 0,
                "suggested_action": "archive",
                "item_preview": {"title": "Very old"},
            },
            {
                "identifier": "Recent",
                "days_expired": 5,
                "file": "/data/jobs.yaml",
                "list_key": "jobs",
                "index": 1,
                "suggested_action": "review",
                "item_preview": {"title": "Recent"},
            },
        ]
        reviews = check_expirations.create_review_items(items)
        assert len(reviews) == 2
        assert reviews[0]["priority"] == "high"
        assert reviews[1]["priority"] == "low"

    def test_review_structure(self):
        items = [
            {
                "identifier": "Test",
                "days_expired": 20,
                "file": "/data/inbox.yaml",
                "list_key": "items",
                "index": 0,
                "suggested_action": "review",
                "item_preview": {"title": "Test"},
            },
        ]
        reviews = check_expirations.create_review_items(items)
        assert reviews[0]["skill"] == "data-expiration"
        assert reviews[0]["type"] == "data_review"
        assert reviews[0]["status"] == "pending"


def test_add_to_pending_reviews_writes_runtime_attention_queue(tmp_path, monkeypatch):
    """Generated review state belongs in runtime, not a vault channels root."""
    runtime_dir = tmp_path / "runtime"
    monkeypatch.setattr(check_expirations, "get_runtime_dir", lambda: runtime_dir)

    added = check_expirations.add_to_pending_reviews(
        [
            {
                "id": "review-1",
                "title": "Review item",
                "status": "pending",
            }
        ]
    )

    reviews_file = runtime_dir / "attention" / "reviews" / "pending_reviews.yaml"
    assert added == 1
    assert reviews_file.is_file()
    data = yaml.safe_load(reviews_file.read_text(encoding="utf-8"))
    assert data["reviews"][0]["id"] == "review-1"
    assert not (tmp_path / "vault" / "channels").exists()
