from __future__ import annotations

from src.lib.capabilities.exposure_policy import (
    CapabilityDiscovery,
    resolve_capability_records,
)


def test_resolve_capability_records_filters_by_active_tiers() -> None:
    discovered = [
        CapabilityDiscovery(id="command:global", type="command", scope="global"),
        CapabilityDiscovery(id="command:user", type="command", scope="user"),
        CapabilityDiscovery(id="command:project", type="command", scope="project"),
    ]

    records = resolve_capability_records(
        discovered,
        policy={"version": 1, "capabilities": {}},
        active_tiers={"global", "user"},
    )

    assert [record.id for record in records] == ["command:global", "command:user"]


def test_policy_scope_defaults_to_discovered_scope() -> None:
    discovered = [
        CapabilityDiscovery(id="command:project", type="command", scope="project"),
    ]

    records = resolve_capability_records(
        discovered,
        policy={"version": 1, "capabilities": {}},
        active_tiers={"global", "user", "project"},
    )

    assert len(records) == 1
    assert records[0].scope == "project"


def test_personal_active_tier_satisfies_user_scope() -> None:
    discovered = [
        CapabilityDiscovery(id="command:user", type="command", scope="user"),
    ]

    records = resolve_capability_records(
        discovered,
        policy={"version": 1, "capabilities": {}},
        active_tiers={"global", "personal"},
    )

    assert [record.id for record in records] == ["command:user"]
