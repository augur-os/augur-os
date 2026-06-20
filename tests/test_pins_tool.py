"""Tests for pin MCP tools (atomic pins.yaml I/O)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.mcp.augur_framework.tools.infrastructure.pins import (
    pin_add_impl,
    pin_list_impl,
    pin_remove_impl,
)


def test_pin_list_empty(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.yaml"

    assert pin_list_impl(pins_path=pins_path) == {"pins": []}


def test_pin_add_creates_entry(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.yaml"

    result = pin_add_impl(
        pins_path=pins_path,
        url="/artifact/foo",
        title="Foo",
        kind="saved",
    )
    pins = pin_list_impl(pins_path=pins_path)["pins"]

    assert result == {"added": True, "url": "/artifact/foo"}
    assert len(pins) == 1
    assert pins[0]["url"] == "/artifact/foo"
    assert pins[0]["title"] == "Foo"
    assert pins[0]["kind"] == "saved"
    # ADR-802: hub was removed; new pins must never carry it.
    assert "hub" not in pins[0]
    assert pins[0]["pinnedAt"].endswith("Z")


def test_pin_add_is_idempotent_on_url(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.yaml"

    first = pin_add_impl(
        pins_path=pins_path,
        url="/workspace/inbox",
        title="Brain Inbox",
        kind="live",
    )
    second = pin_add_impl(
        pins_path=pins_path,
        url="/workspace/inbox",
        title="Updated Brain Inbox",
        kind="saved",
    )
    pins = pin_list_impl(pins_path=pins_path)["pins"]

    assert first == {"added": True, "url": "/workspace/inbox"}
    assert second == {"added": False, "url": "/workspace/inbox"}
    assert len(pins) == 1
    assert pins[0]["title"] == "Brain Inbox"
    assert pins[0]["kind"] == "live"
    assert "hub" not in pins[0]


def test_pin_remove_drops_by_url(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.yaml"
    pin_add_impl(pins_path=pins_path, url="/a", title="A", kind="saved")
    pin_add_impl(pins_path=pins_path, url="/b", title="B", kind="saved")

    result = pin_remove_impl(pins_path=pins_path, url="/a")
    pins = pin_list_impl(pins_path=pins_path)["pins"]

    assert result == {"removed": True, "url": "/a"}
    assert len(pins) == 1
    assert pins[0]["url"] == "/b"


def test_pin_add_stores_category_and_item_key(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.yaml"

    result = pin_add_impl(
        pins_path=pins_path,
        url="/browse/knowledge",
        title="Knowledge",
        kind="browse-card",
        category="skills",
        itemKey="skills::knowledge",
    )
    pins = pin_list_impl(pins_path=pins_path)["pins"]

    assert result == {"added": True, "url": "/browse/knowledge", "itemKey": "skills::knowledge"}
    assert len(pins) == 1
    assert pins[0]["url"] == "/browse/knowledge"
    assert pins[0]["category"] == "skills"
    assert pins[0]["itemKey"] == "skills::knowledge"


def test_pin_add_is_idempotent_by_category_item_key(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.yaml"

    first = pin_add_impl(
        pins_path=pins_path,
        url="/browse/knowledge",
        title="Knowledge",
        kind="browse-card",
        category="skills",
        itemKey="skills::knowledge",
    )
    second = pin_add_impl(
        pins_path=pins_path,
        url="/browse/knowledge-copy",
        title="Knowledge Copy",
        kind="browse-card",
        category="skills",
        itemKey="skills::knowledge",
    )
    pins = pin_list_impl(pins_path=pins_path)["pins"]

    assert first == {"added": True, "url": "/browse/knowledge", "itemKey": "skills::knowledge"}
    assert second == {"added": False, "url": "/browse/knowledge-copy", "itemKey": "skills::knowledge"}
    assert len(pins) == 1
    assert pins[0]["url"] == "/browse/knowledge"


def test_pin_remove_with_category_item_key_removes_only_that_category_pin(tmp_path: Path) -> None:
    pins_path = tmp_path / "pins.yaml"
    pin_add_impl(
        pins_path=pins_path,
        url="/same-url",
        title="Skill",
        kind="browse-card",
        category="skills",
        itemKey="skills::same",
    )
    pin_add_impl(
        pins_path=pins_path,
        url="/same-url",
        title="ADR",
        kind="browse-card",
        category="adrs",
        itemKey="adrs::same",
    )

    result = pin_remove_impl(
        pins_path=pins_path,
        url="/same-url",
        category="skills",
        itemKey="skills::same",
    )
    pins = pin_list_impl(pins_path=pins_path)["pins"]

    assert result == {"removed": True, "url": "/same-url", "itemKey": "skills::same"}
    assert len(pins) == 1
    assert pins[0]["url"] == "/same-url"
    assert pins[0]["category"] == "adrs"
    assert pins[0]["itemKey"] == "adrs::same"
