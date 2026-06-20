from src.lib.routing import resolver


def test_forced_airplane_is_offline(monkeypatch):
    monkeypatch.setattr(
        resolver, "_load_airplane_prefs", lambda: {"enabled": True, "forced": True, "auto_detect": True}
    )
    assert resolver.detect_mode() == "offline"


def test_forced_disabled_is_regular(monkeypatch):
    # forced=True means "trust enabled, skip auto-detect"; enabled=False -> regular.
    monkeypatch.setattr(
        resolver, "_load_airplane_prefs", lambda: {"enabled": False, "forced": True, "auto_detect": True}
    )
    assert resolver.detect_mode() == "regular"


def test_disabled_airplane_is_regular(monkeypatch):
    monkeypatch.setattr(
        resolver, "_load_airplane_prefs", lambda: {"enabled": False, "forced": False, "auto_detect": True}
    )
    monkeypatch.setattr(resolver, "_is_online", lambda: True)
    assert resolver.detect_mode() == "regular"


def test_auto_detect_offline_when_no_connectivity(monkeypatch):
    monkeypatch.setattr(
        resolver, "_load_airplane_prefs", lambda: {"enabled": False, "forced": False, "auto_detect": True}
    )
    monkeypatch.setattr(resolver, "_is_online", lambda: False)
    assert resolver.detect_mode() == "offline"


def test_auto_detect_regular_when_online(monkeypatch):
    monkeypatch.setattr(
        resolver, "_load_airplane_prefs", lambda: {"enabled": False, "forced": False, "auto_detect": True}
    )
    monkeypatch.setattr(resolver, "_is_online", lambda: True)
    assert resolver.detect_mode() == "regular"


def test_explicit_mode_override_wins(monkeypatch):
    # Callers may pass mode explicitly; detection is skipped.
    assert resolver.resolve_mode("offline") == "offline"
    assert resolver.resolve_mode("regular") == "regular"
