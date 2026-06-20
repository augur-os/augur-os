from __future__ import annotations


def test_generated_exports_allow_policy_approved_names_without_discovery(monkeypatch) -> None:
    from src.lib.capabilities import export_filter

    monkeypatch.setattr(export_filter, "_resolved_records_by_id", lambda: {})
    monkeypatch.setattr(
        export_filter,
        "load_capability_policy",
        lambda: {
            "capabilities": {
                "skill:defuddle": {
                    "classification_status": "approved",
                    "export_to": ["codex"],
                    "primary_surface": "agents-md",
                },
                "skill:blocked": {
                    "classification_status": "blocked",
                    "export_to": ["codex"],
                    "primary_surface": "agents-md",
                },
            }
        },
    )

    assert export_filter.allowed_generated_names(
        "skill",
        ["defuddle", "blocked", "unclassified"],
        target="codex",
        existing_names=set(),
    ) == {"defuddle"}
