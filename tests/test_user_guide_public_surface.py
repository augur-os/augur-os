from pathlib import Path


def test_user_guide_is_public_release_safe():
    text = Path("docs/user-guide.md").read_text()

    assert "soft launch" in text
    assert "Native macOS support is implemented" in text
    assert "Native Windows architecture is implemented" in text
    assert "Windows validation is still pending" in text

    assert "augur-data" not in text
    assert "setup-manager" not in text
    assert "Setup Manager" not in text
    assert "macOS-only scheduler" not in text
    assert "launchd" not in text
    assert "Scheduled Tasks & Automation" not in text
